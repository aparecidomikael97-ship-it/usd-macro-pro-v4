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

from contextlib import closing
from pathlib import Path
import os
import re
import stat
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

    @classmethod
    def bootstrap_synthetic_lab(cls, *, lab_dir, checkout_root, limit:int):
        """Explicit LAB-only creation of a BRAND-NEW quota file.

        This is not authorization from HUMAN_OWNER and cannot detect that an
        old quota ledger was deleted. A trustworthy production system needs
        independently registered genesis/high-water and custodian approval.
        """
        return cls(
            lab_dir=lab_dir, checkout_root=checkout_root, limit=limit,
            _explicit_synthetic_bootstrap=True,
        )

    def __init__(self, *, lab_dir, checkout_root, limit:int,
                 _explicit_synthetic_bootstrap:bool=False):
        if type(_explicit_synthetic_bootstrap) is not bool:
            raise ValueError("Bootstrap declaration must be boolean")
        self._explicit_synthetic_bootstrap=_explicit_synthetic_bootstrap
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("Quota limit must be a literal integer between 1 and 100")
        lab=Path(lab_dir)
        checkout=Path(checkout_root)
        if not lab.is_absolute() or not checkout.is_absolute():
            raise ValueError("LAB directory and checkout must be absolute")
        if not lab.is_dir() or not checkout.is_dir():
            raise ValueError("Existing directories required")
        # Reject lexical symlink components and Windows reparse junctions:
        # resolve() alone would hide a path that was redirected.
        for part in (lab, *lab.parents):
            if part.is_symlink() or part.is_junction():
                raise ValueError("LAB path contains symlink or junction")
        root=checkout.resolve(strict=True)
        resolved=lab.resolve(strict=True)
        if resolved==root or resolved.is_relative_to(root):
            raise ValueError("Quota database must be outside source checkout")
        path=resolved/DB_FILENAME
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise ValueError("Quota database is not a normal regular file")
        self.path=path
        self.limit=limit
        # LAB-only process-lifetime identity pins. They DO NOT survive a
        # malicious local DB rollback or establish independent monotonicity.
        self._dir_identity=self._identity(self.path.parent,expect_dir=True)
        self._db_identity=None
        # Observed high-water protects ONLY this process instance from
        # lower-balance in-place rollback. Restart loses the witness.
        self._highwater_units=0
        # Same-instance monotonic row observations (NOT external history).
        self._observed_rows={}
        self._initialize()

    @staticmethod
    def _identity(path, *, expect_dir=False):
        try:
            metadata=path.lstat()
            if path.is_symlink() or path.is_junction():
                raise ValueError("Symlink or Windows junction not allowed")
            if expect_dir:
                if not stat.S_ISDIR(metadata.st_mode):
                    raise ValueError("LAB quota directory must remain a directory")
            else:
                if not stat.S_ISREG(metadata.st_mode):
                    raise ValueError("LAB quota database must be a regular file")
                if metadata.st_nlink != 1:
                    raise ValueError("Hardlinked SQLite quota DB not allowed")
            # Fail closed on a filesystem that cannot report a stable file id.
            if not metadata.st_ino:
                raise ValueError("Stable filesystem object id unavailable")
            return (metadata.st_dev,metadata.st_ino)
        except OSError as exc:
            raise QuotaLabUnavailable("LAB filesystem metadata unavailable") from exc

    def _check_path(self):
        for part in (self.path.parent,*self.path.parent.parents):
            if part.is_symlink() or part.is_junction():
                raise QuotaLabUnavailable("LAB path contains link or junction")
        try:
            parent=self._identity(self.path.parent,expect_dir=True)
            file=self._identity(self.path)
        except (ValueError,QuotaLabUnavailable) as exc:
            raise QuotaLabUnavailable("Quota filesystem object is unsafe") from exc
        if parent!=self._dir_identity or (
            self._db_identity is not None and file!=self._db_identity
        ):
            raise QuotaLabUnavailable("Quota file or directory identity changed")
        return self.path

    def _connect(self):
        self._check_path()
        db=None
        try:
            # A142: SQLite's default open mode can silently create a NEW
            # database if the path disappears after our pre-open identity
            # check. A quota ledger must NEVER be recreated by an ordinary
            # connection. Initialization alone creates it explicitly (xb).
            # Path.as_uri percent-encodes '#' / '?' / '%' for URI safety.
            db=sqlite3.connect(
                self.path.as_uri()+"?mode=rw",
                uri=True,timeout=0.25,isolation_level=None,
            )
            # Detect a replacement between our first pathname check and the
            # sqlite3.connect call BEFORE BEGIN IMMEDIATE or any write.
            # This is identity-based race reduction, NOT an atomic handle-
            # bound open, nor protection against a malicious ABA swap.
            self._check_path()
            db.execute("PRAGMA busy_timeout=250")
            db.execute("PRAGMA synchronous=FULL")
            db.execute("PRAGMA foreign_keys=ON")
            self._check_path()
            return db
        except (sqlite3.Error,QuotaLabUnavailable) as exc:
            if db is not None:
                db.close()
            raise QuotaLabUnavailable("SQLite handle or pinned identity unavailable") from exc

    def _initialize(self):
        existed=self.path.exists()
        created_identity=None
        try:
            # A143 explicitly separates ordinary re-open/recovery from LAB
            # creation. A missing DB is ALWAYS denied for the regular path.
            # A purported bootstrap cannot silently reset an existing DB.
            if existed and self._explicit_synthetic_bootstrap:
                raise QuotaLabUnavailable("Synthetic LAB bootstrap requires empty destination")
            if not existed:
                if not self._explicit_synthetic_bootstrap:
                    raise QuotaLabUnavailable(
                        "Missing quota ledger cannot be interpreted as fresh install"
                    )
                try:
                    # Record the identity of OUR OWN exclusive-creation
                    # handle BEFORE close. The pathname can otherwise be
                    # replaced by another fully valid SQLite between close
                    # and the following identity capture.
                    with self.path.open("xb") as newly_created:
                        created_stat=os.fstat(newly_created.fileno())
                        if not created_stat.st_ino:
                            raise QuotaLabUnavailable(
                                "New LAB file handle lacks stable identity"
                            )
                        created_identity=(created_stat.st_dev,created_stat.st_ino)
                except FileExistsError as exc:
                    raise QuotaLabUnavailable(
                        "Quota bootstrap raced an existing file; no implicit open"
                    ) from exc
            if self.path.is_symlink() or self.path.is_junction():
                raise ValueError("Symlink or junction quota file denied")
            self._db_identity=self._identity(self.path)
            if not existed:
                if self._db_identity!=created_identity:
                    raise QuotaLabUnavailable(
                        "Exclusive LAB-created SQLite handle differs from destination"
                    )
                # An exclusive new file MUST still be blank before SQLite
                # initialization. Windows file IDs can be unreliable/reused;
                # reject a substituted pre-initialized database even when
                # the two filesystem identity tuples appear to coincide.
                # Not an atomic defense against an adversarial ABA swap.
                if self.path.stat().st_size!=0:
                    raise QuotaLabUnavailable(
                        "LAB bootstrap destination was populated before initialization"
                    )
            with closing(self._connect()) as db:
                db.execute("BEGIN IMMEDIATE")
                if not existed:
                    # A pre-existing, initialized SQLite source can be swapped
                    # in between pathname checks. An explicit fresh bootstrap
                    # must never accept schema or application data at genesis.
                    schema_count=db.execute(
                        "SELECT COUNT(*) FROM sqlite_master"
                    ).fetchone()[0]
                    if schema_count!=0:
                        raise QuotaLabUnavailable(
                            "LAB bootstrap encountered pre-existing SQLite schema"
                        )
                if existed:
                    # A140 independent audit: an EXISTING database must
                    # never silently recreate lost quota history. sqlite
                    # quick_check verifies pages, not missing logical tables.
                    existing_tables={
                        row[0] for row in db.execute(
                            "SELECT name FROM sqlite_master WHERE type='table'"
                            " AND name IN ('quota_policy','reservations')"
                        ).fetchall()
                    }
                    if existing_tables!={"quota_policy","reservations"}:
                        raise QuotaLabUnavailable(
                            "Existing quota database has lost required tables"
                        )
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
                self._verify_schema(db)
                db.execute("COMMIT")
            # Detect clearly corrupt pages, not a trusted anti-rollback proof.
            with closing(self._connect()) as db:
                check=db.execute("PRAGMA quick_check").fetchone()
                if check!=("ok",):
                    raise QuotaLabUnavailable("SQLite integrity check failed")
                self._verify_policy(db)
        except (sqlite3.Error,OSError) as exc:
            raise QuotaLabUnavailable("SQLite LAB initialization unavailable") from exc

    @staticmethod
    def _verify_schema(db):
        """LAB-only exact SQLite schema attestation; not anti-rollback."""
        expected={
            "quota_policy": "CREATE TABLE quota_policy (singleton INTEGER PRIMARY KEY CHECK (singleton=1),schema TEXT NOT NULL,configured_limit INTEGER NOT NULL CHECK(configured_limit BETWEEN 1 AND 100))",
            "reservations": "CREATE TABLE reservations (run_id TEXT PRIMARY KEY NOT NULL,units INTEGER NOT NULL CHECK(units BETWEEN 1 AND 100),state TEXT NOT NULL CHECK(state IN ('RESERVED_UNCERTAIN','LOCAL_OUTPUT_OBSERVED')),payload_sha256 TEXT)",
        }
        rows=db.execute("SELECT type,name,tbl_name,sql FROM sqlite_master").fetchall()
        if len(rows)!=3 or {row[1] for row in rows}!=set(expected)|{"sqlite_autoindex_reservations_1"}:
            raise QuotaLabUnavailable("Unexpected SQLite schema objects")
        for kind,name,table,sql in rows:
            if name=="sqlite_autoindex_reservations_1":
                if kind!="index" or table!="reservations" or sql is not None:
                    raise QuotaLabUnavailable("SQLite implicit primary-key index changed")
                continue
            if kind!="table" or table!=name or sql!=expected[name]:
                raise QuotaLabUnavailable("SQLite schema definition changed")
        if db.execute("PRAGMA application_id").fetchone()!=(0,):
            raise QuotaLabUnavailable("SQLite application identity changed")

    def _verify_policy(self,db):
        self._verify_schema(db)
        policy=db.execute(
            "SELECT schema,configured_limit FROM quota_policy WHERE singleton=1"
        ).fetchone()
        if policy!=(SCHEMA,self.limit):
            raise QuotaLabUnavailable("Untrusted or changed quota policy")
        rows=db.execute(
            "SELECT run_id,units,state,payload_sha256 FROM reservations"
        ).fetchall()
        current={}
        total=0
        for run_id,units,state,digest in rows:
            if (
                type(run_id) is not str or RUN_ID_RE.fullmatch(run_id) is None
                or type(units) is not int or not 1<=units<=100
                or state not in ("RESERVED_UNCERTAIN","LOCAL_OUTPUT_OBSERVED")
                or (state=="RESERVED_UNCERTAIN" and digest is not None)
                or (state=="LOCAL_OUTPUT_OBSERVED"
                    and (type(digest) is not str or DIGEST_RE.fullmatch(digest) is None))
            ):
                raise QuotaLabUnavailable("Quota reservation record is not canonical")
            current[run_id]=(units,state,digest)
            total+=units
        if total<self._highwater_units or total>self.limit:
            raise QuotaLabUnavailable("Same-instance quota high-water regressed")
        for run_id,(prior_units,prior_state,prior_digest) in self._observed_rows.items():
            row=current.get(run_id)
            if row is None or row[0]!=prior_units:
                raise QuotaLabUnavailable("Previously observed reservation lost or changed")
            if prior_state=="LOCAL_OUTPUT_OBSERVED":
                if row!=(prior_units,prior_state,prior_digest):
                    raise QuotaLabUnavailable("Observed local output was rolled back or forged")
            elif prior_state=="RESERVED_UNCERTAIN":
                if row[1]=="RESERVED_UNCERTAIN" and row[2] is None:
                    pass
                elif row[1]=="LOCAL_OUTPUT_OBSERVED" and row[2] is not None:
                    pass  # Locally observed monotonic advance; NO provider proof.
                else:
                    raise QuotaLabUnavailable("Quota state regressed")
        self._highwater_units=max(self._highwater_units,total)
        self._observed_rows.update(current)

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
            self._highwater_units=max(self._highwater_units,used+units)
            self._observed_rows[run_id]=(units,"RESERVED_UNCERTAIN",None)
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
            units=self._observed_rows[run_id][0]
            self._observed_rows[run_id]=(units,"LOCAL_OUTPUT_OBSERVED",payload_sha256)
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
            with closing(self._connect()) as db:
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
            with closing(self._connect()) as db:
                self._verify_policy(db)
                result=db.execute(
                    "SELECT COALESCE(SUM(units),0) FROM reservations"
                ).fetchone()[0]
                if type(result) is not int or not 0<=result<=self.limit:
                    raise QuotaLabUnavailable("Quota sum out of bounds")
                self._highwater_units=max(self._highwater_units,result)
                return result
        except (sqlite3.Error,OSError) as exc:
            raise QuotaLabUnavailable("Quota balance unreadable") from exc
