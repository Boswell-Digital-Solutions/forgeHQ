"""GitHub Actions workflow-run source adapter (BDS-FCO-CSD-v0.1, slice CSD-06).

Converts a GitHub Actions workflow run object -- the real, public,
stable shape returned by `GET /repos/{owner}/{repo}/actions/runs/{run_id}`
(and by `gh run view --json ...`) -- into forgeHQ's `CloudSignal.v1`
(`cloud_signal_contracts.py`, CSD-01).

TRANSPORT-FREE, matching CSD-02's adapter and every other adapter/feeder in
this repo: no network I/O, no polling of the GitHub API. The caller
(a future transport slice) is responsible for obtaining the raw run payload.

SCOPE, DELIBERATELY MINIMAL FOR THIS FIRST CI SLICE: only `conclusion ==
"failure"` produces a signal. `cancelled`, `timed_out`, `action_required`,
`neutral`, `stale`, and any non-`"completed"` `status` are real GitHub
Actions outcomes but are not handled yet -- fails closed (returns None)
rather than guessing at their meaning. Repeated-failure and required-check
distinctions (the design's own "repeated workflow failure" / "required
check failure" framing) are future work; this slice proves one real,
unambiguous case: a completed run that failed.

REPOSITORY-SCOPED SUBJECT: a CI failure belongs to a repository, not a
deployed service or a principal/tenant identity -- neither of
`CloudSignalSubject`'s first two kinds fit, so this adapter is what widened
it to a third, `subject_kind="repository"`.

Severity is not derivable from a bare workflow-run object (GitHub Actions
has no native severity field), so this adapter uses one fixed, disclosed
default rather than fabricating a per-run judgment -- a deliberate
simplification for this first slice, not a per-event inference.
"""
from __future__ import annotations

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

# GitHub Actions has no native severity field on a workflow run. Fixed and
# disclosed, not fabricated per-run -- a deliberate simplification for this
# first CI slice (see module docstring).
DEFAULT_SEVERITY = "medium"

_HANDLED_CONCLUSION = "failure"


def _correlation_fingerprint(*, repository: str, workflow_name: str) -> str:
    import hashlib

    # Groups repeated failures of the SAME workflow in the SAME repository
    # into one identity -- a different workflow failing, or the same
    # workflow failing in a different repo, must not collapse together.
    digest = hashlib.sha256(f"{repository}\0{workflow_name}".encode()).hexdigest()[:16]
    return f"fp-ci-{digest}"


def github_workflow_run_to_cloud_signal(
    run: dict,
    *,
    producer_version: str,
) -> CloudSignal | None:
    """Build a `CloudSignal` from a raw GitHub Actions workflow run object.

    Fails closed (returns None) on a missing required field, a `status`
    other than `"completed"`, or a `conclusion` other than `"failure"` --
    see module docstring for why other conclusions aren't handled yet.
    """
    run_id = run.get("id")
    name = run.get("name")
    status = run.get("status")
    conclusion = run.get("conclusion")
    head_sha = run.get("head_sha")
    updated_at = run.get("updated_at")
    repository = run.get("repository") or {}
    repo_full_name = repository.get("full_name")

    if run_id is None or not name or not repo_full_name:
        return None
    if not updated_at or not head_sha:
        return None
    if status != "completed":
        return None
    if conclusion != _HANDLED_CONCLUSION:
        return None

    fingerprint = _correlation_fingerprint(repository=repo_full_name, workflow_name=name)
    source_refs = (f"signal://ci/{repo_full_name}/run/{run_id}",)

    signal = CloudSignal(
        signal_id=f"ci-run-{run_id}",
        source_system=SOURCE_SYSTEM,
        source_kind=SOURCE_KIND,
        subject=CloudSignalSubject(subject_kind="repository", repository=repo_full_name),
        issue_class=ISSUE_CLASS,
        severity=DEFAULT_SEVERITY,
        observed_at=updated_at,
        summary=f'Workflow "{name}" failed on {repo_full_name} (run {run_id}, commit {head_sha[:12]}).',
        evidence=CloudSignalEvidence(source_refs=source_refs),
        correlation=CloudSignalCorrelation(fingerprint=fingerprint),
        provenance=CloudSignalProvenance(
            producer=SOURCE_SYSTEM,
            producer_version=producer_version,
            original_event_id=str(run_id),
        ),
    )
    return CloudSignalShaper().build(signal)
