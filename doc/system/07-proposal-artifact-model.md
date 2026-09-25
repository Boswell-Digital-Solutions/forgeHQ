# §7 — Proposal Artifact Model

forgeHQ artifact vocabulary is implemented as explicit enum-backed families.
Every current artifact family is non-authoritative by posture,
and Phase 1 schema stubs provide typed placeholder models for the required artifact set.

### 13.1 Artifact Families

| Artifact family | Required for reviewability backbone | Purpose |
| --- | --- | --- |
| `signal_snapshot` | yes | admitted source signals and source refs |
| `intake_diagnostics` | no | signal-intake diagnostics |
| `target_ranking` | yes | governed improvement-target ranking |
| `ranking_factor_trace` | no | explainability trace for ranking factors |
| `context_bundle` | yes | bounded single-target context |
| `candidate_design` | yes | bounded change hypothesis |
| `candidate_patch` | yes | generated candidate change |
| `falsification_report` | yes | independent challenge artifact |
| `candidate_verification` | yes | observed gain and residual weakness |
| `confidence_shaping_summary` | yes | non-authoritative confidence summary |
| `forgehq_proposal` | yes | human-review package |
| `forgehq_evidence_bundle` | no | optional supporting evidence bundle |

### 13.2 Lineage Layers

| Layer | Meaning |
| --- | --- |
| `deterministic_evidence` | upstream evidence lineage |
| `non_authoritative_proposal` | forgeHQ proposal lineage |
| `operator_decision` | downstream human decision lineage |

### 13.3 Artifact Law

Missing any required backbone artifact forces `not_reviewable`.
