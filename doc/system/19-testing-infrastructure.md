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
