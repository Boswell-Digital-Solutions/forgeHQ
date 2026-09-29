"""Correlation and proposal eligibility (BDS-FCO-CSD-v0.1, slice CSD-03).

Two pure, transport-free stages between adapter output (`CloudSignal.v1`,
CSD-01/CSD-02) and candidate composition (`CloudProposalCandidate.v1`,
CSD-04, not built yet):

1. `CloudSignalCorrelator` groups a batch of signals by their shared
   `correlation.fingerprint` into `CorrelatedSignalGroup`s, dropping
   replayed duplicates (same `signal_id` seen twice).
2. `CloudProposalEligibilityGate` decides, per group, whether the evidence
   justifies a proposal candidate at all -- confidence is computed from
   evidence shape (how many independent signals, whether immutable hashes
   back them), never from severity alone and never from an LLM's own
   confidence claim (there is no LLM in this pipeline yet; CSD-09, deferred).

STILL SHADOW-ONLY: this module produces `EligibilityOutcome`s, not
`CloudProposalCandidate`s. Composing a candidate's `facts` and
`recommended_action_class` from an eligible group is the composer's job
(CSD-04), deliberately not built here. `open_proposal_fingerprints` and
`suppressed_until` are caller-supplied maps/sets, not fetched from
DataForge-Local -- this stage does no I/O, matching every other module in
this plan so far.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.services.cloud_signal_contracts import CloudSignal

# Aligned with CloudProposalDerivationReceipt's own closed eligibility-decision
# set (cloud_signal_contracts.py) so a later receipt can carry this decision
# through unchanged.
ELIGIBLE = "eligible"
DUPLICATE = "duplicate"
SUPPRESSED = "suppressed"
INSUFFICIENT_EVIDENCE = "insufficient_evidence"


@dataclass(frozen=True, slots=True)
class CorrelatedSignalGroup:
    """All signals sharing one correlation fingerprint, deduplicated by
    signal_id and ordered by first-seen (input) order."""

    fingerprint: str
    signals: tuple[CloudSignal, ...]

    @property
    def signal_ids(self) -> tuple[str, ...]:
        return tuple(s.signal_id for s in self.signals)

    @property
    def subject_identity_key(self) -> str:
        return self.signals[0].subject.identity_key

    @property
    def highest_severity_signal(self) -> CloudSignal:
        order = ("critical", "high", "medium", "low", "info")
        return min(self.signals, key=lambda s: order.index(s.severity))


class CloudSignalCorrelator:
    """Groups signals by correlation fingerprint. Fails closed on an empty
    input rather than raising -- an empty batch correlates to no groups."""

    def correlate(self, signals: list[CloudSignal]) -> tuple[CorrelatedSignalGroup, ...]:
        groups: dict[str, list[CloudSignal]] = {}
        seen_signal_ids: dict[str, set[str]] = {}
        order: list[str] = []

        for signal in signals:
            fp = signal.correlation.fingerprint
            if fp not in groups:
                groups[fp] = []
                seen_signal_ids[fp] = set()
                order.append(fp)
            if signal.signal_id in seen_signal_ids[fp]:
                continue  # replayed duplicate -- not a second independent observation
            seen_signal_ids[fp].add(signal.signal_id)
            groups[fp].append(signal)

        return tuple(
            CorrelatedSignalGroup(fingerprint=fp, signals=tuple(groups[fp])) for fp in order
        )


@dataclass(frozen=True, slots=True)
class EligibilityOutcome:
    fingerprint: str
    decision: str
    confidence_band: str | None  # None when decision is not ELIGIBLE
    reason: str
    signal_ids: tuple[str, ...]


def _compute_confidence_band(group: CorrelatedSignalGroup) -> str:
    # 06/09 design rule, not severity-derived:
    #   HIGH   -- multiple independent observations, OR one signal backed by
    #             an immutable hash (a deterministic, hash-covered failure)
    #   MEDIUM -- one signal with only source_refs/artifact_ids, no
    #             immutable hash
    # No LOW band is computed here: CloudSignalShaper already requires
    # non-empty evidence on every signal that reaches this gate, so nothing
    # in this pipeline can currently produce a genuinely weak observation.
    # INSUFFICIENT_EVIDENCE stays defined (aligned with
    # CloudProposalDerivationReceipt's closed set) for a future adapter that
    # can produce one, but this slice does not wire an unreachable branch to
    # it.
    if len(group.signals) >= 2:
        return "high"
    (only_signal,) = group.signals
    if only_signal.evidence.immutable_hashes:
        return "high"
    return "medium"


class CloudProposalEligibilityGate:
    """Answers only "does this evidence justify a review-queue entry" --
    never "should this be executed." Every decision is explainable via
    `EligibilityOutcome.reason`; a SUPPRESSED/duplicate/insufficient-evidence
    result is itself meaningful evidence, not a silent drop."""

    def evaluate(
        self,
        group: CorrelatedSignalGroup,
        *,
        open_proposal_fingerprints: frozenset[str] = frozenset(),
        suppressed_fingerprints: frozenset[str] = frozenset(),
    ) -> EligibilityOutcome:
        if group.fingerprint in open_proposal_fingerprints:
            return EligibilityOutcome(
                fingerprint=group.fingerprint,
                decision=DUPLICATE,
                confidence_band=None,
                reason="an open proposal already exists for this correlation fingerprint",
                signal_ids=group.signal_ids,
            )
        if group.fingerprint in suppressed_fingerprints:
            return EligibilityOutcome(
                fingerprint=group.fingerprint,
                decision=SUPPRESSED,
                confidence_band=None,
                reason="this fingerprint is within its cooldown window",
                signal_ids=group.signal_ids,
            )

        confidence_band = _compute_confidence_band(group)
        return EligibilityOutcome(
            fingerprint=group.fingerprint,
            decision=ELIGIBLE,
            confidence_band=confidence_band,
            reason=f"{len(group.signals)} correlated signal(s), confidence={confidence_band}",
            signal_ids=group.signal_ids,
        )
