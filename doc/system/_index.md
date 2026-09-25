# forgeHQ — Compiled System Reference

**Designation:** FRG
**Document role:** Canonical compiled technical reference for the forgeHQ proposal-shaping service
**Source:** `doc/system/`
**Build command:** `bash doc/system/BUILD.sh`
**Document version:** 2.0 (2026-06-19) — BDS canonical-compliance migration (7-group class-aware structure, truth classes, designation-bound fail-closed assembly, authored governance trio)
**Protocol:** BDS Documentation Protocol v2.0; BDS Repo Documentation System Canonical Compliance Standard

> **Generated artifact warning:** `doc/FRGSYSTEM.md` is assembled output. Edit the
> source modules under `doc/system/` and rebuild. Hand edits to the compiled
> artifact are overwritten by the next build.

Assembly contract:

- Command: `bash doc/system/BUILD.sh`
- Validation: `bash doc/system/validate_snapshots.sh` runs during assembly
- Primary output: `doc/FRGSYSTEM.md`

This `doc/system/` tree is the canonical source of truth for forgeHQ. It uses
explicit **truth classes**: *canonical facts* define the proposal-shaping role,
artifact model, pipeline/reviewability contract, signal-intake boundaries, and
ecosystem contracts; *snapshot facts* are dated, audit-derived counts (routes,
tables, tests). forgeHQ is non-authoritative — it proposes and evaluates
candidates; it does not mint canonical truth. See §15 for the scope/authority
boundary and §16 for ownership and designation doctrine.

| Part | File | Contents |
| --- | --- | --- |
| §1 | `01-overview-philosophy.md` | Service identity, proposal-shaping role |
| §2 | `02-architecture.md` | Architecture overview |
| §3 | `03-project-structure.md` | Repository tree, module layout |
| §4 | `04-design-system.md` | Design system, brand tokens |
| §5 | `05-frontend.md` | Frontend routes/components |
| §6 | `06-api-layer.md` | API endpoints, auth |
| §7 | `07-proposal-artifact-model.md` | The shaped-proposal artifact model |
| §8 | `08-pipeline-reviewability.md` | Signal→proposal pipeline + reviewability contract |
| §9 | `09-backend.md` | Backend services |
| §10 | `10-database-schema.md` | Tables, migrations |
| §11 | `11-ai-integration.md` | AI integration |
| §12 | `12-error-handling.md` | Error handling contract |
| §13 | `13-tech-stack.md` | Dependencies, versions |
| §14 | `14-ecosystem-integration.md` | Feeder + ecosystem contracts |
| §15 | `15-scope.md` | Service authority boundary, truth classes |
| §16 | `16-governance.md` | Ownership, designation doctrine, authority hierarchy |
| §17 | `17-change-control.md` | Change classes, evidence, verification commands |
| §18 | `18-configuration.md` | Configuration and environment variables |
| §19 | `19-testing-infrastructure.md` | Testing posture |
| §20 | `20-handover-migration-notes.md` | Handover / migration notes |
| §21 | `21-appendices.md` | Glossary, cross-references, revision history |

## Quick Assembly

```bash
bash doc/system/BUILD.sh
```
