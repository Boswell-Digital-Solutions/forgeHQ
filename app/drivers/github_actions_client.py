"""github_actions_client -- read failed workflow runs via the `gh` CLI.

READ-ONLY, one GET per repository: `repos/{owner}/{repo}/actions/runs`
filtered to `status=failure`. It uses the operator's own `gh` login (the
same one used for every other GitHub call on this machine), so it needs no
new secret and opens no inbound port. forgeHQ never reads or stores the
token; `gh` handles authentication.

The `gh` invocation is injectable so tests never touch the network or the
real CLI. Stdlib-only, like the other forgeHQ drivers.
"""
from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Callable

_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class GitHubFetchError(RuntimeError):
    """Raised for an invalid repo name, a failed `gh` call, or an
    unparseable reply. Callers report it; nothing is guessed."""


def _default_runner(argv: list[str]) -> str:
    completed = subprocess.run(  # noqa: S603 - argv is a fixed list, repo is validated
        argv, capture_output=True, text=True, timeout=30, check=False
    )
    if completed.returncode != 0:
        detail = (completed.stderr or "").strip().splitlines()[-1:] or ["gh exited non-zero"]
        raise GitHubFetchError(detail[0])
    return completed.stdout


def fetch_failed_runs(
    repo: str,
    *,
    per_page: int = 30,
    runner: Callable[[list[str]], str] | None = None,
) -> list[dict]:
    """Return the most recent workflow runs whose conclusion is `failure`."""
    if not _REPO_RE.match(repo):
        raise GitHubFetchError(f"invalid repository name: {repo!r}")
    if not 1 <= per_page <= 100:
        raise GitHubFetchError("per_page must be between 1 and 100")

    argv = ["gh", "api", f"repos/{repo}/actions/runs?status=failure&per_page={per_page}"]
    try:
        stdout = (runner or _default_runner)(argv)
    except GitHubFetchError:
        raise
    except Exception as exc:  # timeout, missing gh binary, ...
        raise GitHubFetchError(f"{type(exc).__name__}: {exc}") from exc

    try:
        payload = json.loads(stdout)
    except ValueError as exc:
        raise GitHubFetchError("gh returned non-JSON output") from exc
    runs = payload.get("workflow_runs") if isinstance(payload, dict) else None
    if not isinstance(runs, list):
        raise GitHubFetchError("reply has no workflow_runs list")
    return [run for run in runs if isinstance(run, dict)]
