"""Tests for correlation + proposal eligibility (BDS-FCO-CSD-v0.1, CSD-03).

Still shadow-only: this module never publishes anything and never decides
what a proposal says -- only whether correlated evidence is eligible for one.
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
    ELIGIBLE,
    INSUFFICIENT_EVIDENCE,
    SUPPRESSED,
    CloudProposalEligibilityGate,
    CloudSignalCorrelator,
)


def _signal(
    signal_id: str,
    *,
    fingerprint: str = "fp-neuroforge-prod",
    service: str = "neuroforge",
    severity: str = "high",
    with_hash: bool = True,
) -> CloudSignal:
    return CloudSignal(
        signal_id=signal_id,
        source_system="forgesentinel",
        source_kind="cssa_finding",
        subject=CloudSignalSubject(service=service, environment="production"),
        issue_class="deny_streak",
        severity=severity,
        observed_at="2026-09-29T07:00:00Z",
        summary="Denial streak exceeded threshold.",
        evidence=CloudSignalEvidence(
            source_refs=("signal://cssa/finding/1/evidence",),
            immutable_hashes=("sha256:" + "a" * 64,) if with_hash else (),
        ),
        correlation=CloudSignalCorrelation(fingerprint=fingerprint),
        provenance=CloudSignalProvenance(
            producer="forgesentinel", producer_version="1.0.0", original_event_id=signal_id
        ),
    )


# --- CloudSignalCorrelator ----------------------------------------------


def test_correlator_groups_signals_by_fingerprint():
    signals = [
        _signal("sig-1", fingerprint="fp-a"),
        _signal("sig-2", fingerprint="fp-a"),
        _signal("sig-3", fingerprint="fp-b"),
    ]
    groups = CloudSignalCorrelator().correlate(signals)
    assert len(groups) == 2
    by_fp = {g.fingerprint: g for g in groups}
    assert by_fp["fp-a"].signal_ids == ("sig-1", "sig-2")
    assert by_fp["fp-b"].signal_ids == ("sig-3",)


def test_correlator_drops_replayed_duplicate_signal_ids():
    signals = [
        _signal("sig-1", fingerprint="fp-a"),
        _signal("sig-1", fingerprint="fp-a"),  # replayed, not independent
    ]
    groups = CloudSignalCorrelator().correlate(signals)
    assert len(groups) == 1
    assert groups[0].signal_ids == ("sig-1",)


def test_correlator_empty_input_produces_no_groups():
    assert CloudSignalCorrelator().correlate([]) == ()


def test_correlator_preserves_first_seen_group_order():
    signals = [
        _signal("sig-1", fingerprint="fp-b"),
        _signal("sig-2", fingerprint="fp-a"),
    ]
    groups = CloudSignalCorrelator().correlate(signals)
    assert [g.fingerprint for g in groups] == ["fp-b", "fp-a"]


def test_group_highest_severity_signal_picks_most_severe():
    group = CloudSignalCorrelator().correlate(
        [
            _signal("sig-1", fingerprint="fp-a", severity="low"),
            _signal("sig-2", fingerprint="fp-a", severity="critical"),
        ]
    )[0]
    assert group.highest_severity_signal.signal_id == "sig-2"


# --- CloudProposalEligibilityGate ----------------------------------------


def _group(fingerprint: str, signals):
    return CloudSignalCorrelator().correlate(signals)[0]


def test_gate_multiple_signals_are_high_confidence_and_eligible():
    group = _group("fp-a", [_signal("sig-1", fingerprint="fp-a"), _signal("sig-2", fingerprint="fp-a")])
    outcome = CloudProposalEligibilityGate().evaluate(group)
    assert outcome.decision == ELIGIBLE
    assert outcome.confidence_band == "high"


def test_gate_single_signal_with_immutable_hash_is_high_confidence():
    group = _group("fp-a", [_signal("sig-1", fingerprint="fp-a", with_hash=True)])
    outcome = CloudProposalEligibilityGate().evaluate(group)
    assert outcome.decision == ELIGIBLE
    assert outcome.confidence_band == "high"


def test_gate_single_signal_without_immutable_hash_is_medium_confidence_and_still_eligible():
    group = _group("fp-a", [_signal("sig-1", fingerprint="fp-a", with_hash=False)])
    outcome = CloudProposalEligibilityGate().evaluate(group)
    assert outcome.decision == ELIGIBLE
    assert outcome.confidence_band == "medium"


def test_gate_suppresses_when_open_proposal_already_exists():
    group = _group("fp-a", [_signal("sig-1", fingerprint="fp-a")])
    outcome = CloudProposalEligibilityGate().evaluate(
        group, open_proposal_fingerprints=frozenset({"fp-a"})
    )
    assert outcome.decision == DUPLICATE
    assert outcome.confidence_band is None


def test_gate_suppresses_within_cooldown():
    group = _group("fp-a", [_signal("sig-1", fingerprint="fp-a")])
    outcome = CloudProposalEligibilityGate().evaluate(
        group, suppressed_fingerprints=frozenset({"fp-a"})
    )
    assert outcome.decision == SUPPRESSED
    assert outcome.confidence_band is None


def test_gate_open_proposal_suppression_takes_precedence_over_cooldown():
    group = _group("fp-a", [_signal("sig-1", fingerprint="fp-a")])
    outcome = CloudProposalEligibilityGate().evaluate(
        group,
        open_proposal_fingerprints=frozenset({"fp-a"}),
        suppressed_fingerprints=frozenset({"fp-a"}),
    )
    assert outcome.decision == DUPLICATE


def test_gate_every_decision_carries_an_explainable_reason():
    group = _group("fp-a", [_signal("sig-1", fingerprint="fp-a")])
    for outcome in (
        CloudProposalEligibilityGate().evaluate(group),
        CloudProposalEligibilityGate().evaluate(group, open_proposal_fingerprints=frozenset({"fp-a"})),
        CloudProposalEligibilityGate().evaluate(group, suppressed_fingerprints=frozenset({"fp-a"})),
    ):
        assert outcome.reason.strip() != ""


def test_gate_outcome_decision_values_match_derivation_receipt_closed_set():
    # These string values must stay aligned with
    # CloudProposalDerivationReceipt's own _VALID_ELIGIBILITY_DECISIONS
    # (cloud_signal_contracts.py) so a later receipt can carry an eligibility
    # decision through unchanged -- verified directly, not just asserted.
    from app.services.cloud_signal_contracts import _VALID_ELIGIBILITY_DECISIONS

    assert {ELIGIBLE, DUPLICATE, SUPPRESSED, INSUFFICIENT_EVIDENCE} <= _VALID_ELIGIBILITY_DECISIONS
