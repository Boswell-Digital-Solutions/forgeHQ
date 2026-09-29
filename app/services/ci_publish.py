"""Publish the CI shadow run's eligible proposals to DataForge-Local.

The first place in this pipeline that WRITES to a live system on real data.
It is deliberately narrow:

- DRY RUN BY DEFAULT. `plan_publications()` only builds envelopes; nothing is
  sent unless the caller passes `confirm=True` to `execute_publications()`.
- REFUSES TO PUBLISH BLIND. If the suppression read failed, or any status
  listing was truncated, it raises `PublishRefused`: it cannot show that a
  proposal is not a duplicate, so it will not create one.
- BOUNDED. At most `max_publish` proposals per run (default 3); the rest are
  reported as `not_published_over_limit`, not dropped silently.
- TEMPLATES ONLY. It never passes an AI generator; a candidate whose action
  class has no deterministic template is skipped and counted.
- IDENTITY. A detector-made proposal's id is keyed on the incident
  (subject, issue class, fingerprint, generation), never the title. The
  generation is how many proposals already exist for that fingerprint, so a
  recurrence after the cooldown is a NEW row superseding the old one, while
  publishing the same generation twice is a no-op in the idempotent store.

Approval is never touched here: the proposal lands as `pending` and an
operator decides it in Forge_Command.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from app.drivers.healing_publisher import DEFAULT_DATAFORGE_LOCAL_URL, publish_healing_proposal
from app.services.ci_shadow import CiShadowReport
from app.services.cloud_proposal_candidate_translator import candidate_to_proposal_input
from app.services.cloud_proposal_shaper import CloudProposalShaper, to_cloud_proposal_envelope


class PublishRefused(RuntimeError):
    """Publishing was refused because it could not be shown to be safe."""


@dataclass(frozen=True, slots=True)
class PlannedPublication:
    proposal_id: str
    title: str
    severity: str
    issue_class: str
    subject: str
    fingerprint: str
    generation: int
    signal_count: int
    envelope: dict


@dataclass(slots=True)
class PublishPlan:
    items: list[PlannedPublication] = field(default_factory=list)
    not_published_over_limit: int = 0
    untranslatable: int = 0

    def to_dict(self) -> dict:
        return {
            "items": [
                {
                    "proposal_id": i.proposal_id,
                    "title": i.title,
                    "severity": i.severity,
                    "issue_class": i.issue_class,
                    "subject": i.subject,
                    "generation": i.generation,
                    "signals": i.signal_count,
                }
                for i in self.items
            ],
            "not_published_over_limit": self.not_published_over_limit,
            "untranslatable": self.untranslatable,
        }


def plan_publications(report: CiShadowReport, *, max_publish: int = 3) -> PublishPlan:
    if report.suppression is None:
        raise PublishRefused(
            f"suppression state unavailable ({report.suppression_status}); "
            "cannot show these are not duplicates"
        )
    if report.suppression.truncated_statuses:
        raise PublishRefused(
            f"store listing truncated for {list(report.suppression.truncated_statuses)}; "
            "cannot show these are not duplicates"
        )
    if max_publish < 1:
        raise PublishRefused("max_publish must be at least 1")

    plan = PublishPlan()
    shaper = CloudProposalShaper()
    for candidate in report.candidates:
        if len(plan.items) >= max_publish:
            plan.not_published_over_limit += 1
            continue
        generation = report.suppression.generation_by_fingerprint.get(
            candidate.correlation_fingerprint, 0
        )
        proposal_input = candidate_to_proposal_input(candidate, generation=generation)
        proposal = shaper.shape(proposal_input) if proposal_input is not None else None
        if proposal is None:
            plan.untranslatable += 1
            continue
        plan.items.append(
            PlannedPublication(
                proposal_id=proposal.event_id,
                title=proposal.input.title,
                severity=proposal.input.severity,
                issue_class=proposal.input.issue_class,
                subject=candidate.subject.identity_key,
                fingerprint=candidate.correlation_fingerprint,
                generation=generation,
                signal_count=len(candidate.signal_ids),
                envelope=to_cloud_proposal_envelope(proposal),
            )
        )
    return plan


def execute_publications(
    plan: PublishPlan,
    *,
    confirm: bool,
    base_url: str = DEFAULT_DATAFORGE_LOCAL_URL,
    publish: Callable[..., dict] = publish_healing_proposal,
) -> list[dict]:
    """Send each planned envelope. Without `confirm`, sends nothing and says so."""
    if not confirm:
        return []
    results = []
    for item in plan.items:
        try:
            reply = publish(item.envelope, dataforge_url=base_url)
        except Exception as exc:  # transport / non-2xx: report, keep going
            results.append(
                {"proposal_id": item.proposal_id, "outcome": "error", "detail": f"{type(exc).__name__}: {exc}"}
            )
            continue
        results.append(
            {
                "proposal_id": item.proposal_id,
                "outcome": "stored",
                # The store returns an existing row's status for a repeat id.
                "status": reply.get("status"),
            }
        )
    return results
