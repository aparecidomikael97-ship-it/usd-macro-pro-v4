"""Canonical registry for recovered AtlasQuant/AION commitments since 2026-09-15.

This registry is read-only. Approval history never grants execution authority,
activates production, spends money, publishes content, or enables real trading.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, timedelta
import json
from pathlib import Path
from typing import Any, Mapping

SCHEMA = "ATLASQUANT_AION_HISTORICAL_COMMITMENTS_V1"
MANIFEST_PATH = "docs/continuidade/aion_historical_commitments_2026-10-02.json"
PERIOD_START = "2026-09-15"
PERIOD_END = "2026-10-02"
OFFICIAL_STATES = (
    "APROVADO / PENDENTE",
    "IMPLEMENTADO / EM VALIDAÇÃO",
    "VALIDADO",
    "DEPENDÊNCIA EXTERNA",
    "SUBSTITUÍDO",
    "DESCARTADO",
    "UNVERIFIED",
    "NEEDS HUMAN RECONCILIATION",
)
PENDING_STATES = {
    "APROVADO / PENDENTE",
    "DEPENDÊNCIA EXTERNA",
    "UNVERIFIED",
    "NEEDS HUMAN RECONCILIATION",
}
DAILY_COVERAGE_STATES = {
    "COVERED_WITH_EVIDENCE",
    "REQUIRES_CONVERSATION_SWEEP",
}
TERMINAL_STATES = {"VALIDADO", "SUBSTITUÍDO", "DESCARTADO"}
def _root(root: Path | None = None) -> Path:
    return Path(root) if root is not None else Path(__file__).resolve().parent


def load_manifest(root: Path | None = None) -> dict[str, Any]:
    return json.loads((_root(root) / MANIFEST_PATH).read_text(encoding="utf-8"))


def _expected_days() -> list[str]:
    start = date.fromisoformat(PERIOD_START)
    end = date.fromisoformat(PERIOD_END)
    rows: list[str] = []
    current = start
    while current <= end:
        rows.append(current.isoformat())
        current += timedelta(days=1)
    return rows


def validate_commitment(item: Mapping[str, Any], existing_paths: set[str]) -> list[str]:
    errors: list[str] = []
    item_id = str(item.get("id") or "")
    state = str(item.get("state") or "")
    evidence = [str(x) for x in item.get("evidence", []) if str(x).strip()]
    if not item_id:
        errors.append("commitment without id")
    if state not in OFFICIAL_STATES:
        errors.append(f"{item_id}: invalid state {state!r}")
    if not str(item.get("source_date") or "").startswith("2026-"):
        errors.append(f"{item_id}: source_date required")
    if not str(item.get("summary") or "").strip():
        errors.append(f"{item_id}: summary required")
    if state in PENDING_STATES and (item.get("implemented") is True or item.get("validated") is True):
        errors.append(f"{item_id}: pending commitment cannot be implemented/validated")
    if state == "IMPLEMENTADO / EM VALIDAÇÃO":
        if item.get("implemented") is not True or item.get("validated") is True or not evidence:
            errors.append(f"{item_id}: implemented/in-validation requires implementation evidence")
    if state == "VALIDADO" and (item.get("implemented") is not True or item.get("validated") is not True or not evidence):
        errors.append(f"{item_id}: validated commitment requires implementation and evidence")
    for ref in evidence:
        if ref not in existing_paths:
            errors.append(f"{item_id}: missing evidence {ref}")
    return errors


def validate_repository(root: Path | None = None) -> dict[str, Any]:
    base = _root(root)
    manifest = load_manifest(base)
    errors: list[str] = []
    if manifest.get("schema") != SCHEMA:
        errors.append("schema mismatch")
    period = manifest.get("period") if isinstance(manifest.get("period"), Mapping) else {}
    if period.get("start") != PERIOD_START or period.get("end") != PERIOD_END:
        errors.append("historical period mismatch")
    items = [x for x in manifest.get("commitments", []) if isinstance(x, Mapping)]
    ids = [str(x.get("id") or "") for x in items]
    if not items or len(ids) != len(set(ids)):
        errors.append("commitment registry empty or contains duplicate ids")
    existing_paths = {
        str(path.relative_to(base)).replace("\\", "/")
        for path in base.rglob("*")
        if path.is_file() and ".git" not in path.parts
    }
    for item in items:
        errors.extend(validate_commitment(item, existing_paths))
    items_by_day: dict[str, list[Mapping[str, Any]]] = {}
    for item in items:
        items_by_day.setdefault(str(item.get("source_date") or ""), []).append(item)

    coverage = [
        x for x in manifest.get("daily_coverage", [])
        if isinstance(x, Mapping)
    ]
    coverage_dates = [str(x.get("date") or "") for x in coverage]
    if coverage_dates != _expected_days():
        errors.append("daily coverage must include every day in period exactly once")
    for row in coverage:
        day = str(row.get("date") or "")
        state = str(row.get("state") or "")
        if state not in DAILY_COVERAGE_STATES:
            errors.append(f"{day}: invalid daily coverage state {state!r}")
        expected_ids = sorted(
            str(item.get("id") or "")
            for item in items_by_day.get(day, [])
            if str(item.get("id") or "")
        )
        actual_ids = sorted(str(x) for x in row.get("commitment_ids", []) or [])
        if actual_ids != expected_ids:
            errors.append(f"{day}: daily commitment id set does not match registry")
        for ref in row.get("source_paths", []) or []:
            if str(ref) not in existing_paths:
                errors.append(f"{day}: missing daily source {ref}")
        if row.get("closed") is True:
            if state != "COVERED_WITH_EVIDENCE":
                errors.append(f"{day}: closed day requires covered evidence")
            open_items = [
                item for item in items_by_day.get(day, [])
                if str(item.get("state") or "") not in TERMINAL_STATES
            ]
            if open_items:
                errors.append(f"{day}: closed day still has non-terminal commitments")
            closure_evidence = [str(x) for x in row.get("closure_evidence", []) or []]
            if not closure_evidence:
                errors.append(f"{day}: closed day requires closure evidence")
            for ref in closure_evidence:
                if ref not in existing_paths:
                    errors.append(f"{day}: missing closure evidence {ref}")

    for registry in manifest.get("inherited_registries", []) or []:
        if not isinstance(registry, Mapping):
            errors.append("invalid inherited registry entry")
            continue
        ref = str(registry.get("path") or "")
        if not ref or ref not in existing_paths:
            errors.append(f"missing inherited registry {ref}")

    if manifest.get("execution_authority") is not False:
        errors.append("historical registry must not grant execution authority")
    if manifest.get("automatic_activation") is not False:
        errors.append("historical registry must not auto-activate")
    unresolved_days = [
        str(row.get("date") or "")
        for row in coverage
        if row.get("state") == "REQUIRES_CONVERSATION_SWEEP"
    ]
    return {
        "schema": SCHEMA,
        "ok": not errors,
        "errors": errors,
        "count": len(items),
        "daily_coverage_count": len(coverage),
        "unresolved_days": unresolved_days,
    }


def historical_commitments_snapshot(root: Path | None = None) -> dict[str, Any]:
    manifest = load_manifest(root)
    items = [dict(x) for x in manifest.get("commitments", []) if isinstance(x, Mapping)]
    counts = Counter(str(x.get("state") or "UNKNOWN") for x in items)
    pending = [x["id"] for x in items if x.get("state") in PENDING_STATES]
    coverage = [
        dict(x) for x in manifest.get("daily_coverage", [])
        if isinstance(x, Mapping)
    ]
    unresolved_days = [
        str(row.get("date") or "")
        for row in coverage
        if row.get("state") == "REQUIRES_CONVERSATION_SWEEP"
    ]
    return {
        "schema": SCHEMA,
        "period": {"start": PERIOD_START, "end": PERIOD_END},
        "count": len(items),
        "by_state": dict(sorted(counts.items())),
        "pending_ids": pending,
        "commitments": items,
        "daily_coverage": coverage,
        "unresolved_days": unresolved_days,
        "inherited_gaps": list(manifest.get("inherited_gaps") or []),
        "execution_authority": False,
        "automatic_activation": False,
        "real_trading_enabled": False,
        "external_action_executed": False,
    }


__all__ = [
    "SCHEMA",
    "MANIFEST_PATH",
    "OFFICIAL_STATES",
    "load_manifest",
    "validate_commitment",
    "validate_repository",
    "historical_commitments_snapshot",
]
