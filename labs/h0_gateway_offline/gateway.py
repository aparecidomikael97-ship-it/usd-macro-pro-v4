"""H0-GW-01 OFFLINE SPECIMEN. No network, credentials, provider or production adapter.

IMPORTANT: sqlite + in-process witness and test HMAC do NOT provide independent
custody, delivery proof, antirollback, or provider-side no-late-effect fencing.
"""
from __future__ import annotations

from dataclasses import dataclass
from contextlib import contextmanager
import hashlib
import hmac
import json
import sqlite3
import threading
from typing import Optional


class Denied(RuntimeError):
    pass


class Uncertain(RuntimeError):
    pass


class InjectedCrash(RuntimeError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


@dataclass(frozen=True)
class Intent:
    logical_intent_id: str
    idempotency_key: str
    owner: str
    tenant: str
    workspace: str
    aggregate: str
    action: str
    channel: str
    account: str
    issuer: str
    payload_digest: str
    destination_digest: str
    epoch: int = 1

    def __post_init__(self):
        for key, value in vars(self).items():
            if key == "epoch":
                if type(value) is not int or value < 1:
                    raise ValueError("epoch must be a positive integer")
            elif type(value) is not str or not value.strip():
                raise ValueError(f"required identity field: {key}")

    @property
    def digest(self):
        return hashlib.sha256(canonical(vars(self)).encode()).hexdigest()


@dataclass(frozen=True)
class SimulatedPolicy:
    # True means a *test assumption*, NEVER real enrollment/evidence.
    independent_admin_assumed: bool = False
    exclusive_fake_adapter_assumed: bool = False
    trusted_test_key_assumed: bool = False
    strong_read_assumed: bool = False
    source_gate_assumed: bool = False
    human_owner_gate_assumed: bool = False
    simulated_monthly_budget: int = 0

    def check(self, quoted_cost: int = 0):
        if not all((self.independent_admin_assumed,
                    self.exclusive_fake_adapter_assumed,
                    self.trusted_test_key_assumed,
                    self.strong_read_assumed,
                    self.source_gate_assumed,
                    self.human_owner_gate_assumed)):
            raise Denied("SIMULATED_ARCHITECTURE_OR_SOURCE_GATES_NOT_MET")
        if type(quoted_cost) is not int or quoted_cost < 0 or quoted_cost > self.simulated_monthly_budget:
            raise Denied("SIMULATED_BUDGET_BLOCKED")


class SimulatedHighWater:
    """Same-process witness only. NOT independent / not crash-atomic with ledger."""
    def __init__(self):
        self.values = {}
        self.lock = threading.RLock()
        self.available = True

    def observe(self, identity, version):
        with self.lock:
            if not self.available:
                raise Denied("SIMULATED_WITNESS_UNAVAILABLE")
            self.values[identity] = max(self.values.get(identity, 0), version)

    def check(self, identity, version):
        with self.lock:
            if not self.available or identity not in self.values:
                raise Denied("SIMULATED_WITNESS_UNAVAILABLE")
            if version < self.values[identity]:
                raise Denied("ROLLBACK_DETECTED_QUARANTINE")


class FakeAdapter:
    """Only accepted adapter, no network implementation at all."""
    def __init__(self, sink=None, result="accepted"):
        self.sink = [] if sink is None else sink
        self.result = result

    def call(self, identity: Intent):
        self.sink.append(identity.digest)
        if self.result in ("timeout", "429", "5xx"):
            raise Uncertain("SYNTHETIC_PROVIDER_" + self.result)
        return {"status": "simulated_ack_no_proof", "operation_id": "untrusted-test-id"}


class FakeReceiptAuthority:
    """Harness-controlled HMAC test key. NOT a provider or independent signer."""
    def __init__(self, key=b"SIMULATION_ONLY_TEST_KEY", issuer="fake-provider", key_id="test-key-1"):
        self.key = key
        self.issuer = issuer
        self.key_id = key_id
        self.available = True

    def sign(self, intent: Intent, *, kind: str, nonce: str, sequence: int, operation_id="fake-operation-1"):
        fields = {"identity_digest": intent.digest, "epoch": intent.epoch,
                  "issuer": self.issuer, "key_id": self.key_id, "kind": kind,
                  "nonce": nonce, "sequence": sequence, "operation_id": operation_id}
        signature = hmac.new(self.key, canonical(fields).encode(), hashlib.sha256).hexdigest()
        return {**fields, "signature": signature}

    def verify(self, receipt, intent):
        if not self.available:
            raise Denied("SIGNER_OR_VERIFIER_UNAVAILABLE")
        if not isinstance(receipt, dict):
            raise Denied("INVALID_RECEIPT_TYPE")
        fields = {k: v for k, v in receipt.items() if k != "signature"}
        if set(fields) != {"identity_digest", "epoch", "issuer", "key_id", "kind",
                           "nonce", "sequence", "operation_id"}:
            raise Denied("RECEIPT_FIELDS_INVALID")
        if fields["identity_digest"] != intent.digest or fields["epoch"] != intent.epoch:
            raise Denied("RECEIPT_SCOPE_OR_EPOCH_MISMATCH")
        if fields["issuer"] != self.issuer or fields["key_id"] != self.key_id:
            raise Denied("RECEIPT_UNTRUSTED_ISSUER")
        if type(fields["sequence"]) is not int or fields["sequence"] <= 0 or not fields["nonce"] or not fields["operation_id"]:
            raise Denied("RECEIPT_SEQUENCE_OR_NONCE_INVALID")
        expected = hmac.new(self.key, canonical(fields).encode(), hashlib.sha256).hexdigest()
        if not isinstance(receipt.get("signature"), str) or not hmac.compare_digest(receipt["signature"], expected):
            raise Denied("RECEIPT_SIGNATURE_INVALID")


class Gateway:
    """A separate, inert state-machine lab. Never used by AION production Outbox."""
    def __init__(self, db_path, policy: SimulatedPolicy, witness: Optional[SimulatedHighWater] = None,
                 verifier: Optional[FakeReceiptAuthority] = None):
        self.db_path = str(db_path)
        self.policy = policy
        self.witness = witness
        self.verifier = verifier
        with self._tx() as con:
            con.execute("""CREATE TABLE IF NOT EXISTS intents (
                intent_id TEXT PRIMARY KEY, identity_json TEXT NOT NULL,
                state TEXT NOT NULL, version INTEGER NOT NULL,
                issued_count INTEGER NOT NULL DEFAULT 0,
                boundary TEXT NOT NULL DEFAULT '', operation_id TEXT NOT NULL DEFAULT '',
                receipt_seq INTEGER NOT NULL DEFAULT 0)""")
            con.execute("""CREATE TABLE IF NOT EXISTS seen_nonces (
                nonce TEXT PRIMARY KEY, intent_id TEXT NOT NULL)""")
            con.execute("""CREATE TABLE IF NOT EXISTS audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT, intent_id TEXT NOT NULL,
                event TEXT NOT NULL, version INTEGER NOT NULL)""")

    @contextmanager
    def _tx(self):
        con = sqlite3.connect(self.db_path, timeout=30, isolation_level=None)
        con.execute("PRAGMA busy_timeout=30000")
        try:
            con.execute("BEGIN IMMEDIATE")
            yield con
            con.commit()
        except BaseException:
            con.rollback()
            raise
        finally:
            con.close()

    @staticmethod
    def _row(con, intent):
        return con.execute("SELECT identity_json,state,version,issued_count,boundary,operation_id,receipt_seq FROM intents WHERE intent_id=?",
                           (intent.logical_intent_id,)).fetchone()

    def _validate(self, con, intent):
        row = self._row(con, intent)
        if not row:
            raise Denied("UNKNOWN_LOGICAL_INTENT")
        if row[0] != canonical(vars(intent)):
            raise Denied("INTENT_SCOPE_OR_PAYLOAD_CONFLICT")
        if self.witness is not None:
            self.witness.check(intent.logical_intent_id, row[2])
        return row

    def prepare(self, intent: Intent):
        self.policy.check()
        with self._tx() as con:
            row = self._row(con, intent)
            if row:
                self._validate(con, intent)
                return "ALREADY_PREPARED_OR_TERMINAL"
            # In this simulator only, witness update precedes initial commit;
            # this is NOT a distributed atomic commit or independent proof.
            if self.witness:
                self.witness.observe(intent.logical_intent_id, 1)
            con.execute("INSERT INTO intents(intent_id,identity_json,state,version) VALUES(?,?,?,1)",
                        (intent.logical_intent_id, canonical(vars(intent)), "PREPARED"))
            con.execute("INSERT INTO audit(intent_id,event,version) VALUES(?,?,1)",
                        (intent.logical_intent_id, "PREPARED"))
        return "PREPARED"

    def _transition_pre_handoff(self, intent: Intent, target: str):
        self.policy.check()
        with self._tx() as con:
            row = self._validate(con, intent)
            if row[1] != "PREPARED" or row[3] != 0:
                raise Denied("ALREADY_ISSUED_OR_FENCED")
            new_version = row[2] + 1
            con.execute("UPDATE intents SET state=?,version=?,issued_count=? WHERE intent_id=? AND version=?",
                        (target, new_version, 1 if target == "UNKNOWN" else 0,
                         intent.logical_intent_id, row[2]))
            con.execute("INSERT INTO audit(intent_id,event,version) VALUES(?,?,?)",
                        (intent.logical_intent_id,
                         "ISSUE_ONCE" if target == "UNKNOWN" else "FENCED_PRE_HANDOFF", new_version))
            # The independent witness is hypothetical. Local toy witness only.
            if self.witness:
                self.witness.observe(intent.logical_intent_id, new_version)
        return target

    def fence_pre_handoff(self, intent: Intent):
        return self._transition_pre_handoff(intent, "FENCED_PRE_HANDOFF")

    def dispatch_once(self, intent: Intent, adapter, *, crash_at=None, quoted_cost=0):
        self.policy.check(quoted_cost)
        # Exact class check prevents arbitrary SDK objects entering this laboratory.
        if type(adapter) is not FakeAdapter:
            raise Denied("REAL_OR_UNTRUSTED_ADAPTER_FORBIDDEN")
        self._transition_pre_handoff(intent, "UNKNOWN")  # durable ISSUE_ONCE before call
        if crash_at == "after_marker":
            raise InjectedCrash("AFTER_DURABLE_MARKER_BEFORE_FAKE_CALL")
        try:
            ack = adapter.call(intent)
        except Uncertain:
            raise  # durable UNKNOWN; NEVER reschedule/retry
        if crash_at == "after_handoff":
            raise InjectedCrash("AFTER_FAKE_CALL_BEFORE_RESPONSE")
        return ack  # deliberately does not promote provider/recipient success

    def accept_receipt(self, intent: Intent, receipt: dict):
        self.policy.check()
        if self.verifier is None:
            raise Denied("INDEPENDENT_PRODUCER_NOT_ENROLLED")
        self.verifier.verify(receipt, intent)
        kind = receipt["kind"]
        # A post-ISSUE_ONCE provider fence can never be proved by this simulator.
        if kind not in ("API_CREATED", "CARRIER_ACCEPTED", "DELIVERED"):
            raise Denied("NO_EFFECT_FENCED_CANNOT_BE_SIMULATED_POST_HANDOFF")
        with self._tx() as con:
            row = self._validate(con, intent)
            if row[3] != 1 or row[1] not in ("UNKNOWN", "PROVIDER_ACCEPTED", "DELIVERED_OBSERVED"):
                raise Denied("NO_ISSUED_INTENT_OR_TERMINAL")
            if receipt["sequence"] <= row[6] or con.execute("SELECT 1 FROM seen_nonces WHERE nonce=?", (receipt["nonce"],)).fetchone():
                raise Denied("RECEIPT_REPLAY_OR_NONMONOTONIC_SEQUENCE")
            if row[5] and receipt["operation_id"] != row[5]:
                raise Denied("PROVIDER_OPERATION_ID_FORK")
            # Delayed FAILED never produces a negative proof. Preserve strongest positive boundary.
            weights = {"": 0, "API_CREATED": 1, "CARRIER_ACCEPTED": 2, "DELIVERED": 3}
            boundary = kind if weights[kind] > weights[row[4]] else row[4]
            state = "DELIVERED_OBSERVED" if boundary == "DELIVERED" else "PROVIDER_ACCEPTED"
            next_version = row[2] + 1
            con.execute("INSERT INTO seen_nonces(nonce,intent_id) VALUES(?,?)", (receipt["nonce"], intent.logical_intent_id))
            con.execute("UPDATE intents SET state=?,boundary=?,operation_id=?,receipt_seq=?,version=? WHERE intent_id=?",
                        (state, boundary, receipt["operation_id"], receipt["sequence"], next_version, intent.logical_intent_id))
            con.execute("INSERT INTO audit(intent_id,event,version) VALUES(?,?,?)",
                        (intent.logical_intent_id, "SIMULATED_RECEIPT_" + kind, next_version))
            if self.witness:
                self.witness.observe(intent.logical_intent_id, next_version)
        return state

    def inspect(self, intent: Intent):
        with self._tx() as con:
            row = self._validate(con, intent)
            return {"state": row[1], "version": row[2], "issue_count": row[3],
                    "boundary": row[4], "operation_id": row[5], "receipt_seq": row[6]}

    def provider_lookup_without_id(self, intent):
        self.inspect(intent)
        return "UNKNOWN"  # 404 / no lookup by logical intent cannot prove no effect

    @staticmethod
    def production_worker_eligible(*, source_verified, h0_verified, owner_verified):
        # No offline test state can unlock the operational Worker.
        return False
