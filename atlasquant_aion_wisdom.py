"""AION Wisdom Journal.

A controlled knowledge layer that turns validated observations and reviewed
lessons into auditable, revisable knowledge without allowing silent
self-modification.

The Wisdom Journal records:
- what was learned;
- where the lesson came from;
- confidence as knowledge confidence, never profit probability;
- truth state (CONFIRMED / INFERENCE / HYPOTHESIS / UNKNOWN);
- where the lesson applies;
- validation/review timestamps;
- whether review is due.

Nothing in this module changes production rules, strategy weights, deployment,
feature flags or broker execution.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import math
import re
import unicodedata

SCHEMA = "ATLASQUANT_AION_WISDOM_JOURNAL_V1"

MAX_ENTRIES = 3000
TRUTH_STATES = ("CONFIRMED", "INFERENCE", "HYPOTHESIS", "UNKNOWN")
ENTRY_STATES = ("ACTIVE", "RETIRED")
REVIEW_STATES = ("CURRENT", "DUE", "UNKNOWN")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any, limit: int = 1200) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _norm(value: Any) -> str:
    raw = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(ch for ch in raw if not unicodedata.combining(ch)).casefold().strip()


def _finite(value: Any) -> float | None:
    try:
        out = float(value)
        return out if math.isfinite(out) else None
    except Exception:
        return None


def _confidence(value: Any) -> float:
    number = _finite(value)
    if number is None:
        return 0.0
    return round(max(0.0, min(100.0, number)), 2)


def _list_text(
    value: Sequence[Any] | None,
    *,
    limit: int = 50,
    item_limit: int = 260,
) -> list[str]:
    rows = value if isinstance(value, (list, tuple)) else []
    out: list[str] = []
    for item in rows:
        text = _clean(item, item_limit)
        if text and text not in out:
            out.append(text)
        if len(out) >= limit:
            break
    return out


def _stable_digest(payload: Any, *, length: int = 24) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return sha256(raw.encode("utf-8")).hexdigest()[:length]


def _entry_id(topic: str, created_at: str, insight: str) -> str:
    return "WIS-" + _stable_digest(
        {"topic": topic, "created_at": created_at, "insight": insight},
        length=14,
    ).upper()


def _truth(value: Any) -> str:
    state = _clean(value, 40).upper()
    return state if state in TRUTH_STATES else "UNKNOWN"


def _entry_state(value: Any) -> str:
    state = _clean(value, 40).upper()
    return state if state in ENTRY_STATES else "ACTIVE"


def _parse_datetime(value: Any) -> datetime | None:
    raw = _clean(value, 80)
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def new_wisdom_entry(
    topic: Any,
    insight: Any,
    *,
    domain: Any = "general",
    truth_state: Any = "HYPOTHESIS",
    confidence_pct: Any = 0,
    evidence_refs: Sequence[Any] | None = None,
    applies_to: Sequence[Any] | None = None,
    source_episode_ids: Sequence[Any] | None = None,
    validation_note: Any = "",
    validated_at: Any = "",
    review_due_at: Any = "",
    created_at: str | None = None,
    created_by: Any = "AION",
) -> dict[str, Any]:
    topic_text = _clean(topic, 240)
    insight_text = _clean(insight, 1400)
    if not topic_text:
        raise ValueError("wisdom topic required")
    if not insight_text:
        raise ValueError("wisdom insight required")

    refs = _list_text(evidence_refs, limit=60)
    truth = _truth(truth_state)
    if truth == "CONFIRMED" and not refs:
        raise ValueError("confirmed wisdom requires evidence refs")

    created = str(created_at or _now())
    validated = _clean(validated_at, 80)
    due = _clean(review_due_at, 80)
    if validated and _parse_datetime(validated) is None:
        raise ValueError("invalid validated_at")
    if due and _parse_datetime(due) is None:
        raise ValueError("invalid review_due_at")

    return {
        "schema": SCHEMA,
        "wisdom_id": _entry_id(topic_text, created, insight_text),
        "state": "ACTIVE",
        "topic": topic_text,
        "domain": _clean(domain, 100).lower() or "general",
        "insight": insight_text,
        "truth_state": truth,
        "confidence_pct": _confidence(confidence_pct),
        "confidence_meaning": "KNOWLEDGE_CONFIDENCE_NOT_PROFIT_PROBABILITY",
        "evidence_refs": refs,
        "applies_to": _list_text(applies_to, limit=40),
        "source_episode_ids": _list_text(source_episode_ids, limit=60),
        "validation_note": _clean(validation_note, 1200),
        "validated_at": validated,
        "review_due_at": due,
        "created_at": created,
        "created_by": _clean(created_by, 120) or "AION",
        "retired_at": "",
        "retired_by": "",
        "retirement_note": "",
        "manual_review_required": True,
        "automatic_rule_change": False,
        "automatic_weight_change": False,
        "automatic_promotion": False,
        "real_orders_enabled": False,
    }


def normalize_wisdom_entry(raw: Mapping[str, Any]) -> dict[str, Any]:
    item = dict(raw or {})
    topic = _clean(item.get("topic"), 240)
    insight = _clean(item.get("insight"), 1400)
    if not topic or not insight:
        raise ValueError("wisdom topic and insight required")

    created = _clean(item.get("created_at"), 80) or _now()
    truth = _truth(item.get("truth_state"))
    refs = _list_text(item.get("evidence_refs"), limit=60)
    if truth == "CONFIRMED" and not refs:
        truth = "UNKNOWN"

    validated = _clean(item.get("validated_at"), 80)
    if validated and _parse_datetime(validated) is None:
        validated = ""
    due = _clean(item.get("review_due_at"), 80)
    if due and _parse_datetime(due) is None:
        due = ""

    state = _entry_state(item.get("state"))
    retired_at = _clean(item.get("retired_at"), 80)
    retired_by = _clean(item.get("retired_by"), 120)
    retirement_note = _clean(item.get("retirement_note"), 1200)
    if state == "RETIRED" and not retired_at:
        retired_at = created

    return {
        "schema": SCHEMA,
        "wisdom_id": _clean(item.get("wisdom_id"), 80)
        or _entry_id(topic, created, insight),
        "state": state,
        "topic": topic,
        "domain": _clean(item.get("domain"), 100).lower() or "general",
        "insight": insight,
        "truth_state": truth,
        "confidence_pct": _confidence(item.get("confidence_pct")),
        "confidence_meaning": "KNOWLEDGE_CONFIDENCE_NOT_PROFIT_PROBABILITY",
        "evidence_refs": refs,
        "applies_to": _list_text(item.get("applies_to"), limit=40),
        "source_episode_ids": _list_text(item.get("source_episode_ids"), limit=60),
        "validation_note": _clean(item.get("validation_note"), 1200),
        "validated_at": validated,
        "review_due_at": due,
        "created_at": created,
        "created_by": _clean(item.get("created_by"), 120) or "AION",
        "retired_at": retired_at,
        "retired_by": retired_by,
        "retirement_note": retirement_note,
        "manual_review_required": True,
        "automatic_rule_change": False,
        "automatic_weight_change": False,
        "automatic_promotion": False,
        "real_orders_enabled": False,
    }


def normalize_wisdom_entries(
    rows: Sequence[Mapping[str, Any]] | None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in list(rows or [])[-MAX_ENTRIES * 2 :]:
        if not isinstance(raw, Mapping):
            continue
        try:
            item = normalize_wisdom_entry(raw)
        except Exception:
            continue
        wid = item["wisdom_id"]
        if wid in seen:
            continue
        seen.add(wid)
        out.append(item)
    return out[-MAX_ENTRIES:]


def upsert_wisdom_entry(
    rows: Sequence[Mapping[str, Any]] | None,
    entry: Mapping[str, Any],
) -> list[dict[str, Any]]:
    current = normalize_wisdom_entries(rows)
    item = normalize_wisdom_entry(entry)
    out: list[dict[str, Any]] = []
    replaced = False
    for row in current:
        if row["wisdom_id"] == item["wisdom_id"]:
            out.append(item)
            replaced = True
        else:
            out.append(row)
    if not replaced:
        out.append(item)
    return out[-MAX_ENTRIES:]


def retire_wisdom_entry(
    entry: Mapping[str, Any],
    *,
    retired_by: Any,
    retirement_note: Any,
    retired_at: str | None = None,
) -> dict[str, Any]:
    item = normalize_wisdom_entry(entry)
    who = _clean(retired_by, 120)
    note = _clean(retirement_note, 1200)
    if not who:
        raise ValueError("retired_by required")
    if not note:
        raise ValueError("retirement note required")
    item.update({
        "state": "RETIRED",
        "retired_at": str(retired_at or _now()),
        "retired_by": who,
        "retirement_note": note,
    })
    return normalize_wisdom_entry(item)


def wisdom_review_state(entry: Mapping[str, Any], *, now: str | None = None) -> str:
    item = normalize_wisdom_entry(entry)
    if item["state"] == "RETIRED":
        return "CURRENT"
    due = _parse_datetime(item.get("review_due_at"))
    if due is None:
        return "UNKNOWN"
    current = _parse_datetime(now or _now())
    if current is None:
        return "UNKNOWN"
    return "DUE" if current >= due else "CURRENT"


def candidate_from_learning_episode(
    episode: Mapping[str, Any],
    *,
    created_by: Any = "AION",
    review_due_at: Any = "",
) -> dict[str, Any]:
    row = dict(episode or {})
    if str(row.get("state") or "").upper() != "SETTLED":
        raise ValueError("settled learning episode required")
    subject = _clean(row.get("subject"), 240)
    if not subject:
        raise ValueError("learning episode subject required")

    evaluation = _clean(row.get("evaluation"), 80).upper() or "RECORDED"
    prediction = _clean(row.get("prediction"), 500)
    actual = _clean(row.get("actual_outcome"), 500)
    cause = _clean(row.get("error_cause"), 80).upper()
    cause_truth = _clean(row.get("error_cause_truth"), 80).upper()
    refs = _list_text(row.get("evidence_refs"), limit=60)

    if row.get("correct") is True:
        insight = (
            f"Em {subject}, a previsão '{prediction}' correspondeu ao resultado observado "
            f"'{actual}'. Isso é um aprendizado observado, não uma regra universal."
        )
        truth = "INFERENCE" if refs else "HYPOTHESIS"
    elif row.get("correct") is False:
        if cause != "UNKNOWN" and cause_truth == "CONFIRMED":
            insight = (
                f"Em {subject}, a previsão '{prediction}' divergiu do resultado '{actual}'. "
                f"A causa registrada foi {cause}, com evidência marcada como confirmada."
            )
            truth = "INFERENCE" if refs else "HYPOTHESIS"
        else:
            insight = (
                f"Em {subject}, a previsão '{prediction}' divergiu do resultado '{actual}'. "
                "A causa permanece desconhecida; nenhuma causalidade adicional deve ser inventada."
            )
            truth = "HYPOTHESIS"
    else:
        insight = (
            f"Em {subject}, o episódio foi encerrado com avaliação {evaluation}. "
            "O resultado ainda não sustenta uma regra geral."
        )
        truth = "HYPOTHESIS"

    return new_wisdom_entry(
        subject,
        insight,
        domain=row.get("domain") or "general",
        truth_state=truth,
        confidence_pct=row.get("forecast_confidence_pct") or 0,
        evidence_refs=refs,
        applies_to=[row.get("domain") or "general"],
        source_episode_ids=[row.get("episode_id") or ""],
        validation_note=(
            "Candidato derivado de episódio SETTLED. Requer revisão humana antes de ser tratado "
            "como conhecimento confirmado."
        ),
        validated_at=row.get("settled_at") or "",
        review_due_at=review_due_at,
        created_by=created_by,
    )


def search_wisdom(
    query: Any,
    entries: Sequence[Mapping[str, Any]] | None,
    *,
    limit: int = 8,
    include_retired: bool = False,
) -> list[dict[str, Any]]:
    tokens = [
        x for x in re.findall(r"[a-z0-9][a-z0-9._/-]{2,}", _norm(query))
        if len(x) >= 3
    ]
    if not tokens:
        return []
    scored: list[tuple[int, dict[str, Any]]] = []
    for item in normalize_wisdom_entries(entries):
        if item["state"] == "RETIRED" and not include_retired:
            continue
        haystack = _norm(
            " ".join([
                item["topic"],
                item["domain"],
                item["insight"],
                " ".join(item["applies_to"]),
            ])
        )
        score = sum(haystack.count(token) for token in tokens)
        if score > 0:
            scored.append((score, item))
    scored.sort(key=lambda pair: (-pair[0], pair[1]["topic"], pair[1]["wisdom_id"]))
    return [dict(item) for _, item in scored[: max(1, min(int(limit or 8), 50))]]


def wisdom_evidence_hits(
    query: Any,
    entries: Sequence[Mapping[str, Any]] | None,
    *,
    limit: int = 5,
    now: str | None = None,
) -> list[dict[str, Any]]:
    """Return Wisdom Journal matches in the common AION evidence-hit shape.

    A CONFIRMED lesson is only emitted as CONFIRMED evidence while its review
    state is CURRENT. If review is DUE/UNKNOWN, it remains retrievable but is
    downgraded to INFERENCE so historical validation is never confused with
    current freshness.
    """
    rows = search_wisdom(query, entries, limit=limit, include_retired=False)
    out: list[dict[str, Any]] = []
    for index, item in enumerate(rows):
        review = wisdom_review_state(item, now=now)
        original_truth = str(item.get("truth_state") or "UNKNOWN").upper()
        effective_truth = original_truth
        if original_truth == "CONFIRMED" and review != "CURRENT":
            effective_truth = "INFERENCE"
        refs = list(item.get("evidence_refs") or [])
        excerpt = (
            f"[wisdom truth={original_truth}; review={review}; "
            f"confidence={float(item.get('confidence_pct') or 0):.1f}%] "
            f"{item.get('topic')}: {item.get('insight')}"
        )
        out.append({
            "path": f"WISDOM:{item.get('wisdom_id')}",
            "title": str(item.get("topic") or "Wisdom Journal"),
            "excerpt": excerpt[:1400],
            "score": max(1, len(rows) - index),
            "kind": effective_truth,
            "truth_state": effective_truth,
            "original_truth_state": original_truth,
            "review_state": review,
            "confidence_pct": float(item.get("confidence_pct") or 0),
            "source": "aion_wisdom_journal",
            "source_refs": refs,
            "wisdom_id": item.get("wisdom_id"),
            "knowledge_memory": True,
            "current_market_fact": False,
        })
    return out


def wisdom_summary(
    entries: Sequence[Mapping[str, Any]] | None,
    *,
    now: str | None = None,
) -> dict[str, Any]:
    rows = normalize_wisdom_entries(entries)
    active = [x for x in rows if x["state"] == "ACTIVE"]
    retired = [x for x in rows if x["state"] == "RETIRED"]
    by_truth = {state: 0 for state in TRUTH_STATES}
    due = 0
    unknown_review = 0
    for item in active:
        by_truth[item["truth_state"]] += 1
        review = wisdom_review_state(item, now=now)
        if review == "DUE":
            due += 1
        elif review == "UNKNOWN":
            unknown_review += 1
    return {
        "schema": SCHEMA,
        "entries": len(rows),
        "active": len(active),
        "retired": len(retired),
        "by_truth_state": by_truth,
        "review_due": due,
        "review_unknown": unknown_review,
        "confirmed_with_evidence": sum(
            1 for x in active
            if x["truth_state"] == "CONFIRMED" and bool(x["evidence_refs"])
        ),
        "manual_review_required": True,
        "automatic_rule_change": False,
        "automatic_weight_change": False,
        "automatic_promotion": False,
        "real_orders_enabled": False,
    }


def wisdom_digest(entries: Sequence[Mapping[str, Any]] | None) -> str:
    return _stable_digest(normalize_wisdom_entries(entries), length=24)


__all__ = [
    "SCHEMA",
    "TRUTH_STATES",
    "ENTRY_STATES",
    "REVIEW_STATES",
    "new_wisdom_entry",
    "normalize_wisdom_entry",
    "normalize_wisdom_entries",
    "upsert_wisdom_entry",
    "retire_wisdom_entry",
    "wisdom_review_state",
    "candidate_from_learning_episode",
    "search_wisdom",
    "wisdom_evidence_hits",
    "wisdom_summary",
    "wisdom_digest",
]
