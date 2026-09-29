"""Tests for the Render deploy-event -> CloudSignal adapter
(BDS-FCO-CSD-v0.1, CSD-07).

Fixtures mirror the real, documented Render webhook "thin" payload shape
(https://render.com/docs/webhooks): `type`, `timestamp`, `data.id`,
`data.serviceId`, `data.serviceName`, `data.status`.
"""
from app.services.render_deploy_adapter import (
    DEFAULT_SEVERITY,
    ISSUE_CLASS,
    SOURCE_KIND,
    SOURCE_SYSTEM,
    render_deploy_event_to_cloud_signal,
)


def _event(**overrides) -> dict:
    defaults = dict(
        type="deploy_ended",
        timestamp="2026-09-29T09:00:00Z",
        data={
            "id": "evt-abc123def456ghi789jk",
            "serviceId": "srv-abc123",
            "serviceName": "neuroforge",
            "status": "failed",
        },
    )
    defaults.update(overrides)
    return defaults


def test_adapter_converts_a_failed_deploy_ended_event():
    signal = render_deploy_event_to_cloud_signal(_event(), producer_version="1.0.0")
    assert signal is not None
    assert signal.subject.subject_kind == "service"
    assert signal.subject.service == "neuroforge"
    assert signal.source_system == SOURCE_SYSTEM == "render"
    assert signal.source_kind == SOURCE_KIND == "deploy_event"
    assert signal.issue_class == ISSUE_CLASS == "deploy_failure"
    assert signal.severity == DEFAULT_SEVERITY == "high"


def test_adapter_fails_closed_on_non_deploy_ended_type():
    for event_type in ("deploy_started", "service_suspended", "service_resumed"):
        assert (
            render_deploy_event_to_cloud_signal(_event(type=event_type), producer_version="1.0.0")
            is None
        )


def test_adapter_fails_closed_on_non_failed_status():
    for status in ("succeeded", "canceled", None):
        data = dict(_event()["data"])
        data["status"] = status
        assert (
            render_deploy_event_to_cloud_signal(_event(data=data), producer_version="1.0.0") is None
        )


def test_adapter_fails_closed_on_missing_service_name():
    data = dict(_event()["data"])
    data["serviceName"] = None
    assert render_deploy_event_to_cloud_signal(_event(data=data), producer_version="1.0.0") is None


def test_adapter_fails_closed_on_missing_event_id():
    data = dict(_event()["data"])
    data["id"] = None
    assert render_deploy_event_to_cloud_signal(_event(data=data), producer_version="1.0.0") is None


def test_adapter_summary_names_service_and_event():
    signal = render_deploy_event_to_cloud_signal(_event(), producer_version="1.0.0")
    assert signal is not None
    assert "neuroforge" in signal.summary
    assert "evt-abc123def456ghi789jk" in signal.summary


def test_adapter_wraps_evidence_in_admissible_signal_scheme():
    signal = render_deploy_event_to_cloud_signal(_event(), producer_version="1.0.0")
    assert signal is not None
    assert signal.evidence.source_refs == (
        "signal://deploy/neuroforge/event/evt-abc123def456ghi789jk",
    )


def test_adapter_carries_no_immutable_hashes():
    # Render's own docs describe this webhook shape as "thin" -- no commit
    # SHA or build detail is available; this adapter must not fabricate one.
    signal = render_deploy_event_to_cloud_signal(_event(), producer_version="1.0.0")
    assert signal is not None
    assert signal.evidence.immutable_hashes == ()


def test_adapter_fingerprint_stable_across_repeated_failures_of_same_service():
    a = render_deploy_event_to_cloud_signal(
        _event(data={**_event()["data"], "id": "evt-a"}), producer_version="1.0.0"
    )
    b = render_deploy_event_to_cloud_signal(
        _event(data={**_event()["data"], "id": "evt-b"}), producer_version="1.0.0"
    )
    assert a is not None and b is not None
    assert a.correlation.fingerprint == b.correlation.fingerprint


def test_adapter_fingerprint_differs_across_services():
    a = render_deploy_event_to_cloud_signal(_event(), producer_version="1.0.0")
    b = render_deploy_event_to_cloud_signal(
        _event(data={**_event()["data"], "serviceId": "srv-other", "serviceName": "rake"}),
        producer_version="1.0.0",
    )
    assert a is not None and b is not None
    assert a.correlation.fingerprint != b.correlation.fingerprint
