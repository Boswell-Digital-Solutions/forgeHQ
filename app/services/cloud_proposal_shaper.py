"""Cloud-subject proposal shaping for the Cloud Proposals lane (forgeHQ).

Sibling to `code_fix_shaper.py`: where that module shapes a proposal targeting a
file inside a local git checkout, this one shapes a proposal targeting a "cloud
subject" — a deployed service or environment with nothing to write to disk. The
distinction is real, not cosmetic: `code_fix_shaper.py`'s envelope is consumed by
Forge_Command's self-healing bridge, which WRITES `payload.proposed_edit.content`
to `repository/file_path`. A cloud-subject proposal has no file to write; it is a
review-queue entry for an operator to approve/reject/defer, nothing more.

DETERMINISTIC INPUT, NOT DETERMINISTIC GENERATION: unlike `code_fix_shaper.py`'s
mechanical rule transforms, there is no signal-derived cloud-subject detector yet.
This shaper takes already-composed proposal content (problem statement, evidence,
recommendation) and packages it into the envelope; it does not derive that content
from a signal itself. Building a real detector is future work, out of scope here —
this proves the forgeHQ -> DataForge-Local -> Forge_Command round trip end to end
with real (if manually-composed) proposals, exactly as `code_fix_shaper.py`'s own
scope note describes for its own first slice. The shaper is transport-free — the
same driver (`app/drivers/healing_publisher.py`) publishes the envelope.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

CLOUD_PROPOSAL_SCHEMA = "cloud.proposal.v1"
SOURCE_SYSTEM = "forgehq"


@dataclass(frozen=True)
class CloudSubject:
    """What the proposal is about: a deployed service, not a repo file."""

    service: str
    environment: str = "production"


@dataclass(frozen=True)
class CloudProposalInput:
    """Caller-composed proposal content for a cloud subject.

    Mirrors the fields Forge_Command's `CloudProposal` frontend type already
    expects, so the envelope's payload needs no translation on the consuming
    side beyond a straight field copy.
    """

    subject: CloudSubject
    title: str
    issue_class: str
    problem_statement: str
    evidence_summary: str
    scope_summary: str
    recommended_action: str
    expected_gain: str
    risk_summary: str
    severity: str = "low"
    confidence_band: str = "medium"
    alternatives: list[str] = field(default_factory=list)
    diagnostic_artifact_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CloudProposal:
    """forgeHQ's own non-authoritative cloud-subject proposal."""

    input: CloudProposalInput

    @property
    def event_id(self) -> str:
        # Deterministic so re-shaping the same proposal is an idempotent ingest —
        # mirrors CodeFixProposal.event_id's approach, keyed on subject + title
        # rather than repository/file_path/rule.
        i = self.input
        digest = hashlib.sha256(
            f"{i.subject.service}\0{i.subject.environment}\0{i.title}\0{i.issue_class}".encode()
        ).hexdigest()[:16]
        return f"forgehq-cloud-{digest}"


class CloudProposalShaper:
    """Packages already-composed cloud-subject proposal content into a
    `CloudProposal`. Fails closed on missing required fields (empty title,
    service, or problem statement never produce a proposal)."""

    def shape(self, proposal_input: CloudProposalInput) -> CloudProposal | None:
        i = proposal_input
        if not i.subject.service.strip() or not i.title.strip() or not i.problem_statement.strip():
            return None
        return CloudProposal(input=i)


def to_cloud_proposal_envelope(proposal: CloudProposal) -> dict:
    """Adapt a forgeHQ CloudProposal to the DataForge-Local `cloud.proposal.v1`
    envelope consumed by Forge_Command's cloud-proposal bridge.

    `repo_id`/`commit_sha` are omitted (both nullable on the DataForge-Local
    `healing_proposals` table) since a cloud subject has neither. `payload`
    carries exactly the fields Forge_Command's `CloudProposal` frontend type
    expects, so the Rust bridge forwards it without translation.
    """
    i = proposal.input
    return {
        "event_id": proposal.event_id,
        "source_system": SOURCE_SYSTEM,
        "schema_version": CLOUD_PROPOSAL_SCHEMA,
        "event_class": "proposal",
        "source_environment": "cloud",
        "severity": i.severity,
        "payload": {
            "kind": "cloud_proposal",
            "title": i.title,
            "service": i.subject.service,
            "environment": i.subject.environment,
            "issueClass": i.issue_class,
            "confidenceBand": i.confidence_band,
            "problemStatement": i.problem_statement,
            "evidenceSummary": i.evidence_summary,
            "scopeSummary": i.scope_summary,
            "recommendedAction": i.recommended_action,
            "expectedGain": i.expected_gain,
            "riskSummary": i.risk_summary,
            "alternatives": list(i.alternatives),
            "diagnosticArtifactIds": list(i.diagnostic_artifact_ids),
        },
    }
