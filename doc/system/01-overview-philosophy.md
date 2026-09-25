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
