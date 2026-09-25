# §3 — Project Structure

The current repo structure is intentionally narrow.
It reflects a contract-first bootstrap rather than a full service implementation.

### 4.1 Directory Layout

```text
forgeHQ/
├── AGENTS.md
├── FORGEHQ_COMPREHENSIVE_TEST_PLAN.md
├── app/
│   ├── __main__.py          # `python -m app` -> producer CLI
│   ├── cli.py               # producer entrypoint (self-heal); spawned by ForgeCommand
│   ├── domain/
│   │   ├── artifacts/
│   │   ├── pipeline/
│   │   ├── reviewability/
│   │   ├── signals/
│   │   └── workers/
│   ├── drivers/             # live edges (learning/context/pact/publish clients)
│   ├── orchestration/
│   ├── persistence/
│   ├── read_models/
│   ├── schemas/
│   └── services/            # incl. self_healing_runner.build_live_runner
├── doc/
│   └── system/
├── docs/
│   ├── architecture/
│   ├── audits/
│   ├── contracts/
│   ├── qa/
│   └── reference/bds/
├── scripts/
├── tests/
│   ├── contract/
│   ├── pipeline/
│   ├── read_models/
│   └── workers/
├── CLAUDE.md
├── SYSTEM.md
├── pytest.ini
└── requirements.txt
```

### 4.2 File Naming Rules

| Surface | Rule |
| --- | --- |
| Domain enums | `enums.py` inside bounded domain folders |
| Schema stubs | one artifact or run model per file under `app/schemas/` |
| Orchestration | router/orchestrator modules under `app/orchestration/` |
| Contract tests | `test_*.py` under `tests/contract/` or related slices |
| System docs | numbered files under `doc/system/` |
| Imported doctrine references | `docs/reference/bds/` |
| QA support docs | `docs/qa/` |
| Root system reference | generated `SYSTEM.md` |
| Root QA plan | `FORGEHQ_COMPREHENSIVE_TEST_PLAN.md` |
| Repo instructions | root `CLAUDE.md` |
| QA scripts | `scripts/qa-*.sh` |

### 4.3 Generated Files

| File | Generation source |
| --- | --- |
| `SYSTEM.md` | `doc/system/_index.md` plus numbered part files via `doc/system/BUILD.sh` |
| `context-bundle.md` | selected documentation sections via `scripts/context-bundle.sh` |
