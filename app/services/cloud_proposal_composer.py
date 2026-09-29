"""Deterministic proposal composer (BDS-FCO-CSD-v0.1, slice CSD-04).

Turns an `ELIGIBLE` outcome (CSD-03) plus its correlated signal group into a
real `CloudProposalCandidate.v1` (CSD-01) -- the last step before the
existing, already-shipped `CloudProposalShaper` (Phase 1 of
`BDS-FCO-CLOUDPROP-v1.1`) packages one into a `cloud.proposal.v1` envelope.

DETERMINISTIC, NO LLM: composition is template lookup keyed on `issue_class`,
matching this plan's own deterministic-only-v0.1 ruling. `facts` are built
only from what the correlated signals actually say (their own `summary`
strings, already factual sentences written by the detector itself) plus a
plain aggregate count -- nothing here infers a root cause or invents
content. An `issue_class` with no known template is **not composed**; it
fails closed rather than falling back to a generic guess. AI-assisted
composition for unmapped classes is CSD-09, deliberately deferred.

Five issue classes have templates: `denial_streak` and `quota_exceeded_burst`
(forgesentinel's two real detectors, `src/watchdog/decisions.ts`, CSD-02),
`ci_workflow_failure` (CSD-06's GitHub Actions adapter), and `deploy_failure`
(CSD-07's Render adapter), and `ci_startup_failure` (GitHub runs that never
started) -- not invented, matching what each adapter can
actually produce.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.services.cloud_signal_contracts import (
    CloudProposalCandidate,
    CloudProposalCandidateShaper,
)
from app.services.cloud_signal_correlation import ELIGIBLE, CorrelatedSignalGroup, EligibilityOutcome


MAX_LISTED_FACTS = 5


def _facts_from_summaries(group: CorrelatedSignalGroup) -> tuple[str, ...]:
    # Each signal's own summary is already a factual sentence written by the
    # detector that observed it -- reusing it, deduplicated and in order,
    # rather than paraphrasing or inferring anything new.
    seen: set[str] = set()
    unique: list[str] = []
    for signal in group.signals:
        if signal.summary not in seen:
            seen.add(signal.summary)
            unique.append(signal.summary)
    # A real group can hold 100 signals (one repo-wide incident); listing every
    # summary made an unreadable review-queue entry (~12,000 characters).
    facts = unique[:MAX_LISTED_FACTS]
    if len(unique) > MAX_LISTED_FACTS:
        facts.append(f"{len(unique) - MAX_LISTED_FACTS} further similar signal(s) not listed.")
    facts.append(f"{len(group.signals)} correlated signal(s) observed for this fingerprint.")
    return tuple(facts)


@dataclass(frozen=True, slots=True)
class _IssueClassTemplate:
    recommended_action_class: str
    facts: Callable[[CorrelatedSignalGroup], tuple[str, ...]]


# Keyed on the real detector names CSD-02's adapter passes through as
# issue_class -- verified against forgesentinel's src/watchdog/decisions.ts,
# not invented.
_ISSUE_CLASS_TEMPLATES: dict[str, _IssueClassTemplate] = {
    "denial_streak": _IssueClassTemplate(
        recommended_action_class="investigate_policy_denial_pattern",
        facts=_facts_from_summaries,
    ),
    "quota_exceeded_burst": _IssueClassTemplate(
        recommended_action_class="investigate_quota_exhaustion",
        facts=_facts_from_summaries,
    ),
    "ci_workflow_failure": _IssueClassTemplate(
        recommended_action_class="investigate_ci_workflow_failure",
        facts=_facts_from_summaries,
    ),
    "deploy_failure": _IssueClassTemplate(
        recommended_action_class="investigate_deploy_failure",
        facts=_facts_from_summaries,
    ),
    "ci_startup_failure": _IssueClassTemplate(
        recommended_action_class="investigate_ci_startup_failure",
        facts=_facts_from_summaries,
    ),
}


class CloudProposalComposer:
    """Composes a `CloudProposalCandidate` from an eligible correlated
    group. Fails closed (returns None) when the outcome isn't `ELIGIBLE`,
    when the group's `issue_class` has no known template, or when the
    resulting candidate fails `CloudProposalCandidateShaper`'s own
    validation."""

    def compose(
        self, group: CorrelatedSignalGroup, outcome: EligibilityOutcome
    ) -> CloudProposalCandidate | None:
        if outcome.decision != ELIGIBLE or outcome.confidence_band is None:
            return None
        if outcome.fingerprint != group.fingerprint:
            return None

        issue_class = group.signals[0].issue_class
        template = _ISSUE_CLASS_TEMPLATES.get(issue_class)
        if template is None:
            return None

        return CloudProposalCandidateShaper().build(
            subject=group.signals[0].subject,
            issue_class=issue_class,
            severity=group.highest_severity_signal.severity,
            confidence_band=outcome.confidence_band,
            signal_ids=group.signal_ids,
            correlation_fingerprint=group.fingerprint,
            facts=template.facts(group),
            recommended_action_class=template.recommended_action_class,
        )
