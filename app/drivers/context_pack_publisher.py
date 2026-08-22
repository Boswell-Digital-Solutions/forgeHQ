"""context_pack_publisher — publish a governed context pack to DataForge-Local.

Turns a context-runtime assemble result (+ its code-native payloads) into the
NeuroForge read shape ({primary, supporting, metadata}) and POSTs it to
DataForge-Local's context-pack store, keyed by the governed context_bundle_id.
NeuroForge then serves inference from the precomputed packet instead of
re-grounding — the faster/cheaper-tokens path.

Stdlib-only (urllib), same posture as healing_publisher / context_client.
Fail-closed: raises on a missing governed handle or transport/non-2xx.

The pack carries the full governance + verification provenance in metadata:
the lineage handle (task_intent_id / context_bundle_id / bundle_hash), the
admitted source classes, and (when supplied) the pact verification verdict.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from typing import Any

DEFAULT_DATAFORGE_LOCAL_URL = "http://127.0.0.1:8005"


def _is_prose_doc(ref: str, payload: dict[str, Any]) -> bool:
    """A prose repo-doc source (vs code/validation). These carry command examples
    (e.g. ``python -m app``) that trip Render's Cloudflare edge WAF on the NeuroForge
    chat endpoint — see ``_exclude_doc_grounding``."""
    return (
        ref.startswith("doc://")
        or payload.get("role") == "repo_truth"
        or payload.get("source_class") == "accepted_lore_record"
    )


def _exclude_doc_grounding() -> bool:
    """WAF STOPGAP (2026-06-10): Render fronts ``*.onrender.com`` with Cloudflare, whose
    managed command-injection rule blocks request bodies containing backtick-wrapped
    ``python -m <module>``. forgeHQ's prose repo docs (doc:// / repo_truth) carry such
    strings, so by default we drop prose-doc grounding from the context sent to NeuroForge
    (code grounding is kept). Re-enable docs once Render adds a /api/v1/chat exception:
    set ``FORGEHQ_INCLUDE_DOC_GROUNDING=1``."""
    return os.getenv("FORGEHQ_INCLUDE_DOC_GROUNDING", "").strip().lower() not in ("1", "true", "yes")


class ContextPackPublishError(ValueError):
    """Raised when a governed pack cannot be built/published — fail closed."""


def build_pack_body(
    assemble_result: dict[str, Any],
    payloads: dict[str, dict[str, Any]],
    *,
    pact_verdict: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the DataForge-Local context-pack body from a context-runtime result.

    ``assemble_result`` is the context-runtime /v1/context/assemble response.
    ``payloads`` maps each admitted ref -> its fetched payload
    ({role, source_class, artifact_class, content, content_hash, contract}).
    """
    bundle_id = assemble_result.get("context_bundle_id")
    bundle_hash = assemble_result.get("bundle_hash")
    task_intent_id = assemble_result.get("task_intent_id")
    # precomputed-context-core's two canonical id shapes: "ctxb_<hash>" (the
    # original format, still minted as manifest.legacy_context_bundle_id) and
    # the current algorithm-tagged "ctxb.sha256.<hash>" (manifest's primary
    # context_bundle_id, what context-runtime actually returns here now).
    # Accepting both keeps this consuming its context-runtime authority's
    # real output rather than requiring it downgrade to the legacy shape.
    if not isinstance(bundle_id, str) or not (
        bundle_id.startswith("ctxb_") or bundle_id.startswith("ctxb.sha256.")
    ):
        raise ContextPackPublishError(f"missing/invalid context_bundle_id: {bundle_id!r}")
    if not isinstance(bundle_hash, str) or not bundle_hash.strip():
        raise ContextPackPublishError("missing bundle_hash")

    refs = assemble_result.get("context_item_refs") or assemble_result.get("payload_refs") or []

    exclude_docs = _exclude_doc_grounding()
    primary = ""
    supporting: list[str] = []
    source_classes: list[str] = []
    excluded_doc_refs = 0
    for ref in refs:
        payload = payloads.get(ref)
        if not payload:
            continue
        content = payload.get("content") or ""
        source_classes.append(payload.get("source_class", ""))
        # The target file (active_scene) is the primary grounded context;
        # everything else is supporting.
        if payload.get("role") == "target" or payload.get("source_class") == "active_scene":
            primary = content
        elif exclude_docs and _is_prose_doc(ref, payload):
            # WAF stopgap: prose docs carry `python -m …` which Render's Cloudflare
            # edge blocks; drop them from grounding (code grounding is kept).
            excluded_doc_refs += 1
            continue
        else:
            supporting.append(content)

    if not primary and supporting:
        # Fail-closed-ish: never publish an empty primary if any content exists.
        primary = supporting.pop(0)

    metadata: dict[str, Any] = {
        "task_intent_id": task_intent_id,
        "context_bundle_id": bundle_id,
        "context_bundle_hash": bundle_hash,
        "freshness_band": (assemble_result.get("manifest") or {}).get("freshness_band"),
        "source_classes": source_classes,
        "admitted_ref_count": len(refs),
        "excluded_doc_refs": excluded_doc_refs,
        "provenance": "context-runtime+pcc",
    }
    if pact_verdict is not None:
        metadata["pact_verdict"] = {
            "ok": pact_verdict.get("ok"),
            "packet_id": pact_verdict.get("packet_id"),
            "receipt_id": pact_verdict.get("receipt_id"),
        }

    return {
        "context_pack_id": bundle_id,
        "bundle_hash": bundle_hash,
        "task_intent_id": task_intent_id,
        "primary": primary,
        "supporting": supporting,
        "metadata": metadata,
    }


def publish_context_pack(
    pack_body: dict[str, Any],
    *,
    dataforge_url: str = DEFAULT_DATAFORGE_LOCAL_URL,
    timeout: float = 10.0,
) -> dict[str, Any]:
    """POST a context-pack body to DataForge-Local. Returns {context_pack_id, status}."""
    if not pack_body.get("context_pack_id"):
        raise ContextPackPublishError("pack_body missing context_pack_id")
    url = f"{dataforge_url.rstrip('/')}/df/rag/context-pack"
    body = json.dumps(pack_body).encode("utf-8")
    request = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_context_pack(
    context_pack_id: str,
    *,
    dataforge_url: str = DEFAULT_DATAFORGE_LOCAL_URL,
    timeout: float = 10.0,
) -> dict[str, Any]:
    """GET a precomputed pack by id from DataForge-Local — the consumer side.

    Returns NeuroForge's read shape {primary, supporting, metadata}. This is the
    same fetch-by-id path NeuroForge's Context Builder uses; the AI shaper uses it
    to generate from the precomputed governed packet instead of re-grounding.
    """
    url = f"{dataforge_url.rstrip('/')}/df/rag/context-pack/{urllib.parse.quote(context_pack_id, safe='')}"
    request = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))
