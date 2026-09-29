"""CI shadow run: real GitHub failures through the detector pipeline, nothing published.

First live-data slice of BDS-FCO-CSD-v0.1's transport gate. For each
repository: fetch recent failed workflow runs (`github_actions_client`),
convert them (`github_workflow_adapter`), correlate, run the eligibility
gate, and compose candidates (`cloud_proposal_composer`) -- then REPORT how
much of that survived. This module has no publish path: it never touches
DataForge-Local, Forge_Command, or any store, so running it can never put an
entry in front of an operator.

KNOWN LIMIT, stated so the numbers are not over-read: the eligibility gate is
called with no open-proposal or cooldown knowledge (there is no read of
DataForge-Local here), so `eligible` counts groups that would be eligible
*ignoring* suppression. Publishing would need that read first.

A repository that cannot be fetched is reported under `errors` and skipped;
one bad repo never hides the others' results.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from app.drivers.github_actions_client import GitHubFetchError, fetch_failed_runs
from app.services.cloud_proposal_composer import CloudProposalComposer
from app.services.cloud_signal_correlation import (
    ELIGIBLE,
    CloudProposalEligibilityGate,
    CloudSignalCorrelator,
)
from app.services.github_workflow_adapter import github_workflow_run_to_cloud_signal


@dataclass(frozen=True, slots=True)
class CiGroupReport:
    repository: str
    fingerprint: str
    signal_count: int
    decision: str
    confidence_band: str | None
    composed: bool
    sample_summary: str


@dataclass(slots=True)
class CiShadowReport:
    repositories: list[str]
    runs_fetched: int = 0
    signals_converted: int = 0
    signals_rejected: int = 0
    runs_stale_skipped: int = 0
    groups: list[CiGroupReport] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)

    @property
    def eligible(self) -> int:
        return sum(1 for g in self.groups if g.decision == ELIGIBLE)

    @property
    def composed(self) -> int:
        return sum(1 for g in self.groups if g.composed)

    def to_dict(self) -> dict:
        return {
            "repositories": self.repositories,
            "runs_fetched": self.runs_fetched,
            "signals_converted": self.signals_converted,
            "signals_rejected": self.signals_rejected,
            "runs_stale_skipped": self.runs_stale_skipped,
            "groups": len(self.groups),
            "eligible_ignoring_suppression": self.eligible,
            "composed_candidates": self.composed,
            "errors": self.errors,
            "group_detail": [
                {
                    "repository": g.repository,
                    "fingerprint": g.fingerprint,
                    "signals": g.signal_count,
                    "decision": g.decision,
                    "confidence": g.confidence_band,
                    "composed": g.composed,
                    "sample": g.sample_summary,
                }
                for g in self.groups
            ],
            "published": 0,
        }


def _is_recent(run: dict, cutoff: datetime) -> bool:
    raw = run.get("updated_at")
    if not isinstance(raw, str):
        return False
    try:
        updated = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return False
    if updated.tzinfo is None:
        return False
    return updated >= cutoff


def run_ci_shadow(
    repositories: list[str],
    *,
    producer_version: str,
    per_page: int = 30,
    max_age_days: int | None = 14,
    now: datetime | None = None,
    fetch: Callable[..., list[dict]] = fetch_failed_runs,
) -> CiShadowReport:
    """`max_age_days` skips runs whose `updated_at` is older than the window
    (counted in `runs_stale_skipped`, not silently dropped). A run with a
    missing or unparseable `updated_at` is also skipped, since its age is
    unknown. `None` disables the window."""
    report = CiShadowReport(repositories=list(repositories))
    cutoff = None
    if max_age_days is not None:
        cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=max_age_days)
    signals = []
    for repo in repositories:
        try:
            runs = fetch(repo, per_page=per_page)
        except GitHubFetchError as exc:
            report.errors[repo] = str(exc)
            continue
        report.runs_fetched += len(runs)
        for run in runs:
            if cutoff is not None and not _is_recent(run, cutoff):
                report.runs_stale_skipped += 1
                continue
            signal = github_workflow_run_to_cloud_signal(run, producer_version=producer_version)
            if signal is None:
                report.signals_rejected += 1
            else:
                report.signals_converted += 1
                signals.append(signal)

    gate = CloudProposalEligibilityGate()
    composer = CloudProposalComposer()
    for group in CloudSignalCorrelator().correlate(signals):
        outcome = gate.evaluate(group)
        candidate = composer.compose(group, outcome)
        first = group.signals[0]
        report.groups.append(
            CiGroupReport(
                repository=first.subject.repository or "",
                fingerprint=group.fingerprint,
                signal_count=len(group.signals),
                decision=outcome.decision,
                confidence_band=outcome.confidence_band,
                composed=candidate is not None,
                sample_summary=first.summary,
            )
        )
    return report
