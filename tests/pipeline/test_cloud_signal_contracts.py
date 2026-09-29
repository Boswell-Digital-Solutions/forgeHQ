"""Tests for the Cloud Subject Detector contract pack (BDS-FCO-CSD-v0.1, CSD-01).

Covers fail-closed validation on all three contracts and, most importantly,
the `cloud://` recursion guard: a forgeHQ-originated cloud proposal must not
be admissible as CloudSignal evidence, since `cloud_source_feeder.py` already
turns an existing proposal into a `cloud://` ref forgeHQ would otherwise
happily re-ingest as a new signal.
"""
from app.services.cloud_signal_contracts import (
    CLOUD_PROPOSAL_CANDIDATE_SCHEMA,
    CLOUD_PROPOSAL_DERIVATION_RECEIPT_SCHEMA,
    CLOUD_SIGNAL_SCHEMA,
    CloudProposalCandidateShaper,
    CloudProposalDerivationReceipt,
    CloudProposalDerivationReceiptShaper,
    CloudSignal,
    CloudSignalCorrelation,
    CloudSignalEvidence,
    CloudSignalProvenance,
    CloudSignalShaper,
    CloudSignalSubject,
    is_admissible_evidence_source,
)


def _signal(**overrides) -> CloudSignal:
    defaults = dict(
        signal_id="sig-001",
        source_system="forgesentinel",
        source_kind="cssa_finding",
        subject=CloudSignalSubject(service="neuroforge", environment="production"),
        issue_class="deploy_failure",
        severity="high",
        observed_at="2026-09-29T07:00:00Z",
        summary="Repeated denial-streak finding on the NeuroForge provider route.",
        evidence=CloudSignalEvidence(source_refs=("signal://cssa/finding-001",)),
        correlation=CloudSignalCorrelation(fingerprint="fp-neuroforge-prod-deploy_failure"),
        provenance=CloudSignalProvenance(
            producer="forgesentinel", producer_version="1.0.0", original_event_id="evt-001"
        ),
    )
    defaults.update(overrides)
    return CloudSignal(**defaults)


def test_schema_constants_are_versioned():
    assert CLOUD_SIGNAL_SCHEMA == "cloud.signal.v1"
    assert CLOUD_PROPOSAL_CANDIDATE_SCHEMA == "cloud.proposal_candidate.v1"
    assert CLOUD_PROPOSAL_DERIVATION_RECEIPT_SCHEMA == "cloud.proposal_derivation_receipt.v1"


# --- CloudSignal -------------------------------------------------------


def test_signal_shape_valid_input_produces_signal():
    result = CloudSignalShaper().build(_signal())
    assert result is not None
    assert result.subject.service == "neuroforge"


def test_signal_fails_closed_on_missing_signal_id():
    assert CloudSignalShaper().build(_signal(signal_id="")) is None


def test_signal_fails_closed_on_missing_service():
    sig = _signal(subject=CloudSignalSubject(service=""))
    assert CloudSignalShaper().build(sig) is None


def test_signal_fails_closed_on_unknown_severity():
    assert CloudSignalShaper().build(_signal(severity="apocalyptic")) is None


def test_signal_fails_closed_on_non_evidence_only_authority_posture():
    assert CloudSignalShaper().build(_signal(authority_posture="autonomous_execute")) is None


def test_signal_fails_closed_on_missing_correlation_fingerprint():
    sig = _signal(correlation=CloudSignalCorrelation(fingerprint=""))
    assert CloudSignalShaper().build(sig) is None


def test_signal_fails_closed_on_missing_provenance():
    sig = _signal(
        provenance=CloudSignalProvenance(producer="", producer_version="1.0.0", original_event_id="evt-001")
    )
    assert CloudSignalShaper().build(sig) is None


def test_signal_fails_closed_on_no_evidence_at_all():
    sig = _signal(evidence=CloudSignalEvidence())
    assert CloudSignalShaper().build(sig) is None


def test_signal_immutable_hashes_alone_satisfy_evidence_requirement():
    sig = _signal(evidence=CloudSignalEvidence(immutable_hashes=("sha256:deadbeef",)))
    assert CloudSignalShaper().build(sig) is not None


def test_cloud_scheme_is_not_admissible_evidence_source():
    # The recursion guard: an existing Forge_Command cloud proposal, mapped by
    # cloud_source_feeder.py into a cloud:// ref, must never feed a signal.
    assert is_admissible_evidence_source("cloud://neuroforge/some-proposal-id") is False


def test_signal_scheme_is_admissible_evidence_source():
    assert is_admissible_evidence_source("signal://cssa/finding-001") is True


def test_unknown_scheme_is_not_admissible_evidence_source():
    assert is_admissible_evidence_source("forgeeval://something") is False
    assert is_admissible_evidence_source("not-a-uri-at-all") is False


def test_signal_fails_closed_when_any_source_ref_is_a_cloud_proposal():
    # A forgeHQ-originated proposal must not be able to loop back into a new
    # signal even if it arrives alongside otherwise-legitimate evidence.
    sig = _signal(
        evidence=CloudSignalEvidence(
            source_refs=("signal://cssa/finding-001", "cloud://neuroforge/prior-proposal-id")
        )
    )
    assert CloudSignalShaper().build(sig) is None


# --- CloudProposalCandidate ---------------------------------------------


def _candidate_kwargs(**overrides):
    defaults = dict(
        subject=CloudSignalSubject(service="neuroforge", environment="production"),
        issue_class="deploy_failure",
        severity="high",
        confidence_band="high",
        signal_ids=("sig-001",),
        correlation_fingerprint="fp-neuroforge-prod-deploy_failure",
        facts=("deployment exited unsuccessfully",),
        recommended_action_class="investigate_deploy_failure",
    )
    defaults.update(overrides)
    return defaults


def test_candidate_shape_valid_input_produces_candidate():
    candidate = CloudProposalCandidateShaper().build(**_candidate_kwargs())
    assert candidate is not None
    assert candidate.subject.service == "neuroforge"


def test_candidate_id_is_deterministic_and_namespaced():
    a = CloudProposalCandidateShaper().build(**_candidate_kwargs())
    b = CloudProposalCandidateShaper().build(**_candidate_kwargs())
    assert a is not None and b is not None
    assert a.candidate_id == b.candidate_id
    assert a.candidate_id.startswith("forgehq-cloud-candidate-")


def test_candidate_id_is_keyed_on_fingerprint_not_prose():
    # This is the fingerprint-based identity fix, applied fresh to the new
    # contract: two candidates with the same evidence fingerprint collapse to
    # the same identity even if some future caller attaches different prose
    # (facts differ here, but subject/issue_class/fingerprint don't).
    a = CloudProposalCandidateShaper().build(**_candidate_kwargs())
    b = CloudProposalCandidateShaper().build(
        **_candidate_kwargs(facts=("a completely different worded observation",))
    )
    assert a is not None and b is not None
    assert a.candidate_id == b.candidate_id


def test_candidate_id_differs_when_fingerprint_differs():
    a = CloudProposalCandidateShaper().build(**_candidate_kwargs())
    b = CloudProposalCandidateShaper().build(
        **_candidate_kwargs(correlation_fingerprint="fp-different-incident")
    )
    assert a is not None and b is not None
    assert a.candidate_id != b.candidate_id


def test_candidate_fails_closed_on_no_signal_ids():
    assert CloudProposalCandidateShaper().build(**_candidate_kwargs(signal_ids=())) is None


def test_candidate_fails_closed_on_no_facts():
    assert CloudProposalCandidateShaper().build(**_candidate_kwargs(facts=())) is None


def test_candidate_fails_closed_on_unknown_confidence_band():
    assert CloudProposalCandidateShaper().build(**_candidate_kwargs(confidence_band="certain")) is None


def test_candidate_always_carries_the_mandatory_no_mutation_constraint():
    candidate = CloudProposalCandidateShaper().build(**_candidate_kwargs())
    assert candidate is not None
    assert "no production mutation authorized" in candidate.constraints


def test_candidate_mandatory_constraint_survives_caller_omission():
    candidate = CloudProposalCandidateShaper().build(**_candidate_kwargs(constraints=("unrelated note",)))
    assert candidate is not None
    assert "no production mutation authorized" in candidate.constraints
    assert "unrelated note" in candidate.constraints


# --- CloudProposalDerivationReceipt -------------------------------------


def _receipt(**overrides) -> CloudProposalDerivationReceipt:
    defaults = dict(
        candidate_id="forgehq-cloud-candidate-deadbeefdeadbeef",
        signal_ids=("sig-001",),
        correlation_fingerprint="fp-neuroforge-prod-deploy_failure",
        adapter_versions={"cssa_adapter": "0.1.0"},
        detector_version="0.1.0",
        composer_version="0.1.0",
        evidence_hashes=("sha256:deadbeef",),
        eligibility_decision="eligible",
        composition_mode="deterministic",
        created_at="2026-09-29T07:00:00Z",
    )
    defaults.update(overrides)
    return CloudProposalDerivationReceipt(**defaults)


def test_receipt_shape_valid_input_produces_receipt():
    result = CloudProposalDerivationReceiptShaper().build(_receipt())
    assert result is not None
    assert result.proposal_id is None  # not yet published -- CSD-05, later slice


def test_receipt_fails_closed_on_no_adapter_versions():
    assert CloudProposalDerivationReceiptShaper().build(_receipt(adapter_versions={})) is None


def test_receipt_fails_closed_on_no_evidence_hashes():
    assert CloudProposalDerivationReceiptShaper().build(_receipt(evidence_hashes=())) is None


def test_receipt_fails_closed_on_unknown_eligibility_decision():
    assert CloudProposalDerivationReceiptShaper().build(_receipt(eligibility_decision="rubber_stamped")) is None


def test_receipt_fails_closed_on_ai_assisted_composition_mode():
    # v0.1 is deterministic-composition-only; ai_assisted is real future
    # scope (CSD-09) but not authorized by this slice.
    assert CloudProposalDerivationReceiptShaper().build(_receipt(composition_mode="ai_assisted")) is None


def test_receipt_fails_closed_on_missing_candidate_id():
    assert CloudProposalDerivationReceiptShaper().build(_receipt(candidate_id="")) is None
