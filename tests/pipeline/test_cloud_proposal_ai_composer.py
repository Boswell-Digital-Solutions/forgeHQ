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


# --- NeuroForgeCompositionGenerator (real backend, fake transport only) ----
#
# No test here makes a network call: `transport` is always injected, and the
# credential env vars are cleared/pinned per test so a real key in the
# developer's shell can never leak into (or be needed by) a test.

import json

import pytest

from app.services.cloud_proposal_ai_composer import (
    NeuroForgeCompositionGenerator,
    _parse_prose,
)


@pytest.fixture(autouse=True)
def _no_ambient_credentials(monkeypatch):
    monkeypatch.delenv("NEUROFORGE_API_KEY", raising=False)
    monkeypatch.delenv("NEUROFORGE_SERVICE_KEY", raising=False)


_GOOD_REPLY = {
    "title": "Investigate the denial pattern",
    "problem_statement": "3 block/quarantine decisions for principal principal-xyz within 15m (threshold 3).",
    "evidence_summary": "1 correlated signal(s): cssa-finding-001.",
    "scope_summary": "Tenant tenant-abc, principal principal-xyz.",
    "recommended_action": "Review the decisions before changing any policy.",
    "expected_gain": "Confirms whether the pattern is expected.",
    "risk_summary": "no production mutation authorized",
    "alternatives": ["Do nothing and observe"],
}


class _RecordingTransport:
    def __init__(self, content):
        self.content = content
        self.calls = []

    def __call__(self, url, body, headers, timeout):
        self.calls.append((url, body, headers, timeout))
        return {"content": self.content}


def test_neuroforge_generator_returns_prose_from_a_valid_json_reply():
    transport = _RecordingTransport(json.dumps(_GOOD_REPLY))
    gen = NeuroForgeCompositionGenerator(api_key="test-key", transport=transport)
    prose = gen.compose(_candidate())
    assert prose is not None
    assert prose.title == _GOOD_REPLY["title"]
    assert prose.alternatives == ("Do nothing and observe",)


def test_neuroforge_generator_output_still_passes_the_fact_validator():
    transport = _RecordingTransport(json.dumps(_GOOD_REPLY))
    gen = NeuroForgeCompositionGenerator(api_key="test-key", transport=transport)
    candidate = _candidate()
    prose = gen.compose(candidate)
    assert prose is not None
    accepted, reason = validate_composed_prose(candidate, prose)
    assert accepted, reason


def test_neuroforge_generator_sends_bearer_auth_to_the_chat_endpoint():
    transport = _RecordingTransport(json.dumps(_GOOD_REPLY))
    NeuroForgeCompositionGenerator(
        base_url="https://nf.example/", api_key="test-key", transport=transport
    ).compose(_candidate())
    url, body, headers, _timeout = transport.calls[0]
    assert url == "https://nf.example/api/v1/chat"
    assert headers["Authorization"] == "Bearer test-key"
    assert body["task_type"] == "cloud_proposal_composition"
    assert body["temperature"] == 0.0


def test_neuroforge_generator_fails_closed_without_a_key_and_never_calls_out():
    transport = _RecordingTransport(json.dumps(_GOOD_REPLY))
    gen = NeuroForgeCompositionGenerator(transport=transport)
    assert gen.compose(_candidate()) is None
    assert transport.calls == []  # never sends an unauthenticated request


def test_neuroforge_generator_reads_key_from_env_at_call_time(monkeypatch):
    transport = _RecordingTransport(json.dumps(_GOOD_REPLY))
    gen = NeuroForgeCompositionGenerator(transport=transport)
    monkeypatch.setenv("NEUROFORGE_SERVICE_KEY", "env-key")
    assert gen.compose(_candidate()) is not None
    assert transport.calls[0][2]["Authorization"] == "Bearer env-key"


def test_neuroforge_generator_prompt_contains_only_bounded_candidate_data():
    transport = _RecordingTransport(json.dumps(_GOOD_REPLY))
    candidate = _candidate(correlation_fingerprint="fp-SECRET-FINGERPRINT")
    NeuroForgeCompositionGenerator(api_key="k", transport=transport).compose(candidate)
    _url, body, _headers, _timeout = transport.calls[0]
    sent = json.dumps(body)
    assert "fp-SECRET-FINGERPRINT" not in sent  # fingerprint never leaves
    assert "cssa-finding-001" not in sent  # signal ids never leave
    assert candidate.facts[0] in sent  # the facts do


def test_neuroforge_generator_fails_closed_on_transport_error():
    def boom(url, body, headers, timeout):
        raise OSError("connection refused")

    gen = NeuroForgeCompositionGenerator(api_key="k", transport=boom)
    assert gen.compose(_candidate()) is None


@pytest.mark.parametrize(
    "reply",
    [
        None,
        "",
        "not json at all",
        json.dumps(["a", "list"]),
        json.dumps({k: v for k, v in _GOOD_REPLY.items() if k != "title"}),
        json.dumps({**_GOOD_REPLY, "title": 7}),
        json.dumps({**_GOOD_REPLY, "alternatives": "nope"}),
        json.dumps({**_GOOD_REPLY, "alternatives": [1, 2]}),
    ],
)
def test_neuroforge_generator_fails_closed_on_malformed_replies(reply):
    gen = NeuroForgeCompositionGenerator(api_key="k", transport=_RecordingTransport(reply))
    assert gen.compose(_candidate()) is None


def test_parse_prose_strips_a_single_markdown_fence():
    fenced = "```json\n" + json.dumps(_GOOD_REPLY) + "\n```"
    assert _parse_prose(fenced) is not None


def test_a_fabricating_neuroforge_reply_is_rejected_by_the_translator():
    from app.services.cloud_proposal_candidate_translator import candidate_to_proposal_input

    fabricated = {**_GOOD_REPLY, "problem_statement": "Actually 999 decisions occurred."}
    gen = NeuroForgeCompositionGenerator(
        api_key="k", transport=_RecordingTransport(json.dumps(fabricated))
    )
    assert candidate_to_proposal_input(_candidate(), ai_generator=gen) is None
