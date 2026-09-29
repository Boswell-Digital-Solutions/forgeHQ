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

TWO GENERATORS: `DeterministicStubCompositionGenerator` (no network, the
default stand-in, mirroring `ai_shaper_service.py`'s
`DeterministicHygieneGenerator`) and `NeuroForgeCompositionGenerator` (a
real bounded call to NeuroForge's chat ladder). The real one has only ever
been unit-tested against an injected fake transport -- NO live call has been
made from this repo's tests or from the session that wrote it, because no
`NEUROFORGE_API_KEY`/`NEUROFORGE_SERVICE_KEY` was available to that session
(a live probe returned 401 UNAUTHENTICATED). It gets its key from the
environment at call time, injected by Forge_Command at spawn like every
other forgeHQ NeuroForge call. It is still opt-in: nothing constructs it
by default.

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

import json
import os
import re
import urllib.request
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


DEFAULT_NEUROFORGE_URL = "https://neuroforge-9lxc.onrender.com"

_SYSTEM_PROMPT = (
    "You compose a review-queue entry for a human operator from structured "
    "evidence. Use ONLY the facts provided. Do not invent numbers, counts, "
    "names, causes, or events that are not in the facts. Do not recommend "
    "executing, deploying, rolling back, or changing any system -- "
    "recommend investigation and review only. Reply with ONE JSON object "
    "and nothing else, with exactly these string keys: title, "
    "problem_statement, evidence_summary, scope_summary, recommended_action, "
    "expected_gain, risk_summary, and alternatives (a JSON array of strings, "
    "may be empty)."
)

_REQUIRED_KEYS = (
    "title",
    "problem_statement",
    "evidence_summary",
    "scope_summary",
    "recommended_action",
    "expected_gain",
    "risk_summary",
)


def _build_user_prompt(candidate: CloudProposalCandidate) -> str:
    # The ONLY candidate data a model ever sees: no fingerprint, no hashes,
    # no signal internals, no severity/confidence -- see module docstring.
    facts = "\n".join(f"- {fact}" for fact in candidate.facts)
    constraints = "\n".join(f"- {c}" for c in candidate.constraints)
    return (
        f"Subject: {_subject_description(candidate)}\n"
        f"Issue class: {candidate.issue_class}\n"
        f"Recommended action class: {candidate.recommended_action_class}\n"
        f"Signal count: {len(candidate.signal_ids)}\n\n"
        f"Facts:\n{facts}\n\nConstraints:\n{constraints}\n"
    )


def _parse_prose(text: str | None) -> ComposedProse | None:
    """Parse a model reply into `ComposedProse`, or None on anything
    malformed. Strips a single surrounding markdown fence."""
    if not text or not text.strip():
        return None
    body = text.strip()
    if body.startswith("```"):
        lines = body.splitlines()[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        body = "\n".join(lines)
    try:
        data = json.loads(body)
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    if any(not isinstance(data.get(key), str) for key in _REQUIRED_KEYS):
        return None
    alternatives = data.get("alternatives", [])
    if not isinstance(alternatives, list) or any(not isinstance(a, str) for a in alternatives):
        return None
    return ComposedProse(
        **{key: data[key] for key in _REQUIRED_KEYS},
        alternatives=tuple(alternatives),
    )


def _default_transport(url: str, body: dict, headers: dict, timeout: float) -> dict:
    request = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST"
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


class NeuroForgeCompositionGenerator:
    """Real bounded-composition backend: one call to NeuroForge's governed
    chat ladder (`POST /api/v1/chat`), same endpoint and auth posture as
    `app/drivers/neuroforge_generator.py`.

    FAILS CLOSED ON EVERYTHING: no API key, transport error, non-JSON reply,
    a missing/mistyped field -- all return None, so the translator falls
    through to its own fail-closed path. It never sends an unauthenticated
    request, and `validate_composed_prose()` still runs on whatever it
    returns (the translator applies it to every generator).

    The key is read from `NEUROFORGE_API_KEY`/`NEUROFORGE_SERVICE_KEY` at
    call time -- injected by Forge_Command at spawn, never stored in a
    forgeHQ file. `transport` is injectable so tests never touch a network.
    """

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_NEUROFORGE_URL,
        api_key: str | None = None,
        task_type: str = "cloud_proposal_composition",
        max_tokens: int = 1024,
        temperature: float = 0.0,
        timeout: float = 60.0,
        transport=None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._task_type = task_type
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._timeout = timeout
        self._transport = transport or _default_transport

    def _resolve_key(self) -> str | None:
        if self._api_key:
            return self._api_key
        return os.getenv("NEUROFORGE_API_KEY") or os.getenv("NEUROFORGE_SERVICE_KEY") or None

    def build_request(self, candidate: CloudProposalCandidate) -> dict:
        return {
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_prompt(candidate)},
            ],
            "task_type": self._task_type,
            "max_tokens": self._max_tokens,
            "temperature": self._temperature,
        }

    def compose(self, candidate: CloudProposalCandidate) -> ComposedProse | None:
        key = self._resolve_key()
        if not key:
            return None
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {key}"}
        try:
            decision = self._transport(
                f"{self._base_url}/api/v1/chat",
                self.build_request(candidate),
                headers,
                self._timeout,
            )
        except Exception:  # transport / non-2xx -- a failed attempt, fail closed
            return None
        if not isinstance(decision, dict):
            return None
        return _parse_prose(decision.get("content"))


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
