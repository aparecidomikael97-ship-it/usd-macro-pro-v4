"""Shared dispute/consensus gate for AION specialist outputs.

The collective consumes structured specialist evidence that already exists in
memory. It never calls specialists, tools, providers or networks. Conflicting
confirmed claims remain a dispute; the collective never silently chooses a
winner.
"""
from __future__ import annotations

import json
import unicodedata
from typing import Any, Mapping, Sequence

from atlasquant_aion_truth import assess_truth


SCHEMA = "ATLASQUANT_AION_SPECIALIST_COLLECTIVE_V1"
MAX_RESULTS = 8
DANGEROUS_TRUE_FIELDS = (
    "executes_action",
    "real_orders_enabled",
    "permissions_expanded",
    "automatic_approval",
)


def _clean(value: Any, limit: int = 240) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _norm(value: Any) -> str:
    raw = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(ch for ch in raw if not unicodedata.combining(ch)).casefold().strip()


def _stable(value: Any) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError):
        return _clean(value, 1000)


def _claim_key(value: Any) -> str:
    return _norm(_clean(value, 500))


def _source_identity(claim: Mapping[str, Any]) -> str:
    ref = _clean(claim.get("source_ref") or claim.get("url"), 500)
    if ref:
        return "ref:" + ref.casefold()
    source = _clean(claim.get("source"), 200)
    return "source:" + source.casefold() if source else ""


def adjudicate_specialist_collective(
    results: Sequence[Mapping[str, Any]] | None,
    *,
    expected_specialists: Sequence[Any] | None = None,
    minimum_usable_specialists: int = 2,
    minimum_independent_sources: int = 2,
) -> dict[str, Any]:
    """Adjudicate specialist evidence without granting authority or execution."""
    expected = [
        _norm(item)
        for item in list(expected_specialists or [])
        if _norm(item)
    ]
    expected = list(dict.fromkeys(expected))
    raw_results = list(results or [])
    blockers: list[str] = []
    rows: list[dict[str, Any]] = []
    combined_claims: list[dict[str, Any]] = []
    seen_specialists: set[str] = set()
    usable_specialists: set[str] = set()
    all_sources: set[str] = set()
    claim_votes: dict[str, dict[str, set[str]]] = {}
    explicit_conflict = False

    if type(minimum_usable_specialists) is not int or minimum_usable_specialists < 1:
        blockers.append("MINIMUM_USABLE_SPECIALISTS_INVALID")
        minimum_usable_specialists = 2
    if type(minimum_independent_sources) is not int or minimum_independent_sources < 1:
        blockers.append("MINIMUM_INDEPENDENT_SOURCES_INVALID")
        minimum_independent_sources = 2
    if len(raw_results) > MAX_RESULTS:
        blockers.append("SPECIALIST_RESULT_LIMIT_EXCEEDED")
        raw_results = raw_results[:MAX_RESULTS]

    for index, raw in enumerate(raw_results):
        if not isinstance(raw, Mapping):
            blockers.append(f"SPECIALIST_RESULT_INVALID:{index}")
            continue
        specialist = _norm(raw.get("specialist"))
        if not specialist:
            blockers.append(f"SPECIALIST_ID_MISSING:{index}")
            continue
        if specialist in seen_specialists:
            blockers.append("DUPLICATE_SPECIALIST:" + specialist)
            continue
        seen_specialists.add(specialist)
        if expected and specialist not in expected:
            blockers.append("UNEXPECTED_SPECIALIST:" + specialist)

        privilege_claims = [
            field
            for field in DANGEROUS_TRUE_FIELDS
            if raw.get(field) is True
        ]
        if privilege_claims:
            blockers.append(
                "SPECIALIST_PRIVILEGE_CLAIM:"
                + specialist
                + ":"
                + privilege_claims[0]
            )

        claims = [
            dict(item)
            for item in list(raw.get("claims") or [])
            if isinstance(item, Mapping)
        ]
        assessment = assess_truth(claims)
        input_state = _clean(raw.get("input_state"), 60).upper()
        answer_truth = _clean(
            raw.get("answer_truth") or raw.get("truth_state"),
            60,
        ).upper()
        raw_conflict = (
            _clean(raw.get("conflict_state"), 40).upper() == "CONFLICT"
            or bool(raw.get("conflicts"))
        )
        explicit_conflict = explicit_conflict or raw_conflict

        unusable_input = input_state in {
            "ABSENT",
            "STALE",
            "CONFLICTING",
            "UNVERIFIED",
            "INVALID",
        }
        answer_denies_confirmed = bool(answer_truth) and answer_truth != "CONFIRMED"
        usable = (
            bool(claims)
            and not unusable_input
            and not answer_denies_confirmed
            and not raw_conflict
            and assessment.get("status") == "CONFIRMED"
            and assessment.get("conflict_state") != "CONFLICT"
        )

        if usable:
            usable_specialists.add(specialist)
            combined_claims.extend(claims)
            for claim in claims:
                truth = _clean(
                    claim.get("truth_state") or claim.get("kind"),
                    40,
                ).upper()
                if truth != "CONFIRMED":
                    continue
                key = _claim_key(claim.get("claim"))
                if not key:
                    continue
                stable_value = _stable(claim.get("value"))
                claim_votes.setdefault(key, {}).setdefault(
                    stable_value,
                    set(),
                ).add(specialist)
                source_id = _source_identity(claim)
                if source_id:
                    all_sources.add(source_id)

        rows.append({
            "specialist": specialist,
            "usable": usable,
            "input_state": input_state or "UNKNOWN",
            "answer_truth": answer_truth or str(
                assessment.get("status") or "UNKNOWN"
            ),
            "claim_count": len(claims),
            "truth_status": str(assessment.get("status") or "UNKNOWN"),
            "conflict_state": (
                "CONFLICT"
                if raw_conflict
                or assessment.get("conflict_state") == "CONFLICT"
                else "NONE"
            ),
            "executes_action": False,
        })

    aggregate = assess_truth(combined_claims)
    conflict_claims = list(aggregate.get("conflict_claims") or [])
    if explicit_conflict and not conflict_claims:
        conflict_claims = ["SPECIALIST_REPORTED_CONFLICT"]

    aligned_claims = sorted(
        key
        for key, values in claim_votes.items()
        if len(values) == 1
        and any(len(specialists) >= 2 for specialists in values.values())
    )
    missing = [
        specialist for specialist in expected
        if specialist not in seen_specialists
    ]

    if blockers:
        state = "BLOCK"
        next_action = "CORRECT_SPECIALIST_CONTRACT"
    elif aggregate.get("conflict_state") == "CONFLICT" or explicit_conflict:
        state = "DISPUTE"
        next_action = "REQUEST_INDEPENDENT_EVIDENCE"
    elif (
        missing
        or len(usable_specialists) < minimum_usable_specialists
        or len(all_sources) < minimum_independent_sources
    ):
        state = "REVIEW_REQUIRED"
        next_action = "REQUEST_INDEPENDENT_EVIDENCE"
    elif aligned_claims:
        state = "ALIGNED"
        next_action = "SYNTHESIZE_WITH_EVIDENCE"
    elif aggregate.get("status") == "CONFIRMED":
        state = "COMPLEMENTARY"
        next_action = "SYNTHESIZE_WITH_DISSENT_VISIBLE"
    else:
        state = "REVIEW_REQUIRED"
        next_action = "REQUEST_INDEPENDENT_EVIDENCE"

    return {
        "schema": SCHEMA,
        "state": state,
        "expected_specialists": expected,
        "received_specialists": sorted(seen_specialists),
        "usable_specialists": sorted(usable_specialists),
        "missing_specialists": missing,
        "specialist_rows": rows,
        "aggregate_truth": aggregate,
        "independent_source_count": len(all_sources),
        "aligned_claims": aligned_claims,
        "conflict_claims": conflict_claims,
        "blockers": list(dict.fromkeys(blockers)),
        "next_action": next_action,
        "winner_selected": False,
        "automatic_resolution": False,
        "private_chain_of_thought_exposed": False,
        "executes_action": False,
        "grants_permission": False,
        "real_orders_enabled": False,
    }


__all__ = [
    "SCHEMA",
    "MAX_RESULTS",
    "adjudicate_specialist_collective",
]
