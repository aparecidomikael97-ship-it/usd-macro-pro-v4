"""In-memory shared quota backend contract for Trader macro scheduling (LAB).

No network, SQL, secrets, filesystem writes, Worker, paid API or scheduler.
Multiple client adapters may share this fake backend to exercise atomic budget
reservation, idempotent reconciliation, and commit-outcome-unknown handling.
This does NOT prove actual distributed storage or provider billing limits.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timezone
from threading import RLock
from typing import Any
import re

SCHEMA = "ATLASQUANT_MASTER_SHARED_QUOTA_FAKE_V1"
PROVIDER = "EODHD_CALENDAR"
KEY_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,120}$")


class CommitOutcomeUnknown(RuntimeError):
    """Reservation might have committed; NEVER blindly retry with a new key."""

    def __init__(self, request_key: str):
        super().__init__("reservation commit outcome unknown")
        self.request_key = request_key


class FakeCentralQuotaBackend:
    """One shared in-memory lock; deterministic test double, NOT a real store."""

    def __init__(self):
        self._lock = RLock()
        self._policies: dict[tuple[str, str], tuple[int, int]] = {}
        self._attempts: dict[str, dict[str, Any]] = {}
        self.commit_outcome_unknown_once = False
        self.available = True

    def declare_policy(self, day_utc: date, cap_units: int,
                       demand_reserve_units: int) -> str:
        if not isinstance(day_utc, date) or isinstance(day_utc, datetime):
            raise ValueError("UTC date required")
        if (isinstance(cap_units, bool) or not isinstance(cap_units, int) or
                not 1 <= cap_units <= 10000 or
                isinstance(demand_reserve_units, bool) or
                not isinstance(demand_reserve_units, int) or
                not 0 <= demand_reserve_units < cap_units):
            raise ValueError("Invalid LAB policy")
        with self._lock:
            key = (PROVIDER, day_utc.isoformat())
            existing = self._policies.get(key)
            proposal = (cap_units, demand_reserve_units)
            if existing is not None:
                return "UNCHANGED" if existing == proposal else "POLICY_CONFLICT"
            self._policies[key] = proposal
            return "DECLARED_LAB_ONLY"

    def reserve_atomic(self, request_key: str, *, day_utc: str, cost_units: int,
                       purpose: str) -> str:
        with self._lock:
            if not self.available:
                return "BACKEND_UNAVAILABLE"
            if request_key in self._attempts:
                return "DUPLICATE"
            policy = self._policies.get((PROVIDER, day_utc))
            if policy is None:
                return "NO_POLICY"
            cap, reserve = policy
            entries = [a for a in self._attempts.values()
                       if a["provider"] == PROVIDER and a["day_utc"] == day_utc]
            used = sum(a["cost_units"] for a in entries)
            scheduled = sum(a["cost_units"] for a in entries
                            if a["purpose"] == "SCHEDULED")
            if used + cost_units > cap:
                return "DAILY_UNITS_EXHAUSTED"
            if purpose == "SCHEDULED" and scheduled + cost_units > cap - reserve:
                return "DEMAND_RESERVE_PROTECTED"
            self._attempts[request_key] = {
                "provider": PROVIDER, "day_utc": day_utc,
                "purpose": purpose, "cost_units": cost_units,
                "state": "RESERVED",
            }
            if self.commit_outcome_unknown_once:
                self.commit_outcome_unknown_once = False
                raise CommitOutcomeUnknown(request_key)
            return "RESERVED_LAB_ONLY"

    def lookup(self, request_key: str) -> dict[str, Any] | None:
        with self._lock:
            if not self.available:
                raise RuntimeError("backend unavailable")
            record = self._attempts.get(request_key)
            return deepcopy(record) if record is not None else None

    def finish(self, request_key: str, *, succeeded: bool) -> str:
        with self._lock:
            if not self.available:
                return "BACKEND_UNAVAILABLE"
            row = self._attempts.get(request_key)
            if row is None:
                return "UNKNOWN_REQUEST"
            if row["state"] != "RESERVED":
                return "ALREADY_FINALIZED"
            row["state"] = "SUCCEEDED" if succeeded else "FAILED"
            return row["state"]

    def snapshot(self, day_utc: date) -> dict[str, Any]:
        with self._lock:
            key = (PROVIDER, day_utc.isoformat())
            cap_reserve = self._policies.get(key)
            units = sum(a["cost_units"] for a in self._attempts.values()
                        if a["provider"] == PROVIDER and a["day_utc"] == key[1])
            return {
                "schema": SCHEMA,
                "used_units_lab": units,
                "cap_units_lab": cap_reserve[0] if cap_reserve else None,
                "provider_counter_verified": False,
                "multi_host_verified": False,
                "scheduler_enabled": False,
                "aion_worker_enabled": False,
            }


class SharedQuotaClientLab:
    """Client boundary: never interprets unknown commit as an empty slot."""

    def __init__(self, backend: FakeCentralQuotaBackend):
        if not isinstance(backend, FakeCentralQuotaBackend):
            raise TypeError("Only LAB fake backend permitted")
        self.backend = backend

    def reserve(self, request_key: str, cost_units: int, *,
                at: datetime, purpose: str,
                entitlement_confirmed: bool = False) -> dict[str, Any]:
        if not isinstance(request_key, str) or not KEY_RE.fullmatch(request_key):
            raise ValueError("Non-secret request key required")
        if (isinstance(cost_units, bool) or not isinstance(cost_units, int) or
                not 1 <= cost_units <= 10000):
            raise ValueError("Known integer API-unit cost required")
        if purpose not in ("SCHEDULED", "ON_DEMAND"):
            raise ValueError("Invalid purpose")
        if not isinstance(at, datetime) or at.tzinfo is None:
            raise ValueError("Aware instant required")
        if entitlement_confirmed is not True:
            return {"state": "PROVIDER_NOT_AUTHORIZED", "reserved": False}
        day = at.astimezone(timezone.utc).date().isoformat()
        try:
            state = self.backend.reserve_atomic(
                request_key, day_utc=day, cost_units=cost_units, purpose=purpose)
        except CommitOutcomeUnknown:
            return {"state": "COMMIT_OUTCOME_UNKNOWN_RECONCILE",
                    "reserved": False, "retry_allowed": False}
        return {"state": state, "reserved": state == "RESERVED_LAB_ONLY",
                "retry_allowed": False}

    def reconcile(self, request_key: str) -> dict[str, Any]:
        """Read only the SAME idempotency key after an uncertain outcome."""
        if not isinstance(request_key, str) or not KEY_RE.fullmatch(request_key):
            raise ValueError("Invalid request key")
        try:
            record = self.backend.lookup(request_key)
        except Exception:
            return {"state": "BACKEND_UNAVAILABLE", "retry_allowed": False}
        if record is None:
            # Absence in a fake is NOT proof that a remote transaction rolled back.
            return {"state": "NO_DURABLE_PROOF", "retry_allowed": False}
        return {
            "state": "RESERVATION_FOUND",
            "attempt_state": record["state"],
            "cost_units": record["cost_units"],
            "retry_allowed": False,
        }


__all__ = ["SCHEMA", "CommitOutcomeUnknown", "FakeCentralQuotaBackend",
           "SharedQuotaClientLab"]
