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
