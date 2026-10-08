"""proposal_store_reader -- read cloud proposals back from DataForge-Local.

READ-ONLY: one GET per status against `/api/v1/healing-proposals`. It never
POSTs or PATCHes, so it cannot create, change or decide a proposal. It exists
so the detector can see what is already open or recently decided before it
proposes anything (the eligibility gate's duplicate/cooldown suppression).

DataForge-Local caps a listing at 200 rows and returns newest first. When a
status hits that cap the result is flagged `truncated`, and callers must
report that the picture is incomplete rather than treat it as the whole
store. The HTTP call is injectable so tests never touch the network.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass

from app.drivers.healing_publisher import DEFAULT_DATAFORGE_LOCAL_URL

CLOUD_PROPOSAL_SCHEMA = "cloud.proposal.v1"
LIST_LIMIT = 200


class ProposalStoreError(RuntimeError):
    """The store could not be read. Callers report it; nothing is guessed."""


@dataclass(frozen=True, slots=True)
class StoredCloudProposal:
    proposal_id: str
    status: str
    fingerprint: str | None  # None for proposals composed before the field existed
    issue_class: str
    decided_at: str | None  # decision.at when a decision was recorded
    created_at: str | None


@dataclass(frozen=True, slots=True)
class StoreSnapshot:
    proposals: tuple[StoredCloudProposal, ...]
    truncated_statuses: tuple[str, ...]


def _default_get(url: str, timeout: float) -> dict:
    request = urllib.request.Request(url)
    request.add_unredirected_header(
        "Authorization", "Bearer " + os.environ.get("HEALING_PRODUCER_TOKEN", "")
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed http(s) base
        return json.loads(response.read().decode("utf-8"))


def _to_proposal(item: dict) -> StoredCloudProposal | None:
    envelope = item.get("envelope")
    if (
        not isinstance(envelope, dict)
        or envelope.get("schema_version") != CLOUD_PROPOSAL_SCHEMA
    ):
        return None
    payload = (
        envelope.get("payload") if isinstance(envelope.get("payload"), dict) else {}
    )
    decision = item.get("decision") if isinstance(item.get("decision"), dict) else {}
    fingerprint = payload.get("correlationFingerprint")
    return StoredCloudProposal(
        proposal_id=str(item.get("proposal_id") or ""),
        status=str(item.get("status") or ""),
        fingerprint=fingerprint
        if isinstance(fingerprint, str) and fingerprint
        else None,
        issue_class=str(payload.get("issueClass") or ""),
        decided_at=decision.get("at") if isinstance(decision.get("at"), str) else None,
        created_at=item.get("created_at")
        if isinstance(item.get("created_at"), str)
        else None,
    )


def read_cloud_proposals(
    statuses: tuple[str, ...] = ("pending", "ingested", "accepted", "rejected"),
    *,
    base_url: str = DEFAULT_DATAFORGE_LOCAL_URL,
    timeout: float = 10.0,
    get: Callable[[str, float], dict] | None = None,
) -> StoreSnapshot:
    fetch = get or _default_get
    proposals: list[StoredCloudProposal] = []
    truncated: list[str] = []
    for status in statuses:
        query = urllib.parse.urlencode({"status": status, "limit": LIST_LIMIT})
        url = f"{base_url.rstrip('/')}/api/v1/healing-proposals?{query}"
        try:
            reply = fetch(url, timeout)
        except Exception as exc:  # unreachable, non-2xx, bad JSON
            raise ProposalStoreError(f"{type(exc).__name__}: {exc}") from exc
        items = reply.get("items") if isinstance(reply, dict) else None
        if not isinstance(items, list):
            raise ProposalStoreError("reply has no items list")
        if len(items) >= LIST_LIMIT:
            truncated.append(status)
        for item in items:
            proposal = _to_proposal(item) if isinstance(item, dict) else None
            if proposal is not None:
                proposals.append(proposal)
    return StoreSnapshot(
        proposals=tuple(proposals), truncated_statuses=tuple(truncated)
    )
