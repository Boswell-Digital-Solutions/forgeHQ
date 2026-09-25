# forgeHQ — Compiled System Reference

**Designation:** FRG
**Document role:** Canonical compiled technical reference for the forgeHQ proposal-shaping service
**Source:** `doc/system/`
**Build command:** `bash doc/system/BUILD.sh`
**Document version:** 2.0 (2026-06-19) — BDS canonical-compliance migration (7-group class-aware structure, truth classes, designation-bound fail-closed assembly, authored governance trio)
**Protocol:** BDS Documentation Protocol v2.0; BDS Repo Documentation System Canonical Compliance Standard

> **Generated artifact warning:** `doc/FRGSYSTEM.md` is assembled output. Edit the
> source modules under `doc/system/` and rebuild. Hand edits to the compiled
> artifact are overwritten by the next build.

Assembly contract:

- Command: `bash doc/system/BUILD.sh`
- Validation: `bash doc/system/validate_snapshots.sh` runs during assembly
- Primary output: `doc/FRGSYSTEM.md`

This `doc/system/` tree is the canonical source of truth for forgeHQ. It uses
explicit **truth classes**: *canonical facts* define the proposal-shaping role,
artifact model, pipeline/reviewability contract, signal-intake boundaries, and
ecosystem contracts; *snapshot facts* are dated, audit-derived counts (routes,
tables, tests). forgeHQ is non-authoritative — it proposes and evaluates
candidates; it does not mint canonical truth. See §15 for the scope/authority
boundary and §16 for ownership and designation doctrine.

| Part | File | Contents |
| --- | --- | --- |
| §1 | `01-overview-philosophy.md` | Service identity, proposal-shaping role |
| §2 | `02-architecture.md` | Architecture overview |
| §3 | `03-project-structure.md` | Repository tree, module layout |
| §4 | `04-design-system.md` | Design system, brand tokens |
| §5 | `05-frontend.md` | Frontend routes/components |
| §6 | `06-api-layer.md` | API endpoints, auth |
| §7 | `07-proposal-artifact-model.md` | The shaped-proposal artifact model |
| §8 | `08-pipeline-reviewability.md` | Signal→proposal pipeline + reviewability contract |
| §9 | `09-backend.md` | Backend services |
| §10 | `10-database-schema.md` | Tables, migrations |
| §11 | `11-ai-integration.md` | AI integration |
| §12 | `12-error-handling.md` | Error handling contract |
| §13 | `13-tech-stack.md` | Dependencies, versions |
| §14 | `14-ecosystem-integration.md` | Feeder + ecosystem contracts |
| §15 | `15-scope.md` | Service authority boundary, truth classes |
| §16 | `16-governance.md` | Ownership, designation doctrine, authority hierarchy |
| §17 | `17-change-control.md` | Change classes, evidence, verification commands |
| §18 | `18-configuration.md` | Configuration and environment variables |
| §19 | `19-testing-infrastructure.md` | Testing posture |
| §20 | `20-handover-migration-notes.md` | Handover / migration notes |
| §21 | `21-appendices.md` | Glossary, cross-references, revision history |

## Quick Assembly

```bash
bash doc/system/BUILD.sh
```

---

# §1 — Overview & Philosophy

> **System identity — bds family (Boswell Digital Solutions business system, local-systems tier).** forgeHQ is a business-side proposal-and-evaluation surface in the Forge ecosystem backend (`ecosystem/local-systems`); it proposes and evaluates candidates and does not mint canonical truth.

*Last updated: 2026-04-04 (Phase 6: ForgeCommand read models and read model service added)*

forgeHQ is a backend/domain-contract repository for bounded proposal generation.
The current repo state implements the governance slice (Phase 0), the documentation
stack, a Phase 1 no-op pipeline scaffold, the Phase 2 signal intake, target ranking,
and context curation service layer, the Phase 3 design and generation slice, the
Phase 4 critic and verification slice, the Phase 5 proposal packaging and persistence
stubs, and the Phase 6 ForgeCommand integration read models.
This repository defines how forgeHQ names artifacts, stages work,
separates proposal posture from decision posture,
and advances a shaping run through bounded service-produced artifacts without
inventing live runtime semantics beyond its governed scope.

### 1.1 Core Principles

- forgeHQ is non-authoritative by design.
- Upstream truth remains with ForgeEval and ForgeMath where adopted.
- Human review remains downstream of forgeHQ proposals.
- Challenge and verification are mandatory before reviewability.
- Proposal lifecycle state never collapses into operator decision state.
- Ambiguity and scope escape fail closed.
- Documentation is part of repo truth, not a side artifact.

### 1.2 Current Product Boundary

| Area | Current status |
| --- | --- |
| Governance docs | Implemented |
| Artifact family registry | Implemented |
| Stage vocabulary | Implemented |
| Worker boundary registry | Implemented |
| Shaping run model | Implemented |
| Core artifact schema stubs | Implemented |
| Strict stage router | Implemented |
| No-op orchestrator skeleton | Implemented |
| Reviewability vocabulary | Implemented |
| Documentation assembly stack | Implemented |
| Signal authority classification (`SourceAuthorityClass`) | Implemented |
| Signal intake service (`SignalIntakeService`) | Implemented |
| Target ranking service (`TargetRankingService`) | Implemented |
| Context bundle service (`ContextBundleService`) | Implemented |
| `IntakeDiagnostics` and `RankingFactorTrace` schemas | Implemented |
| `AGENTS.md` repo doctrine file | Implemented |
| Candidate design service (`CandidateDesignService`) | Implemented |
| Candidate generation service (`CandidateGenerationService`) | Implemented |
| Falsification service (`FalsificationService`) | Implemented |
| Candidate verification service (`CandidateVerificationService`) | Implemented |
| `ChallengePosture` and `VerificationPosture` enums | Implemented |
| Proposal packaging service (`ProposalPackagingService`) | Implemented |
| Reviewability engine (`compute_reviewability`) | Implemented |
| Persistence stubs (`ArtifactRegistry`, `LineageRepository`, `ProposalRepository`) | Implemented (in-memory; DataForge wiring pending) |
| ForgeCommand read models (`ProposalQueueItem`, `ProposalDetailModel`, layered) | Implemented |
| ForgeCommand read model service (`ForgeCommandReadModelService`) | Implemented |
| API surface | Not implemented |
| UI or operator surface | Not implemented |

---

# §2 — Architecture

*Last updated: 2026-04-04 (Phases 2–6 implemented)*

The current implementation is a contract-first Python repository with a full
Phases 0–6 service layer. It does not yet expose an HTTP API or UI runtime,
but all backbone pipeline services, in-memory persistence stubs, and
ForgeCommand read models are implemented and tested.

### 2.1 Current Implemented Shape

```text
forgeHQ/
  app/domain/artifacts/
  app/domain/pipeline/
  app/domain/reviewability/
  app/domain/signals/
  app/domain/workers/
  app/schemas/
  app/orchestration/
  app/services/
  app/persistence/
  app/read_models/
  docs/architecture/
  docs/contracts/
  doc/system/
  scripts/
  tests/
```

### 2.2 Boundary Diagram

```text
ForgeEval / ForgeMath
        |
        v
   forgeHQ service layer
   (SignalIntake → Ranking → ContextBundle → Design → Generation
    → Falsification → Verification → Packaging → ReadModels)
        |
        v
DataForge (persistence — wiring pending)
        |
        v
ForgeCommand (read models implemented; API surface pending)
```

### 2.3 Architectural Posture

| Concern | Current posture |
| --- | --- |
| Upstream authority | Declared boundary; signal authority classification implemented |
| Runtime orchestration | No-op scaffold + live service layer (Phases 2–6) |
| Persistence boundary | In-memory stubs implemented; DataForge wiring pending |
| Operator review surface | Read models implemented (`ProposalQueueItem`, `ProposalDetailModel`); API pending |
| Repo documentation truth | Implemented via `doc/system/` and `SYSTEM.md` |

### 2.4 Hard Architectural Laws

- forgeHQ may consume upstream evidence but may not overwrite upstream canonical truth
- no proposal becomes reviewable without challenge and verification
- orchestrator sequencing may exist later, but orchestrator proposal authorship is forbidden
- reviewability posture must stay explicit, not inferred

---

# §3 — Project Structure

The current repo structure is intentionally narrow.
It reflects a contract-first bootstrap rather than a full service implementation.

### 4.1 Directory Layout

```text
forgeHQ/
├── AGENTS.md
├── FORGEHQ_COMPREHENSIVE_TEST_PLAN.md
├── app/
│   ├── __main__.py          # `python -m app` -> producer CLI
│   ├── cli.py               # producer entrypoint (self-heal); spawned by ForgeCommand
│   ├── domain/
│   │   ├── artifacts/
│   │   ├── pipeline/
│   │   ├── reviewability/
│   │   ├── signals/
│   │   └── workers/
│   ├── drivers/             # live edges (learning/context/pact/publish clients)
│   ├── orchestration/
│   ├── persistence/
│   ├── read_models/
│   ├── schemas/
│   └── services/            # incl. self_healing_runner.build_live_runner
├── doc/
│   └── system/
├── docs/
│   ├── architecture/
│   ├── audits/
│   ├── contracts/
│   ├── qa/
│   └── reference/bds/
├── scripts/
├── tests/
│   ├── contract/
│   ├── pipeline/
│   ├── read_models/
│   └── workers/
├── CLAUDE.md
├── SYSTEM.md
├── pytest.ini
└── requirements.txt
```

### 4.2 File Naming Rules

| Surface | Rule |
| --- | --- |
| Domain enums | `enums.py` inside bounded domain folders |
| Schema stubs | one artifact or run model per file under `app/schemas/` |
| Orchestration | router/orchestrator modules under `app/orchestration/` |
| Contract tests | `test_*.py` under `tests/contract/` or related slices |
| System docs | numbered files under `doc/system/` |
| Imported doctrine references | `docs/reference/bds/` |
| QA support docs | `docs/qa/` |
| Root system reference | generated `SYSTEM.md` |
| Root QA plan | `FORGEHQ_COMPREHENSIVE_TEST_PLAN.md` |
| Repo instructions | root `CLAUDE.md` |
| QA scripts | `scripts/qa-*.sh` |

### 4.3 Generated Files

| File | Generation source |
| --- | --- |
| `SYSTEM.md` | `doc/system/_index.md` plus numbered part files via `doc/system/BUILD.sh` |
| `context-bundle.md` | selected documentation sections via `scripts/context-bundle.sh` |

---

# §4 — Design System

forgeHQ currently has no user-facing frontend and therefore no UI design token system.
Its current design surface is documentation and contract language.

### 6.1 Documentation Style Rules

| Rule | Current posture |
| --- | --- |
| Voice | Present tense and declarative |
| Proposal posture | Explicitly non-authoritative |
| Structured data | Prefer tables for registries and contracts |
| Root truth surface | `doc/system/` plus generated `SYSTEM.md` |

### 6.2 Non-Authoritative Language

Allowed language includes:

- propose
- hypothesize
- suggest
- indicate
- candidate
- challenge

Prohibited language includes:

- approved
- confirmed fix
- proven truth
- must apply
- merge now

---

# §5 — Frontend

forgeHQ currently implements no frontend surface.

### 7.1 Current Status

| Surface | Status |
| --- | --- |
| Browser UI | Not implemented |
| Desktop UI | Not implemented |
| Operator dashboard | Not implemented in this repo |

### 7.2 Boundary Note

Human review is a downstream concern intended for ForgeCommand-facing surfaces,
not a current frontend owned by this repository.

---

# §6 — API Layer

forgeHQ currently exposes no HTTP or RPC API.

### 8.1 Current Status

| Surface | Status |
| --- | --- |
| HTTP routes | Not implemented |
| Request schemas | Not implemented |
| Auth middleware | Not implemented |
| Error response contracts | Not implemented |

### 8.2 Boundary Note

API surfaces may appear in later phases,
but no transport contract is part of the current repo truth.

---

# §7 — Proposal Artifact Model

forgeHQ artifact vocabulary is implemented as explicit enum-backed families.
Every current artifact family is non-authoritative by posture,
and Phase 1 schema stubs provide typed placeholder models for the required artifact set.

### 13.1 Artifact Families

| Artifact family | Required for reviewability backbone | Purpose |
| --- | --- | --- |
| `signal_snapshot` | yes | admitted source signals and source refs |
| `intake_diagnostics` | no | signal-intake diagnostics |
| `target_ranking` | yes | governed improvement-target ranking |
| `ranking_factor_trace` | no | explainability trace for ranking factors |
| `context_bundle` | yes | bounded single-target context |
| `candidate_design` | yes | bounded change hypothesis |
| `candidate_patch` | yes | generated candidate change |
| `falsification_report` | yes | independent challenge artifact |
| `candidate_verification` | yes | observed gain and residual weakness |
| `confidence_shaping_summary` | yes | non-authoritative confidence summary |
| `forgehq_proposal` | yes | human-review package |
| `forgehq_evidence_bundle` | no | optional supporting evidence bundle |

### 13.2 Lineage Layers

| Layer | Meaning |
| --- | --- |
| `deterministic_evidence` | upstream evidence lineage |
| `non_authoritative_proposal` | forgeHQ proposal lineage |
| `operator_decision` | downstream human decision lineage |

### 13.3 Artifact Law

Missing any required backbone artifact forces `not_reviewable`.

---

# §8 — Pipeline & Reviewability

*Last updated: 2026-04-04 (Phases 2–6 implemented)*

The current repo implements the full shaping pipeline through live service logic (Phases 2–6),
plus a Phase 1 no-op router/orchestrator for placeholder artifact progression.
All 8 pipeline stages have corresponding service implementations.

### 14.1 Stage Order

| Order | Stage | Primary owner |
| --- | --- | --- |
| 1 | `signal_intake` | `signal_analyst` |
| 2 | `target_ranking` | `signal_analyst` |
| 3 | `context_curation` | `context_curator` |
| 4 | `candidate_design` | `designer` |
| 5 | `candidate_generation` | `generator` |
| 6 | `falsification` | `critic_falsifier` |
| 7 | `verification` | `verifier` |
| 8 | `proposal_packaging` | `proposal_assembler` |

### 14.2 Reviewability Conditions

A proposal is reviewable only when all of the following are present:

- design
- candidate
- challenge
- verification
- non-authoritative notice
- explicit scope boundary statement
- valid parent refs
- no unresolved scope escape
- no broken lineage condition

### 14.3 Automatic Not-Reviewable Conditions

- missing challenge artifact
- missing verification artifact
- missing source refs
- scope escape detected
- invalid parent evidence refs
- confidence summary missing downgrade factors
- rollback class required but absent

### 14.4 Worker Boundary Law

- each worker emits only its admitted artifact families
- orchestrator emits no proposal content
- generator and critic/falsifier lanes remain structurally independent

### 14.5 Router and Service Guarantees

**Phase 1 router (stage_router.py):**
- no stages may be skipped
- candidate generation is blocked when candidate design is missing
- proposal packaging is blocked when falsification is missing
- proposal packaging is blocked when verification is missing
- invalid run histories fail closed before artifact emission

**Service layer (Phases 2–6):**
- `SignalIntakeService` — rejects unknown source ref schemes; fails closed when no source is admitted
- `TargetRankingService` — rejects placeholder snapshots; enforces deterministic 2× weighting
- `ContextBundleService` — rejects scope exceeding 50 items, duplicates, placeholder inputs
- `CandidateDesignService` — rejects placeholder bundles; locks scope boundary from context
- `CandidateGenerationService` — enforces all `modified_refs` ⊆ `context_item_refs`
- `FalsificationService` — requires at least one evaluated disconfirming check
- `CandidateVerificationService` — requires both observed gains and residual weaknesses (no-green-only)
- `ProposalPackagingService` — computes reviewability via pure `compute_reviewability()` function

---

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

---

# §10 — Database Schema

*Last updated: 2026-04-04 (in-memory persistence stubs implemented)*

forgeHQ defines no SQL schema, ORM models, or migrations.
In-memory persistence stubs are implemented for all three persistence surfaces;
DataForge wire adapters are pending.

### 11.1 Current Persistence Status

| Surface | Status |
| --- | --- |
| SQL migrations | Not implemented |
| ORM models | Not implemented |
| In-memory artifact registry | Implemented — `app/persistence/artifact_registry.py` (`ArtifactRegistry`) |
| In-memory lineage edge store | Implemented — `app/persistence/lineage_repository.py` (`LineageRepository`, `LineageEdge`) |
| In-memory proposal row store | Implemented — `app/persistence/proposal_repository.py` (`ProposalRepository`, `ProposalRow`) |
| DataForge wire adapter | Not implemented |

### 11.2 In-Memory Persistence Models

The stubs are frozen dataclasses and append-only stores — they define the persistence
structure that will be wired to DataForge, not SQL tables.

| Class | Module | Structure |
| --- | --- | --- |
| `ArtifactRegistry` | `app/persistence/artifact_registry.py` | Dict keyed by `artifact_id`; append-only; raises `ArtifactRegistryError` on duplicate |
| `LineageEdge` | `app/persistence/lineage_repository.py` | Frozen dataclass: `parent_artifact_id`, `child_artifact_id`, `relationship_type`, `run_id` |
| `LineageRepository` | `app/persistence/lineage_repository.py` | List of `LineageEdge`; queryable by artifact id |
| `ProposalRow` | `app/persistence/proposal_repository.py` | Frozen dataclass with separate `proposal_lifecycle_state` and `operator_decision_state` fields |
| `ProposalRepository` | `app/persistence/proposal_repository.py` | Dict keyed by `proposal_artifact_id`; queryable by run_id |

### 11.3 Future Boundary

When DataForge wiring is added, the in-memory stubs must be replaced with adapters
that preserve:

- deterministic evidence lineage
- non-authoritative proposal lineage
- operator decision linkage (always separate from proposal lifecycle state)

---

# §11 — AI Integration

forgeHQ currently has no runtime AI inference surface.
AI usage is limited to AI-assisted software development against the repository documentation stack.

### 12.1 Current AI Surfaces

| Surface | Status |
| --- | --- |
| Runtime model invocation | Not implemented |
| Provider routing | Not implemented |
| Prompt persistence | Not implemented |
| Dev-time context loading | Implemented via `CLAUDE.md` and `scripts/context-bundle.sh` |

### 12.2 Current AI Governance

- repo truth is assembled through `doc/system/`
- root `CLAUDE.md` defines project-specific working rules
- context bundles select bounded documentation slices for implementation work
- generated model output does not become canonical upstream truth by itself

---

# §12 — Error Handling Contract

*Last updated: 2026-04-04 (Phases 2–6 error classes documented)*

Current repo behavior is fail-closed by doctrine.
The implemented service layer raises explicit typed exceptions rather than silently
degrading or returning partial results.

### 15.1 Current Fail-Closed Conditions

| Condition | Current contract posture |
| --- | --- |
| Ambiguous system role | Reject broadening repo authority |
| Unknown signal source ref scheme | `UnknownSourceRefError` → source rejected at intake |
| All sources rejected at intake | `NoAdmittedSourcesError` raised |
| Placeholder snapshot or ranking passed to service | `RankingError` raised |
| Scope exceeds 50 items or contains duplicates | `ScopeEscapeError` raised |
| Placeholder bundle or target_id mismatch in design | `DesignError` raised |
| `modified_refs` not a subset of `context_item_refs` | `GenerationScopeError` raised |
| No disconfirming checks evaluated in falsification | `FalsificationError` raised |
| Empty measurement basis or observed gains in verification | `VerificationError` raised |
| Empty residual weaknesses in verification (green-only) | `VerificationError` raised |
| Duplicate artifact registration | `ArtifactRegistryError` raised |
| Missing backbone artifact at packaging | `PackagingError` raised |
| Missing challenge or verification for reviewability | `not_reviewable` state set |
| Proposal/operator state collapse | Forbidden by separate enums |
| Missing documentation build inputs | Build and context scripts exit non-zero |

### 15.2 Error Class Inventory

| Exception class | Module | Inherits from |
| --- | --- | --- |
| `StageTransitionError` | `app/orchestration/stage_router.py` | `ValueError` |
| `InvalidStageTransitionError` | `app/orchestration/stage_router.py` | `StageTransitionError` |
| `MissingRequiredArtifactError` | `app/orchestration/stage_router.py` | `StageTransitionError` |
| `InvalidStageEmissionError` | `app/orchestration/stage_router.py` | `StageTransitionError` |
| `SignalIntakeError` | `app/services/signal_intake_service.py` | `ValueError` |
| `UnknownSourceRefError` | `app/services/signal_intake_service.py` | `SignalIntakeError` |
| `NoAdmittedSourcesError` | `app/services/signal_intake_service.py` | `SignalIntakeError` |
| `RankingError` | `app/services/target_ranking_service.py` | `ValueError` |
| `ScopeEscapeError` | `app/services/context_bundle_service.py` | `ValueError` |
| `DesignError` | `app/services/candidate_design_service.py` | `ValueError` |
| `GenerationScopeError` | `app/services/candidate_generation_service.py` | `ValueError` |
| `FalsificationError` | `app/services/falsification_service.py` | `ValueError` |
| `VerificationError` | `app/services/candidate_verification_service.py` | `ValueError` |
| `PackagingError` | `app/services/proposal_packaging_service.py` | `ValueError` |
| `ArtifactRegistryError` | `app/persistence/artifact_registry.py` | `RuntimeError` |

### 15.3 Current Error Surface

| Surface | Current handling |
| --- | --- |
| Service layer violations | Typed exception raised immediately; no silent degradation |
| Stage router violations | Typed `StageTransitionError` subclass raised |
| Persistence violations | `ArtifactRegistryError` raised on duplicate registration |
| Bash documentation scripts | Non-zero exit with stderr message |
| Runtime API errors | Not applicable — no HTTP API exists yet |

---

# §13 — Tech Stack

The current repo uses a minimal stack because only the governance contract slice is implemented.

### 3.1 Runtime and Test Stack

| Layer | Current choice | Notes |
| --- | --- | --- |
| Language | Python 3.12 | Current local interpreter |
| Test framework | `pytest==7.4.3` | Repo contract tests |
| Shell scripting | Bash | Documentation assembly and context-bundle scripts |
| Docs format | Markdown | Canonical repo-reference format |

### 3.2 Python Standard Library Usage

| Module | Current use |
| --- | --- |
| `enum` | `StrEnum` vocabularies for bounded contracts |
| `dataclasses` | Frozen contract helpers |
| `types.MappingProxyType` | Immutable registry views |

### 3.3 Not Yet Present

| Category | Current status |
| --- | --- |
| Web framework | Not implemented |
| ORM/migrations | Not implemented |
| Database driver | Not implemented |
| Frontend framework | Not implemented |
| Runtime AI provider SDK | Not implemented |

---

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

---

# §15 — Scope

**Truth class:** canonical doctrine

This `doc/system/` tree is the modular source of the **forgeHQ compiled system
reference**, assembled into the designation-bound artifact `doc/FRGSYSTEM.md`
(designation `FRG`) via `bash doc/system/BUILD.sh`. This chapter defines forgeHQ's
service authority and where it ends. forgeHQ is an internal Forge ecosystem
service — not a public product, not a SaaS offering, and nothing here asserts
public-release or production-certification status.

## forgeHQ Service Authority

forgeHQ is a **proposal-shaping service**: it takes scheme-based signal intake
(from eval and cloud feeders) and shapes those signals into reviewable, durable
**proposal artifacts** with a clear pipeline and reviewability contract. Its
authority is shaping-oriented: it decides how a raw signal becomes a structured,
reviewable proposal, and it records that proposal's provenance — it does not
decide, approve, or apply.

## What forgeHQ Owns

- The **proposal artifact model** (§7) — the structured, durable shape a shaped
  proposal takes.
- The **pipeline + reviewability contract** (§8) — how signals flow into
  proposals and how each step stays inspectable.
- **Scheme-based signal intake** from its feeders (eval + cloud), and the
  shaping/enrichment it applies before a proposal is emitted.

## What forgeHQ Does Not Own

- **The Forge_Command self-healing / approve-apply lane.** forgeHQ is its own
  service, not the FC lane; it shapes proposals, it does not approve or apply them.
- **Decision or mutation authority.** Acceptance, application, and canonical
  mutation belong to the operator/control plane (ForgeCommand) and DataForge.
- **Durable systems memory.** Canonical durable records belong to DataForge.
- **Orchestration / scheduling.** ForgeCommand is the operator/control plane.

## Release / Readiness Language Restrictions

This documentation describes an internal service under governed development. It
must be described as a verification-current internal service, not as externally
release-certified, and must not claim public-release/SaaS readiness or present
coverage percentages as guarantees unless a later governed slice proves the claim.

## Documentation truth classes

- **Canonical facts** define forgeHQ's proposal-shaping role, the artifact model,
  the pipeline/reviewability contract, signal-intake boundaries, and ecosystem
  contracts. They change only through deliberate change control (§17).
- **Snapshot facts** are audit-derived counts (routes, tables, tests) labelled
  with a measurement date and corrected by re-measurement, not change control.

Ownership, designation doctrine, and the authority hierarchy that govern this tree
are defined in §16.

---

# §16 — Governance

**Truth class:** canonical doctrine

Ownership, review, and change-authority boundaries for this documentation system.
§15 defines forgeHQ's *service* authority; this chapter defines the
*documentation* authority that governs how this `doc/system/` tree is owned,
designated, and changed.

## Ownership

| Artifact | Owner |
|----------|-------|
| `doc/system/` source modules | forgeHQ repository (this repo) |
| `doc/FRGSYSTEM.md` compiled artifact | forgeHQ repository — generated, never hand-edited |
| `FRG` designation | ForgeCommand designation registry (governed registry state, not local repo opinion) |
| Ecosystem composite compiled system reference | ForgeCommand |

The operating context is a single-operator governed environment: compliance state
must be explicit, visible, and reconstructable; remediation is bounded and
reviewable; approval remains human-authoritative.

## Designation doctrine

- The designation is exactly three letters (`FRG`), unique across the governed
  repo registry, and stable once assigned.
- The compiled artifact filename is bound to the designation:
  `doc/{DESIGNATION}SYSTEM.md` → `doc/FRGSYSTEM.md`. `BUILD.sh` fails closed if the requested
  output path does not end in `FRGSYSTEM.md`.
- Designation changes occur only through explicit change control in the
  ForgeCommand registry, never by local edit.
- Legacy outputs (`SYSTEM.md` at repo root, two-letter prefixed artifacts, the
  bootstrap `doc/SYSTEM.md`) are non-canonical; if detected they are migration
  signals, not truth surfaces.

## Authority hierarchy

When documentation sources conflict, resolve in this order:

1. `doc/FRGSYSTEM.md` — the compiled system reference (implemented reality)
2. `CLAUDE.md` — AI implementation instructions and working rules
3. Module/feature specs and plans under `docs/`
4. README and ad-hoc notes

The compiled system reference wins because it describes implemented reality; all
other surfaces describe intent, instruction, or history.

## Truth-class enforcement

Every statement in this tree is a **canonical fact** (service role, contracts, and
invariants — changed only through change control, §17) or a **snapshot fact**
(audit-derived counts: routes, tables, tests, coverage — labelled with a
measurement date and corrected by re-measurement, not change control). Snapshot
facts must never be promoted to guarantees; release/readiness language is
constrained per §15.

## Editing rule

Source modules under `doc/system/` are the only editing surface. The compiled
artifact is regenerated by `bash doc/system/BUILD.sh` and validated by
`doc/system/validate_snapshots.sh` during assembly. A hand edit to `doc/FRGSYSTEM.md` is a
governance violation and is overwritten by the next build.

## Enforcement

ForgeCommand is the enforcement surface for documentation compliance. Where
automated enforcement is not yet wired up for this repo, enforcement is manual but
explicit: the change-control workflow in §17.

---

# §17 — Change Control

**Truth class:** canonical doctrine

This chapter defines how changes to forgeHQ are classified, evidenced, verified,
and rolled back. Every change class names the evidence and verification commands
that must accompany it. forgeHQ is an internal Forge ecosystem service; nothing
here authorizes public-release or production-certification claims.

## Change Classes

| Class | Scope | Example |
|-------|-------|---------|
| C0 | Documentation only | Editing `doc/system/` chapters, rebuilding `doc/FRGSYSTEM.md` |
| C1 | Proposal artifact model | Shape/fields of a shaped proposal (§7) |
| C2 | Pipeline / reviewability | Signal→proposal flow, inspectability contract (§8) |
| C3 | Signal intake | Scheme-based intake from eval/cloud feeders |
| C4 | API surface | Route add/change, request/response contract |
| C5 | Schema / migration | Tables, migrations for shaped proposals |
| C6 | Configuration / security | Env contract, auth, secrets |

## Required Evidence Per Change Class

- **C0** — rebuilt artifact (`bash doc/system/BUILD.sh` → `BUILD_OK`), edited
  source chapter (never a hand-edit to `doc/FRGSYSTEM.md`).
- **C1** — the artifact-model change reflected in §7 with provenance preserved.
- **C2** — evidence each pipeline step remains inspectable/reviewable (no opaque
  shaping); forgeHQ shapes, it does not decide/approve/apply.
- **C3** — the feeder scheme documented; intake stays bounded and deterministic.
- **C4** — contract tests for the new/changed route.
- **C5** — the migration applied cleanly (forward + rollback); §10 re-measured.
- **C6** — env/setting reflected in §18 (Configuration); secrets never hard-coded.

## Required Verification Commands

```bash
python -m pytest -q                     # full suite
bash doc/system/BUILD.sh                # doc changes (C0) -> BUILD_OK designation=FRG
```

## Authority / Boundary Rules

forgeHQ stays a proposal-*shaping* service (§15): a change must not give it
decision, approval, or application authority — those belong to ForgeCommand and
DataForge. Shaped proposals carry provenance and remain reviewable end-to-end.

## Documentation Change Rules (C0)

`doc/system/` source modules are the only editing surface. The compiled
`doc/FRGSYSTEM.md` is regenerated, never hand-edited (§16). Snapshot facts are
re-measured and re-dated, not asserted as guarantees.

## Release / Readiness Claim Rules

No change may introduce public-release, public-SaaS, or production-certification
language, or present a coverage percentage as a guarantee, unless a governed
release slice proves that specific claim.

---

# §18 — Configuration & Environment

The current repo does not define service-runtime environment variables because no service runtime is implemented yet.
One optional QA tooling override is supported for test-runner discovery.

### 5.1 Environment Variables

| Variable | Type | Default | Reader | Status |
| --- | --- | --- | --- | --- |
| `PYTEST_RUNNER` | path string | auto-detected | `scripts/qa-mode-a-preflight.sh`, `scripts/qa-regression-smoke.sh` | Optional override for the pytest executable |

### 5.2 Operational Commands

| Command | Purpose |
| --- | --- |
| `python3 -m pytest` | Run repo tests when `pytest` is installed locally |
| `doc/system/BUILD.sh` | Rebuild root `SYSTEM.md` |
| `scripts/context-bundle.sh --list` | Show selective doc-loading options |
| `scripts/qa-mode-a-preflight.sh` | Execute Mode A T0 QA checks for current repo maturity |
| `scripts/qa-regression-smoke.sh` | Run the lightweight regression smoke suite |

### 5.3 Configuration Posture

- Service runtime configuration is intentionally absent until a service slice exists.
- QA tooling may use `PYTEST_RUNNER` to pin a specific pytest executable while the repo remains environment-light.
- When service configuration appears later, every variable must be documented here with type, default, and owner.

---

# §19 — Testing Infrastructure

*Last updated: 2026-04-04 (Phases 2–6 test suites added)*

The current repo implements Phases 0–6, so the test suite now spans contract
coverage, full pipeline service tests, and ForgeCommand read model tests.
T0 pre-flight and T1 contract coverage remain the required gate; T3–T8 are
not yet applicable because no HTTP API or UI surface exists.

### 16.1 QA Foundation Artifacts

| Surface | Responsibility |
| --- | --- |
| `FORGEHQ_COMPREHENSIVE_TEST_PLAN.md` | spec-first test plan derived from current `SYSTEM.md` truth |
| `docs/qa/FORGEHQ_MODE_A_T0_CHECKLIST.md` | human-readable Mode A pre-flight checklist |
| `docs/qa/FORGEHQ_QA_FINDINGS_LOG_TEMPLATE.md` | findings capture template using BugCheck-style severity levels |
| `docs/qa/FORGEHQ_QA_RUN_REPORT_TEMPLATE.md` | run-report template for applicable tiers |
| `docs/qa/FORGEHQ_TIER_APPLICABILITY_MATRIX.md` | explicit T0-T8 applicability and defer rationale |
| `scripts/qa-mode-a-preflight.sh` | executable T0 checks for the current repo |
| `scripts/qa-regression-smoke.sh` | lightweight regression smoke suite |

### 16.2 Current Test Suites

| Test file | Coverage |
| --- | --- |
| `tests/contract/test_artifact_schemas.py` | non-authoritative schema defaults and shaping-run lifecycle posture |
| `tests/contract/test_governance_enums.py` | artifact families, pipeline order, language posture, lifecycle-state separation |
| `tests/workers/test_worker_emission_boundaries.py` | worker registry coverage and generator/critic separation |
| `tests/contract/test_documentation_protocol.py` | required documentation surfaces, system build parity, context-bundle behavior |
| `tests/contract/test_qa_protocol_foundation.py` | QA plan, templates, applicability matrix, and script exposure |
| `tests/pipeline/test_stage_progression.py` | valid no-op stage progression and skip rejection |
| `tests/pipeline/test_design_required_before_generation.py` | candidate-generation block when design is missing |
| `tests/pipeline/test_reviewability_requires_challenge_and_verification.py` | packaging blocks when falsification or verification are missing |
| `tests/pipeline/test_signal_intake_service.py` | admissibility classification, source-ref preservation, fail-closed on unknown schemes, non-authoritative posture |
| `tests/pipeline/test_target_ranking_service.py` | fail-closed on placeholder snapshot, composite score computation, deterministic 2× weighting, ranking trace explainability |
| `tests/pipeline/test_context_bundle_service.py` | scope policy enforcement, target_id consistency, duplicate ref rejection, non-authoritative posture |
| `tests/pipeline/test_candidate_design_service.py` | fail-closed on placeholder bundle, empty required fields, scope locking from bundle, non-authoritative posture |
| `tests/pipeline/test_candidate_generation_service.py` | design-before-generation enforcement, scope adherence, target_id consistency, non-authoritative posture |
| `tests/pipeline/test_falsification_service.py` | fail-closed on placeholders and missing evaluated checks, downgrade logic, critic lane independence |
| `tests/pipeline/test_candidate_verification_service.py` | fail-closed on empty measurement basis, no-green-only posture, verification posture computation |
| `tests/pipeline/test_proposal_packaging_service.py` | full backbone packaging, reviewability computation, lifecycle/decision separation, lineage edge persistence |
| `tests/read_models/test_forgecommand_read_models.py` | queue item shape, detail model layers (evidence/rationale/challenge/risk), approval blocking for NOT_REVIEWABLE, non-authoritative notice, lifecycle/decision separation |

### 16.3 Current Test Commands

| Command | Purpose |
| --- | --- |
| `python3 -m pytest` | Standard repo test run when local `pytest` is available |
| `doc/system/BUILD.sh` | Rebuild and verify root `SYSTEM.md` |
| `scripts/context-bundle.sh --dry-run --preset core --with-roadmap` | Verify selective context assembly inputs |
| `scripts/qa-mode-a-preflight.sh` | Run Mode A T0 checks for current repo maturity |
| `scripts/qa-regression-smoke.sh` | Run the lightweight regression smoke suite |

### 16.4 Tier Applicability

| Tier | Status | Current rationale |
| --- | --- | --- |
| T0 | Applicable now | docs build, context loading, pytest discovery, and repo tests are real current surfaces |
| T1 | Applicable now | governance, documentation, worker, schema, orchestration, and QA contracts exist |
| T2 | Not applicable yet | no UI surface exists |
| T3 | Not applicable yet | no API surface exists |
| T4/T5 | Not applicable yet | no live runtime or multi-module end-to-end flow exists |
| T6 | Limited applicability now | only tooling responsiveness is measurable today |
| T7 | Not applicable yet | no packaging or release target exists |
| T8 | Not applicable yet | no UI surface exists |

### 16.5 Test Posture

- contract and pipeline tests remain mandatory because repo semantics are contract-first
- documentation build parity remains a testable invariant
- Mode A T0 is the required QA entry gate for the current repo maturity
- regression smoke coverage is intentionally narrow and focuses on documentation plus stage-order regressions
- new repo truth requires matching documentation, QA-plan, and test updates in the same change

---

# §20 — Handover / Migration Notes

*Last updated: 2026-04-04 (Phases 0–6 complete)*

The current repo implements Phases 0–6 of the forgeHQ implementation plan.
The full 8-stage pipeline service layer, in-memory persistence stubs, and
ForgeCommand read models are implemented and tested. No HTTP API or
DataForge wire adapter exists yet.

### 17.1 Current Handover Summary

| Topic | Current truth |
| --- | --- |
| Repo maturity | Phases 0–6 complete; Phase 7 (hardening and scale-out) not started |
| Runtime capability | Full pipeline service layer (Phases 2–6); no HTTP API runtime |
| Pipeline services | All 8 stages implemented with fail-closed service classes |
| Persistence | In-memory stubs (`ArtifactRegistry`, `LineageRepository`, `ProposalRepository`); DataForge wire adapter pending |
| ForgeCommand surface | Read models and read model service implemented; HTTP API adapter pending |
| Test coverage | 159 tests passing across contract, pipeline, worker, and read model suites |
| Canonical documentation source | `doc/system/` |
| Root build artifact | `SYSTEM.md` |
| Root QA plan | `FORGEHQ_COMPREHENSIVE_TEST_PLAN.md` |
| QA support docs | `docs/qa/` |
| QA executable entrypoints | `scripts/qa-mode-a-preflight.sh`, `scripts/qa-regression-smoke.sh` |
| Selective context source | `scripts/context-bundle.sh` |
| Imported ecosystem doctrine | `docs/reference/bds/` |

### 17.2 Migration Notes

- existing governance docs in `docs/` remain valid source material and are reflected in the assembled system reference
- company-core protocols are stored as imported references under `docs/reference/bds/`, not as ambiguous repo-root files
- QA protocol compliance for current maturity now lives in the root test plan plus `docs/qa/` support artifacts
- future slices must update both `docs/` and `doc/system/` when repo truth changes
- the next phase boundary is Phase 7 (hardening and scale-out); prior to that, DataForge wiring and HTTP API surface are the natural next integration points

---

# §21 — Appendices

**Document version:** 1.0 (carry-forward)

Appendices, glossary, and cross-references.

## Unmapped legacy chapters

The following legacy chapters were carried forward but could not be
deterministically mapped to a class-aware slot. Review and place them by
hand:

- `forgeHQ — Complete System Reference`
