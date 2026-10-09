"""Independent checkpoint reference V2. NOT operational trust or authorization.

Public verification only. Signing and independent state live in hosted test
fixtures. No production wiring, network, key generation or automatic recovery.
V1 modules remain byte-for-byte unchanged.
"""
from __future__ import annotations
from copy import deepcopy
from hashlib import sha256
import re
import sqlite3
from threading import RLock

import atlasquant_aion_durable_dual_ed25519_challenge_registry_v1 as ledger
from atlasquant_aion_independent_ed25519_trirole_bridge_contract_v1 import (
    review_three_role_custody_design,
)
from atlasquant_aion_ed25519_public_verify_p256_attestation_review_v1 import (
    verify_ed25519_public_signature,
)
from atlasquant_aion_dual_ed25519_public_crypto_bridge_v1 import (
    verify_dual_ed25519_public_signatures_untrusted, CANDIDATE,
)

SCHEMA = "AION_INDEPENDENT_MONOTONIC_CHECKPOINT_REFERENCE_V2"
PURPOSE = "INDEPENDENT_LEDGER_CHECKPOINT_NOT_AUTHORIZATION"
V2_BINDING_SCHEMA = "AION_CUSTODY_BOUND_POLICY_TRANSCRIPT_V2"
V2_PURPOSE = "CUSTODY_BOUND_REFERENCE_MIGRATION_NOT_AUTHORIZATION"
ZERO = ledger.GENESIS
FALSE_GATES = {**ledger.FALSE_GATES,
    "execution_allowed": False, "hardware_antirollback_verified": False,
    "owner_identity_authenticated": False, "independent_custody_verified": False,
    "p256_tpm_origin_attested": False, "physical_sandbox_verified": False,
    "physical_network_deny_verified": False, "key_enrollment_authorized": False,
    "installer_authorized": False, "build_authorized": False,
    "deploy_authorized": False, "safe_to_resume": False,
}
_HEX = re.compile(r"sha256:[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9_.-]{8,72}\Z")
_FIELDS = {"schema","version","purpose","phase","installation_id","trust_chain_id",
    "witness_id","generation","policy_sha256","custody_sha256","ledger_state_sha256",
    "checkpoint_sequence","previous_checkpoint_sha256","owner_public_key_sha256",
    "collector_public_key_sha256","transaction_id","challenge_id","observed_at",
    "clock_trusted"}
_SCOPE = {"installation_id","trust_chain_id","witness_id",
          "owner_public_key_sha256","collector_public_key_sha256","custody_sha256"}
_LIMIT = 2048


class ReferenceWitnessError(RuntimeError):
    pass


def _digest(domain, value):
    return "sha256:" + sha256(domain.encode("ascii")+b"\x00"
                              +ledger._json(value).encode("ascii")).hexdigest()


def _plain(value):
    return ledger._copy(value)


def _scope(value):
    value = _plain(value)
    if type(value) is not dict or set(value) != _SCOPE:
        raise ValueError("SCOPE_INVALID")
    for field in ("installation_id","trust_chain_id","witness_id"):
        if type(value[field]) is not str or not _ID.fullmatch(value[field]):
            raise ValueError("SCOPE_INVALID")
    for field in _SCOPE-{"installation_id","trust_chain_id","witness_id"}:
        if type(value[field]) is not str or not _HEX.fullmatch(value[field]):
            raise ValueError("SCOPE_INVALID")
    if value["owner_public_key_sha256"] == value["collector_public_key_sha256"]:
        raise ValueError("ROLE_SWAP")
    return value


def custody_digest(proposal):
    """Self-described custody/cost is bound, never certified as true."""
    proposal = _plain(proposal)
    if review_three_role_custody_design(proposal)["state"] != "THREE_ROLE_CUSTODY_DESIGN_CANDIDATE_UNTRUSTED":
        raise ValueError("PROPOSAL_INVALID")
    custody = {k:proposal[k] for k in ("owner","collector","host",
                                      "estimated_monthly_brl","collector_binary_sha256")}
    return _digest("AION:CUSTODY:V2",custody)


def build_v2_binding(proposal, nonce):
    """Explicit new transcript; NO silent reinterpretation of V1 signatures."""
    proposal = _plain(proposal)
    custody_digest(proposal)
    if type(nonce) is not str or not ledger.NONCE.fullmatch(nonce):
        raise ValueError("NONCE_INVALID")
    body = {"schema":V2_BINDING_SCHEMA,"purpose":V2_PURPOSE,
            "nonce":nonce,"proposal":proposal}
    transcript = _digest("AION:FULL_POLICY:V2",body)
    return {**body,"transcript_sha256":transcript,
        "role_intents":{role:_digest("AION:"+role+":CUSTODY_INTENT:V2",body)
                        for role in ("owner","collector")},**FALSE_GATES}


def verify_v2_request(request, scope):
    """Requires V2 signatures AND V1 math needed by unchanged SQLite store."""
    request = _plain(request)
    scope = _scope(scope)
    if type(request) is not dict or set(request) != {
            "v1_request","v2_owner_signature_hex","v2_collector_signature_hex"}:
        raise ValueError("REQUEST_INVALID")
    raw = request["v1_request"]
    if type(raw) is not dict or set(raw) != ledger._REQUEST_KEYS:
        raise ValueError("REQUEST_INVALID")
    if verify_dual_ed25519_public_signatures_untrusted(**raw)["state"] != CANDIDATE:
        raise ValueError("V1_MATH_INVALID")
    proposal = raw["proposal"]
    if custody_digest(proposal) != scope["custody_sha256"]:
        raise ValueError("CUSTODY_SCOPE_INVALID")
    binding = build_v2_binding(proposal,raw["nonce"])
    for role, domain in (("owner","HUMAN_OWNER_ED25519"),("collector","COLLECTOR_ED25519")):
        if proposal[role]["public_key_sha256"] != scope[role+"_public_key_sha256"]:
            raise ValueError("KEY_SCOPE_INVALID")
        message = bytes.fromhex(binding["role_intents"][role][7:])
        out = verify_ed25519_public_signature(role=domain,
            public_key_hex=raw[role+"_public_key_hex"],
            signature_hex=request["v2_"+role+"_signature_hex"],message_hex=message.hex(),
            claimed_public_key_sha256=scope[role+"_public_key_sha256"],
            claimed_message_sha256="sha256:"+sha256(message).hexdigest())
        if not out["signature_mathematically_valid"]:
            raise ValueError("V2_MATH_INVALID")
    return raw


def ledger_snapshot(store):
    """Consistent, validated READ-ONLY logical SQLite snapshot, no new tables.

    Pins/scope do not come from this database. Domain hash covers EVERY existing
    row, including challenge bodies, receipts, clock, policy and audit head.
    """
    if type(store) is not ledger.ReferenceChallengeRegistry:
        raise ValueError("STORE_INVALID")
    conn = store._connect()
    try:
        conn.execute("PRAGMA query_only=ON")
        conn.execute("BEGIN")
        store._validate(conn)
        order = {"meta":"id","policy":"id","challenges":"nonce","evidence":"sequence"}
        tables = {name:[dict(row) for row in conn.execute(
            "SELECT * FROM "+name+" ORDER BY "+key)] for name,key in order.items()}
        # Validated registry enforces bounded table counts and JSON sizes.
        return tables
    finally:
        conn.rollback()
        conn.close()


def snapshot_digest(snapshot):
    fields = {"meta":{"id","version","last_now"},"policy":{"id","generation","digest"},
              "challenges":{"nonce","body","state","receipt"},
              "evidence":{"sequence","previous_digest","body","digest"}}
    bounds = {"meta":1,"policy":1,"challenges":ledger.MAX_RECORDS,"evidence":ledger.MAX_EVENTS}
    if type(snapshot) is not dict or set(snapshot) != set(fields):
        raise ValueError("SNAPSHOT_INVALID")
    for table, rows in snapshot.items():
        if type(rows) is not list or len(rows) > bounds[table]:
            raise ValueError("SNAPSHOT_BOUND")
        for row in rows:
            if type(row) is not dict or set(row) != fields[table]:
                raise ValueError("SNAPSHOT_INVALID")
            for key, value in row.items():
                if key in ("id","version","last_now","generation","sequence"):
                    if type(value) is not int or not 0 <= value < 2**63:
                        raise ValueError("SNAPSHOT_TYPE")
                elif value is None and key == "receipt":
                    pass
                elif type(value) is not str or len(value) > 8192:
                    raise ValueError("SNAPSHOT_TYPE")
    return _digest("AION:COMPLETE_LEDGER_STATE:V2",snapshot)


def expected_consumption(store, before, raw, now_ts):
    """Exact expected single V1 transition; NOT repair or a second ledger."""
    target = deepcopy(before)
    nonce = raw["nonce"]
    row = next((r for r in target["challenges"] if r["nonce"] == nonce),None)
    if row is None or row["state"] != "ISSUED":
        raise ValueError("NONCE_NOT_ISSUED")
    record = ledger._decode(row["body"])
    if record["binding"] != ledger._binding(raw["proposal"],nonce):
        raise ValueError("BINDING_INVALID")
    now = ledger._time(now_ts)
    if not ledger._time(record["issued_at"]) <= now < ledger._time(record["expires_at"]):
        raise ValueError("CHALLENGE_TIME_INVALID")
    if now < target["meta"][0]["last_now"]:
        raise ValueError("CLOCK_ROLLBACK")
    policy_before = ({"generation":target["policy"][0]["generation"],
                      "digest":target["policy"][0]["digest"]} if target["policy"] else None)
    policy_after = {"generation":raw["proposal"]["policy_generation"],
                    "digest":raw["proposal"]["policy_sha256"]}
    if policy_before and (policy_after["generation"] < policy_before["generation"]
            or policy_after["generation"] == policy_before["generation"]
            and policy_after["digest"] != policy_before["digest"]):
        raise ValueError("POLICY_ROLLBACK")
    seq = len(target["evidence"])+1
    receipt = ledger.ReferenceChallengeRegistry._receipt(None,nonce,record,now_ts=now_ts,sequence=seq)
    row["state"],row["receipt"] = "CONSUMED",ledger._json(receipt)
    target["policy"] = [{"id":1,**policy_after}]
    target["meta"][0]["last_now"] = now
    prev = target["evidence"][-1]["digest"] if target["evidence"] else ZERO
    body = {"nonce":nonce,"from_state":"ISSUED","to_state":"CONSUMED",
            "record_digest":record["record_digest"],"receipt_digest":receipt["receipt_digest"],
            "policy_before":policy_before,"policy_after":policy_after,"observed_at":now_ts}
    target["evidence"].append({"sequence":seq,"previous_digest":prev,
        "body":ledger._json(body),"digest":ledger._hash(
            {"sequence":seq,"previous_digest":prev,"body":body})})
    return target


def _checkpoint(value):
    value = _plain(value)
    if type(value) is not dict or set(value) != _FIELDS:
        raise ValueError("CHECKPOINT_SCHEMA_INVALID")
    _scope({k:value[k] for k in _SCOPE})
    if (value["schema"] != SCHEMA or type(value["version"]) is not int
            or value["version"] != 2 or value["purpose"] != PURPOSE
            or value["phase"] not in ("PREPARED","CONFIRMED")
            or value["clock_trusted"] is not False):
        raise ValueError("CHECKPOINT_DOMAIN_INVALID")
    for key in ("generation","checkpoint_sequence"):
        if type(value[key]) is not int or not 0 <= value[key] <= ledger.MAX_GENERATION:
            raise ValueError("CHECKPOINT_SEQUENCE_INVALID")
    if value["checkpoint_sequence"] == 0:
        raise ValueError("CHECKPOINT_SEQUENCE_INVALID")
    for key in ("policy_sha256","ledger_state_sha256","previous_checkpoint_sha256"):
        if type(value[key]) is not str or not _HEX.fullmatch(value[key]):
            raise ValueError("CHECKPOINT_DIGEST_INVALID")
    for key in ("transaction_id","challenge_id"):
        if type(value[key]) is not str or not ledger.NONCE.fullmatch(value[key]):
            raise ValueError("CHECKPOINT_ID_INVALID")
    ledger._time(value["observed_at"])
    return value


def checkpoint_digest(checkpoint):
    return _digest("AION:CHECKPOINT:V2",_checkpoint(checkpoint))


def checkpoint_message(checkpoint):
    return bytes.fromhex(checkpoint_digest(checkpoint)[7:])


def verify_checkpoint(envelope, *, trusted_public_key_hex, expected):
    """Pinned key supplied separately, exact independently expected checkpoint.

    Pin is NOT extracted from envelope/client/SQLite. Static signature alone
    cannot prove live witness freshness or latest head; expected must come from
    the independent state protocol. Real enrollment/transport remain absent.
    """
    result = {"state":"BLOCKED","external_witness_checkpoint_verified":False,
              "ledger_matches_witness":False,**FALSE_GATES}
    try:
        envelope = _plain(envelope)
        expected = _checkpoint(expected)
        if (type(envelope) is not dict or set(envelope) != {"checkpoint","signature_hex"}
                or _checkpoint(envelope["checkpoint"]) != expected):
            return result
        if type(trusted_public_key_hex) is not str or not re.fullmatch(r"[0-9a-f]{64}",trusted_public_key_hex):
            return result
        message = checkpoint_message(expected)
        verification = verify_ed25519_public_signature(role="COLLECTOR_ED25519",
            public_key_hex=trusted_public_key_hex,signature_hex=envelope["signature_hex"],
            message_hex=message.hex(),
            claimed_public_key_sha256="sha256:"+sha256(bytes.fromhex(trusted_public_key_hex)).hexdigest(),
            claimed_message_sha256="sha256:"+sha256(message).hexdigest())
        if verification["signature_mathematically_valid"]:
            result["external_witness_checkpoint_verified"] = True
            result["state"] = "CHECKPOINT_SIGNATURE_VERIFIED_REFERENCE_ONLY"
        return result
    except (ValueError,TypeError,KeyError,OverflowError,RecursionError):
        return result


class ReferenceWitnessState:
    """Controlled independent RAM state machine, NOT a trusted real service.

    Does not sign. Only the disposable TEST wrapper owns an ephemeral signer.
    Enrollment/bootstrap is explicit with fixed scope and exact initial ledger
    hash. No dynamic trust-chain rotation or reset. Pending cannot authorize.
    """
    def __init__(self, *, scope, initial_ledger_sha256):
        self.scope = _scope(scope)
        if type(initial_ledger_sha256) is not str or not _HEX.fullmatch(initial_ledger_sha256):
            raise ValueError("INITIAL_HEAD_INVALID")
        self.ledger_head = initial_ledger_sha256
        self.head = None
        self.pending = None
        self.used = set()
        self.lock = RLock()

    def prepare(self, *, before_snapshot, request, candidate):
        candidate = _checkpoint(candidate)
        # Authenticate V2 role intents independently; never trust adapter claims.
        raw = verify_v2_request(request,self.scope)
        before_sha256 = snapshot_digest(before_snapshot)
        target = expected_consumption(None,before_snapshot,raw,candidate["observed_at"])
        if (candidate["ledger_state_sha256"] != snapshot_digest(target)
                or candidate["challenge_id"] != raw["nonce"]
                or candidate["generation"] != raw["proposal"]["policy_generation"]
                or candidate["policy_sha256"] != raw["proposal"]["policy_sha256"]):
            raise ReferenceWitnessError("TARGET_NOT_RECOMPUTED_FROM_SIGNED_REQUEST")
        with self.lock:
            if (self.pending is not None or len(self.used) >= _LIMIT
                    or {k:candidate[k] for k in _SCOPE} != self.scope
                    or before_sha256 != self.ledger_head
                    or candidate["phase"] != "PREPARED"
                    or candidate["transaction_id"] in self.used
                    or candidate["checkpoint_sequence"] != (self.head["checkpoint_sequence"]+1 if self.head else 1)
                    or candidate["previous_checkpoint_sha256"] != (checkpoint_digest(self.head) if self.head else ZERO)):
                raise ReferenceWitnessError("PREPARE_CONFLICT_OR_ROLLBACK")
            if self.head and (candidate["generation"] < self.head["generation"]
                    or candidate["generation"] == self.head["generation"]
                    and candidate["policy_sha256"] != self.head["policy_sha256"]):
                raise ReferenceWitnessError("GENERATION_CONFLICT")
            self.pending = deepcopy(candidate)
            return deepcopy(candidate)

    def confirm(self, *, transaction_id, ledger_state_sha256):
        with self.lock:
            if (self.pending is None or self.pending["transaction_id"] != transaction_id
                    or self.pending["ledger_state_sha256"] != ledger_state_sha256):
                raise ReferenceWitnessError("NO_COMPATIBLE_PENDING")
            checkpoint = {**self.pending,"phase":"CONFIRMED"}
            self.head = checkpoint
            self.ledger_head = ledger_state_sha256
            self.used.add(transaction_id)
            self.pending = None
            return deepcopy(checkpoint)

    def recover(self, *, transaction_id, ledger_state_sha256):
        with self.lock:
            if self.pending is not None:
                return self.confirm(transaction_id=transaction_id,
                                    ledger_state_sha256=ledger_state_sha256)
            if (self.head is None or self.head["transaction_id"] != transaction_id
                    or self.head["ledger_state_sha256"] != ledger_state_sha256):
                raise ReferenceWitnessError("SUPERVISED_RECOVERY_REQUIRED")
            return deepcopy(self.head)

    def matches_pending(self, candidate):
        candidate = _checkpoint(candidate)
        with self.lock:
            return self.pending == candidate

    def expected_head(self):
        with self.lock:
            return {"sequence":self.head["checkpoint_sequence"] if self.head else 0,
                    "digest":checkpoint_digest(self.head) if self.head else ZERO}


def _out(reason, *, consumed=False, verified=False, matches=False, checkpoint=None):
    return {"schema":SCHEMA,"state":"REFERENCE_LEDGER_MATCHES_WITNESS" if matches else "BLOCKED",
            "reason":reason,"dual_signature_mathematically_valid":consumed,
            "nonce_consumed_intact_ledger":consumed,
            "external_witness_checkpoint_verified":verified,"ledger_matches_witness":matches,
            "snapshot_atomic_across_witness":False,"exactly_once_execution_proven":False,
            "reference_only":True,"checkpoint":deepcopy(checkpoint),**FALSE_GATES}


class ReferenceWitnessAdapter:
    """Explicit fixture calls only. SQLite and witness are NOT one ACID unit.

    Witness port is the CI test double, never a provider/executor. The separately
    supplied live state is the SAME independent CI witness, not a second store.
    An untrusted port response cannot select the expected monotonic head.
    Verification
    independently checks the separately supplied pin and exact prepared target.
    Restart recovery requires the original prepared intent; losing it blocks.
    """
    def __init__(self, *, store, witness, scope, trusted_witness_public_key_hex,
                 trusted_witness_state):
        if type(store) is not ledger.ReferenceChallengeRegistry:
            raise ValueError("STORE_INVALID")
        if type(trusted_witness_state) is not ReferenceWitnessState:
            raise ValueError("INDEPENDENT_LIVE_STATE_REQUIRED")
        self.store, self.witness = store,witness
        self.scope = _scope(scope)
        if trusted_witness_state.scope != self.scope:
            raise ValueError("INDEPENDENT_STATE_SCOPE_MISMATCH")
        self.trusted_state = trusted_witness_state
        self.pin = trusted_witness_public_key_hex

    def prepare(self, *, request, transaction_id, now_ts):
        raw = verify_v2_request(request,self.scope)
        if type(transaction_id) is not str or not ledger.NONCE.fullmatch(transaction_id):
            raise ValueError("TRANSACTION_INVALID")
        before = ledger_snapshot(self.store)
        target = expected_consumption(self.store,before,raw,now_ts)
        head = self.trusted_state.expected_head()
        candidate = _checkpoint({"schema":SCHEMA,"version":2,"purpose":PURPOSE,
            "phase":"PREPARED",**self.scope,"generation":raw["proposal"]["policy_generation"],
            "policy_sha256":raw["proposal"]["policy_sha256"],
            "ledger_state_sha256":snapshot_digest(target),
            "checkpoint_sequence":head["sequence"]+1,
            "previous_checkpoint_sha256":head["digest"],"transaction_id":transaction_id,
            "challenge_id":raw["nonce"],"observed_at":now_ts,"clock_trusted":False})
        envelope = self.witness.prepare(before_snapshot=before,request=_plain(request),candidate=candidate)
        if (not verify_checkpoint(envelope,trusted_public_key_hex=self.pin,expected=candidate)["external_witness_checkpoint_verified"]
                or not self.trusted_state.matches_pending(candidate)):
            raise ReferenceWitnessError("PREPARE_NOT_AUTHENTICATED")
        return deepcopy(candidate)

    def consume_and_confirm(self, *, request, transaction_id, now_ts):
        try:
            prepared = self.prepare(request=request,transaction_id=transaction_id,now_ts=now_ts)
            raw = verify_v2_request(request,self.scope)
            result = self.store.consume(request=raw,now_ts=now_ts)
            if not result["nonce_transaction_consumed"]:
                return _out("SQLITE_NOT_ACKNOWLEDGED_PENDING_RECOVERY")
            return self.recover(prepared=prepared)
        except (ReferenceWitnessError,ledger.ReferenceStoreError,ValueError,TypeError,
                KeyError,OverflowError,sqlite3.Error,OSError):
            return _out("PREPARE_OR_CONFIRM_UNAVAILABLE_SUPERVISED_RECOVERY")

    def recover(self, *, prepared):
        """No consumption, issuance, repair or fallback in recovery."""
        try:
            prepared = _checkpoint(prepared)
            if (prepared["phase"] != "PREPARED"
                    or {k:prepared[k] for k in _SCOPE} != self.scope):
                raise ValueError("RECOVERY_SCOPE_INVALID")
            current = snapshot_digest(ledger_snapshot(self.store))
            if current != prepared["ledger_state_sha256"]:
                return _out("LEDGER_WITNESS_DIVERGENCE_SUPERVISED_RECOVERY")
            envelope = self.witness.recover(transaction_id=prepared["transaction_id"],
                                           ledger_state_sha256=current)
            expected = {**prepared,"phase":"CONFIRMED"}
            verified = verify_checkpoint(envelope,trusted_public_key_hex=self.pin,expected=expected)
            if not verified["external_witness_checkpoint_verified"]:
                return _out("CONFIRM_NOT_AUTHENTICATED")
            head = self.trusted_state.expected_head()
            if head != {"sequence":expected["checkpoint_sequence"],"digest":checkpoint_digest(expected)}:
                return _out("NOT_LATEST_INDEPENDENT_WITNESS_HEAD")
            return _out("",consumed=True,verified=True,matches=True,checkpoint=expected)
        except (ReferenceWitnessError,ledger.ReferenceStoreError,ValueError,TypeError,
                KeyError,OverflowError,sqlite3.Error,OSError):
            return _out("RECOVERY_BLOCKED_NO_FALLBACK")
