"""Tests for the deterministic code-fix shaper + the healing.code_fix.v1 adapter.

Covers each rule, fail-closed no-ops, deterministic event_id, and that the
adapted envelope matches the DataForge-Local contract the FC bridge applies
(payload.proposed_edit.content = the full new file content).
"""
import hashlib

from app.services.code_fix_shaper import (
    HEALING_CODE_FIX_SCHEMA,
    SOURCE_SYSTEM,
    CodeFixShaper,
    CodeIssue,
    to_healing_code_fix_envelope,
)


def _issue(kind: str, content: str) -> CodeIssue:
    return CodeIssue(
        repository="sandbox-demo",
        file_path="calc.py",
        current_content=content,
        issue_kind=kind,
        severity="low",
        commit_sha="abc123",
    )


def test_missing_trailing_newline_fix():
    proposal = CodeFixShaper().shape(_issue("missing_trailing_newline", "x = 1"))
    assert proposal is not None
    assert proposal.new_content == "x = 1\n"
    assert proposal.rule == "missing_trailing_newline"


def test_trailing_whitespace_fix():
    proposal = CodeFixShaper().shape(
        _issue("trailing_whitespace", "x = 1   \ny = 2\t\n")
    )
    assert proposal is not None
    assert proposal.new_content == "x = 1\ny = 2\n"


def test_unsupported_kind_returns_none():
    assert CodeFixShaper().shape(_issue("rewrite_everything_with_ai", "x = 1")) is None


def test_shape_all_combines_rules_into_one_proposal():
    # trailing whitespace AND missing trailing newline -> one hygiene proposal
    proposal = CodeFixShaper().shape_all("sandbox-demo", "m.py", "x = 1   \ny = 2")
    assert proposal is not None
    assert proposal.rule == "hygiene"
    assert proposal.new_content == "x = 1\ny = 2\n"
    assert "trailing_whitespace" in proposal.summary
    assert "missing_trailing_newline" in proposal.summary


def test_shape_all_clean_file_returns_none():
    assert CodeFixShaper().shape_all("sandbox-demo", "m.py", "x = 1\ny = 2\n") is None


def test_noop_fails_closed():
    # already has a trailing newline -> nothing to fix -> no empty 'fix' emitted
    assert CodeFixShaper().shape(_issue("missing_trailing_newline", "x = 1\n")) is None
    # no trailing whitespace -> no-op
    assert CodeFixShaper().shape(_issue("trailing_whitespace", "x = 1\n")) is None


def test_diff_is_real_unified_diff():
    proposal = CodeFixShaper().shape(_issue("missing_trailing_newline", "x = 1"))
    assert proposal is not None
    assert proposal.diff.startswith("--- a/calc.py")
    assert "+++ b/calc.py" in proposal.diff


def test_event_id_is_deterministic_and_namespaced():
    a = CodeFixShaper().shape(_issue("missing_trailing_newline", "x = 1"))
    b = CodeFixShaper().shape(_issue("missing_trailing_newline", "x = 1"))
    assert a is not None and b is not None
    assert a.event_id == b.event_id  # idempotent ingest
    assert a.event_id.startswith("forgehq-missing_trailing_newline-")


def test_envelope_matches_healing_code_fix_contract():
    proposal = CodeFixShaper().shape(_issue("missing_trailing_newline", "x = 1"))
    assert proposal is not None
    env = to_healing_code_fix_envelope(proposal)

    assert env["event_id"] == proposal.event_id
    assert env["source_system"] == SOURCE_SYSTEM == "forgehq"
    assert env["schema_version"] == HEALING_CODE_FIX_SCHEMA == "healing.code_fix.v1"
    assert env["event_class"] == "proposal"
    assert env["repo_id"] == "sandbox-demo"
    assert env["commit_sha"] == "abc123"

    payload = env["payload"]
    assert payload["kind"] == "code_fix_proposal"
    assert payload["summary"]
    assert payload["diff"].startswith("--- a/calc.py")
    # the load-bearing field: the bridge writes this content to repository/file_path
    edit = payload["proposed_edit"]
    assert edit == {
        "repository": "sandbox-demo",
        "file_path": "calc.py",
        "base_content_sha256": "sha256:"
        + hashlib.sha256(proposal.current_content.encode()).hexdigest(),
        "content": "x = 1\n",
    }
