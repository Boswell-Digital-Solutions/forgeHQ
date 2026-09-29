"""Cloud Subject Detector contract pack (BDS-FCO-CSD-v0.1, slice CSD-01).

Three non-authoritative contract shapes for turning a real upstream cloud
observation into an evidence-backed proposal candidate, without yet building
any adapter, correlator, or live detector:

- `CloudSignal` (`cloud.signal.v1`): one observation from a source adapter.
  Never a proposal by itself.
- `CloudProposalCandidate` (`cloud.proposal_candidate.v1`): the factual case
  for a proposal, after correlation/eligibility decide one is warranted.
  Deliberately carries no title, prose, or recommendation text -- that is
  the composer's job (CSD-04, not this slice).
- `CloudProposalDerivationReceipt` (`cloud.proposal_derivation_receipt.v1`):
  the audit trail tying a published proposal back to the signals and
  candidate it came from.

Sibling to `cloud_proposal_shaper.py`: same fail-closed `Shaper.build(...) ->
T | None` idiom, same non-authoritative posture. This module builds and
validates the shapes; it does not correlate, decide eligibility, compose
prose, or publish anything -- those are later, separately authorized slices
(see `docs/plans/active/BDS-FCO-CSD-v0.1-CLOUD-SUBJECT-DETECTOR.md` at the
forge workspace root for the full sequencing).

RECURSION GUARD (CSD-00 finding, load-bearing -- do not relax without
re-reading that doc's "CSD-00" section): `cloud_source_feeder.py` already
maps an *existing* Forge_Command cloud proposal into a `cloud://` source ref
for forgeHQ's own intake, and `app.domain.signals.enums` classifies
`cloud://` as an admissible weak signal for general forgeHQ intake. If a
`CloudSignal`'s evidence admitted `cloud://` refs, a forgeHQ-originated
proposal could loop back into producing another one. `signal://` is
therefore the *only* admissible evidence-source scheme here -- a narrower
rule than forgeHQ's general intake admissibility.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

CLOUD_SIGNAL_SCHEMA = "cloud.signal.v1"
CLOUD_PROPOSAL_CANDIDATE_SCHEMA = "cloud.proposal_candidate.v1"
CLOUD_PROPOSAL_DERIVATION_RECEIPT_SCHEMA = "cloud.proposal_derivation_receipt.v1"

_VALID_SEVERITIES = frozenset({"info", "low", "medium", "high", "critical"})
_VALID_CONFIDENCE_BANDS = frozenset({"low", "medium", "high"})
_VALID_ELIGIBILITY_DECISIONS = frozenset(
    {"eligible", "duplicate", "suppressed", "insufficient_evidence"}
)
# v0.1 is deterministic-composition-only (BDS-FCO-CSD-v0.1's own scoping ruling).
# "ai_assisted" is a real future value (CSD-09) but is fail-closed rejected here
# until that slice is separately authorized.
_VALID_COMPOSITION_MODES = frozenset({"deterministic"})

# Only `signal://` may feed CloudSignal evidence. See module docstring.
_ADMISSIBLE_EVIDENCE_SCHEMES = frozenset({"signal"})

# Always present in a CloudProposalCandidate's constraints, regardless of
# caller input -- the detector never earns authority to mutate cloud state.
_MANDATORY_CANDIDATE_CONSTRAINT = "no production mutation authorized"


MAX_LISTED_IDS = 5


def summarize_ids(ids: tuple[str, ...]) -> str:
    """First few ids, then a count -- a real group can hold 100 signals, and
    a review-queue entry must stay readable."""
    listed = ", ".join(ids[:MAX_LISTED_IDS])
    extra = len(ids) - MAX_LISTED_IDS
    return listed if extra <= 0 else f"{listed}, and {extra} more"


def is_admissible_evidence_source(source_ref: str) -> bool:
    """True only for `signal://...` refs. Deliberately excludes `cloud://`,
    which forgeHQ's general intake admits but which this detector must not
    consume as candidate evidence (see module docstring)."""
    if "://" not in source_ref:
        return False
    scheme = source_ref.split("://", 1)[0].lower()
    return scheme in _ADMISSIBLE_EVIDENCE_SCHEMES


@dataclass(frozen=True, slots=True)
class CloudSignalSubject:
    """What the signal is about -- a deployed service (`subject_kind`
    "service"), a principal/tenant identity (`subject_kind` "identity"), or a
    source-code repository (`subject_kind` "repository").

    Widened from service-only after finding forgesentinel's two real
    detectors (`denial_streak`, `quota_exceeded_burst`,
    `src/watchdog/decisions.ts`) never populate `scope.cloud_service` at
    all -- they are principal/tenant-scoped identity anomalies, not
    service-outage observations, and forcing a `service` value onto them
    would mean inventing one. Widened again for `repository` after CSD-06's
    GitHub Actions adapter: a CI workflow failure is scoped to a repository,
    not a service or an identity either. `subject_kind` defaults to
    "service" so every existing service-scoped construction stays valid
    unchanged."""

    subject_kind: str = "service"
    environment: str = "production"
    service: str | None = None
    tenant_id: str | None = None
    principal_id: str | None = None
    repository: str | None = None

    @property
    def identity_key(self) -> str:
        """A stable identity string for fingerprinting/display, independent
        of `subject_kind`."""
        if self.subject_kind == "service":
            return f"service:{self.service}"
        if self.subject_kind == "repository":
            return f"repository:{self.repository}"
        return f"identity:{self.tenant_id or ''}:{self.principal_id or ''}"


def is_valid_subject(subject: CloudSignalSubject) -> bool:
    """Shared validity rule for both `CloudSignal` and
    `CloudProposalCandidate` subjects, so the two shapers can't drift apart
    on what counts as a real subject."""
    if subject.subject_kind == "service":
        return bool(subject.service and subject.service.strip())
    if subject.subject_kind == "identity":
        return bool(
            (subject.tenant_id and subject.tenant_id.strip())
            or (subject.principal_id and subject.principal_id.strip())
        )
    if subject.subject_kind == "repository":
        return bool(subject.repository and subject.repository.strip())
    return False


@dataclass(frozen=True, slots=True)
class CloudSignalEvidence:
    artifact_ids: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()
    immutable_hashes: tuple[str, ...] = ()

    def is_empty(self) -> bool:
        return not (self.artifact_ids or self.source_refs or self.immutable_hashes)


@dataclass(frozen=True, slots=True)
class CloudSignalCorrelation:
    fingerprint: str
    dimensions: dict = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CloudSignalProvenance:
    producer: str
    producer_version: str
    original_event_id: str


@dataclass(frozen=True, slots=True)
class CloudSignal:
    """One observation from a source adapter. Never a proposal by itself."""

    signal_id: str
    source_system: str
    source_kind: str
    subject: CloudSignalSubject
    issue_class: str
    severity: str
    observed_at: str
    summary: str
    evidence: CloudSignalEvidence
    correlation: CloudSignalCorrelation
    provenance: CloudSignalProvenance
    authority_posture: str = "evidence_only"


class CloudSignalShaper:
    """Builds a `CloudSignal`, failing closed on missing identity/evidence,
    an unknown severity, a non-`evidence_only` authority posture, or any
    evidence source ref outside the admissible scheme set."""

    def build(self, signal: CloudSignal) -> CloudSignal | None:
        s = signal
        if not s.signal_id.strip() or not s.source_system.strip() or not s.source_kind.strip():
            return None
        if not is_valid_subject(s.subject):
            return None
        if not s.issue_class.strip() or not s.summary.strip() or not s.observed_at.strip():
            return None
        if s.severity not in _VALID_SEVERITIES:
            return None
        if s.authority_posture != "evidence_only":
            return None
        if not s.correlation.fingerprint.strip():
            return None
        if (
            not s.provenance.producer.strip()
            or not s.provenance.producer_version.strip()
            or not s.provenance.original_event_id.strip()
        ):
            return None
        if s.evidence.is_empty():
            return None
        if any(not is_admissible_evidence_source(ref) for ref in s.evidence.source_refs):
            return None
        return s


@dataclass(frozen=True, slots=True)
class CloudProposalCandidate:
    """The factual case for a proposal. No title, no prose, no
    recommendation -- composition is a separate, later slice (CSD-04)."""

    subject: CloudSignalSubject
    issue_class: str
    severity: str
    confidence_band: str
    signal_ids: tuple[str, ...]
    correlation_fingerprint: str
    facts: tuple[str, ...]
    recommended_action_class: str
    evidence_artifact_ids: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()

    @property
    def candidate_id(self) -> str:
        # Deterministic, keyed on evidence identity (subject + issue_class +
        # correlation_fingerprint) -- never on prose. This is the fingerprint-
        # based identity CSD-00 found missing from the already-shipped
        # CloudProposal.event_id (title-keyed); new automated candidates get
        # it from day one rather than repeating that mistake.
        digest = hashlib.sha256(
            f"{self.subject.identity_key}\0{self.subject.environment}\0"
            f"{self.issue_class}\0{self.correlation_fingerprint}".encode()
        ).hexdigest()[:16]
        return f"forgehq-cloud-candidate-{digest}"


class CloudProposalCandidateShaper:
    """Builds a `CloudProposalCandidate`, failing closed on missing evidence
    lineage or an unknown severity/confidence band. Always ensures the
    mandatory no-mutation constraint is present, regardless of caller input."""

    def build(
        self,
        *,
        subject: CloudSignalSubject,
        issue_class: str,
        severity: str,
        confidence_band: str,
        signal_ids: tuple[str, ...],
        correlation_fingerprint: str,
        facts: tuple[str, ...],
        recommended_action_class: str,
        evidence_artifact_ids: tuple[str, ...] = (),
        constraints: tuple[str, ...] = (),
    ) -> CloudProposalCandidate | None:
        if not is_valid_subject(subject) or not issue_class.strip():
            return None
        if severity not in _VALID_SEVERITIES:
            return None
        if confidence_band not in _VALID_CONFIDENCE_BANDS:
            return None
        if not signal_ids:
            return None
        if not correlation_fingerprint.strip():
            return None
        if not facts:
            return None
        if not recommended_action_class.strip():
            return None

        if _MANDATORY_CANDIDATE_CONSTRAINT not in constraints:
            constraints = (*constraints, _MANDATORY_CANDIDATE_CONSTRAINT)

        return CloudProposalCandidate(
            subject=subject,
            issue_class=issue_class,
            severity=severity,
            confidence_band=confidence_band,
            signal_ids=signal_ids,
            correlation_fingerprint=correlation_fingerprint,
            facts=facts,
            recommended_action_class=recommended_action_class,
            evidence_artifact_ids=evidence_artifact_ids,
            constraints=constraints,
        )


@dataclass(frozen=True, slots=True)
class CloudProposalDerivationReceipt:
    """Audit trail tying a published proposal back to the signals and
    candidate it came from. `proposal_id` is filled in once the proposal is
    actually published (a later slice, CSD-05) -- None before that."""

    candidate_id: str
    signal_ids: tuple[str, ...]
    correlation_fingerprint: str
    adapter_versions: dict
    detector_version: str
    composer_version: str
    evidence_hashes: tuple[str, ...]
    eligibility_decision: str
    composition_mode: str
    created_at: str
    proposal_id: str | None = None


class CloudProposalDerivationReceiptShaper:
    """Builds a `CloudProposalDerivationReceipt`, failing closed on missing
    lineage/version identity or an eligibility decision / composition mode
    outside the closed sets this slice supports (deterministic-only for
    composition mode -- see module docstring)."""

    def build(self, receipt: CloudProposalDerivationReceipt) -> CloudProposalDerivationReceipt | None:
        r = receipt
        if not r.candidate_id.strip() or not r.signal_ids:
            return None
        if not r.correlation_fingerprint.strip():
            return None
        if not r.adapter_versions:
            return None
        if not r.detector_version.strip() or not r.composer_version.strip():
            return None
        if not r.evidence_hashes:
            return None
        if r.eligibility_decision not in _VALID_ELIGIBILITY_DECISIONS:
            return None
        if r.composition_mode not in _VALID_COMPOSITION_MODES:
            return None
        if not r.created_at.strip():
            return None
        return r
