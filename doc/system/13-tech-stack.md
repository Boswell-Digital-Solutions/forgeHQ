# §13 — Tech Stack

The current repo uses a minimal stack because only the governance contract slice is implemented.

### 3.1 Runtime and Test Stack

| Layer | Current choice | Notes |
| --- | --- | --- |
| Language | Python 3.12 | Current local interpreter |
| Test framework | `pytest==7.4.3` | Repo contract tests |
| Shell scripting | Bash | Documentation assembly and context-bundle scripts |
| Docs format | Markdown | Canonical repo-reference format |

### 3.2 Python Standard Library Usage

| Module | Current use |
| --- | --- |
| `enum` | `StrEnum` vocabularies for bounded contracts |
| `dataclasses` | Frozen contract helpers |
| `types.MappingProxyType` | Immutable registry views |

### 3.3 Not Yet Present

| Category | Current status |
| --- | --- |
| Web framework | Not implemented |
| ORM/migrations | Not implemented |
| Database driver | Not implemented |
| Frontend framework | Not implemented |
| Runtime AI provider SDK | Not implemented |
