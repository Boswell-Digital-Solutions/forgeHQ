# Known Issues — forgeHQ

Findings tracked per the ecosystem-wide findings protocol (`forge/CLAUDE.md`): a bug, root
cause, gap, or open process/tracking state, recorded here rather than only in chat or memory.

## 2026-09-29 — `tests/contract/test_documentation_protocol.py` asserts the pre-migration
`doc/system/` shape; four tests fail against current, correct output

**What's wrong:** `test_required_documentation_surfaces_exist`,
`test_system_md_matches_modular_documentation_sources`,
`test_index_table_of_contents_covers_all_numbered_part_files`, and
`test_build_script_reassembles_system_md_successfully` all fail on a clean checkout of `main`.

**Root cause:** `doc/system/` was migrated off the old numbered-subdirectory layout to the
canonical `<CODE>SYSTEM.md` + table-of-contents convention (`docs: migrate doc/system/ off the
retired numbered-subdirectory layout`, commit `2532fe9`), but this contract test was never
updated to match:

- The test expects a root-level `SYSTEM.md`. The real, correct build output is `doc/FRGSYSTEM.md`
  (`FRG` is forgeHQ's designation per `doc/PREFIX_REGISTRY.md`).
- The test expects the TOC in `doc/system/_index.md` as a numbered list (`1. [...]`). The real,
  correct TOC is a `| §1 | ... |` table.
- The test expects `bash doc/system/BUILD.sh`'s stdout to contain the literal string
  `"SYSTEM.md assembled:"`. The real, correct output is
  `"BUILD_OK designation=FRG output=doc/FRGSYSTEM.md parts=21 lines=1063"`.

`bash doc/system/BUILD.sh` itself succeeds and produces a correct `doc/FRGSYSTEM.md` (21 parts,
1063 lines, snapshot validation passes) — the doc system is not broken. The test asserts a shape
that no longer exists.

**Fix:** none applied. This needs the contract test's assertions updated to the current
`<CODE>SYSTEM.md` / table-TOC / `BUILD_OK ...` convention, not a doc/system change.

**Scope:** open. Found incidentally while running the full suite for the `BDS-FCO-CSD-v0.1`
(Cloud Subject Detector) slices — not touched or fixed as part of that unrelated work.

## 2026-09-29 — `tests/pipeline/test_pact_verification_bridge.py::test_grounding_refs_conform_to_real_pact_schema` fails on a fresh `.venv`

**What's wrong:** `ModuleNotFoundError: No module named 'jsonschema'`.

**Root cause:** `jsonschema` is not declared as a dependency (or not installed) in this repo's
`.venv`, but this one test imports it directly to validate a grounding-ref payload against a real
PACT schema.

**Fix:** none applied — add `jsonschema` to the repo's dependency set, or gate the import with
the same `pytest.skip("pact not available")` pattern the rest of the test already uses for a
missing PACT checkout.

**Scope:** open. Same incidental discovery as above.

## CI Shadow Run Cannot See Recovery, Branch Scope, or `startup_failure` (Open, found 2026-09-29)

**What is wrong:** `python -m app ci-shadow` reads only runs with conclusion `failure`. Three real defects follow.

1. **No recovery check.** A failure that later cleared still shows as an active group. Live check on 2026-09-29: the shadow run flagged `Forge CLI Quality Gate` in `Forge_Command` (4 failures inside the 14-day window). That workflow's newest run is a success from 2026-09-24.
2. **No branch scope.** A failed run on a throwaway PR branch counts as a repository-level signal. The one failure I inspected (run `35825913344`, 2026-09-23) was on the PR branch `Boswecw-patch-1`. Recovery must therefore be judged per branch, not per repository. A success on `main` does not clear a failed PR branch.
3. **`startup_failure` is invisible.** Every run listed on `Forge_Command` at 2026-09-29T18:51Z had conclusion `startup_failure`. `github_workflow_adapter.py` rejects any conclusion other than `failure`, and the `status=failure` filter in `github_actions_client.py` never fetches it. So the shadow run showed a stale, cleared failure and missed the problem that is happening now. The forge workspace records the cause as the Actions billing lock (KI-FORGE-20260927-002); I did not re-verify that cause.

**Root cause:** The adapter was scoped to "a completed run that failed" as the one unambiguous case (CSD-06), and the driver fetches only that slice. Recovery and `startup_failure` both need the full recent run history, not only the failures.

**Fix:** None applied. Fetch recent runs of every conclusion, keyed by (repository, workflow, branch). Treat a later success on the same branch as recovery. Decide how `startup_failure` maps to an issue class before publishing anything.

**Scope:** Open. Shadow mode publishes nothing, so no operator has seen a wrong entry. Publishing CI proposals must wait for this fix.
