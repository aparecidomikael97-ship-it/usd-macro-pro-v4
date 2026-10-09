"""Disposable-test reference: durable challenges and monotonic policy, NOT authority.

SQLite ACID + an unkeyed integrity chain survive process restart in the same
intact fixture. Disk/administrator rollback, full rehash, key custody, hardware
antirollback, trusted time, installer safety and owner identity are NOT proven.
No production wiring or private-key/signing API. Explicit fixture creation only.
"""
from __future__ import annotations

from contextlib import contextmanager
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile

from atlasquant_aion_nonce_registry import _parse_ts, _epoch_us
from atlasquant_aion_independent_ed25519_trirole_bridge_contract_v1 import (
    build_unsigned_three_role_challenge, PURPOSE, BINDING_SCHEMA, _DOMAINS,
)
from atlasquant_aion_dual_ed25519_public_crypto_bridge_v1 import (
    verify_dual_ed25519_public_signatures_untrusted, CANDIDATE, _FALSE_GATES,
)

SCHEMA = "AION_DURABLE_DUAL_ED25519_CHALLENGE_REFERENCE_V1"
RECEIPT_SCHEMA = "AION_NONCE_TRANSACTION_REFERENCE_RECEIPT_V1"
MAX_GENERATION = 2**32 - 1
MAX_WINDOW_US = 300_000_000
MAX_RECORDS = 2048
MAX_EVENTS = 8192
GENESIS = "sha256:" + "0" * 64
NONCE = re.compile(r"[0-9a-f]{64}\Z")
FALSE_GATES = {
    **_FALSE_GATES,
    "owner_identity_authenticated": False,
    "independent_custody_verified": False,
    "hardware_antirollback_verified": False,
    "physical_sandbox_verified": False,
    "physical_network_deny_verified": False,
    "execution_authorized": False,
    "owner_identity_trusted": False,
    "installer_authorized": False,
    "safe_to_resume": False,
}
_REQUEST_KEYS = {"proposal", "nonce", "owner_public_key_hex", "owner_signature_hex",
                 "collector_public_key_hex", "collector_signature_hex"}


class ReferenceStoreError(RuntimeError):
    """Fail closed; no automatic reset/repair or exception-text leakage."""


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False)


def _hash(value):
    return "sha256:" + sha256(_json(value).encode("ascii")).hexdigest()


def _copy(value):
    budget = [256]
    def visit(item, depth=0):
        budget[0] -= 1
        if budget[0] < 0 or depth > 8:
            raise ValueError("INPUT_BOUND")
        if type(item) is dict:
            if len(item) > budget[0]:
                raise ValueError("INPUT_BOUND")
            if any(type(k) is not str or len(k) > 80 for k in item):
                raise ValueError("INPUT_TYPE")
            return {k: visit(v, depth+1) for k, v in item.items()}
        if type(item) is list:
            if len(item) > budget[0]:
                raise ValueError("INPUT_BOUND")
            return [visit(v, depth+1) for v in item]
        if type(item) is str and len(item) <= 512:
            return item
        if type(item) is bool or item is None:
            return item
        if type(item) is int and 0 <= item <= MAX_GENERATION:
            return item
        raise ValueError("INPUT_TYPE")
    return visit(value)


def _decode(text):
    if type(text) is not str or len(text) > 8192:
        raise ReferenceStoreError("CORRUPT_JSON")
    def pairs(items):
        out = {}
        for k, v in items:
            if k in out:
                raise ValueError("duplicate key")
            out[k] = v
        return out
    try:
        return json.loads(text, object_pairs_hook=pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, TypeError, RecursionError):
        raise ReferenceStoreError("CORRUPT_JSON") from None


def _time(value):
    if type(value) is not str:
        raise ValueError("TIME_INVALID")
    parsed = _parse_ts(value)
    micros = _epoch_us(parsed)
    if micros < 0:
        raise ValueError("TIME_INVALID")
    return micros


def _binding(proposal, nonce):
    proposal = _copy(proposal)
    plan = build_unsigned_three_role_challenge(proposal, nonce)
    if plan["state"] != "THREE_UNSIGNED_ROLE_CHALLENGES_UNTRUSTED":
        raise ValueError("CHALLENGE_INVALID")
    return {
        "nonce": nonce, "purpose": PURPOSE,
        "role_domains": {role: intent["role_domain"] for role, intent in plan["role_messages"].items()},
        "role_public_key_sha256": {role: proposal[role]["public_key_sha256"] for role in ("owner", "collector", "host")},
        "policy_sha256": proposal["policy_sha256"],
        "policy_generation": proposal["policy_generation"],
        "collector_binary_sha256": proposal["collector_binary_sha256"],
        "canonical_transcript_sha256": plan["transcript_sha256"],
    }



def _valid_binding(binding):
    fields = {"nonce","purpose","role_domains","role_public_key_sha256",
              "policy_sha256","policy_generation","collector_binary_sha256",
              "canonical_transcript_sha256"}
    pattern = re.compile(r"sha256:[0-9a-f]{64}\Z")
    if type(binding) is not dict or set(binding) != fields:
        return False
    if (type(binding["nonce"]) is not str or not NONCE.fullmatch(binding["nonce"])
            or binding["purpose"] != PURPOSE or binding["role_domains"] != _DOMAINS
            or type(binding["policy_generation"]) is not int
            or not 0 <= binding["policy_generation"] <= MAX_GENERATION):
        return False
    keys = binding["role_public_key_sha256"]
    if type(keys) is not dict or set(keys) != {"owner","collector","host"}:
        return False
    for value in [*keys.values(),binding["policy_sha256"],binding["collector_binary_sha256"],binding["canonical_transcript_sha256"]]:
        if type(value) is not str or not pattern.fullmatch(value):
            return False
    if len(set(keys.values())) != 3:
        return False
    core = {"schema":BINDING_SCHEMA,"purpose":PURPOSE,"nonce":binding["nonce"],
            "policy_generation":binding["policy_generation"],
            "collector_binary_sha256":binding["collector_binary_sha256"],
            "policy_sha256":binding["policy_sha256"],
            "role_public_key_sha256":keys}
    transcript = "sha256:" + sha256(b"ATLASQUANT:AION:TRIROLE_TRANSCRIPT:V1\x00"
                                    + _json(core).encode("ascii")).hexdigest()
    return transcript == binding["canonical_transcript_sha256"]


def _result(reason, *, math=False, consumed=False, receipt=None):
    return {
        "schema": SCHEMA,
        "state": "NONCE_TRANSACTION_CONSUMED_REFERENCE_UNTRUSTED" if consumed else "BLOCKED",
        "reason": reason,
        "signature_mathematically_valid": math,
        "nonce_transaction_consumed": consumed,
        "reference_policy_monotonicity_observed": consumed,
        "reference_only": True,
        "administrator_disk_rollback_resistance_proven": False,
        "receipt": receipt,
        **FALSE_GATES,
    }


_TABLE_SQL = (
    "CREATE TABLE meta (id INTEGER PRIMARY KEY CHECK(id=1), version INTEGER NOT NULL CHECK(version=1), last_now INTEGER NOT NULL CHECK(last_now>=0))",
    "CREATE TABLE policy (id INTEGER PRIMARY KEY CHECK(id=1), generation INTEGER NOT NULL CHECK(typeof(generation)='integer' AND generation>=0 AND generation<=4294967295), digest TEXT NOT NULL)",
    "CREATE TABLE challenges (nonce TEXT PRIMARY KEY CHECK(length(nonce)=64 AND nonce NOT GLOB '*[^0-9a-f]*'), body TEXT NOT NULL, state TEXT NOT NULL CHECK(state IN ('ISSUED','CONSUMED','EXPIRED','REVOKED')), receipt TEXT)",
    "CREATE TABLE evidence (sequence INTEGER PRIMARY KEY, previous_digest TEXT NOT NULL, body TEXT NOT NULL, digest TEXT NOT NULL UNIQUE)",
)


class ReferenceChallengeRegistry:
    """Explicit temp-fixture SQLite. Never a production trust anchor.

    Equal generation is allowed ONLY for the identical policy digest; a higher
    generation advances ONLY with two mathematically valid role signatures and
    exact issued bindings inside the same consume transaction. Issuance alone
    never advances policy. No admin/disk-resistant antirollback claim is made.
    """
    def __init__(self, path, *, fixture_root, create=False, timeout=0.5):
        if type(path) is not str or type(fixture_root) is not str:
            raise ReferenceStoreError("FIXTURE_PATH_INVALID")
        root = Path(fixture_root)
        candidate = Path(path)
        temp = Path(tempfile.gettempdir()).resolve()
        if (not root.is_absolute() or not root.is_dir() or root.is_symlink()
                or root.resolve() != root or not root.is_relative_to(temp)
                or not candidate.is_absolute() or candidate.parent != root
                or candidate.is_symlink() or not re.fullmatch(r"[A-Za-z0-9_.-]+\.sqlite3", candidate.name)):
            raise ReferenceStoreError("FIXTURE_PATH_INVALID")
        if type(create) is not bool or type(timeout) not in (float, int) or not 0 < timeout <= 5:
            raise ReferenceStoreError("CONFIG_INVALID")
        self.path = candidate
        self.timeout = float(timeout)
        if create:
            fd = os.open(str(candidate), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
            conn = self._connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                for sql in _TABLE_SQL:
                    conn.execute(sql)
                conn.execute("INSERT INTO meta VALUES(1,1,0)")
                conn.execute("PRAGMA user_version=1")
                self._commit(conn)
            finally:
                conn.close()
        with self._transaction():
            pass

    def _connect(self):
        # mode=rw prevents deleted/missing DB from silently becoming a fresh ledger.
        if self.path.is_symlink():
            raise ReferenceStoreError("FIXTURE_PATH_INVALID")
        conn = sqlite3.connect(self.path.as_uri()+"?mode=rw", uri=True,
                               timeout=self.timeout, isolation_level=None)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA synchronous=FULL")
            conn.execute("PRAGMA foreign_keys=ON")
            return conn
        except BaseException:
            conn.close()
            raise

    def _commit(self, conn):
        conn.commit()

    @contextmanager
    def _transaction(self):
        conn = None
        try:
            conn = self._connect()
            conn.execute("BEGIN IMMEDIATE")
            self._validate(conn)
            yield conn
            self._validate(conn)
            self._commit(conn)
        except (sqlite3.Error, ValueError, KeyError, TypeError, OverflowError, ReferenceStoreError):
            if conn is not None:
                conn.rollback()
            raise ReferenceStoreError("STORE_UNAVAILABLE_OR_INCONSISTENT") from None
        except BaseException:
            if conn is not None:
                conn.rollback()
            raise
        finally:
            if conn is not None:
                conn.close()

    def _rows(self, conn, table, bound):
        rows = conn.execute("SELECT * FROM "+table+" LIMIT ?", (bound+1,)).fetchall()
        if len(rows) > bound:
            raise ReferenceStoreError("RECOVERY_BOUND")
        return rows

    def _validate(self, conn):
        if conn.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise ReferenceStoreError("DB_CORRUPT")
        if conn.execute("PRAGMA user_version").fetchone()[0] != 1:
            raise ReferenceStoreError("SCHEMA_INVALID")
        actual = {r[0]: r[1] for r in conn.execute(
            "SELECT name,sql FROM sqlite_master WHERE type='table'")}
        expected = {sql.split()[2]: sql for sql in _TABLE_SQL}
        if actual != expected:
            raise ReferenceStoreError("SCHEMA_INVALID")
        meta = self._rows(conn, "meta", 1)
        policies = self._rows(conn, "policy", 1)
        rows = self._rows(conn, "challenges", MAX_RECORDS)
        events = sorted(self._rows(conn, "evidence", MAX_EVENTS), key=lambda r:r["sequence"])
        if (len(meta) != 1 or meta[0]["id"] != 1 or meta[0]["version"] != 1
                or type(meta[0]["last_now"]) is not int):
            raise ReferenceStoreError("META_INVALID")
        records = {}
        for row in rows:
            body = _decode(row["body"])
            if (set(body) != {"binding","issued_at","expires_at","record_digest"}
                    or body["record_digest"] != _hash({k:v for k,v in body.items() if k!="record_digest"})
                    or body["binding"]["nonce"] != row["nonce"]):
                raise ReferenceStoreError("RECORD_INVALID")
            issued, expires = _time(body["issued_at"]), _time(body["expires_at"])
            if not 0 < expires-issued <= MAX_WINDOW_US:
                raise ReferenceStoreError("RECORD_TIME_INVALID")
            b = body["binding"]
            if not _valid_binding(b):
                raise ReferenceStoreError("RECORD_BINDING_INVALID")
            records[row["nonce"]] = (row, body)
        states, receipts, policy, clock, previous = {}, {}, None, 0, GENESIS
        for index, event in enumerate(events, 1):
            body = _decode(event["body"])
            if (event["sequence"] != index or event["previous_digest"] != previous
                    or event["digest"] != _hash({"sequence":index,"previous_digest":previous,"body":body})
                    or set(body) != {"nonce","from_state","to_state","record_digest","receipt_digest","policy_before","policy_after","observed_at"}):
                raise ReferenceStoreError("AUDIT_INVALID")
            previous = event["digest"]
            nonce = body["nonce"]
            if nonce not in records:
                raise ReferenceStoreError("ORPHAN_EVENT")
            row, record = records[nonce]
            now = _time(body["observed_at"])
            if now < clock or body["policy_before"] != policy or body["record_digest"] != record["record_digest"]:
                raise ReferenceStoreError("AUDIT_BINDING_INVALID")
            clock = now
            if nonce not in states:
                if body["from_state"] is not None or body["to_state"] != "ISSUED" or body["receipt_digest"] is not None or body["policy_after"] != policy:
                    raise ReferenceStoreError("ISSUE_EVENT_INVALID")
                if now != _time(record["issued_at"]):
                    raise ReferenceStoreError("ISSUE_TIME_INVALID")
            else:
                if states[nonce] != "ISSUED" or body["from_state"] != "ISSUED" or body["to_state"] not in ("CONSUMED","EXPIRED","REVOKED"):
                    raise ReferenceStoreError("TRANSITION_INVALID")
                if body["to_state"] == "CONSUMED":
                    binding = record["binding"]
                    candidate = {"generation":binding["policy_generation"],"digest":binding["policy_sha256"]}
                    if policy and (candidate["generation"] < policy["generation"] or
                            candidate["generation"] == policy["generation"] and candidate["digest"] != policy["digest"]):
                        raise ReferenceStoreError("POLICY_ROLLBACK")
                    if body["policy_after"] != candidate or not _time(record["issued_at"]) <= now < _time(record["expires_at"]):
                        raise ReferenceStoreError("CONSUME_EVENT_INVALID")
                    if row["receipt"] is None:
                        raise ReferenceStoreError("RECEIPT_MISSING")
                    receipt = _decode(row["receipt"])
                    expected_receipt = self._receipt(nonce, record, now_ts=body["observed_at"], sequence=index)
                    if receipt != expected_receipt or body["receipt_digest"] != receipt["receipt_digest"]:
                        raise ReferenceStoreError("RECEIPT_INVALID")
                    receipts[nonce] = receipt
                    policy = candidate
                elif body["policy_after"] != policy or body["receipt_digest"] is not None:
                    raise ReferenceStoreError("DENIAL_TRANSITION_INVALID")
                elif body["to_state"] == "EXPIRED" and now < _time(record["expires_at"]):
                    raise ReferenceStoreError("EXPIRY_INVALID")
            states[nonce] = body["to_state"]
        stored_policy = {"generation":policies[0]["generation"],"digest":policies[0]["digest"]} if policies else None
        if policy != stored_policy or meta[0]["last_now"] != clock or set(states) != set(records):
            raise ReferenceStoreError("HEAD_INCONSISTENT")
        for nonce, (row, _) in records.items():
            if row["state"] != states[nonce] or (row["receipt"] is not None) != (nonce in receipts):
                raise ReferenceStoreError("STATE_RECEIPT_INCONSISTENT")

    def _head(self, conn):
        row = conn.execute("SELECT generation,digest FROM policy WHERE id=1").fetchone()
        return dict(row) if row else None

    def _clock(self, conn, now_ts):
        now = _time(now_ts)
        if now < conn.execute("SELECT last_now FROM meta WHERE id=1").fetchone()[0]:
            raise ValueError("CLOCK_ROLLBACK")
        return now

    def _policy_check(self, conn, binding):
        current = self._head(conn)
        if current and (binding["policy_generation"] < current["generation"] or
                binding["policy_generation"] == current["generation"] and binding["policy_sha256"] != current["digest"]):
            raise ValueError("POLICY_GENERATION_ROLLBACK_OR_CONFLICT")

    def _event(self, conn, nonce, previous_state, state, record, receipt, now_ts, before, after):
        latest = conn.execute("SELECT sequence,digest FROM evidence ORDER BY sequence DESC LIMIT 1").fetchone()
        seq = latest["sequence"]+1 if latest else 1
        prev = latest["digest"] if latest else GENESIS
        body = {"nonce":nonce,"from_state":previous_state,"to_state":state,
                "record_digest":record["record_digest"],
                "receipt_digest":receipt["receipt_digest"] if receipt else None,
                "policy_before":before,"policy_after":after,"observed_at":now_ts}
        conn.execute("INSERT INTO evidence VALUES(?,?,?,?)",
                     (seq,prev,_json(body),_hash({"sequence":seq,"previous_digest":prev,"body":body})))
        conn.execute("UPDATE meta SET last_now=? WHERE id=1", (_time(now_ts),))

    def _receipt(self, nonce, record, *, now_ts, sequence):
        body = {"schema":RECEIPT_SCHEMA,"nonce":nonce,"record_digest":record["record_digest"],
                "binding":record["binding"],"consumed_at":now_ts,"audit_sequence":sequence,
                "signature_mathematically_valid":True,"nonce_transaction_consumed":True,
                "reference_only":True,**FALSE_GATES}
        return {**body,"receipt_digest":_hash(body)}

    def issue(self, *, proposal, nonce, issued_at, expires_at):
        try:
            binding = _binding(proposal, nonce)
            issued, expires = _time(issued_at), _time(expires_at)
            if not 0 < expires-issued <= MAX_WINDOW_US:
                raise ValueError("CHALLENGE_WINDOW_INVALID")
            body = {"binding":binding,"issued_at":issued_at,"expires_at":expires_at}
            record = {**body,"record_digest":_hash(body)}
            with self._transaction() as conn:
                self._clock(conn, issued_at)
                self._policy_check(conn, binding)
                conn.execute("INSERT INTO challenges VALUES(?,?,'ISSUED',NULL)", (nonce,_json(record)))
                head = self._head(conn)
                self._event(conn,nonce,None,"ISSUED",record,None,issued_at,head,head)
            return {"schema":SCHEMA,"state":"ISSUED","record_digest":record["record_digest"],**FALSE_GATES}
        except (ValueError, TypeError, ReferenceStoreError, sqlite3.Error):
            return _result("ISSUANCE_REJECTED")

    def consume(self, *, request, now_ts):
        mathematical = False
        try:
            payload = _copy(request)
            if type(payload) is not dict or set(payload) != _REQUEST_KEYS:
                raise ValueError("REQUEST_SCHEMA_INVALID")
            verification = verify_dual_ed25519_public_signatures_untrusted(**payload)
            if verification["state"] != CANDIDATE:
                return _result("DUAL_SIGNATURE_VERIFICATION_FAILED")
            mathematical = True
            binding = _binding(payload["proposal"], payload["nonce"])
            receipt = None
            reason = ""
            with self._transaction() as conn:
                now = self._clock(conn, now_ts)
                row = conn.execute("SELECT * FROM challenges WHERE nonce=?", (payload["nonce"],)).fetchone()
                if row is None:
                    reason = "CHALLENGE_NOT_FOUND"
                elif row["state"] != "ISSUED":
                    reason = "CHALLENGE_"+row["state"]
                else:
                    record = _decode(row["body"])
                    if record["binding"] != binding:
                        reason = "ISSUED_BINDING_MISMATCH"
                    elif now < _time(record["issued_at"]):
                        reason = "CHALLENGE_NOT_YET_VALID"
                    elif now >= _time(record["expires_at"]):
                        conn.execute("UPDATE challenges SET state='EXPIRED' WHERE nonce=? AND state='ISSUED'",(payload["nonce"],))
                        head = self._head(conn)
                        self._event(conn,payload["nonce"],"ISSUED","EXPIRED",record,None,now_ts,head,head)
                        reason = "CHALLENGE_EXPIRED"
                    else:
                        self._policy_check(conn, binding)
                        head = self._head(conn)
                        candidate = {"generation":binding["policy_generation"],"digest":binding["policy_sha256"]}
                        seq = conn.execute("SELECT COALESCE(MAX(sequence),0)+1 FROM evidence").fetchone()[0]
                        receipt = self._receipt(payload["nonce"],record,now_ts=now_ts,sequence=seq)
                        changed = conn.execute("UPDATE challenges SET state='CONSUMED',receipt=? WHERE nonce=? AND state='ISSUED'",
                                               (_json(receipt),payload["nonce"])).rowcount
                        if changed != 1:
                            raise ReferenceStoreError("CAS_FAILED")
                        conn.execute("INSERT INTO policy VALUES(1,?,?) ON CONFLICT(id) DO UPDATE SET generation=excluded.generation,digest=excluded.digest",
                                     (candidate["generation"],candidate["digest"]))
                        self._event(conn,payload["nonce"],"ISSUED","CONSUMED",record,receipt,now_ts,head,candidate)
            return _result(reason,math=mathematical,consumed=receipt is not None,receipt=receipt)
        except (ValueError, KeyError, TypeError, OverflowError, ReferenceStoreError, sqlite3.Error):
            return _result("CONSUMPTION_REJECTED_OR_COMMIT_UNCERTAIN",math=mathematical)

    def revoke(self, *, nonce, now_ts):
        try:
            if type(nonce) is not str or not NONCE.fullmatch(nonce):
                raise ValueError("NONCE_INVALID")
            with self._transaction() as conn:
                self._clock(conn,now_ts)
                row = conn.execute("SELECT * FROM challenges WHERE nonce=?",(nonce,)).fetchone()
                if row is None or row["state"] != "ISSUED":
                    raise ValueError("NOT_REVOCABLE")
                record = _decode(row["body"])
                conn.execute("UPDATE challenges SET state='REVOKED' WHERE nonce=? AND state='ISSUED'",(nonce,))
                head = self._head(conn)
                self._event(conn,nonce,"ISSUED","REVOKED",record,None,now_ts,head,head)
            return {"schema":SCHEMA,"state":"REVOKED",**FALSE_GATES}
        except (ValueError, ReferenceStoreError):
            return _result("REVOCATION_REJECTED")

    def inspect(self):
        with self._transaction() as conn:
            return {"schema":SCHEMA,"policy":self._head(conn),
                    "states":{r["nonce"]:r["state"] for r in conn.execute("SELECT nonce,state FROM challenges")},
                    "event_count":conn.execute("SELECT COUNT(*) FROM evidence").fetchone()[0],
                    "reference_only":True,**FALSE_GATES}
