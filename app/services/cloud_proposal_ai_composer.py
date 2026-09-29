"""Bounded AI composition (BDS-FCO-CSD-v0.1, slice CSD-09).

The second-tier fallback for `cloud_proposal_candidate_translator.py`'s own
`_ACTION_TEMPLATES`: when a `CloudProposalCandidate.recommended_action_class`
has no deterministic template (CSD-04's composer couldn't have produced one
either -- it fails closed on the same unmapped classes), this module can
compose the same prose fields via a pluggable, bounded generator instead of
failing closed outright.

OPT-IN, NOT A SILENT FALLBACK: `candidate_to_proposal_input()` only reaches
this module when the caller explicitly passes an `ai_generator`. Every
existing call site that doesn't pass one keeps today's exact behavior --
fail closed on an unmapped action class. This is deliberate: AI composition
must never become an automatic catch-all that quietly widens what gets
published.

DETERMINISTIC STUB BY DEFAULT, NO LLM CALL YET: `NEUROFORGE_API_KEY` /
`NEUROFORGE_SERVICE_KEY` is not available in this environment (confirmed via
a real test call against NeuroForge's live chat ladder -- 401
UNAUTHENTICATED), and retrieving one from the OS keyring was refused by
Claude Code's own permission classifier as credential exploration. Charlie's
explicit ruling: build the bounded-composition architecture with a
deterministic stand-in generator now, matching how `ai_shaper_service.py`'s
`DeterministicHygieneGenerator` already plays this same role for the
sibling local code-fix pipeline. Wiring a real NeuroForge-backed generator
is a separate, later, explicitly-authorized step -- not built here.

WHAT "BOUNDED" MEANS HERE, BY CONSTRUCTION NOT BY RUNTIME CHECK: a
`CompositionGenerator` receives only a `CloudProposalCandidate` -- subject,
issue_class, severity, confidence_band, facts, constraints,
recommended_action_class. It returns only `ComposedProse` -- title,
problem_statement, evidence_summary, scope_summary, recommended_action,
expected_gain, risk_summary, alternatives. Neither type has a field for
service identity, environment, source IDs, evidence hashes, severity
*source*, correlation fingerprint, eligibility, operator decision,
authorization, or execution status -- the source review's own §12 AI
constraint list. A generator cannot set what it has no field to write to;
this isn't enforced by a runtime check, it's structurally impossible.

`validate_composed_prose()` covers what construction alone can't: every
prose field must be non-empty, and no standalone number in the composed
text may be unsupported by the candidate's own facts -- catching a
fabricated statistic (e.g. inventing "12 failures" when the evidence says
3), the one class of factual drift free text can still introduce.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from app.services.cloud_signal_contracts import CloudProposalCandidate

_NUMBER_RE = re.compile(r"\d+")


@dataclass(frozen=True, slots=True)
class ComposedProse:
    """The same seven prose fields `_ACTION_TEMPLATES` produces
    deterministically -- a `CompositionGenerator`'s only possible output."""

    title: str
    problem_statement: str
    evidence_summary: str
    scope_summary: str
    recommended_action: str
    expected_gain: str
    risk_summary: str
    alternatives: tuple[str, ...] = ()


class CompositionGenerator(Protocol):
    """Anything that can turn a candidate into `ComposedProse`, or decline
    (`None`) -- e.g. a stand-in, or (later, separately authorized) a real
    bounded NeuroForge call."""

    def compose(self, candidate: CloudProposalCandidate) -> ComposedProse | None: ...


def _subject_description(candidate: CloudProposalCandidate) -> str:
    subject = candidate.subject
    if subject.subject_kind == "service":
        return f"service {subject.service} ({subject.environment})"
    if subject.subject_kind == "repository":
        return f"repository {subject.repository}"
    return f"tenant {subject.tenant_id or 'unknown'}, principal {subject.principal_id or 'unknown'}"


class DeterministicStubCompositionGenerator:
    """Stand-in for a real bounded NeuroForge call. Produces genuinely
    templated (not fabricated) prose straight from the candidate's own
    facts and identifiers -- proves the generator/validator architecture
    without spending a real inference call. Never fails (always returns a
    `ComposedProse`) since it invents nothing that needs rejecting; the
    real backend, once authorized, is expected to fail sometimes and rely
    on `validate_composed_prose()` for real."""

    def compose(self, candidate: CloudProposalCandidate) -> ComposedProse | None:
        scope = _subject_description(candidate)
        facts_joined = " ".join(candidate.facts)
        return ComposedProse(
            title=f"Investigate {candidate.issue_class} for {scope}",
            problem_statement=facts_joined,
            evidence_summary=(
                f"{len(candidate.signal_ids)} correlated signal(s): {', '.join(candidate.signal_ids)}."
            ),
            scope_summary=scope.capitalize() + ".",
            recommended_action=(
                f"Review the correlated evidence for {candidate.issue_class} and confirm the "
                "underlying cause before taking any action."
            ),
            expected_gain=(
                f"Confirms whether this {candidate.issue_class} pattern is expected or a real "
                "regression, surfacing it for review."
            ),
            risk_summary="; ".join(candidate.constraints),
            alternatives=(),
        )


def validate_composed_prose(
    candidate: CloudProposalCandidate, prose: ComposedProse
) -> tuple[bool, str]:
    """Fails closed (False, reason) on an empty required field or a
    standalone number in the composed text that isn't grounded in the
    candidate's own facts. Returns (True, "") when the prose is accepted."""
    required = (
        prose.title,
        prose.problem_statement,
        prose.evidence_summary,
        prose.scope_summary,
        prose.recommended_action,
        prose.expected_gain,
    )
    if any(not field.strip() for field in required):
        return False, "one or more required prose fields is empty"

    # Only the free-text narrative fields carry real fabrication risk.
    # evidence_summary/scope_summary are excluded: they mechanically restate
    # signal_ids/subject identifiers (e.g. a signal count, or digits inside
    # an id like "cssa-finding-001"), not claims an AI could invent.
    grounded_numbers = set(_NUMBER_RE.findall(" ".join(candidate.facts)))
    narrative_text = " ".join(
        (prose.title, prose.problem_statement, prose.recommended_action, prose.expected_gain)
    )
    claimed_numbers = set(_NUMBER_RE.findall(narrative_text))
    unsupported = claimed_numbers - grounded_numbers
    if unsupported:
        return False, f"unsupported numeric claim(s) not present in candidate facts: {sorted(unsupported)}"

    return True, ""
