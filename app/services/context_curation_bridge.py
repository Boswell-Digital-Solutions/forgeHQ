"""
Context curation bridge for forgeHQ — Stage 3, wired to context-runtime.

The CONTEXT_CURATION stage's engine is context-runtime (PCC-conforming). This
bridge turns a context-runtime *assemble result* into a forgeHQ ``ContextBundle``,
carrying the governed handle (``context_bundle_id`` + ``bundle_hash``) into the
bundle's scope boundary so it propagates — locked — through CandidateDesign,
CandidateGeneration, and the final proposal. That makes every downstream
artifact traceable back to the exact governed, replay-eligible context it was
built from.

forgeHQ stays non-authoritative: precomputed-context-core / context-runtime
govern admissibility, freshness, and authority; this bridge only adapts the
already-governed refs into the bounded ``ContextBundle``. Fail-closed on a
missing or invalid governed handle; scope violations surface as the existing
``ScopeEscapeError``.
"""
from app.schemas.context_bundle import ContextBundle
from app.schemas.target_ranking import TargetRanking
from app.services.context_bundle_service import ContextBundleService


class ContextCurationError(ValueError):
    """Raised when a governed context-runtime result cannot be adapted safely."""


class ContextCurationBridge:
    """
    Adapts a context-runtime assemble result into a forgeHQ ContextBundle.

    Reuses ContextBundleService for the bounded-scope fail-closed checks
    (placeholder ranking, target_id match, max items, duplicate refs).
    """

    def __init__(self, bundle_service: ContextBundleService | None = None) -> None:
        self._svc = bundle_service or ContextBundleService()

    def curate_from_runtime(
        self,
        run_id: str,
        target_id: str,
        target_ranking: TargetRanking,
        assemble_result: dict,
        scope_boundary_statement: str | None = None,
    ) -> ContextBundle:
        """
        Build a ContextBundle from a governed context-runtime result.

        Raises ContextCurationError if the result lacks a valid governed handle
        (context_bundle_id / bundle_hash) or admitted refs. Scope violations
        raise ScopeEscapeError from the underlying ContextBundleService.
        """
        handle = _governed_handle(assemble_result)
        context_item_refs = _admitted_refs(assemble_result)

        base = (scope_boundary_statement or "").strip() or (
            f"Bounded single-target context for '{target_id}'."
        )
        scoped = (
            f"{base} [governed by context-runtime bundle "
            f"{handle['context_bundle_id']} hash {handle['bundle_hash']}]"
        )

        return self._svc.build_context_bundle(
            run_id=run_id,
            target_id=target_id,
            target_ranking=target_ranking,
            context_item_refs=context_item_refs,
            scope_boundary_statement=scoped,
        )


def _governed_handle(result: dict) -> dict:
    bundle_id = result.get("context_bundle_id")
    bundle_hash = result.get("bundle_hash")
    # precomputed-context-core's two canonical id shapes — see
    # context_pack_publisher.py's identical check for why both are valid.
    if not isinstance(bundle_id, str) or not (
        bundle_id.startswith("ctxb_") or bundle_id.startswith("ctxb.sha256.")
    ):
        raise ContextCurationError(
            f"missing or invalid governed context_bundle_id: {bundle_id!r} — "
            "refusing to curate an ungoverned bundle"
        )
    if not isinstance(bundle_hash, str) or not bundle_hash.strip():
        raise ContextCurationError(
            "missing governed bundle_hash — refusing to curate without a replay handle"
        )
    return {"context_bundle_id": bundle_id, "bundle_hash": bundle_hash}


def _admitted_refs(result: dict) -> tuple[str, ...]:
    refs = result.get("context_item_refs")
    if refs is None:
        refs = result.get("payload_refs")
    if refs is None:
        raise ContextCurationError(
            "context-runtime result missing context_item_refs / payload_refs"
        )
    if not isinstance(refs, (list, tuple)):
        raise ContextCurationError("context_item_refs must be a list of refs")
    return tuple(refs)
