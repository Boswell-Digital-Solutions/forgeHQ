"""SelfHealingRunner — run a real fix through the whole self-healing AI loop.

The operational glue that turns a signal/target into a verified, learning-emitting,
published proposal — so genuine (model, category) outcomes actually accrue:

    classify (the "what" + risk floor)
      -> assemble governed precomputed context (context-runtime)
      -> publish the governed pack (DataForge-Local context-pack store)
      -> shape: generate via NeuroForge's ladder (model captured) -> pact-verify
               -> emit CodeFixOutcome to NeuroForge (teach the matrix)
               -> propose (healing-proposals)

Every collaborator is injectable, so the loop is unit-testable end to end without a
live model/pact/DataForge. `build_live_runner()` wires the real drivers.

forgeHQ stays non-authoritative and uses NeuroForge's ladder; this only orchestrates.
Fail-closed: a fix that doesn't verify is not proposed (but its outcome is still
emitted — a model whose fix won't verify is signal the matrix should learn).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol

from app.drivers import context_client, context_pack_publisher, learning_client
from app.drivers.neuroforge_generator import NeuroForgeGenerator
from app.schemas.code_fix_classification import CodeFixClassification
from app.schemas.code_fix_outcome import CodeFixOutcome
from app.services.ai_shaper_service import (
    AiShaperService,
    DeterministicHygieneGenerator,
    ShapeResult,
)
from app.services.code_fix_classifier import CodeFixClassifier


class ContextSource(Protocol):
    """Assemble a governed context bundle + fetch its payloads (context-runtime)."""

    def assemble(self, *, repo_id: str, repo_root: str, target_file: str) -> dict[str, Any]: ...
    def fetch_payload(self, *, context_bundle_id: str, ref: str) -> dict[str, Any]: ...


class _LiveContextSource:
    def __init__(self, *, context_runtime_url: str, max_source_age_minutes: int | None = None) -> None:
        self._url = context_runtime_url
        self._max_age = max_source_age_minutes

    def assemble(self, *, repo_id: str, repo_root: str, target_file: str) -> dict[str, Any]:
        return context_client.assemble_context_bundle(
            repo_id, repo_root, target_file,
            context_runtime_url=self._url, max_source_age_minutes=self._max_age,
        )

    def fetch_payload(self, *, context_bundle_id: str, ref: str) -> dict[str, Any]:
        return context_client.fetch_payload(context_bundle_id, ref, context_runtime_url=self._url)


@dataclass(frozen=True)
class RunResult:
    classification: CodeFixClassification
    governed: dict[str, Any]
    shape: ShapeResult
    pack_published: bool
    pack_publish_error: str | None = None


class SelfHealingRunner:
    def __init__(
        self,
        *,
        classifier: CodeFixClassifier | None = None,
        context: ContextSource,
        shaper: AiShaperService,
        publish_pack: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        emit_outcome: Callable[[CodeFixOutcome], Any] | None = None,
    ) -> None:
        self._classifier = classifier or CodeFixClassifier()
        self._context = context
        self._shaper = shaper
        self._publish_pack = publish_pack
        self._emit_outcome = emit_outcome or (lambda o: None)

    def run(
        self,
        *,
        repository: str,
        repo_root: str,
        target_file: str,
        raw_kind: str = "",
        secondary_raw_kinds: tuple[str, ...] = (),
        files_changed: int | None = None,
        lines_changed: int | None = None,
        commit_sha: str = "unknown",
        publish: bool = True,
    ) -> RunResult:
        # 1) classify the target (the "what" + resolved risk floor)
        classification = self._classifier.classify(
            file_path=target_file,
            raw_kind=raw_kind,
            secondary_raw_kinds=secondary_raw_kinds,
            files_changed=files_changed,
            lines_changed=lines_changed,
        )

        # 2) assemble the governed precomputed context (context-runtime)
        assembled = self._context.assemble(repo_id=repository, repo_root=repo_root, target_file=target_file)
        bundle_id = assembled["context_bundle_id"]
        payloads = {
            ref: self._context.fetch_payload(context_bundle_id=bundle_id, ref=ref)
            for ref in assembled.get("context_item_refs", [])
        }
        pack_body = context_pack_publisher.build_pack_body(assembled, payloads)
        classification = self._with_bundle(classification, bundle_id)

        # 3) publish the governed pack (durable + servable). This is a durability /
        # re-grounding side-channel (so NeuroForge can re-ground from the stored pack);
        # it is NOT required for the authoritative learning outcome, which uses the
        # in-memory pack below. So a publish failure (e.g. DataForge-Local's context-pack
        # store endpoint not deployed) must NOT abort the run — record it and continue.
        pack_published = False
        pack_publish_error: str | None = None
        if self._publish_pack is not None:
            try:
                self._publish_pack(pack_body)
                pack_published = True
            except Exception as exc:  # noqa: BLE001 - non-authoritative side-channel
                pack_publish_error = f"{type(exc).__name__}: {exc}"

        # 4) governed handle for verification + lineage
        governed = {
            "task_intent_id": assembled.get("task_intent_id"),
            "context_bundle_id": bundle_id,
            "bundle_hash": assembled["bundle_hash"],
            "freshness_band": (assembled.get("manifest") or {}).get("freshness_band"),
        }

        # 5) shape: generate (ladder) -> verify -> emit learning outcome -> propose
        shape = self._shaper.shape(
            repository=repository,
            file_path=target_file,
            governed=governed,
            commit_sha=commit_sha,
            pack=pack_body,
            publish=publish,
            classification=classification,
            outcome_emitter=self._emit_outcome,
        )
        return RunResult(
            classification=classification,
            governed=governed,
            shape=shape,
            pack_published=pack_published,
            pack_publish_error=pack_publish_error,
        )

    @staticmethod
    def _with_bundle(c: CodeFixClassification, bundle_id: str) -> CodeFixClassification:
        from dataclasses import replace
        return replace(c, context_bundle_id=bundle_id)


def build_live_runner(
    *,
    context_runtime_url: str = "http://127.0.0.1:8011",
    dataforge_url: str = context_pack_publisher.DEFAULT_DATAFORGE_LOCAL_URL,
    neuroforge_url: str = "https://neuroforge-9lxc.onrender.com",
    max_source_age_minutes: int | None = None,
    on_outcome: Callable[[CodeFixOutcome, Any, str | None], None] | None = None,
) -> SelfHealingRunner:
    """Wire the real drivers: context-runtime + DataForge-Local + NeuroForge ladder + pact + publish.

    ``on_outcome(outcome, response, error)`` is an optional observer notified after
    each learning emission (``error`` is None on success). Emission is a
    non-authoritative learning side-channel: a NeuroForge outage or a bad/missing
    ingest key must NOT abort the authoritative propose path, so the emit is wrapped
    fail-soft and the failure is surfaced via the observer rather than raised.
    """
    from app.drivers import healing_publisher

    def _emit_outcome(outcome: CodeFixOutcome) -> Any:
        response: Any = None
        error: str | None = None
        try:
            response = learning_client.emit_model_outcome(outcome, neuroforge_url=neuroforge_url)
        except Exception as exc:  # noqa: BLE001 - reported via on_outcome, never fatal
            error = f"{type(exc).__name__}: {exc}"
        if on_outcome is not None:
            on_outcome(outcome, response, error)
        return response

    shaper = AiShaperService(
        # Same fleet-service-key env lookup learning_client already uses for
        # the outcome-emission call below — generation needs it too. Without
        # this, every non-hygiene fix attempt gets NeuroForge's live chat
        # ladder with no Authorization header at all: HTTP 401, unconditionally,
        # regardless of whether NEUROFORGE_API_KEY/NEUROFORGE_SERVICE_KEY is
        # set in the environment this runner was spawned from.
        generator=NeuroForgeGenerator(
            base_url=neuroforge_url, api_key=learning_client._neuroforge_service_key()
        ),
        # Hygiene fixes (whitespace/EOF newline) are deterministic; the model echoes
        # them back unchanged (fail-closed no-op), so route them to the deterministic
        # generator while everything else goes through NeuroForge's ladder.
        hygiene_generator=DeterministicHygieneGenerator(),
        publisher=lambda env: healing_publisher.publish_healing_proposal(env, dataforge_url=dataforge_url),
    )
    return SelfHealingRunner(
        context=_LiveContextSource(
            context_runtime_url=context_runtime_url, max_source_age_minutes=max_source_age_minutes
        ),
        shaper=shaper,
        publish_pack=lambda body: context_pack_publisher.publish_context_pack(body, dataforge_url=dataforge_url),
        emit_outcome=_emit_outcome,
    )
