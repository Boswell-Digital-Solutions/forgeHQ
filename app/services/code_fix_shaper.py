"""Deterministic code-fix shaping for the Self-Healing lane (forgeHQ).

First real forgeHQ -> Self-Healing slice: turn a structured, signal-derived code
issue into a CONCRETE, applicable code-fix proposal (full new file content + a
unified diff), then adapt it to the DataForge-Local ``healing.code_fix.v1``
envelope the ForgeCommand self-healing bridge consumes. (The bridge applies a
proposal by WRITING ``payload.proposed_edit.content`` to
``repository/file_path`` — so a proposal must carry the full new file content,
not a patch.)

DETERMINISTIC ONLY: every rule here is a mechanical, safe transform with no model
in the loop. Non-deterministic / AI-assisted shaping is the broader P4b phase;
this slice proves the forgeHQ -> healing-proposals -> apply round trip end to end
with real (if simple) fixes. The shaper is transport-free — a separate driver
(`app/drivers/healing_publisher.py`) publishes the envelope to DataForge-Local.
"""
from __future__ import annotations

import difflib
import hashlib
from collections.abc import Callable
from dataclasses import dataclass

HEALING_CODE_FIX_SCHEMA = "healing.code_fix.v1"
SOURCE_SYSTEM = "forgehq"


@dataclass(frozen=True)
class CodeIssue:
    """A signal-derived code issue with enough context to fix it deterministically.

    ``current_content`` is the file's current full text (the caller/driver reads
    it; the shaper performs no I/O).
    """

    repository: str
    file_path: str
    current_content: str
    issue_kind: str
    severity: str = "low"
    commit_sha: str = "unknown"


@dataclass(frozen=True)
class CodeFixProposal:
    """forgeHQ's own non-authoritative, concrete + applicable code-fix proposal."""

    repository: str
    file_path: str
    current_content: str
    new_content: str
    summary: str
    rule: str
    severity: str
    commit_sha: str

    @property
    def diff(self) -> str:
        return "".join(
            difflib.unified_diff(
                self.current_content.splitlines(keepends=True),
                self.new_content.splitlines(keepends=True),
                fromfile=f"a/{self.file_path}",
                tofile=f"b/{self.file_path}",
            )
        )

    @property
    def event_id(self) -> str:
        # Deterministic so re-shaping the same fix is an idempotent ingest.
        digest = hashlib.sha256(
            f"{self.repository}\0{self.file_path}\0{self.rule}\0{self.new_content}".encode()
        ).hexdigest()[:16]
        return f"forgehq-{self.rule}-{digest}"


# ── deterministic rules: issue_kind -> (summary, transform) ──
# Each transform maps current content -> new content, or None when nothing to do.


def _ensure_trailing_newline(content: str) -> str | None:
    if content == "" or content.endswith("\n"):
        return None
    return content + "\n"


def _strip_trailing_whitespace(content: str) -> str | None:
    new = "\n".join(line.rstrip() for line in content.split("\n"))
    return new if new != content else None


# Order matters for shape_all: strip trailing whitespace first, then ensure the
# file ends in a newline (so a stripped final line still gets its newline).
_RULES: dict[str, tuple[str, Callable[[str], str | None]]] = {
    "trailing_whitespace": (
        "Strip trailing whitespace from each line.",
        _strip_trailing_whitespace,
    ),
    "missing_trailing_newline": (
        "Ensure the file ends with a single trailing newline.",
        _ensure_trailing_newline,
    ),
}


class CodeFixShaper:
    """Deterministic code-fix shaper.

    Returns None when the issue kind is unsupported or the transform is a no-op
    (fail-closed: forgeHQ never emits an empty/identity 'fix').
    """

    def shape(self, issue: CodeIssue) -> CodeFixProposal | None:
        rule = _RULES.get(issue.issue_kind)
        if rule is None:
            return None
        summary, transform = rule
        new_content = transform(issue.current_content)
        if new_content is None or new_content == issue.current_content:
            return None
        return CodeFixProposal(
            repository=issue.repository,
            file_path=issue.file_path,
            current_content=issue.current_content,
            new_content=new_content,
            summary=summary,
            rule=issue.issue_kind,
            severity=issue.severity,
            commit_sha=issue.commit_sha,
        )

    def shape_all(
        self,
        repository: str,
        file_path: str,
        content: str,
        *,
        severity: str = "low",
        commit_sha: str = "unknown",
    ) -> CodeFixProposal | None:
        """Apply every deterministic rule cumulatively, yielding ONE combined
        hygiene proposal for a file (or None if nothing applies)."""
        new_content = content
        applied: list[str] = []
        for kind, (_summary, transform) in _RULES.items():
            result = transform(new_content)
            if result is not None and result != new_content:
                new_content = result
                applied.append(kind)
        if not applied or new_content == content:
            return None
        return CodeFixProposal(
            repository=repository,
            file_path=file_path,
            current_content=content,
            new_content=new_content,
            summary="Apply deterministic hygiene fixes: " + ", ".join(applied) + ".",
            rule="hygiene",
            severity=severity,
            commit_sha=commit_sha,
        )

    @property
    def supported_kinds(self) -> frozenset[str]:
        return frozenset(_RULES)


def to_healing_code_fix_envelope(proposal: CodeFixProposal) -> dict:
    """Adapt a forgeHQ CodeFixProposal to the DataForge-Local
    ``healing.code_fix.v1`` envelope consumed by the FC self-healing bridge."""
    return {
        "event_id": proposal.event_id,
        "source_system": SOURCE_SYSTEM,
        "schema_version": HEALING_CODE_FIX_SCHEMA,
        "event_class": "proposal",
        "source_environment": "local",
        "repo_id": proposal.repository,
        "commit_sha": proposal.commit_sha,
        "severity": proposal.severity,
        "payload": {
            "kind": "code_fix_proposal",
            "summary": proposal.summary,
            "diff": proposal.diff,
            "proposed_edit": {
                "repository": proposal.repository,
                "file_path": proposal.file_path,
                "content": proposal.new_content,
                "base_content_sha256": "sha256:"
                + hashlib.sha256(proposal.current_content.encode("utf-8")).hexdigest(),
            },
        },
    }
