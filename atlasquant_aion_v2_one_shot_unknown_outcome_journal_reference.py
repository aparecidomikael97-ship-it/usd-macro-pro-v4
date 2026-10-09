"""AION V2 one-shot paid-dispatch UNKNOWN_OUTCOME journal — REFERENCE ONLY.

Synthetic, local SQLite bookkeeping. NEVER performs any HTTP/provider request,
does not authorize a real model call or payment, and does not enroll owner
keys or independent witnesses. A successful local CLAIM is *not* permission
to send; it is a conservative record that a network attempt MAY already
have occurred. Repeated claims NEVER permit another attempted dispatch.

Without an independently protected monotonic high-watermark, a privileged
operator can restore an earlier journal and bypass local once-only claims.
Do NOT place this journal on a production paid execution path.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3
from typing import Any, Mapping

SCHEMA = "ATLASQUANT_AION_V2_ONE_SHOT_UNKNOWN_OUTCOME_SQLITE_REFERENCE_V1"
INTENT_SCHEMA = "ATLASQUANT_AION_V2_SIGNED_PROVIDER_INTENT_BINDING_REFERENCE_V1"
STATE_PREPARED = "PREPARED"
STATE_CLAIMED = "DISPATCH_CLAIMED"
STATE_UNKNOWN = "UNKNOWN_OUTCOME"
STATE_CANCELLED = "CANCELLED_UNSENT_REFERENCE"
REPLAY_BLOCKED = "REPLAY_BLOCKED_NO_SECOND_DISPATCH"
LOCAL_CLAIM = "LOCAL_REFERENCE_CLAIM_RECORDED_UNTRUSTED"
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,119}\Z")
_PERIOD = re.compile(r"20[0-9]{2}-(0[1-9]|1[0-2])\Z")
_INTENT_KEYS = frozenset({
    "schema", "owner_id", "tenant_id", "workspace_id",
    "conversation_id", "message_id", "nonce_hex",
    "signed_v2_intent_sha256", "full_provider_request_sha256",
    "primary_witness_receipt_sha256", "secondary_anchor_receipt_sha256",
    "key_registry_roster_sha256", "policy_generation", "period_id",
    "max_cost_micro_usd",
})
_CONFIG_KEYS = frozenset({
    "owner_id", "tenant_id", "workspace_id", "period_id",
    "policy_generation", "max_period_micro_usd",
})
_STATES = {STATE_PREPARED, STATE_CLAIMED, STATE_UNKNOWN, STATE_CANCELLED}
NO_AUTHORITY = {
    "reference_only": True,
    "real_owner_presence_verified": False,
    "real_human_owner_consent": False,
    "signed_request_trust_verified": False,
    "two_independent_witnesses_verified": False,
    "key_registry_freshness_verified": False,
    "live_cost_reservation_verified": False,
    "journal_rollback_protection_verified": False,
    "cross_database_atomicity_verified": False,
    "provider_idempotency_verified": False,
    "network_invocation_authorized": False,
    "paid_dispatch_authorized": False,
    "paid_dispatch_performed": False,
    "provider_called": False,
    "provider_response_confirmed": False,
    "actual_cost_verified": False,
    "billing_authorized": False,
    "installer_authorized": False,
    "safe_to_resume": False,
}


def _hash(v: Any) -> bool:
    return type(v) is str and bool(_HEX64.fullmatch(v))


def _token(v: Any) -> bool:
    return type(v) is str and bool(_TOKEN.fullmatch(v))


def _int(v: Any, low: int, high: int) -> bool:
    return type(v) is int and low <= v <= high


def _canonical(v: Any) -> str:
    return json.dumps(
        v, sort_keys=True, ensure_ascii=False, allow_nan=False,
        separators=(",", ":"),
    )


def _digest(v: Any) -> str:
    return sha256(_canonical(v).encode("utf-8")).hexdigest()


def _valid_config(v: Any) -> bool:
    return (
        type(v) is dict and set(v) == _CONFIG_KEYS
        and all(_token(v[k]) for k in ("owner_id","tenant_id","workspace_id"))
        and type(v["period_id"]) is str and bool(_PERIOD.fullmatch(v["period_id"]))
        and _int(v["policy_generation"], 1, 2**31-1)
        and _int(v["max_period_micro_usd"], 1, 2_000_000_000)
    )


def _valid_intent(v: Any, config: Mapping[str, Any]) -> bool:
    if type(v) is not dict or set(v) != _INTENT_KEYS:
        return False
    if v["schema"] != INTENT_SCHEMA:
        return False
    if any(v[k] != config[k] or type(v[k]) is not type(config[k])
           for k in ("owner_id","tenant_id","workspace_id",
                     "period_id","policy_generation")):
        return False
    if not all(_token(v[k]) for k in ("conversation_id","message_id")):
        return False
    if not all(_hash(v[k]) for k in (
        "nonce_hex","signed_v2_intent_sha256",
        "full_provider_request_sha256","primary_witness_receipt_sha256",
        "secondary_anchor_receipt_sha256","key_registry_roster_sha256",
    )):
        return False
    if v["nonce_hex"] == "0"*64:
        return False
    return _int(v["max_cost_micro_usd"], 1, config["max_period_micro_usd"])


def _out(state: str, reason: str, *, stored: Any = None,
         journal_seq: int = 0) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": state,
        "reason": reason,
        "stored_reference_state": stored,
        "journal_sequence": journal_seq,
        # Once CLAIMED, even without any API call, a hypothetical real
        # integration MUST conservatively assume the send may have occurred.
        "must_not_automatically_retry": stored in (
            STATE_CLAIMED, STATE_UNKNOWN, STATE_CANCELLED
        ) or state == REPLAY_BLOCKED,
        "reference_claim_written": state == LOCAL_CLAIM,
        **NO_AUTHORITY,
    }


class ReferenceOneShotUnknownOutcomeJournal:
    """One isolated local reference DB, never a trusted cross-store transaction.

    The record of *possible* dispatch is committed BEFORE ANY potential
    provider HTTP send in future architecture. This module does not send.
    """

    def __init__(self, path: str | Path, *, config: Mapping[str, Any]):
        if not _valid_config(config):
            raise ValueError("exact journal scope/cost policy required")
        self.config = dict(config)
        self.db = sqlite3.connect(str(path), timeout=10, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        try:
            existing = {
                row[0] for row in self.db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            tables = {"aion_dispatch_config", "aion_dispatch_intents",
                      "aion_dispatch_evidence"}
            if existing and existing != tables:
                raise ValueError("unknown or partial journal schema; no reset")
            self.db.execute("PRAGMA busy_timeout=10000")
            self.db.execute("PRAGMA journal_mode=WAL")
            self.db.execute("PRAGMA synchronous=FULL")
            self.db.execute("PRAGMA foreign_keys=ON")
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS aion_dispatch_config (
                  singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                  policy_json TEXT NOT NULL, sequence INTEGER NOT NULL
                )
            """)
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS aion_dispatch_intents (
                  nonce_hex TEXT PRIMARY KEY,
                  intent_sha256 TEXT NOT NULL UNIQUE,
                  conversation_id TEXT NOT NULL,
                  message_id TEXT NOT NULL,
                  intent_json TEXT NOT NULL,
                  state TEXT NOT NULL,
                  created_sequence INTEGER NOT NULL,
                  claim_sequence INTEGER,
                  close_sequence INTEGER,
                  UNIQUE(conversation_id,message_id)
                )
            """)
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS aion_dispatch_evidence (
                  nonce_hex TEXT NOT NULL,
                  evidence_sha256 TEXT NOT NULL,
                  PRIMARY KEY(nonce_hex,evidence_sha256),
                  FOREIGN KEY(nonce_hex)
                    REFERENCES aion_dispatch_intents(nonce_hex)
                )
            """)
            self.db.execute("BEGIN IMMEDIATE")
            row = self.db.execute(
                "SELECT * FROM aion_dispatch_config WHERE singleton=1"
            ).fetchone()
            if row is None:
                if existing:
                    raise ValueError("journal config missing; no rebootstrap")
                self.db.execute(
                    "INSERT INTO aion_dispatch_config VALUES (1,?,0)",
                    (_canonical(self.config),),
                )
            self._verify_locked()
            self.db.commit()
        except Exception:
            if self.db.in_transaction:
                self.db.rollback()
            self.db.close()
            raise

    def _verify_locked(self) -> int:
        if self.db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise ValueError("SQLite journal consistency invalid")
        row = self.db.execute(
            "SELECT * FROM aion_dispatch_config WHERE singleton=1"
        ).fetchone()
        if row is None or row["policy_json"] != _canonical(self.config):
            raise ValueError("journal immutable policy mismatch")
        events = self.db.execute(
            "SELECT * FROM aion_dispatch_intents ORDER BY created_sequence"
        ).fetchall()
        seen = set()
        seqs = []
        for event in events:
            try:
                intent = json.loads(event["intent_json"])
            except (ValueError, TypeError):
                raise ValueError("journal intent JSON invalid")
            if (not _valid_intent(intent, self.config)
                or event["intent_json"] != _canonical(intent)
                or event["intent_sha256"] != _digest(intent)
                or event["nonce_hex"] != intent["nonce_hex"]
                or event["conversation_id"] != intent["conversation_id"]
                or event["message_id"] != intent["message_id"]
                or event["state"] not in _STATES
                or not _int(event["created_sequence"], 1, 2**63-1)):
                raise ValueError("journal row mutation or invalid intent")
            state = event["state"]
            claim,close = event["claim_sequence"],event["close_sequence"]
            if state == STATE_PREPARED:
                if claim is not None or close is not None:
                    raise ValueError("prepared row already has dispatch history")
            elif state == STATE_CLAIMED:
                if not _int(claim,event["created_sequence"]+1,2**63-1) or close is not None:
                    raise ValueError("claimed row sequence corrupt")
            elif state == STATE_UNKNOWN:
                if (not _int(claim,event["created_sequence"]+1,2**63-1)
                    or not _int(close,claim+1,2**63-1)):
                    raise ValueError("unknown outcome cannot precede dispatch claim")
            else:
                if claim is not None or not _int(close,event["created_sequence"]+1,2**63-1):
                    raise ValueError("cancelled row must never claim dispatch")
            seqs.append(event["created_sequence"])
            if claim is not None:
                seqs.append(claim)
            if close is not None:
                seqs.append(close)
            if event["nonce_hex"] in seen:
                raise ValueError("duplicate nonce")
            seen.add(event["nonce_hex"])
        evidence = self.db.execute(
            "SELECT nonce_hex,evidence_sha256 FROM aion_dispatch_evidence"
        ).fetchall()
        for item in evidence:
            if not _hash(item["evidence_sha256"]) or item["nonce_hex"] not in seen:
                raise ValueError("invalid unknown-outcome evidence")
        if len(seqs) != len(set(seqs)) or set(seqs) != set(range(1,row["sequence"]+1)):
            raise ValueError("journal sequence not gap-free or contains rollback")
        return row["sequence"]

    def _transaction(self, fn):
        try:
            self.db.execute("BEGIN IMMEDIATE")
            seq=self._verify_locked()
            result=fn(seq)
            self.db.commit()
            return result
        except (sqlite3.Error, ValueError, TypeError, OverflowError):
            if self.db.in_transaction:
                self.db.rollback()
            return _out("BLOCKED","SQLITE_REFERENCE_JOURNAL_CORRUPT_OR_UNAVAILABLE")

    def _next(self, sequence: int) -> int:
        next_seq=sequence+1
        self.db.execute(
            "UPDATE aion_dispatch_config SET sequence=? WHERE singleton=1",
            (next_seq,),
        )
        return next_seq

    def prepare_reference_only(self, intent: Any) -> dict[str, Any]:
        if not _valid_intent(intent,self.config):
            return _out("BLOCKED","FULL_SIGNED_INTENT_OR_SCOPE_INVALID")
        digest=_digest(intent)
        def do(seq):
            old=self.db.execute(
                "SELECT * FROM aion_dispatch_intents WHERE nonce_hex=?"
                " OR intent_sha256=? OR (conversation_id=? AND message_id=?)",
                (intent["nonce_hex"],digest,intent["conversation_id"],
                 intent["message_id"]),
            ).fetchall()
            if old:
                if len(old)==1 and old[0]["intent_sha256"]==digest:
                    return _out(
                        REPLAY_BLOCKED if old[0]["state"] != STATE_PREPARED
                        else "ALREADY_PREPARED_REFERENCE_ONLY",
                        "EXISTING_INTENT_NEVER_A_FRESH_DISPATCH",
                        stored=old[0]["state"],journal_seq=seq,
                    )
                return _out("BLOCKED","NONCE_OR_MESSAGE_REBOUND_DETECTED")
            n=self._next(seq)
            self.db.execute(
                "INSERT INTO aion_dispatch_intents VALUES (?,?,?,?,?,?,?,?,?)",
                (intent["nonce_hex"],digest,intent["conversation_id"],
                 intent["message_id"],_canonical(intent),
                 STATE_PREPARED,n,None,None),
            )
            return _out("PREPARED_REFERENCE_ONLY","NO_EXECUTION_RIGHT_CREATED",
                        stored=STATE_PREPARED,journal_seq=n)
        return self._transaction(do)

    def claim_reference_only(self, *, intent: Any) -> dict[str, Any]:
        if not _valid_intent(intent,self.config):
            return _out("BLOCKED","FULL_SIGNED_INTENT_OR_SCOPE_INVALID")
        digest=_digest(intent)
        def do(seq):
            row=self.db.execute(
                "SELECT * FROM aion_dispatch_intents WHERE nonce_hex=?",
                (intent["nonce_hex"],),
            ).fetchone()
            if row is None:
                return _out("BLOCKED","CANNOT_CLAIM_UNPREPARED_INTENT")
            if row["intent_sha256"] != digest:
                return _out("BLOCKED","INTENT_REBOUND_AFTER_PREPARE")
            if row["state"] != STATE_PREPARED:
                return _out(REPLAY_BLOCKED,
                    "CLAIMED_UNKNOWN_OR_CANCELLED_NEVER_AUTO_RETRY",
                    stored=row["state"],journal_seq=seq)
            n=self._next(seq)
            self.db.execute(
                "UPDATE aion_dispatch_intents SET state=?,claim_sequence=?"
                " WHERE nonce_hex=? AND state=?",
                (STATE_CLAIMED,n,intent["nonce_hex"],STATE_PREPARED),
            )
            return _out(
                LOCAL_CLAIM,
                "REFERENCE_CLAIM_PERSISTED_BEFORE_ANY_POSSIBLE_SEND",
                stored=STATE_CLAIMED,journal_seq=n,
            )
        return self._transaction(do)

    def mark_unknown_reference_only(self, *, nonce_hex: Any) -> dict[str, Any]:
        if not _hash(nonce_hex):
            return _out("BLOCKED","NONCE_INVALID")
        def do(seq):
            row=self.db.execute(
                "SELECT * FROM aion_dispatch_intents WHERE nonce_hex=?",
                (nonce_hex,),
            ).fetchone()
            if row is None or row["state"] in (STATE_PREPARED,STATE_CANCELLED):
                return _out("BLOCKED","NO_DISPATCH_CLAIM_CANNOT_MARK_UNKNOWN")
            if row["state"]==STATE_UNKNOWN:
                return _out(REPLAY_BLOCKED,"UNKNOWN_ALREADY_DURABLE_NO_RESEND",
                            stored=STATE_UNKNOWN,journal_seq=seq)
            n=self._next(seq)
            self.db.execute(
                "UPDATE aion_dispatch_intents SET state=?,close_sequence=?"
                " WHERE nonce_hex=? AND state=?",
                (STATE_UNKNOWN,n,nonce_hex,STATE_CLAIMED),
            )
            return _out("UNKNOWN_OUTCOME_RECORDED_REFERENCE_ONLY",
                "NEVER_ASSUME_NOT_SENT_OR_REFUND_OR_RETRY",
                stored=STATE_UNKNOWN,journal_seq=n)
        return self._transaction(do)

    def cancel_never_claimed_reference_only(self, *, nonce_hex: Any) -> dict[str, Any]:
        if not _hash(nonce_hex):
            return _out("BLOCKED","NONCE_INVALID")
        def do(seq):
            row=self.db.execute(
                "SELECT * FROM aion_dispatch_intents WHERE nonce_hex=?",
                (nonce_hex,),
            ).fetchone()
            if row is None or row["state"] != STATE_PREPARED:
                return _out("BLOCKED","CANNOT_CANCEL_AFTER_POSSIBLE_SEND")
            n=self._next(seq)
            self.db.execute(
                "UPDATE aion_dispatch_intents SET state=?,close_sequence=?"
                " WHERE nonce_hex=? AND state=?",
                (STATE_CANCELLED,n,nonce_hex,STATE_PREPARED),
            )
            return _out("CANCELLED_NEVER_CLAIMED_REFERENCE_ONLY",
                "NONCE_BURNED_AND_MUST_NOT_BE_RECYCLED",
                stored=STATE_CANCELLED,journal_seq=n)
        return self._transaction(do)

    def append_evidence_digest_reference_only(
        self, *, nonce_hex: Any, evidence_sha256: Any,
    ) -> dict[str, Any]:
        """Append opaque observation hash only. NOT real provider attestation."""
        if not _hash(nonce_hex) or not _hash(evidence_sha256):
            return _out("BLOCKED","EVIDENCE_INPUT_INVALID")
        def do(seq):
            row=self.db.execute(
                "SELECT * FROM aion_dispatch_intents WHERE nonce_hex=?",
                (nonce_hex,),
            ).fetchone()
            if row is None or row["state"] not in (STATE_CLAIMED,STATE_UNKNOWN):
                return _out("BLOCKED","EVIDENCE_REQUIRES_POSSIBLE_DISPATCH")
            existing=self.db.execute(
                "SELECT 1 FROM aion_dispatch_evidence WHERE nonce_hex=?"
                " AND evidence_sha256=?",
                (nonce_hex,evidence_sha256),
            ).fetchone()
            if existing:
                return _out("EVIDENCE_DIGEST_ALREADY_NOTED_REFERENCE_ONLY",
                    "EVIDENCE_CANNOT_AUTHORIZE_RETRY",
                    stored=row["state"],journal_seq=seq)
            self.db.execute(
                "INSERT INTO aion_dispatch_evidence VALUES (?,?)",
                (nonce_hex,evidence_sha256),
            )
            return _out("EVIDENCE_DIGEST_NOTED_UNTRUSTED",
                "OBSERVATION_HASH_NOT_PAYMENT_SETTLEMENT_OR_SUCCESS",
                stored=row["state"],journal_seq=seq)
        return self._transaction(do)

    def read_reference_only(self, *, nonce_hex: Any) -> dict[str, Any]:
        if not _hash(nonce_hex):
            return _out("BLOCKED","NONCE_INVALID")
        def do(seq):
            row=self.db.execute(
                "SELECT state FROM aion_dispatch_intents WHERE nonce_hex=?",
                (nonce_hex,),
            ).fetchone()
            if row is None:
                return _out("BLOCKED","NO_REFERENCE_DISPATCH_INTENT")
            state=row["state"]
            # CLAIMED is deliberately exposed as unknown on recovery. The
            # on-disk historical state is retained for forensic chronology.
            return _out("READ_ONLY_UNKNOWN_IF_CLAIMED" if state==STATE_CLAIMED
                        else "READ_ONLY_REFERENCE_STATE",
                        "CLAIMED_IMPLIES_UNKNOWN_AFTER_CRASH_NO_RESEND"
                        if state==STATE_CLAIMED else "NO_EXECUTION_AUTHORITY",
                        stored=state,journal_seq=seq)
        return self._transaction(do)

    def local_snapshot_reference_only(self) -> dict[str, Any]:
        def do(seq):
            records=self.db.execute(
                "SELECT * FROM aion_dispatch_intents ORDER BY nonce_hex"
            ).fetchall()
            evidence=self.db.execute(
                "SELECT * FROM aion_dispatch_evidence ORDER BY nonce_hex,evidence_sha256"
            ).fetchall()
            data={
                "schema":SCHEMA,"policy":self.config,
                "journal_sequence":seq,
                "intents":[dict(x) for x in records],
                "evidence":[dict(x) for x in evidence],
            }
            out=_out("LOCAL_JOURNAL_SNAPSHOT_MATH_ONLY",
                    "NOT_AN_INDEPENDENT_ANTIROLLBACK_ANCHOR",
                    journal_seq=seq)
            out["snapshot_sha256"]=_digest(data)
            out["intent_count"]=len(records)
            return out
        return self._transaction(do)

    def close(self):
        self.db.close()


__all__=[
    "SCHEMA","INTENT_SCHEMA","STATE_PREPARED","STATE_CLAIMED",
    "STATE_UNKNOWN","STATE_CANCELLED","REPLAY_BLOCKED","LOCAL_CLAIM",
    "NO_AUTHORITY","ReferenceOneShotUnknownOutcomeJournal",
]
