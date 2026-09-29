"""Operator-decision feedback analytics (BDS-FCO-CSD-v0.1, slice CSD-10).

The last slice in this plan's original CSD-00..CSD-10 sequence: operator
decisions on published cloud proposals (`approve`/`reject`/`defer`/
`request-evidence` -- Forge_Command's real, implemented vocabulary,
`cloud_proposal_bridge.rs:89`) may inform analytics. Per the source
review's own design ruling: those metrics MAY improve future detector
rules; they MAY NOT automatically change governance or approval
thresholds. This module only ever reports numbers -- it has no write path
into `CSD-03`'s eligibility gate, `CSD-04`'s composer, or anything else in
this pipeline, and never will inside this module's own scope.

TRANSPORT-FREE, matching every other slice: the caller supplies decided
proposal records (e.g. read from DataForge-Local's `healing_proposals`
table), not fetched here.

A REAL GAP FOUND WHILE SCOPING THIS SLICE, NOT PAPERED OVER: the source
review's own design named "source usefulness" (per-adapter acceptance
rates) as a candidate metric. It isn't computable from today's real data --
`CloudProposalCandidate` (CSD-01) carries no `source_system`/`producer`
field, so which adapter (forgesentinel/github_actions/render) originated a
given published proposal is lost by composition time and never reaches the
final envelope. `issue_class` is used here as a grounded stand-in (it maps
1:1 to an originating adapter today: denial_streak/quota_exceeded_burst ->
forgesentinel, ci_workflow_failure -> github_actions, deploy_failure ->
render), with this limitation stated, not hidden.

ALSO NOT COMPUTED, FOR THE SAME REASON: "duplicate rate", "false-positive
rate", and "insufficient-evidence rate" from the source review's own
proposed vocabulary have no real decision category behind them --
Forge_Command's operator decision is exactly `approve`/`reject`/`defer`/
`request-evidence`, nothing finer-grained. Wiring metrics to decision
categories that don't exist would mean inventing a taxonomy this module
has no way to observe; not done here.
"""
from __future__ import annotations

from dataclasses import dataclass

# Forge_Command's real, implemented decision vocabulary
# (cloud_proposal_bridge.rs:89, `DecideRequest.decision`), not the source
# review's own proposed (and partly unimplemented) taxonomy.
_KNOWN_DECISIONS = frozenset({"approve", "reject", "defer", "request-evidence"})


@dataclass(frozen=True, slots=True)
class DecidedProposalRecord:
    """One published proposal's outcome, as the caller would read it back
    from DataForge-Local's `healing_proposals` table: `issue_class` from
    `envelope_json.payload.issueClass`, `decision` from `decision_json.decision`
    (`None` when the proposal has no decision yet -- still pending/ingested,
    not counted toward any rate)."""

    issue_class: str
    decision: str | None


@dataclass(frozen=True, slots=True)
class DecisionRateSummary:
    """Rates are of `decided` (excludes records with `decision is None`),
    not of `total` -- an undecided proposal hasn't produced feedback yet."""

    total: int
    decided: int
    approved: int
    rejected: int
    deferred: int
    request_evidence: int
    unknown_decision: int

    @property
    def acceptance_rate(self) -> float:
        return self.approved / self.decided if self.decided else 0.0

    @property
    def rejection_rate(self) -> float:
        return self.rejected / self.decided if self.decided else 0.0

    @property
    def defer_rate(self) -> float:
        return self.deferred / self.decided if self.decided else 0.0

    @property
    def request_evidence_rate(self) -> float:
        return self.request_evidence / self.decided if self.decided else 0.0


def _summarize(records: list[DecidedProposalRecord]) -> DecisionRateSummary:
    decided_records = [r for r in records if r.decision is not None]
    counts = {"approve": 0, "reject": 0, "defer": 0, "request-evidence": 0}
    unknown = 0
    for record in decided_records:
        if record.decision in counts:
            counts[record.decision] += 1
        else:
            # A decision string outside the known vocabulary -- counted,
            # not silently dropped, so a real total still reconciles.
            unknown += 1
    return DecisionRateSummary(
        total=len(records),
        decided=len(decided_records),
        approved=counts["approve"],
        rejected=counts["reject"],
        deferred=counts["defer"],
        request_evidence=counts["request-evidence"],
        unknown_decision=unknown,
    )


def compute_decision_rates(records: list[DecidedProposalRecord]) -> DecisionRateSummary:
    """Overall acceptance/rejection/defer/request-evidence rates across every
    record, regardless of issue_class."""
    return _summarize(records)


def compute_issue_class_breakdown(
    records: list[DecidedProposalRecord],
) -> dict[str, DecisionRateSummary]:
    """Per-`issue_class` decision rates -- today's grounded stand-in for
    "source usefulness" (see module docstring for why true source_system
    tracking isn't available yet)."""
    by_class: dict[str, list[DecidedProposalRecord]] = {}
    for record in records:
        by_class.setdefault(record.issue_class, []).append(record)
    return {issue_class: _summarize(group) for issue_class, group in by_class.items()}
