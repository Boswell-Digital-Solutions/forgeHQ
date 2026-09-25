# §17 — Change Control

**Truth class:** canonical doctrine

This chapter defines how changes to forgeHQ are classified, evidenced, verified,
and rolled back. Every change class names the evidence and verification commands
that must accompany it. forgeHQ is an internal Forge ecosystem service; nothing
here authorizes public-release or production-certification claims.

## Change Classes

| Class | Scope | Example |
|-------|-------|---------|
| C0 | Documentation only | Editing `doc/system/` chapters, rebuilding `doc/FRGSYSTEM.md` |
| C1 | Proposal artifact model | Shape/fields of a shaped proposal (§7) |
| C2 | Pipeline / reviewability | Signal→proposal flow, inspectability contract (§8) |
| C3 | Signal intake | Scheme-based intake from eval/cloud feeders |
| C4 | API surface | Route add/change, request/response contract |
| C5 | Schema / migration | Tables, migrations for shaped proposals |
| C6 | Configuration / security | Env contract, auth, secrets |

## Required Evidence Per Change Class

- **C0** — rebuilt artifact (`bash doc/system/BUILD.sh` → `BUILD_OK`), edited
  source chapter (never a hand-edit to `doc/FRGSYSTEM.md`).
- **C1** — the artifact-model change reflected in §7 with provenance preserved.
- **C2** — evidence each pipeline step remains inspectable/reviewable (no opaque
  shaping); forgeHQ shapes, it does not decide/approve/apply.
- **C3** — the feeder scheme documented; intake stays bounded and deterministic.
- **C4** — contract tests for the new/changed route.
- **C5** — the migration applied cleanly (forward + rollback); §10 re-measured.
- **C6** — env/setting reflected in §18 (Configuration); secrets never hard-coded.

## Required Verification Commands

```bash
python -m pytest -q                     # full suite
bash doc/system/BUILD.sh                # doc changes (C0) -> BUILD_OK designation=FRG
```

## Authority / Boundary Rules

forgeHQ stays a proposal-*shaping* service (§15): a change must not give it
decision, approval, or application authority — those belong to ForgeCommand and
DataForge. Shaped proposals carry provenance and remain reviewable end-to-end.

## Documentation Change Rules (C0)

`doc/system/` source modules are the only editing surface. The compiled
`doc/FRGSYSTEM.md` is regenerated, never hand-edited (§16). Snapshot facts are
re-measured and re-dated, not asserted as guarantees.

## Release / Readiness Claim Rules

No change may introduce public-release, public-SaaS, or production-certification
language, or present a coverage percentage as a guarantee, unless a governed
release slice proves that specific claim.
