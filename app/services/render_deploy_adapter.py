"""Render deploy-event source adapter (BDS-FCO-CSD-v0.1, slice CSD-07).

Converts a Render deploy webhook payload -- the real, documented "thin"
notification shape (`type`, `timestamp`, `data.id`, `data.serviceId`,
`data.serviceName`, `data.status`; https://render.com/docs/webhooks,
verified against Render's own docs, not invented) -- into forgeHQ's
`CloudSignal.v1` (`cloud_signal_contracts.py`, CSD-01).

Third and last adapter in the source review's own `CSSA -> CI -> Render/
deploy` progression. TRANSPORT-FREE, matching `CSD-02`/`CSD-06`: no network
I/O, no webhook receiver here -- the caller supplies the raw payload.

SERVICE-SCOPED SUBJECT, CHECKED NOT ASSUMED: unlike CSSA (identity-scoped)
and CI (repository-scoped), a Render deploy event names a `serviceId`/
`serviceName` directly -- it fits `CloudSignalSubject`'s existing `"service"`
kind. No third widening was needed here; this was verified against Render's
real webhook documentation before writing this adapter, not assumed from
the other two adapters' pattern.

SCOPE, DELIBERATELY MINIMAL FOR THIS FIRST DEPLOY SLICE: only
`type == "deploy_ended"` with `data.status == "failed"` produces a signal.
`"succeeded"` and `"canceled"` are real Render outcomes but aren't handled
yet -- fails closed rather than guessing. `deploy_started` and other event
types (e.g. service health events) are out of scope for this slice.

NO COMMIT/BUILD EVIDENCE: Render's own docs describe this webhook shape as
"thin" -- it carries no commit SHA or build detail; a caller would need a
separate call to Render's Retrieve Event API for that. This adapter does
not fabricate one, so evidence here is `source_refs` only (no
`immutable_hashes`) -- matching evidence shape governs confidence banding
downstream in CSD-03's eligibility gate, not something this adapter decides.

Severity has no field in Render's deploy-event payload either. This adapter
uses one fixed, disclosed default ("high") rather than a per-event
inference -- a failed production deploy is treated as more urgent than an
arbitrary CI check failure by default, a judgment call stated here, not
derived from data.
"""
from __future__ import annotations

import hashlib

from app.services.cloud_signal_contracts import (
    CloudSignal,
    CloudSignalCorrelation,
    CloudSignalEvidence,
    CloudSignalProvenance,
    CloudSignalShaper,
    CloudSignalSubject,
)

SOURCE_SYSTEM = "render"
SOURCE_KIND = "deploy_event"
ISSUE_CLASS = "deploy_failure"

# No severity field exists on a Render deploy event. Fixed and disclosed,
# not fabricated per-event -- see module docstring.
DEFAULT_SEVERITY = "high"

_HANDLED_EVENT_TYPE = "deploy_ended"
_HANDLED_STATUS = "failed"


def _correlation_fingerprint(*, service_id: str) -> str:
    # Groups repeated failed deploys of the SAME Render service into one
    # identity. No workflow/environment dimension exists in this thin
    # payload to further split on.
    digest = hashlib.sha256(service_id.encode()).hexdigest()[:16]
    return f"fp-deploy-{digest}"


def render_deploy_event_to_cloud_signal(
    event: dict,
    *,
    producer_version: str,
) -> CloudSignal | None:
    """Build a `CloudSignal` from a raw Render deploy webhook payload.

    Fails closed (returns None) on a missing required field, an event
    `type` other than `"deploy_ended"`, or a `status` other than
    `"failed"` -- see module docstring for why other statuses aren't
    handled yet.
    """
    event_type = event.get("type")
    timestamp = event.get("timestamp")
    data = event.get("data") or {}
    event_id = data.get("id")
    service_id = data.get("serviceId")
    service_name = data.get("serviceName")
    status = data.get("status")

    if not timestamp or not event_id or not service_id or not service_name:
        return None
    if event_type != _HANDLED_EVENT_TYPE:
        return None
    if status != _HANDLED_STATUS:
        return None

    fingerprint = _correlation_fingerprint(service_id=service_id)
    source_refs = (f"signal://deploy/{service_name}/event/{event_id}",)

    signal = CloudSignal(
        signal_id=f"render-{event_id}",
        source_system=SOURCE_SYSTEM,
        source_kind=SOURCE_KIND,
        subject=CloudSignalSubject(service=service_name),
        issue_class=ISSUE_CLASS,
        severity=DEFAULT_SEVERITY,
        observed_at=timestamp,
        summary=f'Render deploy failed for service "{service_name}" (event {event_id}).',
        evidence=CloudSignalEvidence(source_refs=source_refs),
        correlation=CloudSignalCorrelation(fingerprint=fingerprint),
        provenance=CloudSignalProvenance(
            producer=SOURCE_SYSTEM,
            producer_version=producer_version,
            original_event_id=event_id,
        ),
    )
    return CloudSignalShaper().build(signal)
