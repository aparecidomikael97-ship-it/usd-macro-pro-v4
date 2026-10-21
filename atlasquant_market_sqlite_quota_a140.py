"""AION P0 A140 — SQLite LAB-only conservative market quota journal.

Guarantees within a single local SQLite file: atomic reserve-before-read under
BEGIN IMMEDIATE, unique run identifiers, durable retained UNKNOWN reservations,
configured-limit immutability, committed local-output observation, and no
automatic refund, replay or retry. These are local crash/concurrency controls.

NOT provided: provider execution, independently trusted origin, external
signature, rollback resistance, cross-machine durability, H0 readiness,
HUMAN_OWNER identity, exactly-once provider execution or production IAM.
"""
from __future__ import annotations

from pathlib import Path
import re
import sqlite3

DB_FILENAME="aion_a140_quota_ledger.sqlite3"
SCHEMA="AION_P0_MARKET_QUOTA_SQLITE_LAB_V1"
RUN_ID_RE=re.compile(r"[a-z][a-z0-9_-]{7,47}")
DIGEST_RE=re.compile(r"[0-9a-f]{64}")


class QuotaLabUnavailable(RuntimeError):
    """Unknown storage state: do not fetch, retry, refund or grant authority."""


class SQLiteLabReservationLedger:
    """Offline SQLite conservative credit reservations.

    A local disk is not an independent witness. A copied/rolled-back SQLite
    database can replay stale history; a later integration MUST address this
    outside the same administrative and filesystem trust domain.
    """

    independent_witness_enrolled=False
    external_provider_effect_proven=False
    human_owner_verified=False
    automatic_retry_allowed=False

    def __init__(self, *, lab_dir, checkout_root, limit:int):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("Quota limit must be a literal integer between 1 and 100")
        lab=Path(lab_dir)
        checkout=Path(checkout_root)
        if not lab.is_absolute() or not checkout.is_absolute():
            raise ValueError("LAB directory and checkout must be absolute")
        if not lab.is_dir() or not checkout.is_dir():
            raise ValueError("Existing directories required")
        # Reject lexical symlink components too; resolve() alone would hide it.
        for part in (lab, *lab.parents):
            if part.is_symlink():
                raise ValueError("LAB path includes symbolic link")
        root=checkout.resolve(strict=True)
        resolved=lab.resolve(strict=True)
        if resolved==root or resolved.is_relative_to(root):
            raise ValueError("Quota database must be outside source checkout")
        path=resolved/DB_FILENAME
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise ValueError("Quota database is not a normal regular file")
        self.path=path
        self.limit=limit
        self._initialize()

    def _check_path(self):
        if self.path.is_symlink() or not self.path.is_file():
            raise QuotaLabUnavailable("Quota database missing or is a symlink")
        for part in (self.path.parent,*self.path.parent.parents):
            if part.is_symlink():
                raise QuotaLabUnavailable("Untrusted LAB path")
        return self.path

    def _connect(self):
        self._check_path()
        try:
            db=sqlite3.connect(str(self.path),timeout=0.25,isolation_level=None)
            db.execute("PRAGMA busy_timeout=250")
            db.execute("PRAGMA synchronous=FULL")
            db.execute("PRAGMA foreign_keys=ON")
            return db
        except sqlite3.Error as exc:
            raise QuotaLabUnavailable("SQLite open or PRAGMA failed") from exc

    def _initialize(self):
        existed=self.path.exists()
        try:
            # Only a new DB may receive an initial policy. An existing DB
            # without meta is corrupt/unsafe, never silently reinitialized.
            if not existed:
                try:
                    with self.path.open("xb"):
                        pass
                except FileExistsError:
                    existed=True
            if self.path.is_symlink():
                raise ValueError("Symlink quota file denied")
            with self._connect() as db:
                db.execute("BEGIN IMMEDIATE")
                db.execute(
                    "CREATE TABLE IF NOT EXISTS quota_policy ("
                    "singleton INTEGER PRIMARY KEY CHECK (singleton=1),"
                    "schema TEXT NOT NULL,"
                    "configured_limit INTEGER NOT NULL CHECK(configured_limit BETWEEN 1 AND 100))"
                )
                db.execute(
                    "CREATE TABLE IF NOT EXISTS reservations ("
                    "run_id TEXT PRIMARY KEY NOT NULL,"
                    "units INTEGER NOT NULL CHECK(units BETWEEN 1 AND 100),"
                    "state TEXT NOT NULL CHECK(state IN ('RESERVED_UNCERTAIN','LOCAL_OUTPUT_OBSERVED')),"
                    "payload_sha256 TEXT)"
                )
                item=db.execute(
                    "SELECT schema,configured_limit FROM quota_policy WHERE singleton=1"
                ).fetchone()
                if item is None and not existed:
                    db.execute(
                        "INSERT INTO quota_policy(singleton,schema,configured_limit) VALUES(1,?,?)",
                        (SCHEMA,self.limit),
                    )
                    item=(SCHEMA,self.limit)
                if item!=(SCHEMA,self.limit):
                    raise QuotaLabUnavailable("SQLite LAB quota policy missing or changed")
                db.execute("COMMIT")
            # Detect clearly corrupt pages, not a trusted anti-rollback proof.
            with self._connect() as db:
                check=db.execute("PRAGMA quick_check").fetchone()
                if check!=("ok",):
                    raise QuotaLabUnavailable("SQLite integrity check failed")
                self._verify_policy(db)
        except (sqlite3.Error,OSError) as exc:
            raise QuotaLabUnavailable("SQLite LAB initialization unavailable") from exc

    def _verify_policy(self,db):
        policy=db.execute(
            "SELECT schema,configured_limit FROM quota_policy WHERE singleton=1"
        ).fetchone()
        if policy!=(SCHEMA,self.limit):
            raise QuotaLabUnavailable("Untrusted or changed quota policy")

    def reserve(self, run_id, units)->bool:
        if (
            type(run_id) is not str or RUN_ID_RE.fullmatch(run_id) is None
            or type(units) is not int or units<=0 or units>100
        ):
            return False
        db=None
        try:
            db=self._connect()
            db.execute("BEGIN IMMEDIATE")
            self._verify_policy(db)
            used=db.execute(
                "SELECT COALESCE(SUM(units),0) FROM reservations"
            ).fetchone()[0]
            existing=db.execute(
                "SELECT run_id FROM reservations WHERE run_id=?",(run_id,)
            ).fetchone()
            if existing is not None or used+units>self.limit:
                db.execute("ROLLBACK")
                return False
            db.execute(
                "INSERT INTO reservations(run_id,units,state,payload_sha256)"
                " VALUES(?,?,'RESERVED_UNCERTAIN',NULL)",(run_id,units),
            )
            db.execute("COMMIT")
            # A separate connection read confirms our own SQLite state.
            # If this fails, return denial, do NOT resend the source read.
            state=self.reservation_state(run_id)
            return bool(
                state and state["units"]==units
                and state["state"]=="RESERVED_UNCERTAIN"
            )
        except (sqlite3.Error,OSError,QuotaLabUnavailable):
            if db is not None and db.in_transaction:
                try: db.rollback()
                except sqlite3.Error: pass
            return False
        finally:
            if db is not None:
                db.close()

    def record_local_output(self, run_id, payload_sha256)->bool:
        if (
            type(run_id) is not str or RUN_ID_RE.fullmatch(run_id) is None
            or type(payload_sha256) is not str
            or DIGEST_RE.fullmatch(payload_sha256) is None
        ):
            return False
        db=None
        try:
            db=self._connect()
            db.execute("BEGIN IMMEDIATE")
            self._verify_policy(db)
            result=db.execute(
                "UPDATE reservations SET state='LOCAL_OUTPUT_OBSERVED',"
                "payload_sha256=? WHERE run_id=? AND state='RESERVED_UNCERTAIN'",
                (payload_sha256,run_id),
            )
            if result.rowcount!=1:
                db.execute("ROLLBACK")
                return False
            db.execute("COMMIT")
            recorded=self.reservation_state(run_id)
            return bool(
                recorded and recorded["state"]=="LOCAL_OUTPUT_OBSERVED"
                and recorded["payload_sha256"]==payload_sha256
            )
        except (sqlite3.Error,OSError,QuotaLabUnavailable):
            if db is not None and db.in_transaction:
                try: db.rollback()
                except sqlite3.Error: pass
            return False
        finally:
            if db is not None:
                db.close()

    def reservation_state(self, run_id):
        if type(run_id) is not str or RUN_ID_RE.fullmatch(run_id) is None:
            return None
        try:
            with self._connect() as db:
                self._verify_policy(db)
                row=db.execute(
                    "SELECT units,state,payload_sha256 FROM reservations WHERE run_id=?",
                    (run_id,),
                ).fetchone()
                if row is None:
                    return None
                return {
                    "run_id":run_id,
                    "units":row[0],
                    "state":row[1],
                    "payload_sha256":row[2],
                    "independent_external_effect_proven":False,
                }
        except (sqlite3.Error,OSError) as exc:
            raise QuotaLabUnavailable("Quota state unreadable") from exc

    @property
    def reserved_units(self)->int:
        try:
            with self._connect() as db:
                self._verify_policy(db)
                result=db.execute(
                    "SELECT COALESCE(SUM(units),0) FROM reservations"
                ).fetchone()[0]
                if type(result) is not int or not 0<=result<=self.limit:
                    raise QuotaLabUnavailable("Quota sum out of bounds")
                return result
        except (sqlite3.Error,OSError) as exc:
            raise QuotaLabUnavailable("Quota balance unreadable") from exc
