"""Tests for the GitHub Actions workflow-run -> CloudSignal adapter
(BDS-FCO-CSD-v0.1, CSD-06).

Fixtures mirror the real, public GitHub REST API workflow-run shape
(`GET /repos/{owner}/{repo}/actions/runs/{run_id}`), trimmed to the fields
this adapter actually reads.
"""
from app.services.github_workflow_adapter import (
    DEFAULT_SEVERITY,
    ISSUE_CLASS,
    SOURCE_KIND,
    SOURCE_SYSTEM,
    github_workflow_run_to_cloud_signal,
)


def _run(**overrides) -> dict:
    defaults = dict(
        id=123456789,
        name="CI",
        head_branch="main",
        head_sha="a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
        run_number=42,
        status="completed",
        conclusion="failure",
        html_url="https://github.com/Boswell-Digital-Solutions/forgeHQ/actions/runs/123456789",
        created_at="2026-09-29T08:00:00Z",
        updated_at="2026-09-29T08:05:00Z",
        event="push",
        repository={"full_name": "Boswell-Digital-Solutions/forgeHQ"},
    )
    defaults.update(overrides)
    return defaults


def test_adapter_converts_a_failed_completed_run():
    signal = github_workflow_run_to_cloud_signal(_run(), producer_version="1.0.0")
    assert signal is not None
    assert signal.subject.subject_kind == "repository"
    assert signal.subject.repository == "Boswell-Digital-Solutions/forgeHQ"
    assert signal.source_system == SOURCE_SYSTEM == "github_actions"
    assert signal.source_kind == SOURCE_KIND == "ci_workflow_run"
    assert signal.issue_class == ISSUE_CLASS == "ci_workflow_failure"
    assert signal.severity == DEFAULT_SEVERITY == "medium"


def test_adapter_fails_closed_on_non_completed_status():
    for status in ("in_progress", "queued", "waiting"):
        assert github_workflow_run_to_cloud_signal(_run(status=status), producer_version="1.0.0") is None


def test_adapter_fails_closed_on_non_failure_conclusion():
    for conclusion in ("success", "cancelled", "skipped", "neutral", "timed_out", "action_required", "stale", None):
        run = _run(conclusion=conclusion)
        assert github_workflow_run_to_cloud_signal(run, producer_version="1.0.0") is None


def test_adapter_fails_closed_on_missing_repository():
    run = _run(repository={})
    assert github_workflow_run_to_cloud_signal(run, producer_version="1.0.0") is None


def test_adapter_fails_closed_on_missing_run_id():
    run = _run(id=None)
    assert github_workflow_run_to_cloud_signal(run, producer_version="1.0.0") is None


def test_adapter_fails_closed_on_missing_head_sha():
    run = _run(head_sha=None)
    assert github_workflow_run_to_cloud_signal(run, producer_version="1.0.0") is None


def test_adapter_summary_names_workflow_repo_run_and_commit():
    signal = github_workflow_run_to_cloud_signal(_run(), producer_version="1.0.0")
    assert signal is not None
    assert "CI" in signal.summary
    assert "Boswell-Digital-Solutions/forgeHQ" in signal.summary
    assert "123456789" in signal.summary
    assert "a1b2c3d4e5f6" in signal.summary  # truncated commit prefix


def test_adapter_wraps_evidence_in_admissible_signal_scheme():
    signal = github_workflow_run_to_cloud_signal(_run(), producer_version="1.0.0")
    assert signal is not None
    assert signal.evidence.source_refs == (
        "signal://ci/Boswell-Digital-Solutions/forgeHQ/run/123456789",
    )


def test_adapter_fingerprint_stable_across_repeated_failures_of_same_workflow():
    a = github_workflow_run_to_cloud_signal(_run(id=1), producer_version="1.0.0")
    b = github_workflow_run_to_cloud_signal(_run(id=2), producer_version="1.0.0")
    assert a is not None and b is not None
    assert a.correlation.fingerprint == b.correlation.fingerprint


def test_adapter_fingerprint_differs_across_workflows_same_repo():
    a = github_workflow_run_to_cloud_signal(_run(name="CI"), producer_version="1.0.0")
    b = github_workflow_run_to_cloud_signal(_run(name="Deploy"), producer_version="1.0.0")
    assert a is not None and b is not None
    assert a.correlation.fingerprint != b.correlation.fingerprint


def test_adapter_fingerprint_differs_across_repos_same_workflow():
    a = github_workflow_run_to_cloud_signal(_run(), producer_version="1.0.0")
    b = github_workflow_run_to_cloud_signal(
        _run(repository={"full_name": "Boswell-Digital-Solutions/Forge_Command"}),
        producer_version="1.0.0",
    )
    assert a is not None and b is not None
    assert a.correlation.fingerprint != b.correlation.fingerprint
