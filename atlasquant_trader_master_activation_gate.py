"""Pure LAB gate for AtlasQuant Trader's *future* independent macro scheduler.

It NEVER enables a job, reads environment secrets, contacts a provider, writes
storage, starts AION, or approves spending. It evaluates structured evidence
claims; even a fully populated packet only becomes eligible for independent
human review. Proof references are NOT cryptographically verified here.

EODHD may meter billable API calls differently from HTTP requests. Its event
datetime has to be verified against an authoritative timezone before release
timing can be trusted. Consultation time is not an economic release time.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

SCHEMA = "ATLASQUANT_MASTER_ACTIVATION_PREFLIGHT_LAB_V1"
# Key, maximum age of documented evidence in civil days.
REQUIRED = (
    ("EODHD_ENTITLEMENT", 7),
    ("EODHD_EVENT_TIMEZONE", 7),
    ("EODHD_BILLABLE_UNITS", 7),
    ("FRED_ACCESS_AND_LIMITS", 7),
    ("BCB_SERIES_SEMANTICS", 30),
    ("CENTRAL_QUOTA_ATOMICITY", 30),
    ("CENTRAL_QUOTA_MULTI_REPLICA", 30),
    ("CENTRAL_QUOTA_CRASH_RECOVERY", 30),
    ("STORAGE_RBAC_AND_RETENTION", 30),
    ("SOURCE_FAILURE_NO_FABRICATION", 30),
    ("SCHEDULER_IDENTITY_AND_AUDIT", 30),
    ("KILL_SWITCH_PROVEN", 30),
    ("BUDGET_HEADROOM_CONFIRMED", 7),
    ("OWNER_REVIEW_RECORDED", 7),
)
CHECK_NAMES = frozenset(key for key, _ in REQUIRED)


def _aware(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or len(raw) > 45:
        return None
    try:
        point = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
    except (ValueError, OverflowError):
        return None
    return point.astimezone(timezone.utc) if point.tzinfo is not None else None


def _status(item: Any, now: datetime, max_days: int) -> str:
    if not isinstance(item, Mapping):
        return "MISSING"
    if item.get("result") != "PASS":
        return "NOT_PASSED" if item.get("result") == "FAIL" else "INVALID"
    checked = _aware(item.get("checked_at_utc"))
    # A human-readable evidence pointer and reviewer are required, but they
    # cannot establish authenticity; never echo them into the public UI.
    reference = item.get("reference")
    reviewer = item.get("reviewer")
    if (checked is None or not isinstance(reference, str) or
            not 4 <= len(reference.strip()) <= 200 or
            not isinstance(reviewer, str) or
            not 2 <= len(reviewer.strip()) <= 80):
        return "INVALID"
    age = now - checked
    if age < -timedelta(minutes=5):
        return "FUTURE_EVIDENCE"
    if age > timedelta(days=max_days):
        return "EXPIRED"
    return "CLAIMED_PASS_REQUIRES_AUDIT"


def assess_activation_preflight(
    evidence: Mapping[str, Any] | None = None, *,
    at: datetime | None = None
) -> dict[str, Any]:
    """Fail-closed *review* model, never an authorization or scheduler."""
    now = at if at is not None else datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError("Evaluation instant must be timezone aware")
    now = now.astimezone(timezone.utc)
    items = evidence if isinstance(evidence, Mapping) else {}
    checks = []
    for key, max_age in REQUIRED:
        state = _status(items.get(key), now, max_age)
        checks.append({
            "check": key, "state": state, "max_evidence_age_days": max_age,
        })
    blocked = [x["check"] for x in checks
               if x["state"] != "CLAIMED_PASS_REQUIRES_AUDIT"]
    return {
        "schema": SCHEMA,
        "evaluated_at_utc": now.isoformat(),
        "checks": checks,
        "blocking_checks": blocked,
        "claims_present": len(checks) - len(blocked),
        "required_checks": len(checks),
        "state": "HARD_NO_GO" if blocked else "PENDING_INDEPENDENT_REVIEW",
        "why_not": ("Evidências obrigatórias ausentes, inválidas ou vencidas."
                    if blocked else
                    "Alegações documentadas não substituem auditoria independente "
                    "nem aprovação humana para executar."),
        "scheduler_enabled": False,
        "activation_authorized": False,
        "aion_worker_enabled": False,
        "trade_authorized": False,
        "provider_requests": 0,
        "provider_billable_units": None,
        "distributed_quota_proven": False,
        "new_economic_release_confirmed": False,
    }


__all__ = ["SCHEMA", "REQUIRED", "CHECK_NAMES", "assess_activation_preflight"]
