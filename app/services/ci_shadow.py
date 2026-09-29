"""CI shadow run: real GitHub runs through the detector pipeline, nothing published.

First live-data slice of BDS-FCO-CSD-v0.1's transport gate. For each
repository: fetch recent workflow runs of every conclusion
(`github_actions_client`), keep the ones that are still-unrecovered recent
failures, convert them (`github_workflow_adapter`), correlate, run the
eligibility gate, and compose candidates (`cloud_proposal_composer`) -- then
REPORT how much survived and why the rest was skipped. This module has no
publish path: it never touches DataForge-Local, Forge_Command, or any store,
so running it can never put an entry in front of an operator.

WHAT COUNTS AS A CANDIDATE. A run with conclusion `failure` or
`startup_failure` (see the adapter for why they differ). A candidate is
skipped, and counted, when:

- it is older than `max_age_days` (`runs_stale_skipped`), or its timestamps
  are missing/unparseable so its age or order cannot be known (also counted
  there); or
- it has RECOVERED (`runs_recovered_skipped`): a later successful run exists
  in the same scope. Scope for `failure` is (workflow, branch) -- a green
  `main` does not clear a red PR branch. Scope for `startup_failure` is the
  whole repository -- it is a repo-wide condition, and any later success on
  any branch shows runs can start again.

Found by running it on real repositories (see docs/KNOWN_ISSUES.md): without
these checks it proposed month-old failures that had since cleared, and it
could not see `startup_failure` at all.

SUPPRESSION. When given the store's suppression sets (a read-only GET of
DataForge-Local via `proposal_store_reader`), the gate answers DUPLICATE for a
fingerprint that already has an open proposal and SUPPRESSED for one an
operator decided within the cooldown. The report keeps both numbers:
`eligible_ignoring_suppression` and `would_publish` (after suppression). If
the store cannot be read, `would_publish` is null and the status says why --
it is never guessed. Proposals published before the fingerprint was carried
in the envelope cannot suppress anything (counted in the report).

A repository that cannot be fetched is reported under `errors` and skipped;
one bad repo never hides the others' results.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from app.drivers.github_actions_client import GitHubFetchError, fetch_recent_runs
from app.drivers.proposal_store_reader import ProposalStoreError, read_cloud_proposals
from app.services.cloud_proposal_composer import CloudProposalComposer
from app.services.cloud_signal_correlation import (
    ELIGIBLE,
    CloudProposalEligibilityGate,
    CloudSignalCorrelator,
)
from app.services.cloud_signal_contracts import CloudProposalCandidate
from app.services.proposal_suppression import SuppressionSets, build_suppression_sets
from app.services.github_workflow_adapter import (
    CONCLUSION_FAILURE,
    CONCLUSION_STARTUP_FAILURE,
    HANDLED_CONCLUSIONS,
    github_workflow_run_to_cloud_signal,
)


@dataclass(frozen=True, slots=True)
class CiGroupReport:
    repository: str
    issue_class: str
    fingerprint: str
    signal_count: int
    decision: str
    decision_ignoring_suppression: str
    confidence_band: str | None
    composed: bool
    sample_summary: str


@dataclass(slots=True)
class CiShadowReport:
    repositories: list[str]
    runs_fetched: int = 0
    candidate_runs: int = 0
    runs_stale_skipped: int = 0
    runs_recovered_skipped: int = 0
    signals_converted: int = 0
    signals_rejected: int = 0
    groups: list[CiGroupReport] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)
    suppression_status: str = "not_read"
    suppression: SuppressionSets | None = None
    # Composed candidates for groups the gate passed, newest group first.
    # Not part of to_dict(); a publisher reads them.
    candidates: list[CloudProposalCandidate] = field(default_factory=list)

    @property
    def eligible(self) -> int:
        return sum(1 for g in self.groups if g.decision_ignoring_suppression == ELIGIBLE)

    @property
    def would_publish(self) -> int | None:
        if self.suppression is None:
            return None
        return sum(1 for g in self.groups if g.decision == ELIGIBLE)

    @property
    def composed(self) -> int:
        return sum(1 for g in self.groups if g.composed)

    def to_dict(self) -> dict:
        return {
            "repositories": self.repositories,
            "runs_fetched": self.runs_fetched,
            "candidate_runs": self.candidate_runs,
            "runs_stale_skipped": self.runs_stale_skipped,
            "runs_recovered_skipped": self.runs_recovered_skipped,
            "signals_converted": self.signals_converted,
            "signals_rejected": self.signals_rejected,
            "groups": len(self.groups),
            "eligible_ignoring_suppression": self.eligible,
            "duplicate_groups": sum(1 for g in self.groups if g.decision == "duplicate"),
            "suppressed_groups": sum(1 for g in self.groups if g.decision == "suppressed"),
            "would_publish": self.would_publish,
            "suppression": {
                "status": self.suppression_status,
                "rows_read": self.suppression.rows_read if self.suppression else None,
                "rows_without_fingerprint": (
                    self.suppression.rows_without_fingerprint if self.suppression else None
                ),
                "open": len(self.suppression.open_fingerprints) if self.suppression else None,
                "cooling_down": (
                    len(self.suppression.cooling_down_fingerprints) if self.suppression else None
                ),
                "truncated_statuses": (
                    list(self.suppression.truncated_statuses) if self.suppression else None
                ),
            },
            "composed_candidates": self.composed,
            "errors": self.errors,
            "group_detail": [
                {
                    "repository": g.repository,
                    "issue_class": g.issue_class,
                    "fingerprint": g.fingerprint,
                    "signals": g.signal_count,
                    "decision": g.decision,
                    "decision_ignoring_suppression": g.decision_ignoring_suppression,
                    "confidence": g.confidence_band,
                    "composed": g.composed,
                    "sample": g.sample_summary,
                }
                for g in self.groups
            ],
            "published": 0,
        }


def _parse_ts(raw) -> datetime | None:
    """A timezone-aware timestamp, or None when missing or unparseable."""
    if not isinstance(raw, str):
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _success_times(runs: list[dict]) -> list[tuple[datetime, str, str]]:
    """(created_at, workflow name, branch) for every completed success."""
    out = []
    for run in runs:
        if run.get("status") != "completed" or run.get("conclusion") != "success":
            continue
        created = _parse_ts(run.get("created_at"))
        if created is not None:
            out.append((created, run.get("name") or "", run.get("head_branch") or ""))
    return out


def _recovered(run: dict, created: datetime, successes: list[tuple[datetime, str, str]]) -> bool:
    if run.get("conclusion") == CONCLUSION_STARTUP_FAILURE:
        return any(t > created for t, _n, _b in successes)
    name = run.get("name") or ""
    branch = run.get("head_branch") or ""
    return any(t > created and n == name and b == branch for t, n, b in successes)


def load_suppression(
    *,
    base_url: str,
    cooldown_days: int = 14,
    read=read_cloud_proposals,
) -> tuple[SuppressionSets | None, str]:
    """(sets, status). On any read failure: (None, "unavailable: <reason>")."""
    try:
        snapshot = read(base_url=base_url)
    except ProposalStoreError as exc:
        return None, f"unavailable: {exc}"
    return build_suppression_sets(snapshot, cooldown_days=cooldown_days), "ok"


def run_ci_shadow(
    repositories: list[str],
    *,
    producer_version: str,
    per_page: int = 100,
    max_age_days: int | None = 14,
    now: datetime | None = None,
    fetch: Callable[..., list[dict]] = fetch_recent_runs,
    suppression: SuppressionSets | None = None,
    suppression_status: str = "not_read",
) -> CiShadowReport:
    """`max_age_days=None` disables the recency window. `suppression` is the
    store's open/cooling-down fingerprints; None means it was not read."""
    report = CiShadowReport(repositories=list(repositories))
    report.suppression = suppression
    report.suppression_status = suppression_status
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
        successes = _success_times(runs)
        for run in runs:
            if run.get("status") != "completed" or run.get("conclusion") not in HANDLED_CONCLUSIONS:
                continue
            report.candidate_runs += 1
            created = _parse_ts(run.get("created_at"))
            updated = _parse_ts(run.get("updated_at"))
            if created is None or updated is None or (cutoff is not None and updated < cutoff):
                report.runs_stale_skipped += 1
                continue
            if _recovered(run, created, successes):
                report.runs_recovered_skipped += 1
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
        raw = gate.evaluate(group)
        outcome = (
            gate.evaluate(
                group,
                open_proposal_fingerprints=suppression.open_fingerprints,
                suppressed_fingerprints=suppression.cooling_down_fingerprints,
            )
            if suppression is not None
            else raw
        )
        candidate = composer.compose(group, outcome)
        if candidate is not None:
            report.candidates.append(candidate)
        first = group.signals[0]
        report.groups.append(
            CiGroupReport(
                repository=first.subject.repository or "",
                issue_class=first.issue_class,
                fingerprint=group.fingerprint,
                signal_count=len(group.signals),
                decision=outcome.decision,
                decision_ignoring_suppression=raw.decision,
                confidence_band=outcome.confidence_band,
                composed=candidate is not None,
                sample_summary=first.summary,
            )
        )
    return report
