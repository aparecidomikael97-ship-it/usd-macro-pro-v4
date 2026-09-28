"""System status from explicitly supplied scoped observations, never optimistic defaults."""
from datetime import datetime
from typing import Mapping
from .context import Context, Domain
from .evidence import Evidence, assess
from .registry import Registry
from .store import CoreStore


FIELDS = ("health", "pr", "build", "tests", "integrations", "known_errors", "latest_changes")


def observed_status(claim: str, records: tuple[Evidence, ...], now: datetime) -> dict:
    matching = tuple(x for x in records if x.claim == claim)
    if not matching:
        return {"state": "UNKNOWN", "value": None, "reason": "SOURCE_UNAVAILABLE", "evidence": []}
    truth = assess(matching, now)
    if truth["conflict_state"] == "CONFLICT":
        return {"state": "UNKNOWN", "value": None, "reason": "CONFLICTING_SOURCES", "evidence": truth["records"]}
    confirmed = [x for x in truth["records"] if x["truth_state"] == "CONFIRMED"]
    if not confirmed:
        return {"state": "UNKNOWN", "value": None, "reason": "NO_CURRENT_OBSERVED_EVIDENCE", "evidence": truth["records"]}
    return {"state": "SYSTEM_OBSERVED", "value": confirmed[0]["value"],
            "reason": "SUPPLIED_SOURCE_EVIDENCE", "evidence": truth["records"]}


def status(context: Context, registry: Registry, store: CoreStore | None,
           observations: Mapping[str, tuple[Evidence, ...]], now: datetime) -> dict:
    context.require_domain(Domain.ADMIN)
    if context.role != "ADMIN":
        raise ValueError("ROLE_DENIED")
    if set(observations) - set(FIELDS):
        raise ValueError("unknown administrative observation")
    capabilities = registry.snapshot()
    memory = store.read(context, now) if store else []
    return {
        "status": "OBSERVATION_REPORT",
        "system": {name: observed_status(name, observations.get(name, ()), now) for name in FIELDS},
        "available_modules": [x for x in capabilities if x["available"]],
        "unavailable_modules": [x for x in capabilities if not x["available"]],
        "pending_tasks": [x for x in memory if x["kind"] == "PENDING_TASK"],
        "completed_tasks": [x for x in memory if x["kind"] == "COMPLETED_TASK"],
        "priorities": [x for x in memory if x["kind"] == "PRIORITY"],
        "pending_inventory_state": "SCOPED_RECORDS_ONLY" if store else "UNAVAILABLE",
        "checkpoint": {"state": "AVAILABLE" if store else "UNAVAILABLE",
                       "storage": "LOCAL_SQLITE" if store and store.persistent else "EPHEMERAL" if store else "NONE",
                       "remote_persistence": "UNAVAILABLE"},
        "context_scope_only": True, "execution_authorized": False,
    }
