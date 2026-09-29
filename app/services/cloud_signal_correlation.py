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


# --- Cross-source correlation (CSD-08) -----------------------------------
#
# CSD-02/CSD-06/CSD-07 each compute correlation.fingerprint in their own
# independent identity space (CSSA keys on tenant/principal, CI on
# repository+workflow, Render on service_id) -- two signals from different
# sources about the same real incident (e.g. a GitHub repo's CI and the
# Render service it deploys to) can never share a fingerprint by accident.
# Recognizing they're the same real thing requires knowing the mapping
# between a GitHub repo and a Render service ahead of time -- that mapping
# is not derivable from any signal itself, and this module does not invent
# one. SubjectAliasRegistry is caller-supplied, mechanism only: with an
# empty registry (today -- no real aliases are known anywhere in this
# ecosystem yet), every group stays standalone, fully backward compatible
# with CSD-03's own single-source correlation.

#: Maps a raw `CorrelatedSignalGroup.subject_identity_key` (e.g.
#: `"repository:org/forgeHQ"`, `"service:neuroforge"`) to a canonical
#: subject id the caller asserts represents the same real system. Supplying
#: this mapping is a human/config decision, never inferred here.
SubjectAliasRegistry = dict[str, str]


@dataclass(frozen=True, slots=True)
class MergedIncidentGroup:
    """One or more `CorrelatedSignalGroup`s that share a canonical subject,
    possibly from different sources. With no alias for a group's subject,
    `canonical_subject_id` falls back to that group's own raw identity key,
    so every group appears here even when nothing merged."""

    canonical_subject_id: str
    groups: tuple[CorrelatedSignalGroup, ...]

    @property
    def signal_ids(self) -> tuple[str, ...]:
        ids: list[str] = []
        for group in self.groups:
            ids.extend(group.signal_ids)
        return tuple(ids)

    @property
    def all_signals(self) -> tuple[CloudSignal, ...]:
        signals: list[CloudSignal] = []
        for group in self.groups:
            signals.extend(group.signals)
        return tuple(signals)

    @property
    def source_systems(self) -> tuple[str, ...]:
        """Distinct `source_system` values across every merged signal, in
        first-seen order -- e.g. `("github_actions", "render")` for a real
        cross-source merge, or a single value when nothing merged."""
        seen: set[str] = set()
        systems: list[str] = []
        for signal in self.all_signals:
            if signal.source_system not in seen:
                seen.add(signal.source_system)
                systems.append(signal.source_system)
        return tuple(systems)


class CrossSourceCorrelator:
    """Merges `CorrelatedSignalGroup`s (CSD-03's own single-source output)
    into `MergedIncidentGroup`s using a caller-supplied `SubjectAliasRegistry`.
    Fails closed to "no merge" for any group whose subject has no alias,
    rather than guessing a cross-source relationship."""

    def merge(
        self,
        groups: tuple[CorrelatedSignalGroup, ...],
        *,
        alias_registry: SubjectAliasRegistry | None = None,
    ) -> tuple[MergedIncidentGroup, ...]:
        registry = alias_registry or {}
        merged: dict[str, list[CorrelatedSignalGroup]] = {}
        order: list[str] = []

        for group in groups:
            raw_key = group.subject_identity_key
            canonical = registry.get(raw_key, raw_key)
            if canonical not in merged:
                merged[canonical] = []
                order.append(canonical)
            merged[canonical].append(group)

        return tuple(
            MergedIncidentGroup(canonical_subject_id=canonical, groups=tuple(merged[canonical]))
            for canonical in order
        )
