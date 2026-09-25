# §9 — Backend

*Last updated: 2026-04-04 (Phases 2–6 implemented)*

The backend implements domain-contract modules, typed schema stubs, a strict stage
router, a no-op orchestrator scaffold, a full Phases 2–6 service layer, in-memory
persistence stubs, and ForgeCommand read models. No HTTP API or persistence wiring
to DataForge has been implemented yet.

### 9.1 Current Backend Modules

| Module | Files | Current responsibility |
| --- | --- | --- |
| Artifact domain | `app/domain/artifacts/enums.py` | Artifact families, lineage layers, backbone registry |
| Pipeline domain | `app/domain/pipeline/enums.py` | Stage order, stage artifacts, stage owners |
| Reviewability domain | `app/domain/reviewability/enums.py` | Reviewability requirements, lifecycle state split, language posture |
| Signals domain | `app/domain/signals/enums.py` | Source authority classification, admissibility decision |
| Worker domain | `app/domain/workers/enums.py` | Worker identities and allowed emissions |
| Schema stubs | `app/schemas/` | Typed artifact and run models for all 8 pipeline stages |
| Stage router | `app/orchestration/stage_router.py` | Fail-closed stage-order and predecessor validation |
| No-op orchestrator | `app/orchestration/forgehq_orchestrator.py` | Placeholder artifact emission in strict stage order |
| Signal intake service | `app/services/signal_intake_service.py` | Source ref admission, authority classification, fail-closed on unknowns |
| Target ranking service | `app/services/target_ranking_service.py` | Composite score with 2× deterministic weighting, ranking trace |
| Context bundle service | `app/services/context_bundle_service.py` | Bounded context curation, scope policy enforcement |
| Candidate design service | `app/services/candidate_design_service.py` | Hypothesis and oracle design, scope locking from bundle |
| Candidate generation service | `app/services/candidate_generation_service.py` | Patch generation with scope adherence enforcement |
| Falsification service | `app/services/falsification_service.py` | Independent challenge, downgrade logic, critic lane |
| Candidate verification service | `app/services/candidate_verification_service.py` | Observed gain + residual weakness, no-green-only posture |
| Signal→target resolver | `app/services/signal_target_resolver.py` | P4b Tier-A: gated forge-eval evidence-bundle node → concrete `(repository, target_file, raw_kind)`. Tier-B (P4b-2): bounded **downstream** lineage walk from a non-file seed (e.g. `forge_eval_run`) over allowlisted `produced` edges → bundle node(s) → Tier-A. Transport-free, fail-closed |
| Self-healing feed | `app/services/self_healing_feed.py` | P4b: resolve caller-supplied admitted signals (Tier-A bundle item, or Tier-B item with `subgraph_nodes`/`subgraph_edges`/`gate_by_node_id`) → run `SelfHealingRunner` per target (injectable); per-target error capture |
| Proposal packaging service | `app/services/proposal_packaging_service.py` | Full backbone packaging, reviewability computation, persistence |
| Reviewability engine | `app/services/reviewability_engine.py` | Pure 7-condition reviewability function |
| Artifact registry | `app/persistence/artifact_registry.py` | In-memory append-only artifact store |
| Lineage repository | `app/persistence/lineage_repository.py` | In-memory directed lineage edge store |
| Proposal repository | `app/persistence/proposal_repository.py` | In-memory proposal row store with lifecycle/decision separation |
| ForgeCommand read models | `app/read_models/forgecommand.py` | `ProposalQueueItem`, `ProposalDetailModel`, and 4 layer types |
| ForgeCommand read model service | `app/services/forgecommand_read_model_service.py` | Assembles queue items and detail models from backbone artifacts |

### 9.2 Pending Backend Slices

| Slice | Status |
| --- | --- |
| DataForge persistence wiring | Pending (in-memory stubs in place) |
| HTTP API surface | Not implemented |
| ForgeCommand API integration | Not implemented (read models done; API layer pending) |

### 9.3 Backend Law

The orchestrator is a bounded scaffold for placeholder progression.
Service layer logic is authoritative for Phases 2–6 pipeline semantics.
Persistence stubs use in-memory storage; DataForge wiring is the next persistence boundary step.
