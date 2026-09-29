"""Tests for bounded AI composition (BDS-FCO-CSD-v0.1, CSD-09).

Deterministic-stub-only, per Charlie's explicit ruling: no real NeuroForge
call exists yet (no API key available; retrieving one was refused by
Claude Code's own permission classifier). These tests prove the
generator/validator architecture -- structural boundedness (ComposedProse
has no field for anything the source review's §12 forbids an AI from
setting) and the numeric-grounding fact validator -- using the
deterministic stand-in.
"""
from app.services.cloud_proposal_ai_composer import (
    ComposedProse,
    DeterministicStubCompositionGenerator,
    validate_composed_prose,
)
from app.services.cloud_signal_contracts import CloudProposalCandidateShaper, CloudSignalSubject


def _candidate(**overrides):
    defaults = dict(
        subject=CloudSignalSubject(subject_kind="identity", tenant_id="tenant-abc", principal_id="principal-xyz"),
        issue_class="some_future_issue_class",
        severity="high",
        confidence_band="high",
        signal_ids=("cssa-finding-001",),
        correlation_fingerprint="fp-abc",
        facts=("3 block/quarantine decisions for principal principal-xyz within 15m (threshold 3).",),
        recommended_action_class="some_future_action_class",
    )
    defaults.update(overrides)
    candidate = CloudProposalCandidateShaper().build(**defaults)
    assert candidate is not None, "test fixture itself must be a valid candidate"
    return candidate


# --- Structural boundedness ------------------------------------------


def test_composed_prose_has_no_field_for_anything_ai_is_forbidden_to_set():
    # The source review's own §12 forbid-list: service identity, environment,
    # source IDs, evidence hashes, severity source, fingerprint, eligibility,
    # operator decision, authorization, execution status. None of these are
    # fields on ComposedProse at all -- a generator has nowhere to put them.
    forbidden_field_names = {
        "subject",
        "service",
        "environment",
        "signal_ids",
        "evidence_artifact_ids",
        "correlation_fingerprint",
        "severity",
        "confidence_band",
        "eligibility_decision",
        "decision",
        "authorization",
        "execution_status",
    }
    actual_fields = {f for f in ComposedProse.__dataclass_fields__}
    assert actual_fields.isdisjoint(forbidden_field_names)


# --- DeterministicStubCompositionGenerator ------------------------------


def test_stub_generator_always_produces_prose():
    candidate = _candidate()
    prose = DeterministicStubCompositionGenerator().compose(candidate)
    assert prose is not None
    assert prose.title.strip() != ""


def test_stub_generator_output_passes_its_own_validator():
    candidate = _candidate()
    prose = DeterministicStubCompositionGenerator().compose(candidate)
    assert prose is not None
    accepted, reason = validate_composed_prose(candidate, prose)
    assert accepted, reason


def test_stub_generator_problem_statement_is_the_candidates_own_facts():
    fact = "3 block/quarantine decisions for principal principal-xyz within 15m (threshold 3)."
    candidate = _candidate(facts=(fact,))
    prose = DeterministicStubCompositionGenerator().compose(candidate)
    assert prose is not None
    assert prose.problem_statement == fact


def test_stub_generator_risk_summary_carries_mandatory_constraint():
    candidate = _candidate()
    prose = DeterministicStubCompositionGenerator().compose(candidate)
    assert prose is not None
    assert "no production mutation authorized" in prose.risk_summary


# --- validate_composed_prose --------------------------------------------


def test_validator_rejects_empty_required_field():
    candidate = _candidate()
    prose = ComposedProse(
        title="",
        problem_statement="x",
        evidence_summary="x",
        scope_summary="x",
        recommended_action="x",
        expected_gain="x",
        risk_summary="x",
    )
    accepted, reason = validate_composed_prose(candidate, prose)
    assert not accepted
    assert "empty" in reason


def test_validator_rejects_a_fabricated_numeric_claim():
    candidate = _candidate(facts=("3 decisions observed.",))
    prose = ComposedProse(
        title="Investigate the incident",
        problem_statement="Actually 999 decisions were observed, far more than reported.",
        evidence_summary="1 correlated signal.",
        scope_summary="Tenant tenant-abc.",
        recommended_action="Escalate immediately.",
        expected_gain="Confirms the real scale.",
        risk_summary="no production mutation authorized",
    )
    accepted, reason = validate_composed_prose(candidate, prose)
    assert not accepted
    assert "999" in reason


def test_validator_accepts_a_number_that_is_grounded_in_facts():
    candidate = _candidate(facts=("3 decisions observed.",))
    prose = ComposedProse(
        title="Investigate the 3 correlated decisions",
        problem_statement="3 decisions observed.",
        evidence_summary="1 correlated signal.",
        scope_summary="Tenant tenant-abc.",
        recommended_action="Review the 3 decisions.",
        expected_gain="Confirms the pattern.",
        risk_summary="no production mutation authorized",
    )
    accepted, reason = validate_composed_prose(candidate, prose)
    assert accepted, reason


def test_validator_does_not_penalize_signal_id_digits_in_evidence_summary():
    # evidence_summary legitimately restates signal_ids (e.g.
    # "cssa-finding-001") and a signal count -- neither is a claim the
    # generator invented, so it must not be checked for grounding.
    candidate = _candidate(signal_ids=("cssa-finding-001", "cssa-finding-002"))
    prose = ComposedProse(
        title="Investigate the incident",
        problem_statement="3 decisions observed.",
        evidence_summary="2 correlated signal(s): cssa-finding-001, cssa-finding-002.",
        scope_summary="Tenant tenant-abc.",
        recommended_action="Review the decisions.",
        expected_gain="Confirms the pattern.",
        risk_summary="no production mutation authorized",
    )
    accepted, reason = validate_composed_prose(candidate, prose)
    assert accepted, reason
