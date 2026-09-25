# §10 — Database Schema

*Last updated: 2026-04-04 (in-memory persistence stubs implemented)*

forgeHQ defines no SQL schema, ORM models, or migrations.
In-memory persistence stubs are implemented for all three persistence surfaces;
DataForge wire adapters are pending.

### 11.1 Current Persistence Status

| Surface | Status |
| --- | --- |
| SQL migrations | Not implemented |
| ORM models | Not implemented |
| In-memory artifact registry | Implemented — `app/persistence/artifact_registry.py` (`ArtifactRegistry`) |
| In-memory lineage edge store | Implemented — `app/persistence/lineage_repository.py` (`LineageRepository`, `LineageEdge`) |
| In-memory proposal row store | Implemented — `app/persistence/proposal_repository.py` (`ProposalRepository`, `ProposalRow`) |
| DataForge wire adapter | Not implemented |

### 11.2 In-Memory Persistence Models

The stubs are frozen dataclasses and append-only stores — they define the persistence
structure that will be wired to DataForge, not SQL tables.

| Class | Module | Structure |
| --- | --- | --- |
| `ArtifactRegistry` | `app/persistence/artifact_registry.py` | Dict keyed by `artifact_id`; append-only; raises `ArtifactRegistryError` on duplicate |
| `LineageEdge` | `app/persistence/lineage_repository.py` | Frozen dataclass: `parent_artifact_id`, `child_artifact_id`, `relationship_type`, `run_id` |
| `LineageRepository` | `app/persistence/lineage_repository.py` | List of `LineageEdge`; queryable by artifact id |
| `ProposalRow` | `app/persistence/proposal_repository.py` | Frozen dataclass with separate `proposal_lifecycle_state` and `operator_decision_state` fields |
| `ProposalRepository` | `app/persistence/proposal_repository.py` | Dict keyed by `proposal_artifact_id`; queryable by run_id |

### 11.3 Future Boundary

When DataForge wiring is added, the in-memory stubs must be replaced with adapters
that preserve:

- deterministic evidence lineage
- non-authoritative proposal lineage
- operator decision linkage (always separate from proposal lifecycle state)
