"""
Pact verification bridge for forgeHQ — Stage 7 (VERIFICATION), wired to pact.

The VERIFICATION stage's engine is pact (PAC). This bridge turns a governed
context handle (from context-runtime) plus a candidate's grounding into a pact
request, runs pact, and returns a verdict whose packet + receipt are BOUND to the
governed bundle (same context_bundle_id / bundle_hash). That binding is the point:
it proves the verification — and the evidence a proposal carries — was produced
against the exact governed, replay-eligible context the fix was built from.

forgeHQ stays non-authoritative: pact owns the deterministic verification truth;
this bridge only adapts inputs and asserts the bundle binding. Fail-closed on a
missing/invalid governed handle, missing grounding, or a broken bundle binding.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Callable

from app.drivers import pact_client

ALLOWED_PACKET_CLASSES = {"answer_packet", "policy_response_packet", "search_assist_packet"}

# context-runtime governance SourceClass -> pact grounding authority_class.
_AUTHORITY_BY_SOURCE_CLASS = {
    "active_scene": "primary",
    "accepted_lore_record": "primary",
    "adjacent_scene_summary_or_clipped_body": "secondary",
    "accepted_style_rule_record": "derived",
}


class PactVerificationError(ValueError):
    """Raised when a candidate cannot be verified safely — fail closed."""


def grounding_ref(
    source_ref: str,
    *,
    source_class: str = "",
    authority_class: str | None = None,
    excerpt: str = "",
) -> dict[str, Any]:
    """Build one pact grounding_ref from a context-runtime admitted ref."""
    if not isinstance(source_ref, str) or not source_ref.strip():
        raise PactVerificationError("grounding source_ref must be a non-empty string")
    auth = authority_class or _AUTHORITY_BY_SOURCE_CLASS.get(source_class, "secondary")
    text = (excerpt or "").strip() or source_ref.strip()
    text = text[:280]
    gid = "g_" + hashlib.sha256(source_ref.encode("utf-8")).hexdigest()[:12]
    return {
        "grounding_id": gid,
        "source_ref": source_ref.strip(),
        "authority_class": auth,
        "excerpt": text,
        "start_offset": 0,
        "end_offset": len(text),
    }


class PactVerificationBridge:
    """Adapts a governed handle + grounding into a pact verification verdict."""

    def __init__(self, verifier: Callable[[dict[str, Any]], dict[str, Any]] | None = None) -> None:
        self._verify = verifier or pact_client.verify_packet

    def build_request(
        self,
        *,
        governed: dict[str, Any],
        grounding_refs: tuple[dict[str, Any], ...],
        task_goal: str,
        instruction_block: str,
        answer_constraints: tuple[str, ...],
        support_blocks: tuple[str, ...] = (),
        packet_class: str = "answer_packet",
        consumer_identity: str = "forgehq",
        permission_context: dict[str, Any] | None = None,
        now: str | None = None,
    ) -> dict[str, Any]:
        """Construct a connectivity-valid pact request bound to the governed bundle."""
        handle = _governed_handle(governed)
        if packet_class not in ALLOWED_PACKET_CLASSES:
            raise PactVerificationError(f"invalid packet_class: {packet_class!r}")
        if not grounding_refs:
            raise PactVerificationError(
                "at least one grounding_ref is required — refusing to verify ungrounded"
            )
        if not task_goal.strip() or not instruction_block.strip():
            raise PactVerificationError("task_goal and instruction_block are required")

        manifest: dict[str, Any] = {
            "task_intent_id": handle["task_intent_id"],
            "context_bundle_id": handle["context_bundle_id"],
            "bundle_hash": handle["bundle_hash"],
        }
        if handle.get("freshness_band"):
            manifest["freshness_band"] = handle["freshness_band"]

        return {
            "packet_class": packet_class,
            "consumer_identity": consumer_identity,
            "permission_context": permission_context or {"tenant": "local", "scope": "self_healing"},
            "serialization_profile": "plain_text_only",
            "execution_mode": "replay",
            "now": now or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "context_bundle_manifest": manifest,
            "compile_input": {
                "task_goal": task_goal.strip(),
                "instruction_block": instruction_block.strip(),
                "support_blocks": list(support_blocks),
                "grounding_refs": list(grounding_refs),
                "answer_constraints": list(answer_constraints),
            },
        }

    def verify(self, **kwargs: Any) -> dict[str, Any]:
        """Build the request, run pact, and return a bundle-bound verdict.

        Raises PactVerificationError if pact returns success but the packet is not
        bound to the governed bundle we submitted (binding integrity).
        """
        governed = _governed_handle(kwargs["governed"])
        request = self.build_request(**kwargs)
        result = self._verify(request)

        packet = result.get("packet") or {}
        receipt = result.get("receipt") or {}
        ok = bool(result.get("ok"))

        verdict = {
            "ok": ok,
            "packet_id": packet.get("packet_id") or packet.get("failure_packet_id"),
            "receipt_id": receipt.get("receipt_id"),
            "context_bundle_id": packet.get("context_bundle_id"),
            "context_bundle_hash": packet.get("context_bundle_hash"),
            "task_intent_id": packet.get("task_intent_id"),
            "failure_state": packet.get("failure_state"),
            "public_reason_code": packet.get("public_reason_code"),
            "raw": result,
        }

        if ok:
            if verdict["context_bundle_id"] != governed["context_bundle_id"]:
                raise PactVerificationError(
                    "pact packet is not bound to the submitted context_bundle_id — "
                    f"sent {governed['context_bundle_id']!r}, got {verdict['context_bundle_id']!r}"
                )
            if verdict["context_bundle_hash"] != governed["bundle_hash"]:
                raise PactVerificationError(
                    "pact packet is not bound to the submitted bundle_hash — "
                    f"sent {governed['bundle_hash']!r}, got {verdict['context_bundle_hash']!r}"
                )

        return verdict


def _governed_handle(governed: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(governed, dict):
        raise PactVerificationError("governed handle must be a dict")
    task_intent_id = governed.get("task_intent_id")
    bundle_id = governed.get("context_bundle_id")
    bundle_hash = governed.get("bundle_hash") or governed.get("context_bundle_hash")
    # precomputed-context-core's two canonical id shapes — see
    # context_pack_publisher.py's identical check for why both are valid.
    if not isinstance(bundle_id, str) or not (
        bundle_id.startswith("ctxb_") or bundle_id.startswith("ctxb.sha256.")
    ):
        raise PactVerificationError(
            f"missing or invalid governed context_bundle_id: {bundle_id!r}"
        )
    if not isinstance(bundle_hash, str) or not bundle_hash.strip():
        raise PactVerificationError("missing governed bundle_hash")
    if not isinstance(task_intent_id, str) or not task_intent_id.strip():
        raise PactVerificationError(
            "missing governed task_intent_id (required for pact connectivity)"
        )
    out = {
        "task_intent_id": task_intent_id.strip(),
        "context_bundle_id": bundle_id.strip(),
        "bundle_hash": bundle_hash.strip(),
    }
    if isinstance(governed.get("freshness_band"), str):
        out["freshness_band"] = governed["freshness_band"]
    return out
