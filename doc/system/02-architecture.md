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
