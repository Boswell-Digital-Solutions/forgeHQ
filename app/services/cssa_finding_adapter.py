"""CSSA finding source adapter (BDS-FCO-CSD-v0.1, slice CSD-02).

Converts a `cloud_security.finding.v1` payload -- the real, already-shipped
watchdog output shape defined by Forge-Agents' `app/security/contracts.py`
(`CloudSecurityFinding`, plan-set 06 §4) and currently produced by
forgesentinel's `DecisionWatchdog` detectors -- into forgeHQ's own
`CloudSignal.v1` (see `cloud_signal_contracts.py`, CSD-01).

TRANSPORT-FREE, matching every other adapter/feeder in this repo
(`cloud_source_feeder.py`'s own docstring: "the caller supplies ... records,
keeping this feeder deterministic"): this module does no network I/O and
polls nothing. forgesentinel currently exposes no HTTP read surface for CSSA
findings (`sentinel watch-cssa` is CLI-only, per the CSD-00 verification
recorded in `docs/plans/active/BDS-FCO-CSD-v0.1-CLOUD-SUBJECT-DETECTOR.md` at
the forge workspace root) -- wiring a live poller is separately out of scope
until that surface exists. The caller (a future CSD-06+ transport slice, or a
one-off script) is responsible for obtaining the raw finding payload and
handing it to `cssa_finding_to_cloud_signal`.

SHADOW MEASUREMENT, NOT LIVE DETECTION: `shadow_convert()` runs a batch of
finding payloads through the adapter and reports how many produce a valid
`CloudSignal`, matching this slice's own scope ("shadow mode only, measure
how many signals would become candidates, no proposal publishing"). A
CloudSignal is not yet a proposal candidate -- correlation and eligibility
(CSD-03) do not exist yet -- so this measures adapter yield, the nearest
honest proxy available at this slice.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from app.services.cloud_signal_contracts import (
    CloudSignal,
    CloudSignalCorrelation,
    CloudSignalEvidence,
    CloudSignalProvenance,
    CloudSignalShaper,
    CloudSignalSubject,
)

SOURCE_SYSTEM = "forgesentinel"
SOURCE_KIND = "cssa_finding"

# Descending severity order (plan-set 06 §4 / Forge-Agents' Severity enum):
# S0 is the most severe. Confirmed against Forge-Agents'
# app/agents/bugcheck/correlation.py weighting ({"S0": 10, ..., "S4": 0.1})
# and a real S4 "no property-based testing" finding -- not assumed.
_SEVERITY_MAP: dict[str, str] = {
    "S0": "critical",
    "S1": "high",
    "S2": "medium",
    "S3": "low",
    "S4": "info",
}


@dataclass(frozen=True, slots=True)
class ShadowConversionResult:
    """Outcome of running one finding payload through the adapter."""

    finding_id: str | None
    signal: CloudSignal | None
    rejected_reason: str | None


@dataclass(frozen=True, slots=True)
class ShadowConversionSummary:
    """Aggregate outcome of `shadow_convert()` over a batch of findings."""

    total: int
    converted: int
    rejected: int
    results: tuple[ShadowConversionResult, ...]

    @property
    def conversion_rate(self) -> float:
        return self.converted / self.total if self.total else 0.0


def _correlation_fingerprint(*, cloud_service: str, detector: str, tenant_id: str | None) -> str:
    # Groups repeated findings of the same detector, on the same service and
    # tenant, into one identity -- the correlation key this slice's own
    # candidate contract (CSD-01) is keyed on. No environment dimension
    # exists on CloudSecurityFinding, so this fingerprint intentionally omits
    # it (CloudSignalSubject still defaults environment to "production").
    digest = hashlib.sha256(
        f"{cloud_service}\0{detector}\0{tenant_id or ''}".encode()
    ).hexdigest()[:16]
    return f"fp-cssa-{digest}"


def cssa_finding_to_cloud_signal(
    finding: dict,
    *,
    producer_version: str,
) -> CloudSignal | None:
    """Build a `CloudSignal` from a raw `cloud_security.finding.v1` payload.

    Fails closed (returns None) on a missing required field, an unmapped
    severity, or a finding with no `scope.cloud_service` -- without a cloud
    subject there is no service to attach the signal to, and this adapter
    does not invent one.

    `producer_version` is supplied by the caller (the version of the
    detector/adapter pipeline that produced this signal), not read from the
    finding -- `CloudSecurityFinding` carries no such field itself.
    """
    finding_id = finding.get("finding_id")
    detector = finding.get("detector")
    severity_raw = finding.get("severity")
    scope = finding.get("scope") or {}
    cloud_service = scope.get("cloud_service")
    tenant_id = scope.get("tenant_id")
    evidence_refs = finding.get("evidence_refs") or []
    summary = finding.get("summary")
    emitted_at = finding.get("emitted_at")
    finding_hash = finding.get("finding_hash")

    if not finding_id or not detector or not summary or not emitted_at:
        return None
    if not cloud_service:
        # No cloud subject named -- fail closed rather than guess one.
        return None
    if severity_raw not in _SEVERITY_MAP:
        return None
    if not finding_hash:
        return None

    severity = _SEVERITY_MAP[severity_raw]
    fingerprint = _correlation_fingerprint(
        cloud_service=cloud_service, detector=detector, tenant_id=tenant_id
    )
    # Wrap each raw evidence ref in forgeHQ's admissible signal:// namespace.
    # CloudSecurityFinding.evidence_refs carries opaque identifiers with no
    # URI convention of its own -- the adapter boundary is exactly where that
    # translation belongs (see cloud_signal_contracts.py's recursion-guard
    # docstring for why cloud:// specifically must never appear here).
    source_refs = tuple(f"signal://cssa/finding/{finding_id}/{ref}" for ref in evidence_refs)

    signal = CloudSignal(
        signal_id=f"cssa-{finding_id}",
        source_system=SOURCE_SYSTEM,
        source_kind=SOURCE_KIND,
        subject=CloudSignalSubject(service=cloud_service),
        issue_class=detector,
        severity=severity,
        observed_at=emitted_at,
        summary=summary,
        evidence=CloudSignalEvidence(
            source_refs=source_refs,
            immutable_hashes=(finding_hash,),
        ),
        correlation=CloudSignalCorrelation(fingerprint=fingerprint),
        provenance=CloudSignalProvenance(
            producer=SOURCE_SYSTEM,
            producer_version=producer_version,
            original_event_id=finding_id,
        ),
    )
    return CloudSignalShaper().build(signal)


def shadow_convert(
    findings: list[dict],
    *,
    producer_version: str,
) -> ShadowConversionSummary:
    """Run a batch of raw finding payloads through the adapter and report
    conversion yield, without publishing anything. This is CSD-02's own
    "shadow mode" measurement -- how many signals would result, not how many
    proposal candidates would result (that needs CSD-03's correlator, not
    yet built)."""
    results: list[ShadowConversionResult] = []
    for finding in findings:
        finding_id = finding.get("finding_id")
        signal = cssa_finding_to_cloud_signal(finding, producer_version=producer_version)
        rejected_reason = None if signal is not None else "failed_closed_validation"
        results.append(
            ShadowConversionResult(
                finding_id=finding_id, signal=signal, rejected_reason=rejected_reason
            )
        )
    converted = sum(1 for r in results if r.signal is not None)
    return ShadowConversionSummary(
        total=len(results),
        converted=converted,
        rejected=len(results) - converted,
        results=tuple(results),
    )
