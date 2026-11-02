"""LAB simulation of EODHD billable-unit reservations across local processes.

This is NOT a provider entitlement check or a central multi-host ledger. A
single explicitly initialized SQLite file is only a concurrency/restart test
fixture for a future centralized transactional implementation (e.g. an
approved PostgreSQL store). One HTTP request may spend multiple API units.

Importing this module does not create a DB, fetch data, start a scheduler,
modify AION, place an order, or approve costs. Every reservation consumes
the conservative full estimated cost even after failure or process crash.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path
import re
import sqlite3
from typing import Any, Iterator

SCHEMA = "ATLASQUANT_MASTER_BILLABLE_UNITS_LAB_V1"
PROVIDER = "EODHD_CALENDAR"
KEY_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,120}$")
MAX_LAB_CAP = 10000


def _utc(at: datetime) -> datetime:
    if not isinstance(at, datetime) or at.tzinfo is None:
        raise ValueError("A timezone-aware UTC instant is required")
    return at.astimezone(timezone.utc)


@contextmanager
def _db(path: str) -> Iterator[sqlite3.Connection]:
    db = sqlite3.connect(path, timeout=10, isolation_level=None)
    try:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        db.execute("PRAGMA foreign_keys=ON")
        yield db
    finally:
        db.close()


class BillableUnitsLab:
    """One-file test double for a future shared, transactional quota ledger."""

    def __init__(self, path: str | Path):
        if not isinstance(path, (str, Path)) or not str(path).strip():
            raise ValueError("An explicit LAB file path is required")
        if str(path) == ":memory:":
            raise ValueError("In-memory DB cannot test restart durability")
        self.path = str(path)

    def initialize(self) -> None:
        """Explicit call; creates no directories or production resources."""
        if not Path(self.path).parent.is_dir():
            raise ValueError("LAB parent directory does not exist")
        with _db(self.path) as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA synchronous=FULL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS daily_policy (
                    provider TEXT NOT NULL,
                    day_utc TEXT NOT NULL,
                    cap_units INTEGER NOT NULL CHECK(cap_units > 0),
                    demand_reserve_units INTEGER NOT NULL
                        CHECK(demand_reserve_units >= 0),
                    PRIMARY KEY(provider, day_utc)
                );
                CREATE TABLE IF NOT EXISTS unit_attempts (
                    request_key TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    day_utc TEXT NOT NULL,
                    purpose TEXT NOT NULL CHECK(purpose IN ('SCHEDULED', 'ON_DEMAND')),
                    cost_units INTEGER NOT NULL CHECK(cost_units > 0),
                    reserved_at_utc TEXT NOT NULL,
                    state TEXT NOT NULL CHECK(state IN ('RESERVED', 'SUCCEEDED', 'FAILED')),
                    error_code TEXT NOT NULL DEFAULT '',
                    FOREIGN KEY(provider, day_utc)
                        REFERENCES daily_policy(provider, day_utc)
                );
                CREATE INDEX IF NOT EXISTS unit_attempts_by_day
                    ON unit_attempts(provider, day_utc);
            """)

    def declare_daily_policy(self, day_utc: date, *, cap_units: int,
                             demand_reserve_units: int, lab_approved: bool = False
                             ) -> str:
        """Never silently increase a limit; this approves *LAB simulation only*."""
        if not isinstance(day_utc, date) or isinstance(day_utc, datetime):
            raise ValueError("Explicit UTC civil date required")
        if (isinstance(cap_units, bool) or not isinstance(cap_units, int) or
                not 1 <= cap_units <= MAX_LAB_CAP):
            raise ValueError("Invalid lab cap")
        if (isinstance(demand_reserve_units, bool) or
                not isinstance(demand_reserve_units, int) or
                not 0 <= demand_reserve_units < cap_units):
            raise ValueError("Invalid on-demand reserve")
        if lab_approved is not True:
            return "DISABLED"
        with _db(self.path) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT cap_units, demand_reserve_units FROM daily_policy"
                " WHERE provider=? AND day_utc=?",
                (PROVIDER, day_utc.isoformat()),
            ).fetchone()
            if row is not None:
                db.commit()
                return ("UNCHANGED" if row["cap_units"] == cap_units and
                        row["demand_reserve_units"] == demand_reserve_units
                        else "POLICY_CONFLICT")
            db.execute(
                "INSERT INTO daily_policy"
                "(provider, day_utc, cap_units, demand_reserve_units)"
                " VALUES (?, ?, ?, ?)",
                (PROVIDER, day_utc.isoformat(), cap_units, demand_reserve_units),
            )
            db.commit()
        return "DECLARED_LAB_ONLY"

    def reserve(self, request_key: str, cost_units: int, *,
                purpose: str, at: datetime,
                entitlement_confirmed: bool = False) -> dict[str, Any]:
        """Atomic local double; unknown cost or entitlement never gets a slot."""
        if not isinstance(request_key, str) or not KEY_RE.fullmatch(request_key):
            raise ValueError("Non-secret stable request key required")
        if (isinstance(cost_units, bool) or not isinstance(cost_units, int) or
                not 1 <= cost_units <= MAX_LAB_CAP):
            raise ValueError("Explicit positive billable-unit cost required")
        if purpose not in ("SCHEDULED", "ON_DEMAND"):
            raise ValueError("Invalid request purpose")
        now = _utc(at)
        if entitlement_confirmed is not True:
            return {"state": "PROVIDER_NOT_AUTHORIZED", "reserved": False}
        day = now.date().isoformat()  # EODHD main daily counter resets at GMT midnight.
        with _db(self.path) as db:
            db.execute("BEGIN IMMEDIATE")
            prior = db.execute(
                "SELECT state FROM unit_attempts WHERE request_key=?",
                (request_key,),
            ).fetchone()
            if prior is not None:
                db.commit()
                return {"state": "DUPLICATE", "attempt_state": prior["state"],
                        "reserved": False}
            policy = db.execute(
                "SELECT cap_units, demand_reserve_units FROM daily_policy"
                " WHERE provider=? AND day_utc=?",
                (PROVIDER, day),
            ).fetchone()
            if policy is None:
                db.commit()
                return {"state": "NO_APPROVED_LAB_POLICY", "reserved": False}
            used, scheduled = db.execute(
                "SELECT COALESCE(SUM(cost_units), 0),"
                " COALESCE(SUM(CASE WHEN purpose='SCHEDULED' THEN cost_units ELSE 0 END), 0)"
                " FROM unit_attempts WHERE provider=? AND day_utc=?",
                (PROVIDER, day),
            ).fetchone()
            if used + cost_units > policy["cap_units"]:
                db.commit()
                return {"state": "DAILY_UNITS_EXHAUSTED", "reserved": False}
            if (purpose == "SCHEDULED" and
                    scheduled + cost_units >
                    policy["cap_units"] - policy["demand_reserve_units"]):
                db.commit()
                return {"state": "DEMAND_RESERVE_PROTECTED", "reserved": False}
            db.execute(
                "INSERT INTO unit_attempts"
                "(request_key, provider, day_utc, purpose, cost_units, reserved_at_utc, state)"
                " VALUES (?, ?, ?, ?, ?, ?, 'RESERVED')",
                (request_key, PROVIDER, day, purpose, cost_units, now.isoformat()),
            )
            db.commit()
        return {"state": "RESERVED_LAB_ONLY", "reserved": True}

    def finish(self, request_key: str, *, succeeded: bool,
               error_code: str = "") -> str:
        """No credit refund for failure/crash, preventing retry overspend."""
        if not isinstance(request_key, str) or not KEY_RE.fullmatch(request_key):
            raise ValueError("Invalid request key")
        if not isinstance(succeeded, bool):
            raise ValueError("Explicit outcome required")
        if (not isinstance(error_code, str) or len(error_code) > 48 or
                (error_code and not re.fullmatch(r"[A-Z0-9_]+", error_code))):
            raise ValueError("Sanitized error code required")
        state = "SUCCEEDED" if succeeded else "FAILED"
        with _db(self.path) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT state FROM unit_attempts WHERE request_key=?",
                             (request_key,)).fetchone()
            if row is None:
                db.rollback()
                raise ValueError("Unreserved request")
            if row["state"] != "RESERVED":
                db.commit()
                return "ALREADY_FINALIZED"
            db.execute(
                "UPDATE unit_attempts SET state=?, error_code=? WHERE request_key=?",
                (state, "" if succeeded else (error_code or "SOURCE_UNAVAILABLE"),
                 request_key),
            )
            db.commit()
        return state

    def snapshot(self, day_utc: date) -> dict[str, Any]:
        """Reports LAB reservations, NEVER actual provider billing balance."""
        if not isinstance(day_utc, date) or isinstance(day_utc, datetime):
            raise ValueError("UTC civil date required")
        day = day_utc.isoformat()
        with _db(self.path) as db:
            policy = db.execute(
                "SELECT cap_units, demand_reserve_units FROM daily_policy"
                " WHERE provider=? AND day_utc=?",
                (PROVIDER, day),
            ).fetchone()
            used, scheduled = db.execute(
                "SELECT COALESCE(SUM(cost_units), 0),"
                " COALESCE(SUM(CASE WHEN purpose='SCHEDULED' THEN cost_units ELSE 0 END), 0)"
                " FROM unit_attempts WHERE provider=? AND day_utc=?",
                (PROVIDER, day),
            ).fetchone()
        cap = policy["cap_units"] if policy else None
        reserve = policy["demand_reserve_units"] if policy else None
        return {
            "schema": SCHEMA, "provider": PROVIDER, "day_utc": day,
            "cap_units_lab": cap, "demand_reserve_units_lab": reserve,
            "units_reserved_lab": used, "scheduled_units_lab": scheduled,
            "remaining_units_lab": max(0, cap - used) if cap is not None else None,
            "provider_meter_verified": False,
            "global_multi_host_quota_proven": False,
            "scheduler_enabled": False, "aion_worker_enabled": False,
            "trade_authorized": False,
        }


__all__ = ["SCHEMA", "PROVIDER", "BillableUnitsLab"]
