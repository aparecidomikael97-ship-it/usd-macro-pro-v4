"""Versioned, isolated operational memory for AION personas.

Normalization is recovery: malformed/incompatible payloads are replaced with a
known-empty structure and a diagnostic record. No value is copied between
personas and no recovered value is treated as confirmed.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

SCHEMA = "ATLASQUANT_AION_PERSONA_MEMORY_V1"
VERSION = 1
PERSONAS = ("trader", "admin", "developer", "video", "business", "laboratory")
ENTRY_KINDS = ("decision", "technical_state", "pending", "test_result", "checkpoint")
MAX_ENTRIES_PER_PERSONA = 200


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _digest(personas: Mapping[str, Any]) -> str:
    raw = json.dumps(personas, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(raw.encode("utf-8")).hexdigest()


def default_persona_memory() -> dict[str, Any]:
    personas = {persona: {"entries": []} for persona in PERSONAS}
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "updated_at": _now(),
        "personas": personas,
        "digest": _digest(personas),
        "recovery": {"state": "CLEAN", "reason": ""},
    }


def _entry(raw: Mapping[str, Any], persona: str) -> dict[str, Any] | None:
    kind = str(raw.get("kind") or "").strip()
    if kind not in ENTRY_KINDS:
        return None
    entry_persona = str(raw.get("persona") or persona).strip()
    if entry_persona != persona:
        return None
    message = str(raw.get("message") or "").strip()[:2000]
    if not message:
        return None
    truth_state = str(raw.get("truth_state") or "UNKNOWN").strip().upper()
    if truth_state not in {"CONFIRMED", "INFERENCE", "HYPOTHESIS", "UNKNOWN"}:
        truth_state = "UNKNOWN"
    return {
        "persona": persona,
        "kind": kind,
        "message": message,
        "truth_state": truth_state,
        "source": str(raw.get("source") or "").strip()[:240],
        "created_at": str(raw.get("created_at") or "")[:64],
        "refs": [str(x)[:240] for x in list(raw.get("refs") or [])[:20] if str(x).strip()],
    }


def normalize_persona_memory(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        result = default_persona_memory()
        result["recovery"] = {"state": "RECOVERED_EMPTY", "reason": "payload is not a mapping"}
        return result
    if str(raw.get("schema") or "") != SCHEMA or raw.get("version") != VERSION:
        result = default_persona_memory()
        result["recovery"] = {"state": "RECOVERED_EMPTY", "reason": "schema/version incompatible"}
        return result
    raw_personas = raw.get("personas")
    if not isinstance(raw_personas, Mapping):
        result = default_persona_memory()
        result["recovery"] = {"state": "RECOVERED_EMPTY", "reason": "personas section invalid"}
        return result
    personas: dict[str, dict[str, list[dict[str, Any]]]] = {}
    rejected = 0
    for persona in PERSONAS:
        section = raw_personas.get(persona) if isinstance(raw_personas.get(persona), Mapping) else {}
        entries = []
        for item in list(section.get("entries") or [])[-MAX_ENTRIES_PER_PERSONA:]:
            normalized = _entry(item, persona) if isinstance(item, Mapping) else None
            if normalized is None:
                rejected += 1
            else:
                entries.append(normalized)
        personas[persona] = {"entries": entries}
    state = "CLEAN" if rejected == 0 else "RECOVERED_PARTIAL"
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "updated_at": str(raw.get("updated_at") or _now())[:64],
        "personas": personas,
        "digest": _digest(personas),
        "recovery": {"state": state, "reason": "" if not rejected else f"{rejected} invalid entries removed"},
    }


def append_persona_entry(
    memory: Mapping[str, Any] | None,
    persona: str,
    *,
    kind: str,
    message: str,
    truth_state: str = "UNKNOWN",
    source: str = "",
    refs: Sequence[Any] | None = None,
) -> dict[str, Any]:
    if persona not in PERSONAS:
        raise KeyError(f"unknown persona: {persona}")
    payload = normalize_persona_memory(memory)
    candidate = _entry({
        "persona": persona,
        "kind": kind,
        "message": message,
        "truth_state": truth_state,
        "source": source,
        "created_at": _now(),
        "refs": list(refs or []),
    }, persona)
    if candidate is None:
        raise ValueError("invalid persona memory entry")
    personas = deepcopy(payload["personas"])
    entries = list(personas[persona]["entries"])
    entries.append(candidate)
    personas[persona]["entries"] = entries[-MAX_ENTRIES_PER_PERSONA:]
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "updated_at": _now(),
        "personas": personas,
        "digest": _digest(personas),
        "recovery": dict(payload["recovery"]),
    }


def persona_entries(memory: Mapping[str, Any] | None, persona: str) -> list[dict[str, Any]]:
    if persona not in PERSONAS:
        return []
    normalized = normalize_persona_memory(memory)
    return [dict(x) for x in normalized["personas"][persona]["entries"]]


__all__ = [
    "ENTRY_KINDS",
    "MAX_ENTRIES_PER_PERSONA",
    "PERSONAS",
    "SCHEMA",
    "VERSION",
    "append_persona_entry",
    "default_persona_memory",
    "normalize_persona_memory",
    "persona_entries",
]
