"""Candidate -> proposal-input translator (BDS-FCO-CSD-v0.1, slice CSD-05).

Bridges CSD-04's `CloudProposalCandidate` (structured, no prose) into the
already-shipped Phase-1 `CloudProposalInput` (`cloud_proposal_shaper.py`,
`BDS-FCO-CLOUDPROP-v1.1`) -- the contract that shaper's `CloudProposalShaper`
and `to_cloud_proposal_envelope()` already know how to turn into a real
`cloud.proposal.v1` envelope.

DETERMINISTIC, NO LLM, same as CSD-04: every prose field here is templated
from the candidate's own structured data (`facts`, `recommended_action_class`,
`subject`, `constraints`) via a per-`recommended_action_class` template, not
inferred. Covers every `recommended_action_class` CSD-04's composer can
currently produce (`denial_streak`/`quota_exceeded_burst`/
`ci_workflow_failure`/`deploy_failure`); an unmapped action class fails
closed rather than composing generic prose.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.services.cloud_proposal_shaper import CloudProposalInput
from app.services.cloud_signal_contracts import CloudProposalCandidate


def _subject_scope_summary(candidate: CloudProposalCandidate) -> str:
    subject = candidate.subject
    if subject.subject_kind == "service":
        return f"Service {subject.service} ({subject.environment})."
    if subject.subject_kind == "repository":
        # Missing until now: this branch didn't exist when CSD-06 introduced
        # the "repository" subject_kind, so a CI-sourced candidate would have
        # fallen through to the identity-shaped summary below and printed
        # "Tenant unknown, principal unknown." Fixed here.
        return f"Repository {subject.repository}."
    return f"Tenant {subject.tenant_id or 'unknown'}, principal {subject.principal_id or 'unknown'}."


@dataclass(frozen=True, slots=True)
class _ActionTemplate:
    title: str  # format string, receives {scope}
    recommended_action: str
    expected_gain: str


_ACTION_TEMPLATES: dict[str, _ActionTemplate] = {
    "investigate_policy_denial_pattern": _ActionTemplate(
        title="Investigate policy denial pattern for {scope}",
        recommended_action=(
            "Review the correlated denial decisions and confirm whether the pattern reflects "
            "a genuine, deliberate authorization boundary or an unexpected client/service "
            "before any policy or entitlement change is made."
        ),
        expected_gain=(
            "Confirms whether the current denial pattern is expected, surfacing it for "
            "review before it escalates or masks a real integration problem."
        ),
    ),
    "investigate_quota_exhaustion": _ActionTemplate(
        title="Investigate quota exhaustion for {scope}",
        recommended_action=(
            "Review quota usage for the correlated burst and confirm whether the exhaustion "
            "reflects expected load or a misconfigured/runaway consumer before any quota "
            "change is made."
        ),
        expected_gain=(
            "Confirms whether the quota-exceeded burst is expected load or a runaway "
            "consumer, before it recurs or blocks legitimate traffic."
        ),
    ),
    "investigate_ci_workflow_failure": _ActionTemplate(
        title="Investigate CI workflow failure for {scope}",
        recommended_action=(
            "Review the correlated workflow failure(s) and confirm whether they reflect a "
            "genuine regression or an environment/flake issue before merging or retrying."
        ),
        expected_gain=(
            "Confirms whether the CI failure reflects a real regression, surfacing it for "
            "review before it blocks or masks other work."
        ),
    ),
    "investigate_deploy_failure": _ActionTemplate(
        title="Investigate deployment failure for {scope}",
        recommended_action=(
            "Review the correlated deploy failure(s) and confirm whether the cause is a "
            "genuine regression, configuration drift, or a transient infrastructure issue "
            "before retrying the deploy."
        ),
        expected_gain=(
            "Confirms whether the deployment failure reflects a real regression or "
            "configuration drift, before another deploy attempt."
        ),
    ),
}


def candidate_to_proposal_input(candidate: CloudProposalCandidate) -> CloudProposalInput | None:
    """Translate a `CloudProposalCandidate` into a `CloudProposalInput`.

    Fails closed (returns None) when `recommended_action_class` has no known
    template -- matching CSD-04's own composer, this never falls back to
    generic prose for something it doesn't recognize.
    """
    template = _ACTION_TEMPLATES.get(candidate.recommended_action_class)
    if template is None:
        return None

    scope = _subject_scope_summary(candidate)
    return CloudProposalInput(
        subject=candidate.subject,
        title=template.title.format(scope=scope),
        issue_class=candidate.issue_class,
        problem_statement=" ".join(candidate.facts),
        evidence_summary=(
            f"{len(candidate.signal_ids)} correlated signal(s): {', '.join(candidate.signal_ids)}."
        ),
        scope_summary=scope,
        recommended_action=template.recommended_action,
        expected_gain=template.expected_gain,
        risk_summary="; ".join(candidate.constraints),
        severity=candidate.severity,
        confidence_band=candidate.confidence_band,
        alternatives=[],
        diagnostic_artifact_ids=list(candidate.evidence_artifact_ids),
    )
