"""Tests for the hygiene_scanner — the first real code-issue source.

Covers: finds fixable files, leaves clean files alone, skips VCS/build dirs and
non-text/oversized files, is read-only, and its proposals adapt to the
healing.code_fix.v1 envelope.
"""
import hashlib

from pathlib import Path

from app.drivers.hygiene_scanner import scan_repo_for_hygiene_fixes
from app.services.code_fix_shaper import to_healing_code_fix_envelope


def _write(root: Path, rel: str, content: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_scanner_finds_only_fixable_text_files(tmp_path):
    _write(tmp_path, "fixable.py", "x = 1   \ny = 2")  # ws + no newline
    _write(tmp_path, "clean.py", "x = 1\n")  # already clean
    _write(tmp_path, "skip.bin", "x = 1")  # non-text suffix
    _write(tmp_path, ".git/config", "bad   ")  # in a skip dir
    _write(tmp_path, "node_modules/lib.js", "y=2")  # in a skip dir

    proposals = scan_repo_for_hygiene_fixes(tmp_path, "demo-repo")

    paths = {p.file_path for p in proposals}
    assert paths == {"fixable.py"}
    assert proposals[0].new_content == "x = 1\ny = 2\n"
    # read-only: the source file is untouched
    assert (tmp_path / "fixable.py").read_text() == "x = 1   \ny = 2"


def test_scanner_respects_max_proposals(tmp_path):
    for i in range(5):
        _write(tmp_path, f"f{i}.py", f"v = {i}")  # each missing a trailing newline
    proposals = scan_repo_for_hygiene_fixes(tmp_path, "demo-repo", max_proposals=2)
    assert len(proposals) == 2


def test_scanner_proposals_adapt_to_envelope(tmp_path):
    _write(tmp_path, "pkg/mod.py", "a = 1\t\n")  # trailing tab
    proposals = scan_repo_for_hygiene_fixes(tmp_path, "demo-repo")
    assert len(proposals) == 1
    env = to_healing_code_fix_envelope(proposals[0])
    assert env["schema_version"] == "healing.code_fix.v1"
    assert env["payload"]["proposed_edit"] == {
        "repository": "demo-repo",
        "file_path": "pkg/mod.py",
        "base_content_sha256": "sha256:"
        + hashlib.sha256("a = 1\t\n".encode()).hexdigest(),
        "content": "a = 1\n",
    }
