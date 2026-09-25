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
