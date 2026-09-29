"""forgeHQ producer CLI — run one real self-healing fix end to end.

The spawnable entrypoint Forge_Command's self-healing tick invokes per target. It
wires the live runner (`build_live_runner`): classify -> assemble governed context
-> publish pack -> generate via NeuroForge's ladder (model captured) -> pact-verify
-> emit CodeFixOutcome to NeuroForge (teach the matrix) -> propose. A structured
JSON result is printed to stdout so the caller can capture it as evidence.

The NeuroForge ingest key is read from the environment (NEUROFORGE_API_KEY /
NEUROFORGE_SERVICE_KEY) by learning_client; Forge_Command injects it at spawn so
the secret never lands in a forgeHQ file.

Exit codes (so the spawning tick can react without parsing stdout):
  0  ran to completion; learning outcome emitted (or skipped — no model to attribute)
  1  hard failure — the run raised (e.g. context-runtime unreachable)
  3  ran + verified/proposed, but the learning emit failed (e.g. 401 ingest key)

Stdlib-only (argparse + json), same posture as the drivers.

Run:  python -m app self-heal --repo <id> --repo-root <path> --target <file>
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

from app.drivers.healing_publisher import DEFAULT_DATAFORGE_LOCAL_URL, publish_healing_proposal
from app.drivers.learning_client import DEFAULT_NEUROFORGE_URL
from app.schemas.code_fix_outcome import CodeFixOutcome
from app.services.ci_shadow import run_ci_shadow
from app.services.cloud_proposal_shaper import (
    CloudProposalInput,
    CloudProposalShaper,
    CloudSubject,
    to_cloud_proposal_envelope,
)
from app.services.self_healing_feed import run_feed
from app.services.self_healing_runner import RunResult, build_live_runner

DEFAULT_CONTEXT_RUNTIME_URL = "http://127.0.0.1:8011"
# A repo source file's mtime age is NOT a freshness signal for code-fix — a file
# unchanged for months is still the current truth. context-runtime fail-closes on
# sources older than max_source_age_minutes (7-day service default, meant for
# cached/external context), which would reject normal repo files. Default to an
# effectively-unlimited window; override with --max-source-age-minutes or
# FORGEHQ_MAX_SOURCE_AGE_MINUTES.
DEFAULT_MAX_SOURCE_AGE_MINUTES = 52_560_000  # ~100 years


def _emit_json(payload: dict[str, Any]) -> None:
    # default=str keeps StrEnum / unexpected values serializable rather than crashing.
    json.dump(payload, sys.stdout, default=str)
    sys.stdout.write("\n")


def _result_to_json(result: RunResult, captured: dict[str, Any]) -> dict[str, Any]:
    c = result.classification
    shape = result.shape
    outcome: CodeFixOutcome | None = captured.get("outcome")
    emitted = "outcome" in captured
    return {
        "status": "completed",
        "proposed": shape.proposed,
        "classification": {
            "routing_cell": c.routing_cell,
            "family": c.family,
            "kind": c.kind,
            "language": c.language,
            "complexity": c.complexity,
            "risk": c.risk,
            "min_tier": c.min_tier,
            "method": c.classification_method,
            "confidence": c.confidence,
        },
        "governed": {
            "context_bundle_id": result.governed.get("context_bundle_id"),
            "task_intent_id": result.governed.get("task_intent_id"),
            "bundle_hash": result.governed.get("bundle_hash"),
            "freshness_band": result.governed.get("freshness_band"),
        },
        "pack_published": result.pack_published,
        "pack_publish_error": result.pack_publish_error,
        "shape": {"proposed": shape.proposed, "reason": shape.reason},
        "model_id": outcome.model_id if outcome is not None else None,
        "reward": outcome.reward if outcome is not None else None,
        "outcome_stage": outcome.stage if outcome is not None else None,
        "emit": {
            "attempted": emitted,
            "skipped_no_model": bool(emitted and outcome is not None and outcome.model_id is None),
            "response": captured.get("response"),
            "error": captured.get("error"),
        },
    }


def run_self_heal(args: argparse.Namespace) -> int:
    captured: dict[str, Any] = {}

    def _on_outcome(outcome: CodeFixOutcome, response: Any, error: str | None) -> None:
        captured["outcome"] = outcome
        captured["response"] = response
        captured["error"] = error

    builder_kwargs: dict[str, Any] = {
        "context_runtime_url": args.context_runtime_url,
        "neuroforge_url": args.neuroforge_url,
        "max_source_age_minutes": args.max_source_age_minutes,
        "on_outcome": _on_outcome,
    }
    if args.dataforge_local_url:
        builder_kwargs["dataforge_url"] = args.dataforge_local_url
    runner = build_live_runner(**builder_kwargs)

    try:
        result = runner.run(
            repository=args.repo,
            repo_root=args.repo_root,
            target_file=args.target,
            raw_kind=args.raw_kind,
            secondary_raw_kinds=tuple(args.secondary_raw_kinds),
            files_changed=args.files_changed,
            lines_changed=args.lines_changed,
            commit_sha=args.commit,
            publish=not args.no_publish,
        )
    except Exception as exc:  # noqa: BLE001 - report, never crash the spawning tick
        _emit_json({"status": "error", "stage": "run", "error": f"{type(exc).__name__}: {exc}"})
        return 1

    _emit_json(_result_to_json(result, captured))
    return 3 if captured.get("error") else 0


def _read_input(path: str | None) -> str:
    if path:
        with open(path, encoding="utf-8") as handle:
            return handle.read()
    return sys.stdin.read()


def run_self_heal_feed(args: argparse.Namespace) -> int:
    """Resolve caller-supplied admitted signals to targets and run the fix loop per target.

    Input (``--input`` file or stdin): ``{"items": [{source_ref, node, gate_allowed, repo_root}]}``.
    The caller (Forge_Command's tick) reads lineage nodes from DataForge-Local, supplies the
    ForgeMath gate decision per candidate, and resolves ``repo_root`` from the registry repo-map.
    """
    try:
        doc = json.loads(_read_input(args.input))
    except Exception as exc:  # noqa: BLE001 - report, never crash the tick
        _emit_json({"status": "error", "stage": "parse", "error": f"{type(exc).__name__}: {exc}"})
        return 1

    items = doc.get("items") if isinstance(doc, dict) else doc
    if not isinstance(items, list):
        _emit_json({"status": "error", "stage": "input", "error": "expected {\"items\": [...]} or a JSON list"})
        return 1

    builder_kwargs: dict[str, Any] = {
        "context_runtime_url": args.context_runtime_url,
        "neuroforge_url": args.neuroforge_url,
        "max_source_age_minutes": args.max_source_age_minutes,
    }
    if args.dataforge_local_url:
        builder_kwargs["dataforge_url"] = args.dataforge_local_url
    runner = build_live_runner(**builder_kwargs)

    feed = run_feed(items, runner=runner, publish=not args.no_publish)

    ran_json = []
    for item in feed.ran:
        entry: dict[str, Any] = {
            "source_ref": item.source_ref,
            "repository": item.repository,
            "target_file": item.target_file,
            "ran": item.ran,
            "error": item.error,
        }
        shape = getattr(item.result, "shape", None)
        if shape is not None:
            entry["proposed"] = getattr(shape, "proposed", None)
        ran_json.append(entry)

    _emit_json(
        {
            "status": "completed",
            "counts": {
                "ran": sum(1 for r in feed.ran if r.ran),
                "failed": sum(1 for r in feed.ran if not r.ran),
                "skipped": len(feed.skipped),
            },
            "ran": ran_json,
            "skipped": [{"id": ident, "reason": reason} for ident, reason in feed.skipped],
        }
    )
    # The batch completed; per-target failures are reported in-band (exit 0) so a single
    # bad target never masks the rest. A hard input/build failure already returned 1 above.
    return 0


def run_cloud_propose(args: argparse.Namespace) -> int:
    """Shape + publish one cloud-subject proposal end to end.

    Input (``--input`` file or stdin): the CloudProposalInput fields as JSON —
    service, environment, title, issueClass, problemStatement, evidenceSummary,
    scopeSummary, recommendedAction, expectedGain, riskSummary, severity,
    confidenceBand, alternatives, diagnosticArtifactIds. No signal-derived
    detection exists yet (see cloud_proposal_shaper.py's module docstring) —
    the caller composes the content; this command shapes and publishes it.
    """
    try:
        doc = json.loads(_read_input(args.input))
    except Exception as exc:  # noqa: BLE001 - report, never crash the caller
        _emit_json({"status": "error", "stage": "parse", "error": f"{type(exc).__name__}: {exc}"})
        return 1
    if not isinstance(doc, dict):
        _emit_json({"status": "error", "stage": "input", "error": "expected a JSON object"})
        return 1

    try:
        proposal_input = CloudProposalInput(
            subject=CloudSubject(
                service=doc.get("service", ""),
                environment=doc.get("environment", "production"),
            ),
            title=doc.get("title", ""),
            issue_class=doc.get("issueClass", ""),
            problem_statement=doc.get("problemStatement", ""),
            evidence_summary=doc.get("evidenceSummary", ""),
            scope_summary=doc.get("scopeSummary", ""),
            recommended_action=doc.get("recommendedAction", ""),
            expected_gain=doc.get("expectedGain", ""),
            risk_summary=doc.get("riskSummary", ""),
            severity=doc.get("severity", "low"),
            confidence_band=doc.get("confidenceBand", "medium"),
            alternatives=list(doc.get("alternatives", [])),
            diagnostic_artifact_ids=list(doc.get("diagnosticArtifactIds", [])),
        )
    except Exception as exc:  # noqa: BLE001 - malformed input, report don't crash
        _emit_json({"status": "error", "stage": "build_input", "error": f"{type(exc).__name__}: {exc}"})
        return 1

    proposal = CloudProposalShaper().shape(proposal_input)
    if proposal is None:
        _emit_json(
            {
                "status": "error",
                "stage": "shape",
                "error": "missing required field: service, title, or problemStatement",
            }
        )
        return 1

    envelope = to_cloud_proposal_envelope(proposal)
    if args.no_publish:
        _emit_json({"status": "shaped", "published": False, "envelope": envelope})
        return 0

    try:
        response = publish_healing_proposal(envelope, dataforge_url=args.dataforge_local_url)
    except Exception as exc:  # noqa: BLE001 - report, never crash the caller
        _emit_json(
            {
                "status": "error",
                "stage": "publish",
                "error": f"{type(exc).__name__}: {exc}",
                "event_id": proposal.event_id,
            }
        )
        return 1

    _emit_json({"status": "completed", "published": True, "response": response})
    return 0


def run_ci_shadow_cmd(args: argparse.Namespace) -> int:
    """Read-only: fetch real failed GitHub runs, push them through the detector
    pipeline, print a yield report. Publishes nothing."""
    report = run_ci_shadow(
        args.repo,
        producer_version="ci-shadow-1",
        per_page=args.per_page,
        max_age_days=args.max_age_days or None,
    )
    _emit_json({"status": "ok", "mode": "shadow", **report.to_dict()})
    # Non-zero only when EVERY repo failed to fetch -- partial data is still data.
    return 1 if report.errors and len(report.errors) == len(report.repositories) else 0


def run_health(_args: argparse.Namespace) -> int:
    """Bounded, producer-owned self-check for the ecosystem-health topology.

    forgeHQ is a CLI producer with no HTTP surface, so this is how a downstream consumer
    (ForgeCommand's `/ecosystem-health`) gets a *real* health signal rather than a fabricated one.
    Verifies the core self-healing building blocks import; reports an honest ok/degraded status.
    Stdlib-only; prints one JSON object to stdout. Exit 0 = ok, 1 = degraded.
    """
    import importlib
    from datetime import datetime, timezone

    checks: dict[str, str] = {}
    status = "ok"
    for label, module in (
        ("self_healing_runner", "app.services.self_healing_runner"),
        ("code_fix_shaper", "app.services.code_fix_shaper"),
        ("cloud_proposal_shaper", "app.services.cloud_proposal_shaper"),
        ("signal_target_resolver", "app.services.signal_target_resolver"),
        ("healing_publisher", "app.drivers.healing_publisher"),
    ):
        try:
            importlib.import_module(module)
            checks[label] = "ok"
        except Exception as exc:  # noqa: BLE001
            checks[label] = f"error: {type(exc).__name__}"
            status = "degraded"

    try:
        version = importlib.metadata.version("forgehq")
    except Exception:  # noqa: BLE001
        version = "unknown"

    _emit_json(
        {
            "service": "forgeHQ",
            "status": status,
            "version": version,
            "role": "self-healing shaper (CLI producer; no HTTP surface)",
            "checks": checks,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    return 0 if status == "ok" else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="app", description="forgeHQ operational entrypoints.")
    sub = parser.add_subparsers(dest="command", required=True)

    sh = sub.add_parser("self-heal", help="Run one self-healing fix end to end.")
    sh.add_argument("--repo", required=True, help="Repository id (logical name).")
    sh.add_argument("--repo-root", required=True, help="Absolute path to the repo working tree.")
    sh.add_argument("--target", required=True, help="Target file to heal (repo-relative).")
    sh.add_argument("--raw-kind", default="", help="Raw signal kind hint for classification.")
    sh.add_argument(
        "--secondary-raw-kind",
        action="append",
        default=[],
        dest="secondary_raw_kinds",
        help="Additional raw kind (repeatable).",
    )
    sh.add_argument("--files-changed", type=int, default=None)
    sh.add_argument("--lines-changed", type=int, default=None)
    sh.add_argument("--commit", default="unknown", help="Commit sha for provenance.")
    sh.add_argument("--no-publish", action="store_true", help="Shape + emit but do not publish.")
    sh.add_argument(
        "--context-runtime-url",
        default=os.getenv("FORGEHQ_CONTEXT_RUNTIME_URL", DEFAULT_CONTEXT_RUNTIME_URL),
    )
    sh.add_argument("--dataforge-local-url", default=os.getenv("FORGEHQ_DATAFORGE_LOCAL_URL"))
    sh.add_argument(
        "--neuroforge-url",
        default=os.getenv("FORGEHQ_NEUROFORGE_URL", DEFAULT_NEUROFORGE_URL),
    )
    sh.add_argument(
        "--max-source-age-minutes",
        type=int,
        default=int(os.getenv("FORGEHQ_MAX_SOURCE_AGE_MINUTES", str(DEFAULT_MAX_SOURCE_AGE_MINUTES))),
    )
    sh.set_defaults(func=run_self_heal)

    shf = sub.add_parser(
        "self-heal-feed",
        help="Resolve admitted signals (forge-eval evidence bundles) to targets and run the fix loop per target.",
    )
    shf.add_argument(
        "--input",
        default=None,
        help='JSON: {"items":[{source_ref,node,gate_allowed,repo_root}]} (default: stdin).',
    )
    shf.add_argument("--no-publish", action="store_true", help="Shape + emit but do not publish.")
    shf.add_argument(
        "--context-runtime-url",
        default=os.getenv("FORGEHQ_CONTEXT_RUNTIME_URL", DEFAULT_CONTEXT_RUNTIME_URL),
    )
    shf.add_argument("--dataforge-local-url", default=os.getenv("FORGEHQ_DATAFORGE_LOCAL_URL"))
    shf.add_argument(
        "--neuroforge-url",
        default=os.getenv("FORGEHQ_NEUROFORGE_URL", DEFAULT_NEUROFORGE_URL),
    )
    shf.add_argument(
        "--max-source-age-minutes",
        type=int,
        default=int(os.getenv("FORGEHQ_MAX_SOURCE_AGE_MINUTES", str(DEFAULT_MAX_SOURCE_AGE_MINUTES))),
    )
    shf.set_defaults(func=run_self_heal_feed)

    cp = sub.add_parser(
        "cloud-propose",
        help="Shape + publish one cloud-subject proposal (no local file target).",
    )
    cp.add_argument(
        "--input",
        default=None,
        help="JSON: CloudProposalInput fields (default: stdin).",
    )
    cp.add_argument("--no-publish", action="store_true", help="Shape + emit but do not publish.")
    cp.add_argument(
        "--dataforge-local-url",
        default=os.getenv("FORGEHQ_DATAFORGE_LOCAL_URL", DEFAULT_DATAFORGE_LOCAL_URL),
    )
    cp.set_defaults(func=run_cloud_propose)

    ci = sub.add_parser(
        "ci-shadow",
        help="Read real failed GitHub Actions runs through the detector pipeline; publish nothing.",
    )
    ci.add_argument(
        "--repo", action="append", required=True, metavar="OWNER/NAME",
        help="Repository to read (repeatable).",
    )
    ci.add_argument("--per-page", type=int, default=30, help="Runs per repo, 1-100.")
    ci.add_argument(
        "--max-age-days", type=int, default=14,
        help="Skip failures older than this many days (0 = no limit).",
    )
    ci.set_defaults(func=run_ci_shadow_cmd)

    hp = sub.add_parser("health", help="Bounded self-check for the ecosystem-health topology.")
    hp.set_defaults(func=run_health)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
