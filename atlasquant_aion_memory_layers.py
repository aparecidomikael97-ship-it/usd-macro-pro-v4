"""Layered, deduplicated and persona-aware AION memory fabric."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping, Sequence
import json

SCHEMA = "ATLASQUANT_AION_MEMORY_LAYERS_V1"
VERSION = 1
LAYERS = (
    "session",
    "working",
    "project",
    "decision",
    "knowledge",
    "user_preference",
    "episodic",
    "checkpoint",
)
STATUSES = ("ACTIVE", "SUPERSEDED", "EXPIRED", "REJECTED")
TRUTH_STATES = ("CONFIRMED", "INFERENCE", "HYPOTHESIS", "UNKNOWN")
MEMORY_DOMAINS = ("TRADER", "BUSINESS", "INVESTMENTS", "CORE")
MAX_ENTRIES = 2000


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any, limit: int = 1600) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _digest(value: Any, length: int = 24) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return sha256(raw.encode("utf-8")).hexdigest()[:length]


def default_memory_layers() -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "entries": entries,
        "digest": _digest(entries),
        "recovery": {"state": "CLEAN", "rejected": 0},
        "automatic_cross_persona_access": False,
        "automatic_cross_domain_access": False,
    }


def normalize_memory_entry(raw: Mapping[str, Any]) -> dict[str, Any]:
    item = dict(raw or {})
    layer = _clean(item.get("layer"), 40).lower()
    content = _clean(item.get("content"), 4000)
    origin = _clean(item.get("origin"), 240)
    category = _clean(item.get("category"), 100).lower()
    if layer not in LAYERS or not content or not origin or not category:
        raise ValueError("memory entry requires valid layer, content, origin and category")
    truth = _clean(item.get("truth_state") or "UNKNOWN", 30).upper()
    if truth not in TRUTH_STATES:
        truth = "UNKNOWN"
    status = _clean(item.get("status") or "ACTIVE", 30).upper()
    if status not in STATUSES:
        status = "REJECTED"
    try:
        confidence = max(0.0, min(100.0, float(item.get("confidence") or 0.0)))
    except Exception:
        confidence = 0.0
    tags = []
    for value in list(item.get("tags") or [])[:30]:
        tag = _clean(value, 80).lower()
        if tag and tag not in tags:
            tags.append(tag)
    created_at = _clean(item.get("created_at"), 80) or _now()
    domain = _clean(item.get("domain"), 40).upper()
    if domain and domain not in MEMORY_DOMAINS:
        domain = "UNKNOWN"
    persona_raw = _clean(item.get("persona"), 80)
    persona = persona_raw.lower()
    version = _clean(item.get("version") or "1", 80)
    key_payload = {"layer": layer, "category": category, "persona": persona_raw, "tags": tags}
    if domain:
        key_payload["domain"] = domain
    memory_key = _clean(item.get("memory_key"), 180) or _digest(key_payload, 20)
    fingerprint_payload = {
        "layer": layer, "content": content, "origin": origin, "category": category,
        "persona": persona, "version": version,
    }
    if domain:
        fingerprint_payload["domain"] = domain
    fingerprint = _digest(fingerprint_payload)
    return {
        "memory_id": _clean(item.get("memory_id"), 80) or "MEM-" + fingerprint.upper(),
        "memory_key": memory_key,
        "layer": layer,
        "content": content,
        "origin": origin,
        "created_at": created_at,
        "confidence": round(confidence, 2),
        "valid_until": _clean(item.get("valid_until"), 80),
        "category": category,
        "version": version,
        "tags": tags,
        "status": status,
        "superseded_by": _clean(item.get("superseded_by"), 80),
        "truth_state": truth,
        "persona": persona,
        "domain": domain,
        "source_refs": [_clean(x, 300) for x in list(item.get("source_refs") or [])[:30] if _clean(x, 300)],
        "fingerprint": fingerprint,
    }


def normalize_memory_layers(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(raw, Mapping) or (
        raw and (raw.get("schema") != SCHEMA or raw.get("version") != VERSION)
    ):
        recovered = default_memory_layers()
        recovered["recovery"] = {"state": "RECOVERED_EMPTY", "rejected": 0}
        return recovered
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    rejected = 0
    for candidate in list(raw.get("entries") or [])[-MAX_ENTRIES * 2:]:
        try:
            item = normalize_memory_entry(candidate)
        except Exception:
            rejected += 1
            continue
        if item["fingerprint"] in seen:
            continue
        seen.add(item["fingerprint"])
        entries.append(item)
    entries = entries[-MAX_ENTRIES:]
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "entries": entries,
        "digest": _digest(entries),
        "recovery": {"state": "CLEAN" if not rejected else "RECOVERED_PARTIAL", "rejected": rejected},
        "automatic_cross_persona_access": False,
        "automatic_cross_domain_access": False,
    }


def remember(
    memory: Mapping[str, Any] | None,
    *,
    layer: str,
    content: Any,
    origin: Any,
    category: Any,
    confidence: Any = 0,
    truth_state: Any = "UNKNOWN",
    valid_until: Any = "",
    version: Any = "1",
    tags: Sequence[Any] | None = None,
    persona: Any = "",
    domain: Any = "",
    source_refs: Sequence[Any] | None = None,
    memory_key: Any = "",
) -> dict[str, Any]:
    state = normalize_memory_layers(memory)
    candidate = normalize_memory_entry({
        "layer": layer, "content": content, "origin": origin, "category": category,
        "confidence": confidence, "truth_state": truth_state, "valid_until": valid_until,
        "version": version, "tags": list(tags or []), "persona": persona, "domain": domain,
        "source_refs": list(source_refs or []), "memory_key": memory_key,
    })
    entries = deepcopy(state["entries"])
    if any(row["fingerprint"] == candidate["fingerprint"] for row in entries):
        return state
    for row in entries:
        if row["memory_key"] == candidate["memory_key"] and row["status"] == "ACTIVE":
            row["status"] = "SUPERSEDED"
            row["superseded_by"] = candidate["memory_id"]
    entries.append(candidate)
    return normalize_memory_layers({
        "schema": SCHEMA, "version": VERSION, "entries": entries,
    })


def _valid_until(value: Any) -> datetime | None:
    text = _clean(value, 80)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def recall(
    memory: Mapping[str, Any] | None,
    *,
    layers: Sequence[str] | None = None,
    persona: Any = "",
    domain: Any = "",
    accessor_profile: Any = "",
    explicit_domains: Sequence[Any] | None = None,
    tags: Sequence[Any] | None = None,
    include_superseded: bool = False,
    include_expired: bool = False,
    limit: int = 50,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    state = normalize_memory_layers(memory)
    selected_layers = {str(x).lower() for x in list(layers or LAYERS)}
    requested_persona = _clean(persona, 80).lower()
    requested_domain = _clean(domain, 40).upper()
    accessor = _clean(accessor_profile, 40).upper().replace(" ", "_")
    explicit: list[str] = []
    if accessor == "AION_CORE":
        for raw_domain in list(explicit_domains or []):
            token = _clean(raw_domain, 40).upper()
            if token in MEMORY_DOMAINS and token not in explicit:
                explicit.append(token)
    requested_tags = {_clean(x, 80).lower() for x in list(tags or []) if _clean(x, 80)}
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    else:
        current = current.astimezone(timezone.utc)
    out = []
    for row in reversed(state["entries"]):
        if row["layer"] not in selected_layers:
            continue
        if not include_superseded and row["status"] != "ACTIVE":
            continue
        # Persona-scoped memories are invisible without the exact persona.
        if row["persona"] and row["persona"] != requested_persona:
            continue
        row_domain = _clean(row.get("domain"), 40).upper()
        cross_domain = False
        if row_domain:
            if requested_domain and row_domain == requested_domain:
                cross_domain = False
            elif accessor == "AION_CORE" and row_domain in explicit:
                cross_domain = True
            else:
                continue
        if requested_tags and not requested_tags.intersection(row["tags"]):
            continue
        deadline = _valid_until(row.get("valid_until"))
        expired = deadline is not None and deadline <= current
        if expired and not include_expired:
            continue
        item = dict(row)
        item["automatic_cross_domain_access"] = False
        item["used_as_current_fact"] = False
        item["promoted"] = False
        if cross_domain:
            item["explicit_cross_domain"] = True
        if expired:
            item["status"] = "EXPIRED"
            if item.get("truth_state") == "CONFIRMED":
                item["truth_state"] = "UNKNOWN"
        out.append(item)
        if len(out) >= max(1, min(int(limit), 200)):
            break
    return out


def memory_layer_summary(memory: Mapping[str, Any] | None) -> dict[str, Any]:
    state = normalize_memory_layers(memory)
    entries = state["entries"]
    return {
        "schema": SCHEMA,
        "total": len(entries),
        "active": sum(row["status"] == "ACTIVE" for row in entries),
        "superseded": sum(row["status"] == "SUPERSEDED" for row in entries),
        "by_layer": {layer: sum(row["layer"] == layer for row in entries) for layer in LAYERS},
        "digest": state["digest"],
        "automatic_cross_persona_access": False,
        "automatic_cross_domain_access": False,
    }


__all__ = [
    "SCHEMA", "VERSION", "LAYERS", "STATUSES", "default_memory_layers",
    "normalize_memory_entry", "normalize_memory_layers", "remember", "recall",
    "memory_layer_summary",
]
