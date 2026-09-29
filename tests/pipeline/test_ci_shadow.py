"""Tests for the CI shadow run and its read-only GitHub driver.

No test touches the network or the real `gh` CLI: the driver's runner and the
shadow run's fetch are always injected. Fixtures reproduce shapes seen on
real runs (2026-09-29), including `startup_failure` runs with an empty name.
"""
import json
from datetime import datetime, timezone

import pytest

from app.drivers.github_actions_client import GitHubFetchError, fetch_recent_runs
from app.services.ci_shadow import run_ci_shadow

_NOW = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)


def _run(
    run_id=1,
    *,
    repo="org/repo",
    name="CI",
    branch="main",
    conclusion="failure",
    status="completed",
    created="2026-09-28T10:00:00Z",
    updated=None,
):
    return {
        "id": run_id,
        "name": name,
        "head_branch": branch,
        "status": status,
        "conclusion": conclusion,
        "head_sha": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
        "created_at": created,
        "updated_at": updated or created,
        "repository": {"full_name": repo},
    }


def _startup(run_id=1, *, repo="org/repo", branch="main", created="2026-09-28T10:00:00Z"):
    # Real shape: empty name, placeholder path.
    run = _run(run_id, repo=repo, name="", branch=branch, conclusion="startup_failure", created=created)
    run["path"] = "BuildFailed"
    return run


def _ok(run_id=99, *, name="CI", branch="main", created="2026-09-28T20:00:00Z"):
    return _run(run_id, name=name, branch=branch, conclusion="success", created=created)


def _fetch_from(mapping):
    def fetch(repo, *, per_page):
        value = mapping[repo]
        if isinstance(value, Exception):
            raise value
        return value

    return fetch


def _shadow(runs, **kw):
    kw.setdefault("now", _NOW)
    return run_ci_shadow(["org/repo"], producer_version="t", fetch=_fetch_from({"org/repo": runs}), **kw)


# --- driver -------------------------------------------------------------


def _runner_returning(payload):
    calls = []

    def runner(argv):
        calls.append(argv)
        return payload if isinstance(payload, str) else json.dumps(payload)

    runner.calls = calls
    return runner


def test_driver_returns_the_workflow_runs_list():
    runner = _runner_returning({"workflow_runs": [_run(1), _run(2)]})
    assert len(fetch_recent_runs("org/repo", runner=runner)) == 2


def test_driver_issues_one_read_only_gh_api_get_with_no_conclusion_filter():
    runner = _runner_returning({"workflow_runs": []})
    fetch_recent_runs("org/repo", per_page=10, runner=runner)
    # No status filter: recovery needs the successes and startup_failure is
    # not returned by a status=failure filter.
    assert runner.calls == [["gh", "api", "repos/org/repo/actions/runs?per_page=10"]]


@pytest.mark.parametrize("bad", ["", "no-slash", "org/repo; rm -rf /", "org/repo/extra", "-x/y z"])
def test_driver_rejects_invalid_repo_names_before_running_anything(bad):
    runner = _runner_returning({"workflow_runs": []})
    with pytest.raises(GitHubFetchError):
        fetch_recent_runs(bad, runner=runner)
    assert runner.calls == []


@pytest.mark.parametrize("per_page", [0, 101, -1])
def test_driver_rejects_out_of_range_per_page(per_page):
    with pytest.raises(GitHubFetchError):
        fetch_recent_runs("org/repo", per_page=per_page, runner=_runner_returning({}))


@pytest.mark.parametrize("payload", ["not json", json.dumps([1, 2]), json.dumps({"x": 1})])
def test_driver_raises_on_malformed_replies(payload):
    with pytest.raises(GitHubFetchError):
        fetch_recent_runs("org/repo", runner=_runner_returning(payload))


def test_driver_wraps_unexpected_runner_exceptions():
    def boom(argv):
        raise FileNotFoundError("gh")

    with pytest.raises(GitHubFetchError):
        fetch_recent_runs("org/repo", runner=boom)


# --- shadow: basics -----------------------------------------------------


def test_shadow_groups_repeated_failures_of_one_workflow_and_branch():
    report = _shadow([_run(1), _run(2), _run(3, name="Deploy")])
    assert report.candidate_runs == 3
    assert len(report.groups) == 2
    assert report.eligible == 2 and report.composed == 2


def test_shadow_only_counts_failures_as_candidates():
    report = _shadow([_run(1), _ok(2), _run(3, conclusion="cancelled"), _run(4, status="in_progress", conclusion=None)])
    assert report.runs_fetched == 4
    assert report.candidate_runs == 1


def test_shadow_one_failing_repo_does_not_hide_the_others():
    fetch = _fetch_from({"org/good": [_run(1, repo="org/good")], "org/bad": GitHubFetchError("HTTP 404")})
    report = run_ci_shadow(["org/good", "org/bad"], producer_version="t", fetch=fetch, now=_NOW)
    assert report.signals_converted == 1
    assert report.errors == {"org/bad": "HTTP 404"}


def test_shadow_publishes_nothing_and_says_so():
    payload = _shadow([_run(1)]).to_dict()
    assert payload["published"] == 0
    assert "eligible_ignoring_suppression" in payload  # the limit is in the key name


def test_shadow_module_has_no_publish_path():
    import app.services.ci_shadow as shadow

    assert not hasattr(shadow, "publish_healing_proposal")
    assert not hasattr(shadow, "healing_publisher")


# --- shadow: recency window --------------------------------------------


def test_shadow_skips_and_counts_failures_older_than_the_window():
    report = _shadow([_run(1, created="2026-09-28T00:00:00Z"), _run(2, created="2026-08-01T00:00:00Z")])
    assert report.runs_stale_skipped == 1
    assert report.signals_converted == 1


def test_shadow_window_can_be_disabled():
    report = _shadow([_run(1, created="2020-01-01T00:00:00Z")], max_age_days=None)
    assert report.runs_stale_skipped == 0
    assert report.signals_converted == 1


@pytest.mark.parametrize("field", ["created_at", "updated_at"])
@pytest.mark.parametrize("bad", [None, "", "not a date", "2026-09-28T00:00:00"])
def test_shadow_treats_unknown_timestamps_as_stale(field, bad):
    run = _run(1)
    run[field] = bad
    report = _shadow([run])
    assert report.runs_stale_skipped == 1
    assert report.signals_converted == 0


# --- shadow: recovery ---------------------------------------------------


def test_a_later_success_on_the_same_workflow_and_branch_clears_the_failure():
    report = _shadow([_run(1, created="2026-09-28T10:00:00Z"), _ok(2, created="2026-09-28T20:00:00Z")])
    assert report.runs_recovered_skipped == 1
    assert report.groups == []


def test_an_earlier_success_does_not_clear_a_later_failure():
    report = _shadow([_ok(1, created="2026-09-28T01:00:00Z"), _run(2, created="2026-09-28T10:00:00Z")])
    assert report.runs_recovered_skipped == 0
    assert len(report.groups) == 1


def test_a_green_main_does_not_clear_a_red_pr_branch():
    # The real case: the failure was on a PR branch, later runs were on main.
    report = _shadow([_run(1, branch="pr-branch"), _ok(2, branch="main")])
    assert report.runs_recovered_skipped == 0
    assert len(report.groups) == 1


def test_a_green_other_workflow_does_not_clear_a_red_workflow():
    report = _shadow([_run(1, name="CI"), _ok(2, name="Lint")])
    assert report.runs_recovered_skipped == 0


def test_failures_on_different_branches_are_separate_groups():
    report = _shadow([_run(1, branch="main"), _run(2, branch="feature")])
    assert len(report.groups) == 2


# --- shadow: startup_failure -------------------------------------------


def test_startup_failures_with_empty_names_are_converted_not_rejected():
    report = _shadow([_startup(1), _startup(2)])
    assert report.signals_converted == 2
    assert report.signals_rejected == 0


def test_startup_failures_across_branches_form_one_repo_wide_group():
    report = _shadow([_startup(1, branch="main"), _startup(2, branch="feature-a"), _startup(3, branch="feature-b")])
    assert len(report.groups) == 1
    group = report.groups[0]
    assert group.issue_class == "ci_startup_failure"
    assert group.signal_count == 3
    assert group.composed is True


def test_any_later_success_in_the_repo_clears_startup_failures():
    report = _shadow(
        [_startup(1, created="2026-09-28T10:00:00Z"), _ok(2, name="Anything", branch="other", created="2026-09-28T11:00:00Z")]
    )
    assert report.runs_recovered_skipped == 1
    assert report.groups == []


def test_a_success_before_the_startup_failures_does_not_clear_them():
    report = _shadow([_ok(1, created="2026-09-28T01:00:00Z"), _startup(2, created="2026-09-28T10:00:00Z")])
    assert report.runs_recovered_skipped == 0
    assert len(report.groups) == 1


def test_code_failures_and_startup_failures_are_separate_groups():
    report = _shadow([_run(1), _startup(2)])
    assert {g.issue_class for g in report.groups} == {"ci_workflow_failure", "ci_startup_failure"}
