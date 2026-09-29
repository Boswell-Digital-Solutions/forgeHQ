"""Tests for the cloud-subject proposal shaper + the cloud.proposal.v1 adapter.

Covers fail-closed validation, deterministic event_id, and that the adapted
envelope matches the DataForge-Local contract Forge_Command's cloud-proposal
bridge reads (payload fields map 1:1 onto the CloudProposal frontend type).
"""
from app.services.cloud_proposal_shaper import (
    CLOUD_PROPOSAL_SCHEMA,
    SOURCE_SYSTEM,
    CloudProposalInput,
    CloudProposalShaper,
    CloudSubject,
    to_cloud_proposal_envelope,
)


def _input(**overrides) -> CloudProposalInput:
    defaults = dict(
        subject=CloudSubject(service="rake", environment="production"),
        title="Investigate Rake render health timeout",
        issue_class="startup_failure",
        problem_statement="Render deployment timed out waiting for /health/render.",
        evidence_summary="Deploy failed with no successful health response.",
        scope_summary="Rake startup path and readiness route.",
        recommended_action="Inspect boot logs for regressions.",
        expected_gain="Restore reliable deploy health confirmation.",
        risk_summary="Moderate risk if this reflects a real regression.",
        severity="high",
        confidence_band="medium",
        alternatives=["Retry deploy unchanged"],
        diagnostic_artifact_ids=["diagnostic-rake"],
    )
    defaults.update(overrides)
    return CloudProposalInput(**defaults)


def test_shape_valid_input_produces_proposal():
    proposal = CloudProposalShaper().shape(_input())
    assert proposal is not None
    assert proposal.input.subject.service == "rake"


def test_shape_fails_closed_on_missing_service():
    proposal_input = _input(subject=CloudSubject(service="", environment="production"))
    assert CloudProposalShaper().shape(proposal_input) is None


def test_shape_fails_closed_on_missing_title():
    assert CloudProposalShaper().shape(_input(title="")) is None


def test_shape_fails_closed_on_missing_problem_statement():
    assert CloudProposalShaper().shape(_input(problem_statement="")) is None


def test_event_id_is_deterministic_and_namespaced():
    a = CloudProposalShaper().shape(_input())
    b = CloudProposalShaper().shape(_input())
    assert a is not None and b is not None
    assert a.event_id == b.event_id  # idempotent ingest
    assert a.event_id.startswith("forgehq-cloud-")


def test_event_id_differs_for_different_subjects():
    a = CloudProposalShaper().shape(_input())
    b = CloudProposalShaper().shape(_input(subject=CloudSubject(service="neuroforge")))
    assert a is not None and b is not None
    assert a.event_id != b.event_id


def test_shape_accepts_identity_scoped_subject():
    # Widened after BDS-FCO-CSD-v0.1's own correction: CSD-04's composer
    # only ever produces identity-scoped candidates (forgesentinel's two
    # real detectors), so this shaper must be able to publish them.
    proposal_input = _input(subject=CloudSubject(subject_kind="identity", tenant_id="tenant-abc"))
    proposal = CloudProposalShaper().shape(proposal_input)
    assert proposal is not None
    assert proposal.input.subject.subject_kind == "identity"


def test_shape_fails_closed_on_identity_subject_with_no_identity_fields():
    proposal_input = _input(subject=CloudSubject(subject_kind="identity"))
    assert CloudProposalShaper().shape(proposal_input) is None


def test_envelope_service_field_falls_back_to_identity_key_for_identity_subject():
    proposal_input = _input(
        subject=CloudSubject(subject_kind="identity", tenant_id="tenant-abc", principal_id="principal-xyz")
    )
    proposal = CloudProposalShaper().shape(proposal_input)
    assert proposal is not None
    env = to_cloud_proposal_envelope(proposal)
    # Always a non-null string (Forge_Command's frontend type requires
    # service: string), legibly prefixed so it reads as an identity, not a
    # fabricated service name.
    assert env["payload"]["service"] == "identity:tenant-abc:principal-xyz"


def test_event_id_differs_between_service_and_identity_subjects_with_overlapping_names():
    # A service literally named "tenant-abc" must not collide with an
    # identity subject whose tenant_id is "tenant-abc" -- identity_key's
    # "service:"/"identity:" prefixing keeps them distinct.
    a = CloudProposalShaper().shape(_input(subject=CloudSubject(service="tenant-abc")))
    b = CloudProposalShaper().shape(
        _input(subject=CloudSubject(subject_kind="identity", tenant_id="tenant-abc"))
    )
    assert a is not None and b is not None
    assert a.event_id != b.event_id


def test_envelope_matches_cloud_proposal_contract():
    proposal = CloudProposalShaper().shape(_input())
    assert proposal is not None
    env = to_cloud_proposal_envelope(proposal)

    assert env["event_id"] == proposal.event_id
    assert env["source_system"] == SOURCE_SYSTEM == "forgehq"
    assert env["schema_version"] == CLOUD_PROPOSAL_SCHEMA == "cloud.proposal.v1"
    assert env["event_class"] == "proposal"
    assert env["source_environment"] == "cloud"
    assert env["severity"] == "high"
    # No file target: repo_id/commit_sha are omitted, not empty-stringed.
    assert "repo_id" not in env
    assert "commit_sha" not in env

    payload = env["payload"]
    assert payload["kind"] == "cloud_proposal"
    assert payload["service"] == "rake"
    assert payload["environment"] == "production"
    assert payload["title"] == "Investigate Rake render health timeout"
    assert payload["issueClass"] == "startup_failure"
    assert payload["confidenceBand"] == "medium"
    assert payload["problemStatement"]
    assert payload["evidenceSummary"]
    assert payload["scopeSummary"]
    assert payload["recommendedAction"]
    assert payload["expectedGain"]
    assert payload["riskSummary"]
    assert payload["alternatives"] == ["Retry deploy unchanged"]
    assert payload["diagnosticArtifactIds"] == ["diagnostic-rake"]
