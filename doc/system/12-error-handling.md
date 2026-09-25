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
