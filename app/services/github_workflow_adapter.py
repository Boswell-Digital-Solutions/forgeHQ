"""GitHub Actions workflow-run source adapter (BDS-FCO-CSD-v0.1, slices CSD-06 + CI follow-up).

Converts a GitHub Actions workflow run object -- the real, public,
stable shape returned by `GET /repos/{owner}/{repo}/actions/runs` (and
`gh run view --json ...`) -- into forgeHQ's `CloudSignal.v1`
(`cloud_signal_contracts.py`, CSD-01).

TRANSPORT-FREE: no network I/O here. `github_actions_client.py` reads runs;
this module only converts one run at a time.

TWO CONCLUSIONS ARE HANDLED, and they mean different things:

- `failure`: the workflow ran and failed. Issue class `ci_workflow_failure`.
  Scoped to a repository, workflow and BRANCH: a failed throwaway PR branch
  is not the same incident as a failed `main`. The run must name a workflow
  and a branch or it cannot be scoped, so it is rejected.
- `startup_failure`: the run never started. Issue class `ci_startup_failure`.
  Verified against real runs (2026-09-29, Forge_Command): these carry an
  EMPTY `name` and a placeholder `path` of "BuildFailed", so a name cannot be
  required for them. They occur across many branches at once (85 of the last
  100 runs), which makes this a repository-wide condition -- account or
  billing state, runner availability, workflow configuration -- not a code
  regression. It is scoped to the repository alone, and the summary states
  only what is known: the run did not start. It does not name a cause.

Every other conclusion (`cancelled`, `timed_out`, `action_required`,
`neutral`, `stale`, `skipped`, `success`) and any non-`completed` status
fails closed (returns None) rather than being guessed at.

Severity has no native GitHub Actions field, so each issue class uses one
fixed, disclosed default rather than a per-run judgment.
"""
from __future__ import annotations

import hashlib

from app.services.cloud_signal_contracts import (
    CloudSignal,
    CloudSignalCorrelation,
    CloudSignalEvidence,
    CloudSignalProvenance,
    CloudSignalShaper,
    CloudSignalSubject,
)

SOURCE_SYSTEM = "github_actions"
SOURCE_KIND = "ci_workflow_run"
ISSUE_CLASS = "ci_workflow_failure"
STARTUP_ISSUE_CLASS = "ci_startup_failure"

# GitHub Actions has no native severity field on a workflow run. Fixed and
# disclosed, not fabricated per-run.
DEFAULT_SEVERITY = "medium"
# A run that never starts blocks every workflow in the repository.
STARTUP_SEVERITY = "high"

CONCLUSION_FAILURE = "failure"
CONCLUSION_STARTUP_FAILURE = "startup_failure"
HANDLED_CONCLUSIONS = frozenset({CONCLUSION_FAILURE, CONCLUSION_STARTUP_FAILURE})


def _fingerprint(*parts: str) -> str:
    digest = hashlib.sha256("\0".join(parts).encode()).hexdigest()[:16]
    return f"fp-ci-{digest}"


def github_workflow_run_to_cloud_signal(
    run: dict,
    *,
    producer_version: str,
) -> CloudSignal | None:
    """Build a `CloudSignal` from a raw GitHub Actions workflow run object.

    Fails closed (returns None) on a missing required field, a `status`
    other than `"completed"`, or a `conclusion` outside `HANDLED_CONCLUSIONS`.
    """
    run_id = run.get("id")
    name = run.get("name")
    branch = run.get("head_branch")
    status = run.get("status")
    conclusion = run.get("conclusion")
    head_sha = run.get("head_sha")
    updated_at = run.get("updated_at")
    repository = run.get("repository") or {}
    repo_full_name = repository.get("full_name")

    if run_id is None or not repo_full_name or not updated_at or not head_sha:
        return None
    if status != "completed" or conclusion not in HANDLED_CONCLUSIONS:
        return None

    if conclusion == CONCLUSION_FAILURE:
        if not name or not branch:
            return None
        issue_class = ISSUE_CLASS
        severity = DEFAULT_SEVERITY
        fingerprint = _fingerprint(repo_full_name, name, branch)
        summary = (
            f'Workflow "{name}" failed on {repo_full_name}@{branch} '
            f"(run {run_id}, commit {head_sha[:12]})."
        )
    else:
        issue_class = STARTUP_ISSUE_CLASS
        severity = STARTUP_SEVERITY
        fingerprint = _fingerprint(repo_full_name, CONCLUSION_STARTUP_FAILURE)
        summary = (
            f"A workflow run did not start on {repo_full_name} "
            f"(startup_failure, run {run_id}, commit {head_sha[:12]})."
        )

    signal = CloudSignal(
        signal_id=f"ci-run-{run_id}",
        source_system=SOURCE_SYSTEM,
        source_kind=SOURCE_KIND,
        subject=CloudSignalSubject(subject_kind="repository", repository=repo_full_name),
        issue_class=issue_class,
        severity=severity,
        observed_at=updated_at,
        summary=summary,
        evidence=CloudSignalEvidence(
            source_refs=(f"signal://ci/{repo_full_name}/run/{run_id}",)
        ),
        correlation=CloudSignalCorrelation(fingerprint=fingerprint),
        provenance=CloudSignalProvenance(
            producer=SOURCE_SYSTEM,
            producer_version=producer_version,
            original_event_id=str(run_id),
        ),
    )
    return CloudSignalShaper().build(signal)
