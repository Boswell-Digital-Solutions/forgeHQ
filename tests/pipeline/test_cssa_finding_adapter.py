"""Tests for the CSSA finding -> CloudSignal adapter (BDS-FCO-CSD-v0.1, CSD-02).

Fixtures mirror the real `cloud_security.finding.v1` shape defined by
Forge-Agents' `app/security/contracts.py` (`CloudSecurityFinding`), verified
directly against that file, not invented.
"""
from app.services.cssa_finding_adapter import (
    SOURCE_KIND,
    SOURCE_SYSTEM,
    cssa_finding_to_cloud_signal,
    shadow_convert,
)


def _finding(**overrides) -> dict:
    defaults = dict(
        schema_version="cloud_security.finding.v1",
        finding_id="finding-001",
        detector="deny_streak",
        severity="S1",
        scope={
            "tenant_id": "tenant-abc",
            "principal_id": None,
            "executor_id": None,
            "app_id": None,
            "cloud_service": "neuroforge",
        },
        window={"from": "2026-09-29T06:00:00Z", "to": "2026-09-29T07:00:00Z"},
        evidence_refs=("decision-001", "decision-002"),
        metrics={"observed": 12.0, "baseline": 2.0, "threshold": 5.0},
        reason_codes=("POLICY_DENY",),
        summary="Denial streak exceeded threshold on the NeuroForge route.",
        emitted_at="2026-09-29T07:00:05Z",
        expires_at="2026-09-29T13:00:05Z",
        finding_hash="sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )
    defaults.update(overrides)
    return defaults


def test_adapter_converts_valid_finding_to_signal():
    signal = cssa_finding_to_cloud_signal(_finding(), producer_version="1.0.0")
    assert signal is not None
    assert signal.subject.service == "neuroforge"
    assert signal.source_system == SOURCE_SYSTEM == "forgesentinel"
    assert signal.source_kind == SOURCE_KIND == "cssa_finding"
    assert signal.issue_class == "deny_streak"


def test_adapter_maps_s0_to_critical():
    signal = cssa_finding_to_cloud_signal(_finding(severity="S0"), producer_version="1.0.0")
    assert signal is not None
    assert signal.severity == "critical"


def test_adapter_maps_s4_to_info():
    signal = cssa_finding_to_cloud_signal(_finding(severity="S4"), producer_version="1.0.0")
    assert signal is not None
    assert signal.severity == "info"


def test_adapter_fails_closed_on_unknown_severity():
    assert cssa_finding_to_cloud_signal(_finding(severity="S99"), producer_version="1.0.0") is None


def test_adapter_fails_closed_on_missing_cloud_service():
    finding = _finding(scope={"tenant_id": "tenant-abc", "cloud_service": None})
    assert cssa_finding_to_cloud_signal(finding, producer_version="1.0.0") is None


def test_adapter_fails_closed_on_missing_finding_id():
    assert cssa_finding_to_cloud_signal(_finding(finding_id=None), producer_version="1.0.0") is None


def test_adapter_fails_closed_on_missing_finding_hash():
    assert cssa_finding_to_cloud_signal(_finding(finding_hash=None), producer_version="1.0.0") is None


def test_adapter_wraps_evidence_refs_in_admissible_signal_scheme():
    signal = cssa_finding_to_cloud_signal(_finding(), producer_version="1.0.0")
    assert signal is not None
    assert signal.evidence.source_refs == (
        "signal://cssa/finding/finding-001/decision-001",
        "signal://cssa/finding/finding-001/decision-002",
    )


def test_adapter_carries_finding_hash_as_immutable_evidence():
    signal = cssa_finding_to_cloud_signal(_finding(), producer_version="1.0.0")
    assert signal is not None
    assert signal.evidence.immutable_hashes == (
        "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )


def test_adapter_fingerprint_is_stable_across_repeated_findings_same_incident():
    a = cssa_finding_to_cloud_signal(_finding(finding_id="finding-001"), producer_version="1.0.0")
    b = cssa_finding_to_cloud_signal(_finding(finding_id="finding-002"), producer_version="1.0.0")
    assert a is not None and b is not None
    # Same detector + service + tenant -> same correlation identity, even
    # though these are two distinct findings (repeated observations of one
    # incident should be group-able by a later correlator, CSD-03).
    assert a.correlation.fingerprint == b.correlation.fingerprint


def test_adapter_fingerprint_differs_across_services():
    a = cssa_finding_to_cloud_signal(_finding(), producer_version="1.0.0")
    b = cssa_finding_to_cloud_signal(
        _finding(scope={"tenant_id": "tenant-abc", "cloud_service": "rake"}),
        producer_version="1.0.0",
    )
    assert a is not None and b is not None
    assert a.correlation.fingerprint != b.correlation.fingerprint


def test_adapter_result_always_carries_evidence_only_authority_posture():
    signal = cssa_finding_to_cloud_signal(_finding(), producer_version="1.0.0")
    assert signal is not None
    assert signal.authority_posture == "evidence_only"


# --- shadow_convert -------------------------------------------------------


def test_shadow_convert_reports_full_yield_for_all_valid_findings():
    findings = [_finding(finding_id=f"finding-{i:03d}") for i in range(5)]
    summary = shadow_convert(findings, producer_version="1.0.0")
    assert summary.total == 5
    assert summary.converted == 5
    assert summary.rejected == 0
    assert summary.conversion_rate == 1.0


def test_shadow_convert_reports_partial_yield_with_mixed_validity():
    findings = [
        _finding(finding_id="finding-001"),
        _finding(finding_id="finding-002", severity="S99"),  # rejected
        _finding(finding_id="finding-003", scope={"cloud_service": None}),  # rejected
    ]
    summary = shadow_convert(findings, producer_version="1.0.0")
    assert summary.total == 3
    assert summary.converted == 1
    assert summary.rejected == 2
    assert summary.conversion_rate == 1 / 3
    rejected_ids = {r.finding_id for r in summary.results if r.signal is None}
    assert rejected_ids == {"finding-002", "finding-003"}


def test_shadow_convert_never_publishes_anything():
    # No side effect exists to assert against directly -- this test documents
    # the invariant: shadow_convert's return value is the only observable
    # effect, there is no publisher/client call anywhere in this module.
    import app.services.cssa_finding_adapter as module

    assert not hasattr(module, "publish")
    assert not hasattr(module, "healing_publisher")


def test_shadow_convert_empty_batch_has_zero_conversion_rate():
    summary = shadow_convert([], producer_version="1.0.0")
    assert summary.total == 0
    assert summary.conversion_rate == 0.0
