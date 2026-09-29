"""Tests for the CI publisher, proposal identity, and the readability caps.

Nothing here touches the network: the publish callable is always injected.
"""
from datetime import datetime, timezone

import pytest

from app.drivers.proposal_store_reader import StoredCloudProposal, StoreSnapshot
from app.services.ci_publish import (
    PublishRefused,
    execute_publications,
    plan_publications,
)
from app.services.ci_shadow import run_ci_shadow
from app.services.cloud_proposal_shaper import (
    CloudProposalInput,
    CloudProposalShaper,
    CloudSubject,
    to_cloud_proposal_envelope,
)
from app.services.proposal_suppression import build_suppression_sets

_NOW = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)


def _run(run_id, *, name="CI", branch="main", conclusion="failure", repo="org/repo"):
    return {
        "id": run_id, "name": name, "head_branch": branch, "status": "completed",
        "conclusion": conclusion, "created_at": "2026-09-28T10:00:00Z",
        "updated_at": "2026-09-28T10:00:00Z",
        "head_sha": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
        "repository": {"full_name": repo},
    }


def _snap(*proposals, truncated=()):
    return StoreSnapshot(proposals=tuple(proposals), truncated_statuses=tuple(truncated))


def _stored(status, fp, decided_at=None):
    return StoredCloudProposal("p-" + fp, status, fp, "ci_workflow_failure", decided_at, None)


def _report(runs, snapshot=None, status="ok"):
    sets = build_suppression_sets(snapshot, now=_NOW) if snapshot is not None else None
    return run_ci_shadow(
        ["org/repo"], producer_version="t", now=_NOW,
        fetch=lambda repo, per_page: runs, suppression=sets,
        suppression_status=status if snapshot is not None else "unavailable: refused",
    )


# --- identity -----------------------------------------------------------


def _input(**kw):
    return CloudProposalInput(
        subject=CloudSubject(subject_kind="repository", repository="org/repo"),
        title=kw.pop("title", "T"), issue_class="ci_workflow_failure",
        problem_statement="p", evidence_summary="e", scope_summary="s",
        recommended_action="r", expected_gain="g", risk_summary="k", **kw,
    )


def _id(**kw):
    return CloudProposalShaper().shape(_input(**kw)).event_id


def test_a_fingerprinted_proposals_id_ignores_the_title():
    assert _id(title="one", correlation_fingerprint="fp") == _id(title="two", correlation_fingerprint="fp")


def test_a_hand_composed_proposals_id_still_follows_the_title():
    assert _id(title="one") != _id(title="two")


def test_generation_makes_a_recurrence_a_new_row():
    assert _id(correlation_fingerprint="fp", generation=0) != _id(correlation_fingerprint="fp", generation=1)
    assert _id(correlation_fingerprint="fp", generation=1) == _id(correlation_fingerprint="fp", generation=1)


def test_different_fingerprints_get_different_ids():
    assert _id(correlation_fingerprint="a") != _id(correlation_fingerprint="b")


def test_envelope_records_the_generation_only_with_a_fingerprint():
    with_fp = to_cloud_proposal_envelope(
        CloudProposalShaper().shape(_input(correlation_fingerprint="fp", generation=2))
    )
    assert with_fp["payload"]["proposalGeneration"] == 2
    without = to_cloud_proposal_envelope(CloudProposalShaper().shape(_input()))
    assert "proposalGeneration" not in without["payload"]


# --- planning: refusals -------------------------------------------------


def test_refuses_when_the_suppression_read_failed():
    with pytest.raises(PublishRefused, match="cannot show"):
        plan_publications(_report([_run(1)], snapshot=None))


def test_refuses_when_a_store_listing_was_truncated():
    with pytest.raises(PublishRefused, match="truncated"):
        plan_publications(_report([_run(1)], snapshot=_snap(truncated=("pending",))))


def test_refuses_a_nonsensical_limit():
    with pytest.raises(PublishRefused):
        plan_publications(_report([_run(1)], snapshot=_snap()), max_publish=0)


# --- planning: content --------------------------------------------------


def test_plans_one_publication_per_eligible_group():
    plan = plan_publications(_report([_run(1), _run(2, name="Lint")], snapshot=_snap()))
    assert len(plan.items) == 2
    assert all(i.envelope["schema_version"] == "cloud.proposal.v1" for i in plan.items)
    assert all(i.envelope["payload"]["correlationFingerprint"] == i.fingerprint for i in plan.items)


def test_an_open_proposal_for_the_fingerprint_means_nothing_is_planned():
    fp = _report([_run(1)], snapshot=_snap()).groups[0].fingerprint
    plan = plan_publications(_report([_run(1)], snapshot=_snap(_stored("ingested", fp))))
    assert plan.items == []


def test_a_recurrence_after_the_cooldown_takes_the_next_generation():
    fp = _report([_run(1)], snapshot=_snap()).groups[0].fingerprint
    old = _stored("rejected", fp, decided_at="2026-08-01T00:00:00+00:00")  # long past the cooldown
    plan = plan_publications(_report([_run(1)], snapshot=_snap(old)))
    assert [i.generation for i in plan.items] == [1]


def test_the_limit_is_enforced_and_the_remainder_is_reported():
    runs = [_run(i, name=f"W{i}") for i in range(1, 6)]
    plan = plan_publications(_report(runs, snapshot=_snap()), max_publish=2)
    assert len(plan.items) == 2
    assert plan.not_published_over_limit == 3


# --- execution ----------------------------------------------------------


def test_without_confirm_nothing_is_sent():
    calls = []
    plan = plan_publications(_report([_run(1)], snapshot=_snap()))
    results = execute_publications(plan, confirm=False, publish=lambda *a, **k: calls.append(1))
    assert results == [] and calls == []


def test_with_confirm_each_item_is_sent_once():
    sent = []

    def publish(envelope, dataforge_url):
        sent.append(envelope["event_id"])
        return {"proposal_id": envelope["event_id"], "status": "pending"}

    plan = plan_publications(_report([_run(1), _run(2, name="Lint")], snapshot=_snap()))
    results = execute_publications(plan, confirm=True, publish=publish)
    assert sent == [i.proposal_id for i in plan.items]
    assert [r["outcome"] for r in results] == ["stored", "stored"]


def test_a_failed_send_is_reported_and_does_not_stop_the_rest():
    def publish(envelope, dataforge_url):
        if envelope["event_id"] == first_id:
            raise OSError("connection refused")
        return {"status": "pending"}

    plan = plan_publications(_report([_run(1), _run(2, name="Lint")], snapshot=_snap()))
    first_id = plan.items[0].proposal_id
    results = execute_publications(plan, confirm=True, publish=publish)
    assert results[0]["outcome"] == "error" and "refused" in results[0]["detail"]
    assert results[1]["outcome"] == "stored"


def test_publisher_never_passes_an_ai_generator():
    import ast

    import app.services.ci_publish as module

    calls = [
        n for n in ast.walk(ast.parse(open(module.__file__).read()))
        if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "candidate_to_proposal_input"
    ]
    assert calls, "expected the planner to call the translator"
    assert all("ai_generator" not in {k.arg for k in c.keywords} for c in calls)


# --- readability caps ---------------------------------------------------


def _many(n):
    return [_run(i) for i in range(1, n + 1)]


def test_a_large_group_yields_a_short_readable_proposal():
    plan = plan_publications(_report(_many(100), snapshot=_snap()))
    payload = plan.items[0].envelope["payload"]
    assert plan.items[0].signal_count == 100
    assert len(payload["problemStatement"]) < 1500  # was ~12,000 uncapped
    assert len(payload["evidenceSummary"]) < 400  # was ~2,000 uncapped
    assert "100 correlated signal(s)" in payload["problemStatement"]
    assert "and 95 more" in payload["evidenceSummary"]


def test_a_small_group_is_listed_in_full():
    payload = plan_publications(_report(_many(3), snapshot=_snap())).items[0].envelope["payload"]
    assert "more" not in payload["evidenceSummary"]
