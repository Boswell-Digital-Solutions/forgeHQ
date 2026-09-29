"""Tests for the deterministic proposal composer (BDS-FCO-CSD-v0.1, CSD-04).

Ties CSD-01 (contracts), CSD-02 (adapter output shape), and CSD-03
(correlation + eligibility) together: a signal batch -> correlated groups ->
eligibility outcomes -> a real CloudProposalCandidate, still with no
publishing anywhere in this pipeline.
"""
from app.services.cloud_signal_contracts import (
    CloudSignal,
    CloudSignalCorrelation,
    CloudSignalEvidence,
    CloudSignalProvenance,
    CloudSignalSubject,
)
from app.services.cloud_signal_correlation import (
    DUPLICATE,
    CloudProposalEligibilityGate,
    CloudSignalCorrelator,
    EligibilityOutcome,
)
from app.services.cloud_proposal_composer import CloudProposalComposer


def _signal(
    signal_id: str,
    *,
    issue_class: str = "denial_streak",
    fingerprint: str = "fp-tenant-abc",
    severity: str = "high",
    summary: str = "3 block/quarantine decisions for principal principal-xyz within 15m (threshold 3).",
) -> CloudSignal:
    return CloudSignal(
        signal_id=signal_id,
        source_system="forgesentinel",
        source_kind="cssa_finding",
        subject=CloudSignalSubject(subject_kind="identity", tenant_id="tenant-abc", principal_id="principal-xyz"),
        issue_class=issue_class,
        severity=severity,
        observed_at="2026-09-29T07:00:00Z",
        summary=summary,
        evidence=CloudSignalEvidence(immutable_hashes=("sha256:" + "a" * 64,)),
        correlation=CloudSignalCorrelation(fingerprint=fingerprint),
        provenance=CloudSignalProvenance(
            producer="forgesentinel", producer_version="1.0.0", original_event_id=signal_id
        ),
    )


def _group_and_outcome(signals, **gate_kwargs):
    group = CloudSignalCorrelator().correlate(signals)[0]
    outcome = CloudProposalEligibilityGate().evaluate(group, **gate_kwargs)
    return group, outcome


def test_composer_produces_candidate_for_known_issue_class():
    group, outcome = _group_and_outcome([_signal("sig-1"), _signal("sig-2")])
    candidate = CloudProposalComposer().compose(group, outcome)
    assert candidate is not None
    assert candidate.issue_class == "denial_streak"
    assert candidate.recommended_action_class == "investigate_policy_denial_pattern"
    assert candidate.confidence_band == "high"
    assert candidate.severity == "high"
    assert candidate.signal_ids == ("sig-1", "sig-2")
    assert candidate.correlation_fingerprint == group.fingerprint


def test_composer_facts_are_the_signals_own_summaries_plus_a_count():
    summary = "3 block/quarantine decisions for principal principal-xyz within 15m (threshold 3)."
    group, outcome = _group_and_outcome([_signal("sig-1", summary=summary)])
    candidate = CloudProposalComposer().compose(group, outcome)
    assert candidate is not None
    assert summary in candidate.facts
    assert "1 correlated signal(s) observed for this fingerprint." in candidate.facts


def test_composer_deduplicates_identical_summaries():
    same_summary = "Same summary text."
    group, outcome = _group_and_outcome(
        [_signal("sig-1", summary=same_summary), _signal("sig-2", summary=same_summary)]
    )
    candidate = CloudProposalComposer().compose(group, outcome)
    assert candidate is not None
    assert candidate.facts.count(same_summary) == 1


def test_composer_handles_quota_exceeded_burst_template():
    group, outcome = _group_and_outcome(
        [_signal("sig-1", issue_class="quota_exceeded_burst", fingerprint="fp-quota")]
    )
    candidate = CloudProposalComposer().compose(group, outcome)
    assert candidate is not None
    assert candidate.recommended_action_class == "investigate_quota_exhaustion"


def test_composer_fails_closed_on_unknown_issue_class():
    group, outcome = _group_and_outcome(
        [_signal("sig-1", issue_class="some_future_detector", fingerprint="fp-unknown")]
    )
    assert CloudProposalComposer().compose(group, outcome) is None


def test_composer_fails_closed_when_outcome_is_not_eligible():
    group, _ = _group_and_outcome([_signal("sig-1")])
    duplicate_outcome = EligibilityOutcome(
        fingerprint=group.fingerprint,
        decision=DUPLICATE,
        confidence_band=None,
        reason="an open proposal already exists",
        signal_ids=group.signal_ids,
    )
    assert CloudProposalComposer().compose(group, duplicate_outcome) is None


def test_composer_fails_closed_on_mismatched_fingerprints():
    group, outcome = _group_and_outcome([_signal("sig-1")])
    mismatched = EligibilityOutcome(
        fingerprint="fp-different",
        decision=outcome.decision,
        confidence_band=outcome.confidence_band,
        reason=outcome.reason,
        signal_ids=outcome.signal_ids,
    )
    assert CloudProposalComposer().compose(group, mismatched) is None


def test_composer_uses_highest_severity_across_correlated_signals():
    group, outcome = _group_and_outcome(
        [_signal("sig-1", severity="low"), _signal("sig-2", severity="critical")]
    )
    candidate = CloudProposalComposer().compose(group, outcome)
    assert candidate is not None
    assert candidate.severity == "critical"


def test_composer_candidate_carries_the_identity_scoped_subject():
    group, outcome = _group_and_outcome([_signal("sig-1")])
    candidate = CloudProposalComposer().compose(group, outcome)
    assert candidate is not None
    assert candidate.subject.subject_kind == "identity"
    assert candidate.subject.tenant_id == "tenant-abc"


def test_composer_candidate_still_carries_the_mandatory_no_mutation_constraint():
    group, outcome = _group_and_outcome([_signal("sig-1")])
    candidate = CloudProposalComposer().compose(group, outcome)
    assert candidate is not None
    assert "no production mutation authorized" in candidate.constraints


def test_composer_never_publishes_anything():
    import app.services.cloud_proposal_composer as module

    assert not hasattr(module, "publish")
    assert not hasattr(module, "healing_publisher")
