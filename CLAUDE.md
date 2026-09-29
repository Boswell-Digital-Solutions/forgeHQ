# forgeHQ — Claude Code Context

Non-authoritative candidate proposal and evaluation workbench (generator / critic pipeline).
Python 3.12+, standard-library-first contracts.

Canonical reference: `doc/system/` → `doc/FRGSYSTEM.md` (`bash doc/system/BUILD.sh`).
Repo governance boundary: `docs/architecture/forgehq-system-role.md`.

---

## Authority

**forgeHQ is non-authoritative.** It proposes and evaluates candidates; it never mints canonical
upstream truth.

- ForgeEval and ForgeMath remain upstream authorities where adopted — consume their outputs, never
  overwrite them.
- DataForge is the downstream persistence boundary. Do not make forgeHQ a persistence authority.
- ForgeCommand is the downstream operator surface. **Do not collapse operator decision state into
  forgeHQ workflow state** — proposal lifecycle and operator decision are separate at both code and
  doc level.
- No merge authority, approval authority, or hidden autonomous action belongs in this repo.
- Generator and critic/falsifier lanes stay **structurally independent**.
- Fail closed on ambiguity, missing artifacts, invalid stage transitions, and scope escape.

The vocabulary is enum-defined, not prose: `app/domain/artifacts/enums.py` (artifact families and
lineage layers), `app/domain/pipeline/enums.py` (no-skip stage order),
`app/domain/reviewability/enums.py` (lifecycle vs. decision state), `app/domain/workers/enums.py`
(worker identities and emission boundaries). Contract tests guard them in `tests/contract/`,
`tests/pipeline/`, `tests/workers/`.

---

## Verification

```bash
python3 -m pytest
bash scripts/qa-regression-smoke.sh      # lightweight regression gate
```

`scripts/qa-mode-a-preflight.sh` is the gate for claiming QA readiness at the current repo
maturity. Keep the QA plan and applicability matrix honest — do not claim T2–T8 coverage before
those surfaces exist.

---

## Non-obvious

- Phase 1 orchestration in `app/orchestration/` is a **placeholder scaffold**, not a live shaping
  runtime, and `app/schemas/` holds typed non-authoritative placeholders. Do not add API,
  persistence, or orchestration logic unless the current phase calls for it.
- `docs/reference/bds/` is imported reference-only doctrine — read it, don't edit it here.

```bash
./scripts/context-bundle.sh --preset core|governance|docs
```
