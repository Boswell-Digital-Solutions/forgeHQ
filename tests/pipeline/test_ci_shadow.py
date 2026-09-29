"""Tests for the CI shadow run and its read-only GitHub driver.

No test here touches the network or the real `gh` CLI: the driver's runner
and the shadow run's fetch are always injected.
"""
import json

import pytest

from app.drivers.github_actions_client import GitHubFetchError, fetch_failed_runs
from app.services.ci_shadow import run_ci_shadow


def _run(run_id=1, *, repo="org/repo", name="CI", conclusion="failure", status="completed"):
    return {
        "id": run_id,
        "name": name,
        "status": status,
        "conclusion": conclusion,
        "head_sha": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
        "updated_at": "2026-09-29T08:05:00Z",
        "repository": {"full_name": repo},
    }


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
    assert len(fetch_failed_runs("org/repo", runner=runner)) == 2


def test_driver_issues_one_read_only_gh_api_get():
    runner = _runner_returning({"workflow_runs": []})
    fetch_failed_runs("org/repo", per_page=10, runner=runner)
    assert runner.calls == [
        ["gh", "api", "repos/org/repo/actions/runs?status=failure&per_page=10"]
    ]


@pytest.mark.parametrize("bad", ["", "no-slash", "org/repo; rm -rf /", "org/repo/extra", "-x/y z"])
def test_driver_rejects_invalid_repo_names_before_running_anything(bad):
    runner = _runner_returning({"workflow_runs": []})
    with pytest.raises(GitHubFetchError):
        fetch_failed_runs(bad, runner=runner)
    assert runner.calls == []


@pytest.mark.parametrize("per_page", [0, 101, -1])
def test_driver_rejects_out_of_range_per_page(per_page):
    with pytest.raises(GitHubFetchError):
        fetch_failed_runs("org/repo", per_page=per_page, runner=_runner_returning({}))


@pytest.mark.parametrize("payload", ["not json", json.dumps([1, 2]), json.dumps({"x": 1})])
def test_driver_raises_on_malformed_replies(payload):
    with pytest.raises(GitHubFetchError):
        fetch_failed_runs("org/repo", runner=_runner_returning(payload))


def test_driver_wraps_unexpected_runner_exceptions():
    def boom(argv):
        raise FileNotFoundError("gh")

    with pytest.raises(GitHubFetchError):
        fetch_failed_runs("org/repo", runner=boom)


# --- shadow run ---------------------------------------------------------


def _fetch_from(mapping):
    def fetch(repo, *, per_page):
        value = mapping[repo]
        if isinstance(value, Exception):
            raise value
        return value

    return fetch


def test_shadow_reports_conversion_grouping_and_composition():
    fetch = _fetch_from({"org/repo": [_run(1), _run(2), _run(3, name="Deploy")]})
    report = run_ci_shadow(["org/repo"], producer_version="t", fetch=fetch)
    assert report.runs_fetched == 3
    assert report.signals_converted == 3
    # Two failures of "CI" collapse into one group; "Deploy" is its own.
    assert len(report.groups) == 2
    assert report.eligible == 2
    assert report.composed == 2


def test_shadow_counts_runs_the_adapter_rejects():
    fetch = _fetch_from({"org/repo": [_run(1), _run(2, conclusion="startup_failure")]})
    report = run_ci_shadow(["org/repo"], producer_version="t", fetch=fetch)
    assert report.runs_fetched == 2
    assert report.signals_converted == 1
    assert report.signals_rejected == 1


def test_shadow_one_failing_repo_does_not_hide_the_others():
    fetch = _fetch_from(
        {
            "org/good": [_run(1, repo="org/good")],
            "org/bad": GitHubFetchError("HTTP 404"),
        }
    )
    report = run_ci_shadow(["org/good", "org/bad"], producer_version="t", fetch=fetch)
    assert report.signals_converted == 1
    assert report.errors == {"org/bad": "HTTP 404"}


def test_shadow_with_no_runs_reports_zeroes():
    report = run_ci_shadow(["org/repo"], producer_version="t", fetch=_fetch_from({"org/repo": []}))
    assert report.runs_fetched == 0
    assert report.groups == []


def test_shadow_publishes_nothing_and_says_so():
    fetch = _fetch_from({"org/repo": [_run(1)]})
    payload = run_ci_shadow(["org/repo"], producer_version="t", fetch=fetch).to_dict()
    assert payload["published"] == 0
    assert "eligible_ignoring_suppression" in payload  # the limit is in the key name


def test_shadow_modules_have_no_publish_path():
    import app.services.ci_shadow as shadow

    assert not hasattr(shadow, "publish_healing_proposal")
    assert not hasattr(shadow, "healing_publisher")


# --- recency window -----------------------------------------------------

from datetime import datetime, timezone

_NOW = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)


def _aged(run_id, updated_at):
    run = _run(run_id)
    run["updated_at"] = updated_at
    return run


def test_shadow_skips_and_counts_runs_older_than_the_window():
    fetch = _fetch_from(
        {
            "org/repo": [
                _aged(1, "2026-09-28T00:00:00Z"),  # 1.5 days old: kept
                _aged(2, "2026-08-01T00:00:00Z"),  # ~59 days old: stale
            ]
        }
    )
    report = run_ci_shadow(["org/repo"], producer_version="t", fetch=fetch, max_age_days=14, now=_NOW)
    assert report.runs_fetched == 2
    assert report.runs_stale_skipped == 1
    assert report.signals_converted == 1


def test_shadow_window_can_be_disabled():
    fetch = _fetch_from({"org/repo": [_aged(1, "2020-01-01T00:00:00Z")]})
    report = run_ci_shadow(["org/repo"], producer_version="t", fetch=fetch, max_age_days=None, now=_NOW)
    assert report.runs_stale_skipped == 0
    assert report.signals_converted == 1


@pytest.mark.parametrize("bad", [None, "", "not a date", "2026-09-28T00:00:00"])
def test_shadow_treats_unknown_age_as_stale(bad):
    run = _run(1)
    run["updated_at"] = bad
    report = run_ci_shadow(
        ["org/repo"], producer_version="t", fetch=_fetch_from({"org/repo": [run]}), max_age_days=14, now=_NOW
    )
    assert report.runs_stale_skipped == 1
    assert report.signals_converted == 0
