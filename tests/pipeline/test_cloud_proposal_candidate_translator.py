"""Tests for the candidate -> proposal-input translator (BDS-FCO-CSD-v0.1, CSD-05).

Ties CSD-04's composer output to the already-shipped Phase-1 shaper: every
field this module produces must be deterministic and traceable back to the
candidate's own structured data, never invented.
"""
from app.services.cloud_proposal_candidate_translator import candidate_to_proposal_input
from app.services.cloud_signal_contracts import CloudProposalCandidateShaper, CloudSignalSubject


def _candidate(**overrides):
    defaults = dict(
        subject=CloudSignalSubject(subject_kind="identity", tenant_id="tenant-abc", principal_id="principal-xyz"),
        issue_class="denial_streak",
        severity="high",
        confidence_band="high",
        signal_ids=("cssa-finding-001", "cssa-finding-002"),
        correlation_fingerprint="fp-cssa-deadbeef",
        facts=("3 block/quarantine decisions for principal principal-xyz within 15m (threshold 3).",),
        recommended_action_class="investigate_policy_denial_pattern",
    )
    defaults.update(overrides)
    candidate = CloudProposalCandidateShaper().build(**defaults)
    assert candidate is not None, "test fixture itself must be a valid candidate"
    return candidate


def test_translator_produces_valid_proposal_input_for_known_action_class():
    proposal_input = candidate_to_proposal_input(_candidate())
    assert proposal_input is not None
    assert proposal_input.issue_class == "denial_streak"
    assert proposal_input.severity == "high"
    assert proposal_input.confidence_band == "high"


def test_translator_title_names_the_identity_scope():
    proposal_input = candidate_to_proposal_input(_candidate())
    assert proposal_input is not None
    assert "tenant-abc" in proposal_input.title
    assert "principal-xyz" in proposal_input.title


def test_translator_problem_statement_is_joined_facts():
    fact = "3 block/quarantine decisions for principal principal-xyz within 15m (threshold 3)."
    proposal_input = candidate_to_proposal_input(_candidate(facts=(fact,)))
    assert proposal_input is not None
    assert proposal_input.problem_statement == fact


def test_translator_evidence_summary_names_signal_count_and_ids():
    proposal_input = candidate_to_proposal_input(_candidate())
    assert proposal_input is not None
    assert "2 correlated signal(s)" in proposal_input.evidence_summary
    assert "cssa-finding-001" in proposal_input.evidence_summary
    assert "cssa-finding-002" in proposal_input.evidence_summary


def test_translator_risk_summary_carries_the_mandatory_no_mutation_constraint():
    proposal_input = candidate_to_proposal_input(_candidate())
    assert proposal_input is not None
    assert "no production mutation authorized" in proposal_input.risk_summary


def test_translator_handles_quota_exceeded_burst_action_class():
    candidate = _candidate(
        issue_class="quota_exceeded_burst",
        recommended_action_class="investigate_quota_exhaustion",
        facts=("5 quota-exceeded decisions for principal principal-xyz within 10m (threshold 5).",),
    )
    proposal_input = candidate_to_proposal_input(candidate)
    assert proposal_input is not None
    assert "quota exhaustion" in proposal_input.title.lower()


def test_translator_service_scoped_candidate_uses_service_scope_summary():
    candidate = _candidate(subject=CloudSignalSubject(service="neuroforge", environment="production"))
    proposal_input = candidate_to_proposal_input(candidate)
    assert proposal_input is not None
    assert proposal_input.scope_summary == "Service neuroforge (production)."


def test_translator_repository_scoped_candidate_uses_repository_scope_summary():
    # Bug fix: this branch didn't exist until now -- a repository-scoped
    # candidate previously fell through to the identity-shaped summary and
    # printed "Tenant unknown, principal unknown."
    candidate = _candidate(
        subject=CloudSignalSubject(subject_kind="repository", repository="org/forgeHQ"),
        issue_class="ci_workflow_failure",
        recommended_action_class="investigate_ci_workflow_failure",
        facts=('Workflow "CI" failed on org/forgeHQ (run 123, commit abc123def456).',),
    )
    proposal_input = candidate_to_proposal_input(candidate)
    assert proposal_input is not None
    assert proposal_input.scope_summary == "Repository org/forgeHQ."
    assert "org/forgeHQ" in proposal_input.title


def test_translator_handles_ci_workflow_failure_action_class():
    candidate = _candidate(
        subject=CloudSignalSubject(subject_kind="repository", repository="org/forgeHQ"),
        issue_class="ci_workflow_failure",
        recommended_action_class="investigate_ci_workflow_failure",
        facts=('Workflow "CI" failed on org/forgeHQ (run 123, commit abc123def456).',),
    )
    proposal_input = candidate_to_proposal_input(candidate)
    assert proposal_input is not None
    assert "CI workflow failure" in proposal_input.title


def test_translator_handles_deploy_failure_action_class():
    candidate = _candidate(
        subject=CloudSignalSubject(service="neuroforge"),
        issue_class="deploy_failure",
        recommended_action_class="investigate_deploy_failure",
        facts=('Render deploy failed for service "neuroforge" (event evt-1).',),
    )
    proposal_input = candidate_to_proposal_input(candidate)
    assert proposal_input is not None
    assert "deployment failure" in proposal_input.title.lower()


def test_translator_fails_closed_on_unknown_recommended_action_class():
    candidate = _candidate(recommended_action_class="some_future_action_class")
    assert candidate_to_proposal_input(candidate) is None


def test_translator_carries_evidence_artifact_ids_through():
    candidate = _candidate(evidence_artifact_ids=("artifact-1",))
    proposal_input = candidate_to_proposal_input(candidate)
    assert proposal_input is not None
    assert proposal_input.diagnostic_artifact_ids == ["artifact-1"]


def test_translator_no_alternatives_invented():
    proposal_input = candidate_to_proposal_input(_candidate())
    assert proposal_input is not None
    assert proposal_input.alternatives == []
