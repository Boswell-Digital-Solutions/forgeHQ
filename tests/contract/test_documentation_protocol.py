from pathlib import Path
import subprocess


REPO_ROOT = Path(__file__).resolve().parents[2]
SYSTEM_DIR = REPO_ROOT / "doc" / "system"
# The compiled reference is doc/<CODE>SYSTEM.md (designation FRG), assembled by
# doc/system/BUILD.sh -- not a root-level SYSTEM.md, which the retired layout used.
COMPILED_SYSTEM = REPO_ROOT / "doc" / "FRGSYSTEM.md"
REFERENCE_DIR = REPO_ROOT / "docs" / "reference" / "bds"
QA_DIR = REPO_ROOT / "docs" / "qa"


def _expected_system_text() -> str:
    chunks = [(SYSTEM_DIR / "_index.md").read_text()]
    for part in sorted(SYSTEM_DIR.glob("[0-9][0-9]-*.md")):
        chunks.append("\n---\n\n")
        chunks.append(part.read_text())
    return "".join(chunks)


def test_required_documentation_surfaces_exist():
    required_paths = [
        REPO_ROOT / "CLAUDE.md",
        REPO_ROOT / "FORGEHQ_COMPREHENSIVE_TEST_PLAN.md",
        COMPILED_SYSTEM,
        REPO_ROOT / "docs" / "forge_hq_architecture_spec.md",
        REPO_ROOT / "docs" / "forge_hq_extended_roadmap.md",
        QA_DIR / "README.md",
        QA_DIR / "FORGEHQ_MODE_A_T0_CHECKLIST.md",
        QA_DIR / "FORGEHQ_QA_FINDINGS_LOG_TEMPLATE.md",
        QA_DIR / "FORGEHQ_QA_RUN_REPORT_TEMPLATE.md",
        QA_DIR / "FORGEHQ_TIER_APPLICABILITY_MATRIX.md",
        REFERENCE_DIR / "README.md",
        REFERENCE_DIR / "BDS_DOCUMENTATION_PROTOCOL_v1.md",
        REFERENCE_DIR / "BDS_REPO_AUDIT_EXECUTION_PROTOCOL.md",
        REFERENCE_DIR / "BDS_DOCUMENTATION_LIFECYCLE_AND_DRIFT_PROTOCOL.md",
        SYSTEM_DIR / "_index.md",
        SYSTEM_DIR / "BUILD.sh",
        REPO_ROOT / "scripts" / "context-bundle.sh",
        REPO_ROOT / "scripts" / "qa-mode-a-preflight.sh",
        REPO_ROOT / "scripts" / "qa-regression-smoke.sh",
    ]

    for path in required_paths:
        assert path.exists(), f"missing required documentation surface: {path}"


def test_compiled_system_doc_matches_modular_documentation_sources():
    assert COMPILED_SYSTEM.read_text() == _expected_system_text()


def test_index_table_of_contents_covers_all_numbered_part_files():
    index_text = (SYSTEM_DIR / "_index.md").read_text()

    # The TOC is a table of `| §N | `NN-name.md` | ... |` rows.
    for part in sorted(SYSTEM_DIR.glob("[0-9][0-9]-*.md")):
        section_number = part.name.split("-", 1)[0].lstrip("0") or "0"
        row_prefix = f"| §{section_number} | `{part.name}` |"
        assert row_prefix in index_text, f"missing TOC row for {part.name}"


def test_context_bundle_generated_artifact_is_gitignored():
    gitignore = (REPO_ROOT / ".gitignore").read_text().splitlines()
    assert "context-bundle.md" in gitignore


def test_company_core_protocols_are_available_under_reference_directory():
    assert (REFERENCE_DIR / "BDS_DOCUMENTATION_PROTOCOL_v1.md").exists()
    assert (REFERENCE_DIR / "BDS_REPO_AUDIT_EXECUTION_PROTOCOL.md").exists()
    assert (REFERENCE_DIR / "BDS_DOCUMENTATION_LIFECYCLE_AND_DRIFT_PROTOCOL.md").exists()


def test_build_script_reassembles_compiled_system_doc_successfully():
    result = subprocess.run(
        ["bash", "doc/system/BUILD.sh"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    # BUILD.sh prints one line: BUILD_OK designation=FRG output=... parts=N lines=M
    part_count = len(list(SYSTEM_DIR.glob("[0-9][0-9]-*.md")))
    assert "BUILD_OK designation=FRG output=doc/FRGSYSTEM.md" in result.stdout
    assert f"parts={part_count} " in result.stdout


def test_context_bundle_script_supports_required_flags():
    list_result = subprocess.run(
        ["bash", "scripts/context-bundle.sh", "--list"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    dry_run_result = subprocess.run(
        [
            "bash",
            "scripts/context-bundle.sh",
            "--dry-run",
            "--preset",
            "core",
            "--with-roadmap",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Available sections:" in list_result.stdout
    assert "Presets:" in list_result.stdout
    assert "core" in list_result.stdout
    assert "governance" in list_result.stdout
    assert "docs" in list_result.stdout
    assert "Would assemble:" in dry_run_result.stdout
    assert "roadmap ->" in dry_run_result.stdout


def test_imported_drift_protocol_has_no_broken_filecite_markers():
    drift_protocol = (REFERENCE_DIR / "BDS_DOCUMENTATION_LIFECYCLE_AND_DRIFT_PROTOCOL.md").read_text()
    assert "filecite" not in drift_protocol
