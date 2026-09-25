# §14 — Ecosystem Integration

*Last updated: 2026-06-10 (producer entrypoint + NeuroForge model-learning edge)*

forgeHQ exists inside a larger BDS ecosystem. Upstream boundaries remain declared-only.
ForgeCommand now has implemented read models; the wire adapter is pending.
DataForge persistence uses in-memory stubs; the wire adapter is pending. The live
self-healing drivers (`learning_client`, `context_client`, `context_pack_publisher`,
`healing_publisher`) call NeuroForge / context-runtime / DataForge-Local directly.

### 10.1 Boundary Table

| System | Relationship | Current status |
| --- | --- | --- |
| ForgeEval | Upstream evidence substrate | Declared boundary; `forgeeval://` scheme admitted by `SignalIntakeService` |
| ForgeMath | Upstream math/rule authority where adopted | Declared boundary; `forgemath://` scheme admitted by `SignalIntakeService` |
| DataForge | Downstream persistence, lineage, rollback linkage | In-memory stubs implemented (`ArtifactRegistry`, `LineageRepository`, `ProposalRepository`); wire adapter pending |
| ForgeCommand | Downstream review surface and operator action state | Read models implemented; **also the producer trigger** — its self-healing tick spawns the `python -m app self-heal` entrypoint and injects the NeuroForge ingest key |
| NeuroForge | Downstream model-learning ingest (Category-Champion) | `learning_client` POSTs a `CodeFixOutcome` to `POST /api/v1/learning/model-outcome` (service-authenticated; fail-soft side-channel) |

### 10.2 Integration Laws

- forgeHQ may consume upstream artifacts but may not overwrite upstream truth
- forgeHQ proposals remain non-authoritative even after packaging
- operator action state belongs downstream and stays separate from proposal lifecycle state
- the learning emit is a non-authoritative side-channel: an ingest failure (down/401) is
  reported, never fatal to the propose path

### 10.3 Producer Entrypoint

`python -m app self-heal --repo <id> --repo-root <path> --target <file>` (see `app/cli.py`)
runs one fix end to end via `build_live_runner` — classify → governed context → publish
pack → generate (NeuroForge ladder, model captured) → pact-verify → emit `CodeFixOutcome`
→ propose — and prints a structured JSON result for the caller to capture as evidence. It
reads `NEUROFORGE_API_KEY` from the environment (ForgeCommand injects it at spawn, so the
secret never lands in a forgeHQ file). Exit codes: `0` ran (emit ok/skipped), `1` hard
failure (run raised), `3` ran but the learning emit failed (e.g. 401 ingest key).

`python -m app self-heal-feed` (feed plan **P4b**) runs the fix loop from *real signals*
instead of a hand-named target. Input (`--input` file or stdin):
`{"items":[{source_ref, node, gate_allowed, repo_root}]}` — ForgeCommand's tick reads
forge-eval evidence-bundle lineage nodes from DataForge-Local, supplies the ForgeMath
`proposal_candidate_allowed` gate per candidate, and resolves `repo_root` from the registry
repo-map. `app/services/signal_target_resolver.py` (Tier-A) maps each gated evidence-bundle
node → one `(repository, target_file, raw_kind)` per evaluated file (`input_contract.target_refs[]`),
and `app/services/self_healing_feed.py` runs `SelfHealingRunner` per target. Transport-free,
fail-closed (ungated / no-file / no-repo_root signals are skipped with a recorded reason);
prints a JSON batch summary (`ran` / `skipped` with reasons). forgeHQ never derives local
paths — `repo_root` is caller-supplied.

**Tier-B (P4b-2) — downstream lineage walk.** For a seed node that carries no file
(e.g. a `forge_eval_run` summarising many files), `resolve_via_downstream_walk` walks the
caller-supplied bounded **downstream** subgraph along allowlisted `ImpactEdge.v1` edge types
(`produced`, the real `forge_eval_run --produced--> forge_eval_evidence_bundle` edge) to the
evidence-bundle node(s) that DO carry `(repo, file)`, then delegates each to Tier-A. Downstream-only
matches DataForge-Local's traversal direction. A Tier-B feed item additionally supplies
`subgraph_nodes` + `subgraph_edges` and `gate_by_node_id` (the ForgeMath gate per bundle, missing =
fail-closed); a bundle seed delegates straight to Tier-A. Bounded (`max_hops`/`max_nodes`, cycle-safe)
and fail-closed: a seed that reaches no bundle is skipped with `no_walk_path` (fully explored) or
`walk_budget_exhausted` (bound hit first), never a guessed file. Resolved targets are tagged
`resolution="walked"` for honest provenance. (FC-side wiring of Tier-B subgraphs into its tick is a
follow-up; today the live tick seeds bundle nodes directly = Tier-A.)
