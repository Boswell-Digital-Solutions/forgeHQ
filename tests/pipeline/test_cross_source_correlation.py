"""Tests for cross-source correlation (BDS-FCO-CSD-v0.1, CSD-08).

Mechanism only, per Charlie's explicit ruling: no real subject aliases
exist anywhere in this ecosystem yet (nothing maps a GitHub repo to the
Render service it deploys to). These tests prove the merge mechanism works
correctly given a caller-supplied alias registry, and that an empty
registry -- today's real state -- changes nothing about CSD-03's existing
single-source correlation.
"""
from app.services.cloud_signal_contracts import (
    CloudSignal,
    CloudSignalCorrelation,
    CloudSignalEvidence,
    CloudSignalProvenance,
    CloudSignalSubject,
)
from app.services.cloud_signal_correlation import CloudSignalCorrelator, CrossSourceCorrelator


def _ci_signal(signal_id: str, *, repository: str = "org/forgeHQ") -> CloudSignal:
    return CloudSignal(
        signal_id=signal_id,
        source_system="github_actions",
        source_kind="ci_workflow_run",
        subject=CloudSignalSubject(subject_kind="repository", repository=repository),
        issue_class="ci_workflow_failure",
        severity="medium",
        observed_at="2026-09-29T09:00:00Z",
        summary="CI failed.",
        evidence=CloudSignalEvidence(source_refs=(f"signal://ci/{repository}/run/1",)),
        correlation=CloudSignalCorrelation(fingerprint="fp-ci-abc"),
        provenance=CloudSignalProvenance(
            producer="github_actions", producer_version="1.0.0", original_event_id="1"
        ),
    )


def _deploy_signal(signal_id: str, *, service: str = "neuroforge") -> CloudSignal:
    return CloudSignal(
        signal_id=signal_id,
        source_system="render",
        source_kind="deploy_event",
        subject=CloudSignalSubject(service=service),
        issue_class="deploy_failure",
        severity="high",
        observed_at="2026-09-29T09:05:00Z",
        summary="Deploy failed.",
        evidence=CloudSignalEvidence(source_refs=(f"signal://deploy/{service}/event/1",)),
        correlation=CloudSignalCorrelation(fingerprint="fp-deploy-xyz"),
        provenance=CloudSignalProvenance(
            producer="render", producer_version="1.0.0", original_event_id="1"
        ),
    )


def test_empty_registry_leaves_every_group_standalone():
    ci_groups = CloudSignalCorrelator().correlate([_ci_signal("sig-ci-1")])
    deploy_groups = CloudSignalCorrelator().correlate([_deploy_signal("sig-deploy-1")])
    merged = CrossSourceCorrelator().merge(ci_groups + deploy_groups)
    assert len(merged) == 2
    assert {m.canonical_subject_id for m in merged} == {
        "repository:org/forgeHQ",
        "service:neuroforge",
    }


def test_no_registry_argument_behaves_like_empty_registry():
    groups = CloudSignalCorrelator().correlate([_ci_signal("sig-1")])
    merged = CrossSourceCorrelator().merge(groups)
    assert len(merged) == 1
    assert merged[0].canonical_subject_id == "repository:org/forgeHQ"


def test_alias_registry_merges_a_ci_group_and_a_deploy_group():
    ci_groups = CloudSignalCorrelator().correlate([_ci_signal("sig-ci-1")])
    deploy_groups = CloudSignalCorrelator().correlate([_deploy_signal("sig-deploy-1")])
    registry = {
        "repository:org/forgeHQ": "canonical:neuroforge",
        "service:neuroforge": "canonical:neuroforge",
    }
    merged = CrossSourceCorrelator().merge(ci_groups + deploy_groups, alias_registry=registry)
    assert len(merged) == 1
    assert merged[0].canonical_subject_id == "canonical:neuroforge"
    assert set(merged[0].signal_ids) == {"sig-ci-1", "sig-deploy-1"}


def test_merged_group_reports_distinct_source_systems():
    ci_groups = CloudSignalCorrelator().correlate([_ci_signal("sig-ci-1")])
    deploy_groups = CloudSignalCorrelator().correlate([_deploy_signal("sig-deploy-1")])
    registry = {"repository:org/forgeHQ": "canonical:x", "service:neuroforge": "canonical:x"}
    merged = CrossSourceCorrelator().merge(ci_groups + deploy_groups, alias_registry=registry)
    assert merged[0].source_systems == ("github_actions", "render")


def test_merged_group_source_systems_is_single_value_when_nothing_merged():
    groups = CloudSignalCorrelator().correlate([_ci_signal("sig-1")])
    merged = CrossSourceCorrelator().merge(groups)
    assert merged[0].source_systems == ("github_actions",)


def test_alias_registry_does_not_merge_unrelated_subjects():
    ci_groups = CloudSignalCorrelator().correlate([_ci_signal("sig-ci-1", repository="org/other-repo")])
    deploy_groups = CloudSignalCorrelator().correlate([_deploy_signal("sig-deploy-1")])
    registry = {"repository:org/forgeHQ": "canonical:neuroforge", "service:neuroforge": "canonical:neuroforge"}
    merged = CrossSourceCorrelator().merge(ci_groups + deploy_groups, alias_registry=registry)
    # org/other-repo has no alias entry -- stays standalone under its own raw key.
    assert len(merged) == 2
    canonical_ids = {m.canonical_subject_id for m in merged}
    assert canonical_ids == {"repository:org/other-repo", "canonical:neuroforge"}


def test_empty_group_list_produces_no_merged_groups():
    assert CrossSourceCorrelator().merge(()) == ()


def test_all_signals_property_flattens_across_merged_groups():
    ci_groups = CloudSignalCorrelator().correlate([_ci_signal("sig-ci-1")])
    deploy_groups = CloudSignalCorrelator().correlate([_deploy_signal("sig-deploy-1")])
    registry = {"repository:org/forgeHQ": "canonical:x", "service:neuroforge": "canonical:x"}
    merged = CrossSourceCorrelator().merge(ci_groups + deploy_groups, alias_registry=registry)
    assert len(merged[0].all_signals) == 2
