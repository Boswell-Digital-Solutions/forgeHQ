# §18 — Configuration & Environment

The current repo does not define service-runtime environment variables because no service runtime is implemented yet.
One optional QA tooling override is supported for test-runner discovery.

### 5.1 Environment Variables

| Variable | Type | Default | Reader | Status |
| --- | --- | --- | --- | --- |
| `PYTEST_RUNNER` | path string | auto-detected | `scripts/qa-mode-a-preflight.sh`, `scripts/qa-regression-smoke.sh` | Optional override for the pytest executable |

### 5.2 Operational Commands

| Command | Purpose |
| --- | --- |
| `python3 -m pytest` | Run repo tests when `pytest` is installed locally |
| `doc/system/BUILD.sh` | Rebuild root `SYSTEM.md` |
| `scripts/context-bundle.sh --list` | Show selective doc-loading options |
| `scripts/qa-mode-a-preflight.sh` | Execute Mode A T0 QA checks for current repo maturity |
| `scripts/qa-regression-smoke.sh` | Run the lightweight regression smoke suite |

### 5.3 Configuration Posture

- Service runtime configuration is intentionally absent until a service slice exists.
- QA tooling may use `PYTEST_RUNNER` to pin a specific pytest executable while the repo remains environment-light.
- When service configuration appears later, every variable must be documented here with type, default, and owner.
