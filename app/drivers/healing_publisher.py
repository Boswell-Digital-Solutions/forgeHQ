"""healing_publisher — emit a healing.code_fix.v1 envelope to DataForge-Local.

The forgeHQ-side sidecar EMIT: POST a shaped proposal envelope to DataForge-Local
``/api/v1/healing-proposals`` (it stores with ``status=pending``; ForgeCommand's
self-healing bridge then reads pending, surfaces for Accept/Reject, and applies).

DataForge-Local is the persistence boundary — forgeHQ never persists locally and
never decides/applies. Stdlib-only (urllib) per forgeHQ's standard-library-first
contract. The POST is idempotent server-side (dedup on envelope.event_id).
"""
from __future__ import annotations

import json
import os
import urllib.request

DEFAULT_DATAFORGE_LOCAL_URL = "http://127.0.0.1:8005"


def publish_healing_proposal(
    envelope: dict,
    *,
    dataforge_url: str = DEFAULT_DATAFORGE_LOCAL_URL,
    timeout: float = 10.0,
) -> dict:
    """POST ``envelope`` to DataForge-Local healing-proposals (status=pending).

    Returns the store response ``{"proposal_id", "status"}``. Raises
    urllib.error.URLError / HTTPError on transport or non-2xx response.
    """
    if not envelope.get("event_id"):
        raise ValueError("envelope missing required field: event_id")

    url = f"{dataforge_url.rstrip('/')}/api/v1/healing-proposals"
    body = json.dumps(envelope).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    request.add_unredirected_header(
        "Authorization", "Bearer " + os.environ.get("HEALING_PRODUCER_TOKEN", "")
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))
