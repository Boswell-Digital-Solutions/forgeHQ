"""Tests for the read-only store reader, suppression sets, and their use in the
CI shadow run. No test touches the network: the reader's GET is injected.
"""
from datetime import datetime, timezone

import pytest

from app.drivers.proposal_store_reader import (
    LIST_LIMIT,
    ProposalStoreError,
    StoredCloudProposal,
    StoreSnapshot,
    read_cloud_proposals,
)
from app.services.ci_shadow import load_suppression, run_ci_shadow
from app.services.proposal_suppression import build_suppression_sets

_NOW = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)


def _row(
    pid, status, *, fingerprint="fp-a", decided_at=None, schema="cloud.proposal.v1"
):
    payload = {"issueClass": "ci_workflow_failure"}
    if fingerprint is not None:
        payload["correlationFingerprint"] = fingerprint
    return {
        "proposal_id": pid,
        "status": status,
        "created_at": "2026-09-01T00:00:00+00:00",
        "decision": {"at": decided_at} if decided_at else None,
        "envelope": {"schema_version": schema, "payload": payload},
    }


def _get_returning(by_status):
    calls = []

    def get(url, timeout):
        calls.append(url)
        for status, items in by_status.items():
            if f"status={status}&" in url:
                return {"items": items, "count": len(items)}
        return {"items": [], "count": 0}

    get.calls = calls
    return get


# --- reader -------------------------------------------------------------


def test_reader_issues_only_get_requests_one_per_status():
    get = _get_returning({})
    read_cloud_proposals(get=get)
    assert len(get.calls) == 4
    assert all("/api/v1/healing-proposals?" in u for u in get.calls)


def test_reader_parses_fingerprint_and_decision_time():
    get = _get_returning(
        {"accepted": [_row("p1", "accepted", decided_at="2026-09-28T00:00:00+00:00")]}
    )
    (p,) = read_cloud_proposals(get=get).proposals
    assert p.fingerprint == "fp-a"
    assert p.decided_at == "2026-09-28T00:00:00+00:00"


def test_reader_skips_other_schemas():
    get = _get_returning(
        {"pending": [_row("p1", "pending", schema="healing.code_fix.v1")]}
    )
    assert read_cloud_proposals(get=get).proposals == ()


def test_reader_reports_a_full_page_as_truncated():
    items = [_row(f"p{i}", "pending") for i in range(LIST_LIMIT)]
    snap = read_cloud_proposals(get=_get_returning({"pending": items}))
    assert snap.truncated_statuses == ("pending",)


def test_reader_raises_on_transport_failure_and_bad_shape():
    def boom(url, timeout):
        raise OSError("connection refused")

    with pytest.raises(ProposalStoreError):
        read_cloud_proposals(get=boom)
    with pytest.raises(ProposalStoreError):
        read_cloud_proposals(get=lambda url, timeout: {"nope": 1})


def test_reader_module_cannot_issue_a_write(monkeypatch):
    import io
    import app.drivers.proposal_store_reader as reader

    calls = []

    def read(request, timeout):
        calls.append(request)
        return io.BytesIO(b'{"items": []}')

    monkeypatch.setattr(reader.urllib.request, "urlopen", read)
    reader.read_cloud_proposals()
    assert calls
    assert all(
        request.get_method() == "GET" and request.data is None for request in calls
    )


# --- suppression sets ---------------------------------------------------


def _snap(*proposals):
    return StoreSnapshot(proposals=tuple(proposals), truncated_statuses=())


def _sp(status, fp="fp-a", decided_at=None):
    return StoredCloudProposal("p", status, fp, "ci_workflow_failure", decided_at, None)


@pytest.mark.parametrize("status", ["pending", "ingested"])
def test_open_statuses_go_in_the_open_set(status):
    sets = build_suppression_sets(_snap(_sp(status)), now=_NOW)
    assert sets.open_fingerprints == {"fp-a"}
    assert sets.cooling_down_fingerprints == frozenset()


@pytest.mark.parametrize("status", ["accepted", "rejected"])
def test_a_recent_decision_cools_the_fingerprint_down(status):
    sets = build_suppression_sets(
        _snap(_sp(status, decided_at="2026-09-25T00:00:00+00:00")), now=_NOW
    )
    assert sets.cooling_down_fingerprints == {"fp-a"}


def test_an_old_decision_no_longer_suppresses():
    sets = build_suppression_sets(
        _snap(_sp("rejected", decided_at="2026-08-01T00:00:00+00:00")), now=_NOW
    )
    assert sets.cooling_down_fingerprints == frozenset()


@pytest.mark.parametrize("bad", [None, "", "not a date", "2026-09-25T00:00:00"])
def test_a_decision_with_unknown_time_is_treated_as_still_cooling(bad):
    sets = build_suppression_sets(_snap(_sp("rejected", decided_at=bad)), now=_NOW)
    assert sets.cooling_down_fingerprints == {"fp-a"}


def test_proposals_without_a_fingerprint_are_counted_not_used():
    sets = build_suppression_sets(
        _snap(_sp("pending", fp=None), _sp("pending", fp="fp-b")), now=_NOW
    )
    assert sets.open_fingerprints == {"fp-b"}
    assert sets.rows_without_fingerprint == 1
    assert sets.rows_read == 2


# --- shadow integration -------------------------------------------------


def _failing_run(run_id, name="CI"):
    return {
        "id": run_id,
        "name": name,
        "head_branch": "main",
        "status": "completed",
        "conclusion": "failure",
        "created_at": "2026-09-28T10:00:00Z",
        "updated_at": "2026-09-28T10:00:00Z",
        "head_sha": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
        "repository": {"full_name": "org/repo"},
    }


def _shadow(suppression=None, status="not_read"):
    return run_ci_shadow(
        ["org/repo"],
        producer_version="t",
        now=_NOW,
        fetch=lambda repo, per_page: [_failing_run(1)],
        suppression=suppression,
        suppression_status=status,
    )


def _the_fingerprint():
    return _shadow().groups[0].fingerprint


def test_without_a_read_would_publish_is_null_not_a_guess():
    payload = _shadow().to_dict()
    assert payload["would_publish"] is None
    assert payload["suppression"]["status"] == "not_read"


def test_an_open_proposal_makes_the_group_a_duplicate():
    fp = _the_fingerprint()
    sets = build_suppression_sets(_snap(_sp("ingested", fp=fp)), now=_NOW)
    payload = _shadow(sets, "ok").to_dict()
    assert payload["eligible_ignoring_suppression"] == 1
    assert payload["duplicate_groups"] == 1
    assert payload["would_publish"] == 0
    assert payload["composed_candidates"] == 0


def test_a_recently_rejected_proposal_suppresses_the_group():
    fp = _the_fingerprint()
    sets = build_suppression_sets(
        _snap(_sp("rejected", fp=fp, decided_at="2026-09-28T00:00:00+00:00")), now=_NOW
    )
    payload = _shadow(sets, "ok").to_dict()
    assert payload["suppressed_groups"] == 1
    assert payload["would_publish"] == 0


def test_an_unrelated_fingerprint_does_not_suppress():
    sets = build_suppression_sets(_snap(_sp("ingested", fp="fp-unrelated")), now=_NOW)
    payload = _shadow(sets, "ok").to_dict()
    assert payload["would_publish"] == 1
    assert payload["composed_candidates"] == 1


def test_load_suppression_reports_unavailable_instead_of_guessing():
    def boom(**kw):
        raise ProposalStoreError("URLError: refused")

    sets, status = load_suppression(base_url="http://x", read=boom)
    assert sets is None
    assert status == "unavailable: URLError: refused"


def test_load_suppression_ok_path():
    sets, status = load_suppression(
        base_url="http://x", read=lambda **kw: _snap(_sp("pending"))
    )
    assert status == "ok" and sets.open_fingerprints == {"fp-a"}


# --- fingerprint carried into the envelope ------------------------------


def test_envelope_carries_the_fingerprint_only_when_set():
    from app.services.cloud_proposal_shaper import (
        CloudProposalInput,
        CloudProposalShaper,
        CloudSubject,
        to_cloud_proposal_envelope,
    )

    def envelope(**kw):
        proposal = CloudProposalShaper().shape(
            CloudProposalInput(
                subject=CloudSubject(service="s"),
                title="t",
                issue_class="c",
                problem_statement="p",
                evidence_summary="e",
                scope_summary="s",
                recommended_action="r",
                expected_gain="g",
                risk_summary="k",
                **kw,
            )
        )
        return to_cloud_proposal_envelope(proposal)

    assert (
        "correlationFingerprint" not in envelope()["payload"]
    )  # unchanged for hand-composed
    assert (
        envelope(correlation_fingerprint="fp-x")["payload"]["correlationFingerprint"]
        == "fp-x"
    )


def test_translator_carries_the_candidates_fingerprint_on_both_paths():
    from app.services.cloud_proposal_ai_composer import (
        DeterministicStubCompositionGenerator,
    )
    from app.services.cloud_proposal_candidate_translator import (
        candidate_to_proposal_input,
    )
    from app.services.cloud_signal_contracts import (
        CloudProposalCandidateShaper,
        CloudSignalSubject,
    )

    def candidate(action_class):
        return CloudProposalCandidateShaper().build(
            subject=CloudSignalSubject(
                subject_kind="repository", repository="org/repo"
            ),
            issue_class="ci_workflow_failure",
            severity="medium",
            confidence_band="high",
            signal_ids=("s1",),
            correlation_fingerprint="fp-carried",
            facts=("2 failures.",),
            recommended_action_class=action_class,
        )

    templated = candidate_to_proposal_input(
        candidate("investigate_ci_workflow_failure")
    )
    assert templated is not None and templated.correlation_fingerprint == "fp-carried"
    ai = candidate_to_proposal_input(
        candidate("some_unmapped"), ai_generator=DeterministicStubCompositionGenerator()
    )
    assert ai is not None and ai.correlation_fingerprint == "fp-carried"
