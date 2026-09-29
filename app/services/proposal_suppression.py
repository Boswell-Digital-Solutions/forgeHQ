"""Turn what is already in the proposal store into the eligibility gate's suppression sets.

Pure and transport-free: takes a `StoreSnapshot` (read by
`proposal_store_reader`) and returns the two fingerprint sets
`CloudProposalEligibilityGate.evaluate` already accepts.

- OPEN -> `open_proposal_fingerprints`: a proposal with this fingerprint is
  still awaiting an operator (`pending`, `ingested`). The gate answers
  DUPLICATE.
- COOLING DOWN -> `suppressed_fingerprints`: an operator decided it
  (`accepted`, `rejected`) less than `cooldown_days` ago. The gate answers
  SUPPRESSED. A rejection is a signal not to ask again immediately; an
  approval means the operator already knows.

LIMITS, stated so the sets are not over-read:
- A stored proposal with no fingerprint (hand-composed, or published before
  the field existed) can never suppress anything. It is counted in
  `rows_without_fingerprint`, not silently ignored.
- The cooldown is a fixed window (default 14 days). "The condition has
  materially changed, so propose again" is NOT judged here.
- A decided row with a missing or unparseable decision time is treated as
  still cooling down, since its age cannot be shown to exceed the window.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from app.drivers.proposal_store_reader import StoreSnapshot

OPEN_STATUSES = frozenset({"pending", "ingested"})
DECIDED_STATUSES = frozenset({"accepted", "rejected"})


@dataclass(frozen=True, slots=True)
class SuppressionSets:
    open_fingerprints: frozenset[str]
    cooling_down_fingerprints: frozenset[str]
    rows_read: int
    rows_without_fingerprint: int
    truncated_statuses: tuple[str, ...]
    # Stored proposals per fingerprint, every status read. The next
    # proposal for a fingerprint takes this as its generation. If a status
    # listing was truncated this can undercount; a clash with an existing id
    # is then a harmless no-op in the idempotent store.
    generation_by_fingerprint: dict = field(default_factory=dict)


def _parse(raw) -> datetime | None:
    if not isinstance(raw, str):
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def build_suppression_sets(
    snapshot: StoreSnapshot,
    *,
    cooldown_days: int = 14,
    now: datetime | None = None,
) -> SuppressionSets:
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=cooldown_days)
    open_fps: set[str] = set()
    cooling: set[str] = set()
    without = 0
    generations: dict[str, int] = {}
    for proposal in snapshot.proposals:
        if proposal.fingerprint is None:
            without += 1
            continue
        generations[proposal.fingerprint] = generations.get(proposal.fingerprint, 0) + 1
        if proposal.status in OPEN_STATUSES:
            open_fps.add(proposal.fingerprint)
        elif proposal.status in DECIDED_STATUSES:
            decided = _parse(proposal.decided_at)
            if decided is None or decided >= cutoff:
                cooling.add(proposal.fingerprint)
    return SuppressionSets(
        open_fingerprints=frozenset(open_fps),
        cooling_down_fingerprints=frozenset(cooling),
        rows_read=len(snapshot.proposals),
        rows_without_fingerprint=without,
        truncated_statuses=snapshot.truncated_statuses,
        generation_by_fingerprint=generations,
    )
