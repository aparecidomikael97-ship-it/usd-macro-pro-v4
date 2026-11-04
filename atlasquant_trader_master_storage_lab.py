"""Isolated LAB proof for durable macro quota and provenance (NO RUNNER).

SQLite is used only by an explicitly constructed test instance. Importing this
module never opens a database, calls an API, schedules a task, or enables AION.
A single DB file can coordinate local processes and survive their restarts; it
is NOT a multi-host/global provider quota solution. Production requires an
approved centralized transactional store, entitlement checks, and a kill switch.

A successful *consultation* is not a new economic release. Economic period,
consultation timestamp, provider, and any change in the observed value are
distinct. An API error never creates or overwrites an observation.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime, timezone
from math import isfinite
from pathlib import Path
import re
import sqlite3
from typing import Any, Iterator
from zoneinfo import ZoneInfo

SCHEMA = "ATLASQUANT_MASTER_DURABLE_LAB_V1"
BRT = ZoneInfo("America/Sao_Paulo")
PROVIDERS = {
    "EODHD_CALENDAR": "EODHD Economic Events",
    "BCB_SGS": "BCB-SGS",
    "FRED": "FRED",
}
KEY_RE = re.compile(r"^[a-zA-Z0-9_.:-]{1,120}$")
SERIES_RE = re.compile(r"^[A-Z0-9_]{2,64}$")


def _utc(at: datetime) -> datetime:
    if not isinstance(at, datetime) or at.tzinfo is None:
        raise ValueError("Consultation time must include a timezone")
    return at.astimezone(timezone.utc)


def _period(raw: str, checked: datetime) -> str:
    if not isinstance(raw, str) or not re.fullmatch(r"\d{4}-\d{2}(?:-\d{2})?", raw):
        raise ValueError("Economic period must be YYYY-MM or YYYY-MM-DD")
    try:
        first = date.fromisoformat(raw + "-01" if len(raw) == 7 else raw)
    except ValueError as error:
        raise ValueError("Invalid economic period") from error
    if first > checked.astimezone(BRT).date():
        raise ValueError("Cannot record a future economic period as observed")
    return raw


@contextmanager
def _connection(path: str) -> Iterator[sqlite3.Connection]:
    db = sqlite3.connect(path, isolation_level=None, timeout=10)
    try:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout = 10000")
        yield db
    finally:
        db.close()


class LabMacroLedger:
    """Opt-in, explicit-path SQLite contract; not wired into the live app."""

    def __init__(self, path: str | Path):
        if not isinstance(path, (str, Path)) or not str(path).strip():
            raise ValueError("An explicit lab database path is required")
        if str(path) == ":memory:":
            raise ValueError("In-memory DB cannot prove restart durability")
        self.path = str(path)

    def initialize(self) -> None:
        """Only explicit call that creates the LAB database/tables."""
        if not Path(self.path).parent.is_dir():
            raise ValueError("Database parent directory must already exist")
        with _connection(self.path) as db:
            db.execute("PRAGMA journal_mode = WAL")
            db.execute("PRAGMA synchronous = FULL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS attempts (
                    request_key TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    day_brt TEXT NOT NULL,
                    day_utc TEXT NOT NULL,
                    checked_at_utc TEXT NOT NULL,
                    state TEXT NOT NULL CHECK(state IN
                        ('RESERVED', 'SUCCEEDED', 'FAILED')),
                    error_code TEXT NOT NULL DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS attempts_budget_brt
                    ON attempts(provider, day_brt);
                CREATE INDEX IF NOT EXISTS attempts_budget_utc
                    ON attempts(provider, day_utc);
                CREATE TABLE IF NOT EXISTS observations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_key TEXT NOT NULL REFERENCES attempts(request_key),
                    provider TEXT NOT NULL,
                    series TEXT NOT NULL,
                    economic_period TEXT NOT NULL,
                    checked_at_utc TEXT NOT NULL,
                    origin TEXT NOT NULL,
                    unit TEXT NOT NULL,
                    value REAL NOT NULL,
                    change_kind TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS observations_latest
                    ON observations(provider, series, economic_period DESC, id DESC);
            """)

    def reserve(self, provider: str, request_key: str, at: datetime, *,
                daily_cap: int, authorized: bool = False) -> dict[str, Any]:
        """Atomically reserve budget BEFORE any external request.

        Unknown entitlement = disabled. Reservations survive crashes and even
        failures consume budget; callers may not retry with the same key.
        UTC and Brasília-day limits are BOTH enforced conservatively.
        """
        if provider not in PROVIDERS or not isinstance(request_key, str) or not KEY_RE.fullmatch(request_key):
            raise ValueError("Invalid provider or non-secret request key")
        if isinstance(daily_cap, bool) or not isinstance(daily_cap, int) or not 1 <= daily_cap <= 8:
            raise ValueError("LAB per-provider cap must be between 1 and 8")
        now = _utc(at)
        if authorized is not True:
            return {"state": "DISABLED", "reserved": False, "schema": SCHEMA}
        day_brt = now.astimezone(BRT).date().isoformat()
        day_utc = now.date().isoformat()
        with _connection(self.path) as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute(
                "SELECT provider, state FROM attempts WHERE request_key = ?",
                (request_key,),
            ).fetchone()
            if existing is not None:
                db.commit()
                if existing["provider"] != provider:
                    raise ValueError("Request key already belongs to another provider")
                return {"state": "EXISTS", "attempt_state": existing["state"],
                        "reserved": False, "schema": SCHEMA}
            brt_count = db.execute(
                "SELECT COUNT(*) FROM attempts WHERE provider=? AND day_brt=?",
                (provider, day_brt),
            ).fetchone()[0]
            utc_count = db.execute(
                "SELECT COUNT(*) FROM attempts WHERE provider=? AND day_utc=?",
                (provider, day_utc),
            ).fetchone()[0]
            if brt_count >= daily_cap or utc_count >= daily_cap:
                db.commit()
                return {"state": "CAP_EXHAUSTED", "reserved": False,
                        "schema": SCHEMA}
            db.execute(
                "INSERT INTO attempts(request_key, provider, day_brt, day_utc, checked_at_utc, state)"
                " VALUES (?, ?, ?, ?, ?, 'RESERVED')",
                (request_key, provider, day_brt, day_utc, now.isoformat()),
            )
            db.commit()
        return {"state": "RESERVED", "reserved": True, "schema": SCHEMA}

    def finish(self, request_key: str, *, succeeded: bool,
               error_code: str = "") -> str:
        """Record only an outcome; a failed call never writes a numeric value."""
        if not isinstance(request_key, str) or not KEY_RE.fullmatch(request_key):
            raise ValueError("Invalid request key")
        if not isinstance(succeeded, bool):
            raise ValueError("Explicit success/failure required")
        if (not isinstance(error_code, str) or len(error_code) > 48 or
                (error_code and not re.fullmatch(r"[A-Z0-9_]+", error_code))):
            raise ValueError("Error code must be a sanitized identifier")
        if not succeeded and not error_code:
            error_code = "SOURCE_UNAVAILABLE"
        state = "SUCCEEDED" if succeeded else "FAILED"
        with _connection(self.path) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT state FROM attempts WHERE request_key=?",
                             (request_key,)).fetchone()
            if row is None:
                db.rollback()
                raise ValueError("Unreserved request")
            if row["state"] != "RESERVED":
                db.commit()
                return "ALREADY_FINALIZED"
            db.execute(
                "UPDATE attempts SET state=?, error_code=? WHERE request_key=?",
                (state, "" if succeeded else error_code, request_key),
            )
            db.commit()
        return state

    def record_observation(self, request_key: str, *, provider: str, series: str,
                           economic_period: str, value: float,
                           unit: str, origin: str) -> str:
        """Save verified observation; 'new to ledger' != newly released."""
        if provider not in ("BCB_SGS", "FRED") or origin != PROVIDERS[provider]:
            raise ValueError("Unsupported or mismatched official source")
        if not isinstance(series, str) or not SERIES_RE.fullmatch(series):
            raise ValueError("Invalid official series identifier")
        if not isinstance(unit, str) or not 1 <= len(unit.strip()) <= 64:
            raise ValueError("Unit required")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
            raise ValueError("Finite numeric observation required")
        if abs(value) > 100000:
            raise ValueError("Observation outside conservative bound")
        with _connection(self.path) as db:
            db.execute("BEGIN IMMEDIATE")
            attempt = db.execute(
                "SELECT provider, state, checked_at_utc FROM attempts WHERE request_key=?",
                (request_key,),
            ).fetchone()
            if attempt is None or attempt["provider"] != provider or attempt["state"] != "SUCCEEDED":
                db.rollback()
                raise ValueError("Successful source consultation required")
            checked = datetime.fromisoformat(attempt["checked_at_utc"])
            period = _period(economic_period, checked)
            previous = db.execute(
                "SELECT value, unit, origin, request_key FROM observations"
                " WHERE provider=? AND series=? AND economic_period=?"
                " ORDER BY id DESC LIMIT 1",
                (provider, series, period),
            ).fetchone()
            if previous is not None:
                if (previous["value"] == float(value) and
                        previous["unit"] == unit.strip() and previous["origin"] == origin):
                    db.commit()
                    return "UNCHANGED_PERIOD"
                if previous["request_key"] == request_key:
                    db.rollback()
                    raise ValueError("A revision needs an independent new consultation")
                kind = "VALUE_CHANGE_UNVERIFIED_REVISION"
            else:
                kind = "FIRST_SEEN_PERIOD_NOT_RELEASE_PROOF"
            db.execute(
                "INSERT INTO observations(request_key, provider, series, economic_period,"
                " checked_at_utc, origin, unit, value, change_kind)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (request_key, provider, series, period, checked.isoformat(),
                 origin, unit.strip(), float(value), kind),
            )
            db.commit()
        return kind

    def snapshot(self, provider: str, series: str) -> dict[str, Any]:
        """Read historical evidence with no claim of current/new disclosure."""
        if provider not in PROVIDERS or not SERIES_RE.fullmatch(series):
            raise ValueError("Invalid provider or series")
        with _connection(self.path) as db:
            latest_check = db.execute(
                "SELECT checked_at_utc, state, error_code FROM attempts"
                " WHERE provider=? ORDER BY checked_at_utc DESC, rowid DESC LIMIT 1",
                (provider,),
            ).fetchone()
            observation = db.execute(
                "SELECT economic_period, checked_at_utc, origin, unit, value, change_kind"
                " FROM observations WHERE provider=? AND series=?"
                " ORDER BY economic_period DESC, id DESC LIMIT 1",
                (provider, series),
            ).fetchone()
        return {
            "schema": SCHEMA, "provider": provider, "series": series,
            "latest_check_at_utc": latest_check["checked_at_utc"] if latest_check else "",
            "latest_check_status": latest_check["state"] if latest_check else "NOT_CHECKED",
            "latest_error_code": latest_check["error_code"] if latest_check else "",
            "economic_period": observation["economic_period"] if observation else "",
            "observation_checked_at_utc": observation["checked_at_utc"] if observation else "",
            "origin": observation["origin"] if observation else "",
            "unit": observation["unit"] if observation else "",
            "last_known_value": observation["value"] if observation else None,
            "value_change_kind": observation["change_kind"] if observation else "",
            "current_display_value": None,
            "new_release_confirmed": False,
            "trade_authorized": False,
            "status": "HISTORICAL_ONLY_LAB" if observation else "NO_OBSERVATION",
        }


__all__ = ["SCHEMA", "PROVIDERS", "LabMacroLedger"]
