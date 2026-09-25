# §15 — Scope

**Truth class:** canonical doctrine

This `doc/system/` tree is the modular source of the **forgeHQ compiled system
reference**, assembled into the designation-bound artifact `doc/FRGSYSTEM.md`
(designation `FRG`) via `bash doc/system/BUILD.sh`. This chapter defines forgeHQ's
service authority and where it ends. forgeHQ is an internal Forge ecosystem
service — not a public product, not a SaaS offering, and nothing here asserts
public-release or production-certification status.

## forgeHQ Service Authority

forgeHQ is a **proposal-shaping service**: it takes scheme-based signal intake
(from eval and cloud feeders) and shapes those signals into reviewable, durable
**proposal artifacts** with a clear pipeline and reviewability contract. Its
authority is shaping-oriented: it decides how a raw signal becomes a structured,
reviewable proposal, and it records that proposal's provenance — it does not
decide, approve, or apply.

## What forgeHQ Owns

- The **proposal artifact model** (§7) — the structured, durable shape a shaped
  proposal takes.
- The **pipeline + reviewability contract** (§8) — how signals flow into
  proposals and how each step stays inspectable.
- **Scheme-based signal intake** from its feeders (eval + cloud), and the
  shaping/enrichment it applies before a proposal is emitted.

## What forgeHQ Does Not Own

- **The Forge_Command self-healing / approve-apply lane.** forgeHQ is its own
  service, not the FC lane; it shapes proposals, it does not approve or apply them.
- **Decision or mutation authority.** Acceptance, application, and canonical
  mutation belong to the operator/control plane (ForgeCommand) and DataForge.
- **Durable systems memory.** Canonical durable records belong to DataForge.
- **Orchestration / scheduling.** ForgeCommand is the operator/control plane.

## Release / Readiness Language Restrictions

This documentation describes an internal service under governed development. It
must be described as a verification-current internal service, not as externally
release-certified, and must not claim public-release/SaaS readiness or present
coverage percentages as guarantees unless a later governed slice proves the claim.

## Documentation truth classes

- **Canonical facts** define forgeHQ's proposal-shaping role, the artifact model,
  the pipeline/reviewability contract, signal-intake boundaries, and ecosystem
  contracts. They change only through deliberate change control (§17).
- **Snapshot facts** are audit-derived counts (routes, tables, tests) labelled
  with a measurement date and corrected by re-measurement, not change control.

Ownership, designation doctrine, and the authority hierarchy that govern this tree
are defined in §16.
