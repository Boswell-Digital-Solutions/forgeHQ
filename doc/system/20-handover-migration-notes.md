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
