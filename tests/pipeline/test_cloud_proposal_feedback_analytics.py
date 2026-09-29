"""Tests for operator-decision feedback analytics (BDS-FCO-CSD-v0.1, CSD-10).

Report-only: no test here should ever need to assert that this module wrote
to or altered any other module's state, because it has no such path at all.
"""
from app.services.cloud_proposal_feedback_analytics import (
    DecidedProposalRecord,
    compute_decision_rates,
    compute_issue_class_breakdown,
)


def test_rates_are_zero_with_no_records():
    summary = compute_decision_rates([])
    assert summary.total == 0
    assert summary.decided == 0
    assert summary.acceptance_rate == 0.0


def test_undecided_records_are_excluded_from_rates_but_counted_in_total():
    records = [
        DecidedProposalRecord(issue_class="denial_streak", decision=None),
        DecidedProposalRecord(issue_class="denial_streak", decision="approve"),
    ]
    summary = compute_decision_rates(records)
    assert summary.total == 2
    assert summary.decided == 1
    assert summary.approved == 1
    assert summary.acceptance_rate == 1.0


def test_acceptance_rejection_defer_request_evidence_rates_are_computed_correctly():
    records = [
        DecidedProposalRecord(issue_class="denial_streak", decision="approve"),
        DecidedProposalRecord(issue_class="denial_streak", decision="approve"),
        DecidedProposalRecord(issue_class="denial_streak", decision="reject"),
        DecidedProposalRecord(issue_class="denial_streak", decision="defer"),
        DecidedProposalRecord(issue_class="denial_streak", decision="request-evidence"),
    ]
    summary = compute_decision_rates(records)
    assert summary.decided == 5
    assert summary.approved == 2
    assert summary.rejected == 1
    assert summary.deferred == 1
    assert summary.request_evidence == 1
    assert summary.acceptance_rate == 2 / 5
    assert summary.rejection_rate == 1 / 5
    assert summary.defer_rate == 1 / 5
    assert summary.request_evidence_rate == 1 / 5


def test_unknown_decision_string_is_counted_not_silently_dropped():
    records = [
        DecidedProposalRecord(issue_class="denial_streak", decision="approve"),
        DecidedProposalRecord(issue_class="denial_streak", decision="some_future_decision"),
    ]
    summary = compute_decision_rates(records)
    assert summary.decided == 2
    assert summary.unknown_decision == 1
    # The unknown decision still reconciles into `decided` -- rates
    # against the real total, not silently against a shrunk denominator.
    assert summary.acceptance_rate == 1 / 2


def test_issue_class_breakdown_groups_correctly():
    records = [
        DecidedProposalRecord(issue_class="denial_streak", decision="approve"),
        DecidedProposalRecord(issue_class="denial_streak", decision="reject"),
        DecidedProposalRecord(issue_class="ci_workflow_failure", decision="approve"),
    ]
    breakdown = compute_issue_class_breakdown(records)
    assert set(breakdown) == {"denial_streak", "ci_workflow_failure"}
    assert breakdown["denial_streak"].decided == 2
    assert breakdown["denial_streak"].acceptance_rate == 0.5
    assert breakdown["ci_workflow_failure"].decided == 1
    assert breakdown["ci_workflow_failure"].acceptance_rate == 1.0


def test_issue_class_breakdown_empty_input_is_empty_dict():
    assert compute_issue_class_breakdown([]) == {}


def test_module_has_no_write_path_anywhere():
    # This module is report-only by design (source review's own ruling:
    # feedback "may not automatically change governance or approval
    # thresholds") -- there is no function here that could write to
    # another module's state, only pure computation over caller-supplied
    # records.
    import app.services.cloud_proposal_feedback_analytics as module

    assert not hasattr(module, "publish")
    assert not hasattr(module, "healing_publisher")
    assert not hasattr(module, "update_eligibility_gate")
    assert not hasattr(module, "update_thresholds")
