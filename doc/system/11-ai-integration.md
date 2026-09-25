# §11 — AI Integration

forgeHQ currently has no runtime AI inference surface.
AI usage is limited to AI-assisted software development against the repository documentation stack.

### 12.1 Current AI Surfaces

| Surface | Status |
| --- | --- |
| Runtime model invocation | Not implemented |
| Provider routing | Not implemented |
| Prompt persistence | Not implemented |
| Dev-time context loading | Implemented via `CLAUDE.md` and `scripts/context-bundle.sh` |

### 12.2 Current AI Governance

- repo truth is assembled through `doc/system/`
- root `CLAUDE.md` defines project-specific working rules
- context bundles select bounded documentation slices for implementation work
- generated model output does not become canonical upstream truth by itself
