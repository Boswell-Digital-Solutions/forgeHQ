# Known Issues — forgeHQ

Findings tracked per the ecosystem-wide findings protocol (`forge/CLAUDE.md`): a bug, root
cause, gap, or open process/tracking state, recorded here rather than only in chat or memory.

## 2026-09-29 — `tests/contract/test_documentation_protocol.py` asserts the pre-migration
`doc/system/` shape; four tests fail against current, correct output (Fixed, pending merge)

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

**Fix (pending merge):** The four assertions now match the current convention: the compiled
reference is `doc/FRGSYSTEM.md`; the TOC check looks for each `| §N | \`NN-name.md\` |` row; and
the build test checks `BUILD_OK designation=FRG output=doc/FRGSYSTEM.md parts=N` with `N` counted
from the chapter files instead of a fixed string. Two tests were renamed to say what they check
(`test_compiled_system_doc_matches_modular_documentation_sources`,
`test_build_script_reassembles_compiled_system_doc_successfully`). No `doc/system/` change was
needed. Checked that the fixed tests still fail on drift: a stale compiled doc and a missing TOC
row are both caught.

**Scope:** Closed once merged, for these four tests. `CLAUDE.md` pointed at a root `SYSTEM.md`; it now points at
`doc/FRGSYSTEM.md`. Open: `FORGEHQ_COMPREHENSIVE_TEST_PLAN.md` still says it was generated from
`SYSTEM.md` v1.2 (2026-04-03) and that the build reports `SYSTEM.md assembled`. It is a dated
planning document, so it was not rewritten here.

## 2026-09-29 — `tests/pipeline/test_pact_verification_bridge.py::test_grounding_refs_conform_to_real_pact_schema` fails on a fresh `.venv` (Fixed, pending merge)

**What's wrong:** `ModuleNotFoundError: No module named 'jsonschema'`.

**Root cause:** `jsonschema` is not declared as a dependency (or not installed) in this repo's
`.venv`, but this one test imports it directly to validate a grounding-ref payload against a real
PACT schema.

**Fix (pending merge):** `jsonschema==4.26.0` is pinned in `requirements.txt`, marked test-only. The test now
runs and passes rather than being skipped. Verified in a fresh virtualenv built only from
`requirements.txt`, not just the project `.venv`.

**Scope:** Closed once merged.

## 2026-09-29 — `httpx` is imported at runtime but was never declared; `tests/lineage/` could not be collected (Fixed, pending merge)

**What's wrong:** `app/lineage/reviewability.py` imports `httpx` at module level, and
`tests/lineage/_lineage_harness.py` uses it. `requirements.txt` declared only `pytest`. In a
fresh `.venv`, `tests/lineage/test_forgehq_emitter.py` failed at collection with
`ModuleNotFoundError: No module named 'httpx'`.

**Also worth knowing:** This was never recorded. Every earlier full-suite run in this file's
history reported "5 pre-existing failures" while passing `--ignore=tests/lineage/test_forgehq_emitter.py`,
so the real count was five failures plus one collection error, and the ignored module's tests were
never run in those counts.

**Root cause:** `httpx` was installed ad hoc in some environments and never added to the
dependency file. It is a runtime dependency of the app, not only of tests.

**Fix (pending merge):** `httpx==0.28.1` is pinned in `requirements.txt`. Verified in a fresh
virtualenv built only from `requirements.txt`: the full suite runs with nothing ignored, 613 passed, 1 skipped, 0 failed. The skip is
`test_live_pact_verification_is_bundle_bound`, which needs a live PACT bundle.

**Scope:** Closed once merged. The lineage SDK is a sibling checkout on `sys.path`
(`contracts/forge_lineage/sdk`), not an installable package, so it is not in `requirements.txt`.

## CI Shadow Run Cannot See Recovery, Branch Scope, or `startup_failure` (Fixed in PR #25, pending merge; found 2026-09-29)

**What is wrong:** `python -m app ci-shadow` reads only runs with conclusion `failure`. Three real defects follow.

1. **No recovery check.** A failure that later cleared still shows as an active group. Live check on 2026-09-29: the shadow run flagged `Forge CLI Quality Gate` in `Forge_Command` (4 failures inside the 14-day window). That workflow's newest run is a success from 2026-09-24.
2. **No branch scope.** A failed run on a throwaway PR branch counts as a repository-level signal. The one failure I inspected (run `35825913344`, 2026-09-23) was on the PR branch `Boswecw-patch-1`. Recovery must therefore be judged per branch, not per repository. A success on `main` does not clear a failed PR branch.
3. **`startup_failure` is invisible.** Every run listed on `Forge_Command` at 2026-09-29T18:51Z had conclusion `startup_failure`. `github_workflow_adapter.py` rejects any conclusion other than `failure`, and the `status=failure` filter in `github_actions_client.py` never fetches it. So the shadow run showed a stale, cleared failure and missed the problem that is happening now. The forge workspace records the cause as the Actions billing lock (KI-FORGE-20260927-002); I did not re-verify that cause.

**Root cause:** The adapter was scoped to "a completed run that failed" as the one unambiguous case (CSD-06), and the driver fetches only that slice. Recovery and `startup_failure` both need the full recent run history, not only the failures.

**Fix (PR #25, not yet merged):** The driver now fetches recent runs of every conclusion (no `status=failure` filter). The adapter handles `startup_failure` as its own issue class, `ci_startup_failure`, scoped to the repository. It does not require a name or branch for that conclusion, and its summary says only that the run did not start. Code failures are scoped to repository, workflow and branch. The shadow run skips and counts a failure that a later success in the same scope has cleared. For `failure` the scope is the same workflow and branch. For `startup_failure` it is the whole repository, since a later success on any branch shows that runs can start again. `ci_startup_failure` has composer and translator templates. The recommendation lists what to check and does not assert a cause.

**Verified live (read-only, 2026-09-29):** The stale `Forge CLI Quality Gate` group is gone. The run now reports one repo-wide `ci_startup_failure` group for `Forge_Command` (85 runs) and one for `forge` (100 runs). `forgeHQ` has no workflow runs at all, so it reports nothing.

**Scope (open):**
- The driver reads at most 100 runs per repository. `forge`'s newest 100 are all `startup_failure`, back to 2026-09-26, so 100 is a lower bound.
- The cause of the `startup_failure` runs was not verified here. The forge workspace records it as the Actions billing lock (KI-FORGE-20260927-002). The detector deliberately asserts no cause.
- Suppression read (PR #26, pending merge): the shadow run now reads DataForge-Local (read-only GET) and the gate answers DUPLICATE for a fingerprint with an open proposal and SUPPRESSED for one an operator decided within 14 days. Published proposals now carry `correlationFingerprint`. Still open: (1) proposals published before that field cannot suppress anything, and the two now in the store are such cases; (2) RESOLVED in the publish PR (#27): the first two fingerprinted proposals were published on 2026-09-29 and the next run reported them as duplicates and published nothing; (3) the cooldown is a fixed window, and "the condition has materially changed, so propose again" is not judged; (4) RESOLVED in #27: a detector-made proposal's `event_id` is keyed on subject, issue class, fingerprint and generation, never the title, and a recurrence after the cooldown takes the next generation as a new row; hand-composed proposals keep the title-keyed id; (5) each status listing is capped at 200 rows and a full page is flagged, not hidden.
- GitHub's run list returned different sets for one repository between two invocations minutes apart, cause not established. Treat one run as a snapshot.

## CI Publish: First Real Proposals Published; Readability Polish Open (2026-09-29)

**What happened:** `python -m app ci-publish --confirm-publish` published two `ci_startup_failure` proposals to DataForge-Local for operator review: `Forge_Command` (85 runs) and `forge` (100 runs). Forge_Command's intake ingested both. The command is a dry run without `--confirm-publish`, sends at most 3 proposals per run, and refuses to run if it cannot read the store or a listing is truncated.

**Open:**
- The problem statement repeats one sentence with a different run id up to five times. It is factual but noisy for a repo-wide condition. A start-of-incident summary would read better.
- The published `service` field shows `repository:<owner>/<name>`, the identity-key fallback, because the wire field is still named `service`.
- Nothing runs this on a schedule. It runs only when an operator invokes it.
- The cause of the underlying `startup_failure` runs is unverified (KI-FORGE-20260927-002 records the billing lock). The proposals name no cause.
