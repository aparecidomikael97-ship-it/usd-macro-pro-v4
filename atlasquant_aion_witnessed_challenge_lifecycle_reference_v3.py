"""Witnessed challenge lifecycle V3, disposable reference ONLY.

Reuses frozen V1 SQLite CAS/validator and V2 snapshot/custody/public verification.
No signing/private keys/network/executor/automatic service or production wiring.
"""
from __future__ import annotations
from copy import deepcopy
from hashlib import sha256
import re
import sqlite3

import atlasquant_aion_durable_dual_ed25519_challenge_registry_v1 as ledger
import atlasquant_aion_independent_monotonic_witness_reference_v2 as v2

SCHEMA="AION_WITNESSED_CHALLENGE_TRANSITION_REFERENCE_V3"
CHECKPOINT_SCHEMA="AION_WITNESSED_CHALLENGE_CHECKPOINT_REFERENCE_V3"
OPERATIONS=("ISSUE_CHALLENGE","CONSUME_CHALLENGE","EXPIRE_CHALLENGE","REVOKE_CHALLENGE")
PURPOSES={op:op+"_REFERENCE_NOT_AUTHORIZATION" for op in OPERATIONS}
NEXT={"ISSUE_CHALLENGE":"ISSUED","CONSUME_CHALLENGE":"CONSUMED",
      "EXPIRE_CHALLENGE":"EXPIRED","REVOKE_CHALLENGE":"REVOKED"}
FALSE_GATES={**v2.FALSE_GATES,"trusted_owner_identity_verified":False,
             "protected_witness_storage_verified":False,"trusted_clock_verified":False,
             "temporal_expiration_proven":False}
_FIELDS={"schema","version","operation","purpose",*v2._SCOPE,
         "nonce","transaction_id","checkpoint_sequence","previous_ledger_sha256",
         "ledger_state_sha256","previous_checkpoint_sha256","generation",
         "policy_sha256","proposal","collector_binary_sha256","previous_state",
         "next_state","observed_at","issued_at","expires_at","clock_trusted"}
_REQUEST_FIELDS={"transition","owner_public_key_hex","owner_signature_hex",
                 "collector_public_key_hex","collector_signature_hex","v1_request"}


def _policy(value):
    value=v2._plain(value)
    if (type(value) is not dict or set(value)!={"generation","digest"}
            or type(value["generation"]) is not int
            or not 0<=value["generation"]<=ledger.MAX_GENERATION
            or type(value["digest"]) is not str or not v2._HEX.fullmatch(value["digest"])):
        raise ValueError("POLICY_INVALID")
    return value


def _transition(value):
    value=v2._plain(value)
    if type(value) is not dict or set(value)!=_FIELDS:
        raise ValueError("TRANSITION_SCHEMA_INVALID")
    op=value["operation"]
    if (type(op) is not str or op not in OPERATIONS or value["schema"]!=SCHEMA
            or type(value["version"]) is not int or value["version"]!=3
            or value["purpose"]!=PURPOSES[op] or value["clock_trusted"] is not False):
        raise ValueError("TRANSITION_DOMAIN_INVALID")
    scope=v2._scope({k:value[k] for k in v2._SCOPE})
    proposal=value["proposal"]
    if v2.custody_digest(proposal)!=scope["custody_sha256"]:
        raise ValueError("CUSTODY_MISMATCH")
    for role in ("owner","collector"):
        if proposal[role]["public_key_sha256"]!=scope[role+"_public_key_sha256"]:
            raise ValueError("ROLE_SCOPE_MISMATCH")
    if value["collector_binary_sha256"]!=proposal["collector_binary_sha256"]:
        raise ValueError("BINARY_MISMATCH")
    for key in ("nonce","transaction_id"):
        if type(value[key]) is not str or not ledger.NONCE.fullmatch(value[key]):
            raise ValueError("IDENTIFIER_INVALID")
    if (type(value["checkpoint_sequence"]) is not int
            or not 1<=value["checkpoint_sequence"]<=ledger.MAX_GENERATION):
        raise ValueError("SEQUENCE_INVALID")
    _policy({"generation":value["generation"],"digest":value["policy_sha256"]})
    for key in ("previous_ledger_sha256","ledger_state_sha256","previous_checkpoint_sha256"):
        if type(value[key]) is not str or not v2._HEX.fullmatch(value[key]):
            raise ValueError("DIGEST_INVALID")
    if (value["previous_state"]!=(None if op=="ISSUE_CHALLENGE" else "ISSUED")
            or value["next_state"]!=NEXT[op]):
        raise ValueError("LIFECYCLE_INVALID")
    for key in ("observed_at","issued_at","expires_at"):
        ledger._time(value[key])
    return value


def transition_message(transition,role):
    transition=_transition(transition)
    if type(role) is not str or role not in ("owner","collector"):
        raise ValueError("ROLE_INVALID")
    return bytes.fromhex(v2._digest(
        "AION:V3:"+transition["operation"]+":"+role.upper()+":INTENT",transition)[7:])


def _checkpoint(value):
    value=v2._plain(value)
    if (type(value) is not dict or set(value)!=_FIELDS|{"checkpoint_schema","phase","request_sha256"}
            or value["checkpoint_schema"]!=CHECKPOINT_SCHEMA
            or value["phase"] not in ("PREPARED","CONFIRMED")):
        raise ValueError("CHECKPOINT_SCHEMA_INVALID")
    if type(value["request_sha256"]) is not str or not v2._HEX.fullmatch(value["request_sha256"]):
        raise ValueError("REQUEST_DIGEST_INVALID")
    _transition({k:value[k] for k in _FIELDS})
    return value


def checkpoint_digest(checkpoint):
    checkpoint=_checkpoint(checkpoint)
    return v2._digest("AION:V3:"+checkpoint["operation"]+":WITNESS:"+checkpoint["phase"],checkpoint)


def checkpoint_message(checkpoint):
    return bytes.fromhex(checkpoint_digest(checkpoint)[7:])


def _public_math(key,signature,message,role,fingerprint):
    return v2.verify_ed25519_public_signature(
        role=role,public_key_hex=key,signature_hex=signature,message_hex=message.hex(),
        claimed_public_key_sha256=fingerprint,
        claimed_message_sha256="sha256:"+sha256(message).hexdigest()
    )["signature_mathematically_valid"]


def verify_checkpoint(envelope,*,pin,expected):
    try:
        envelope=v2._plain(envelope)
        expected=_checkpoint(expected)
        if (type(envelope) is not dict or set(envelope)!={"checkpoint","signature_hex"}
                or _checkpoint(envelope["checkpoint"])!=expected
                or type(pin) is not str or not re.fullmatch(r"[0-9a-f]{64}",pin)):
            return False
        return _public_math(pin,envelope["signature_hex"],checkpoint_message(expected),
            "COLLECTOR_ED25519","sha256:"+sha256(bytes.fromhex(pin)).hexdigest())
    except (ValueError,TypeError,KeyError,OverflowError,RecursionError):
        return False


def verify_request(request,scope):
    request=v2._plain(request)
    scope=v2._scope(scope)
    if type(request) is not dict or set(request)!=_REQUEST_FIELDS:
        raise ValueError("REQUEST_INVALID")
    body=_transition(request["transition"])
    if {k:body[k] for k in v2._SCOPE}!=scope:
        raise ValueError("SCOPE_MISMATCH")
    for role,domain in (("owner","HUMAN_OWNER_ED25519"),("collector","COLLECTOR_ED25519")):
        if not _public_math(request[role+"_public_key_hex"],request[role+"_signature_hex"],
                transition_message(body,role),domain,scope[role+"_public_key_sha256"]):
            raise ValueError("TRANSITION_SIGNATURE_INVALID")
    raw=request["v1_request"]
    if body["operation"] in ("CONSUME_CHALLENGE","EXPIRE_CHALLENGE"):
        if (type(raw) is not dict or set(raw)!=ledger._REQUEST_KEYS
                or raw["proposal"]!=body["proposal"] or raw["nonce"]!=body["nonce"]
                or v2.verify_dual_ed25519_public_signatures_untrusted(**raw)["state"]!=v2.CANDIDATE):
            raise ValueError("LEGACY_LEDGER_MATH_INVALID")
    elif raw is not None:
        raise ValueError("UNEXPECTED_LEGACY_REQUEST")
    return request


def request_digest(request):
    return v2._digest("AION:V3:VALIDATED_REQUEST",v2._plain(request))


def _target(before,*,operation,proposal,nonce,observed_at,issued_at,expires_at,current_policy):
    """Exact V1 logical transition; writes ONLY existing V1 methods later."""
    v2.snapshot_digest(before)
    current_policy=_policy(current_policy)
    binding=ledger._binding(proposal,nonce)
    now=ledger._time(observed_at)
    if now<before["meta"][0]["last_now"]:
        raise ValueError("CLOCK_ROLLBACK")
    persisted=({"generation":before["policy"][0]["generation"],"digest":before["policy"][0]["digest"]}
               if before["policy"] else None)
    if persisted is not None and persisted!=current_policy:
        raise ValueError("POLICY_HEAD_DIVERGENCE")
    if operation in ("ISSUE_CHALLENGE","CONSUME_CHALLENGE"):
        if (proposal["policy_generation"]<current_policy["generation"]
                or proposal["policy_generation"]==current_policy["generation"]
                and proposal["policy_sha256"]!=current_policy["digest"]):
            raise ValueError("POLICY_ROLLBACK_OR_CONFLICT")
    row=next((r for r in before["challenges"] if r["nonce"]==nonce),None)
    if operation=="ISSUE_CHALLENGE":
        if row is not None or issued_at!=observed_at:
            raise ValueError("NONCE_DUPLICATE_OR_ISSUE_TIME")
        if not 0<ledger._time(expires_at)-now<=ledger.MAX_WINDOW_US:
            raise ValueError("CHALLENGE_WINDOW_INVALID")
    else:
        if row is None or row["state"]!="ISSUED":
            raise ValueError("TERMINAL_OR_MISSING_NONCE")
        existing=ledger._decode(row["body"])
        if (existing["binding"]!=binding or existing["issued_at"]!=issued_at
                or existing["expires_at"]!=expires_at):
            raise ValueError("ORIGINAL_RECORD_MISMATCH")
    if operation=="CONSUME_CHALLENGE":
        target=v2.expected_consumption(None,before,{"proposal":proposal,"nonce":nonce},observed_at)
        after_policy={"generation":proposal["policy_generation"],"digest":proposal["policy_sha256"]}
        return target,after_policy
    if operation=="EXPIRE_CHALLENGE" and now<ledger._time(expires_at):
        raise ValueError("NOT_EXPIRED_ON_UNTRUSTED_CLOCK")
    target=deepcopy(before)
    if operation=="ISSUE_CHALLENGE":
        body={"binding":binding,"issued_at":issued_at,"expires_at":expires_at}
        record={**body,"record_digest":ledger._hash(body)}
        target["challenges"].append({"nonce":nonce,"body":ledger._json(record),"state":"ISSUED","receipt":None})
        target["challenges"].sort(key=lambda r:r["nonce"])
    else:
        target_row=next(r for r in target["challenges"] if r["nonce"]==nonce)
        record=ledger._decode(target_row["body"])
        target_row["state"]=NEXT[operation]
    seq=len(target["evidence"])+1
    prev=target["evidence"][-1]["digest"] if target["evidence"] else ledger.GENESIS
    event={"nonce":nonce,"from_state":None if operation=="ISSUE_CHALLENGE" else "ISSUED",
           "to_state":NEXT[operation],"record_digest":record["record_digest"],
           "receipt_digest":None,"policy_before":persisted,"policy_after":persisted,
           "observed_at":observed_at}
    target["evidence"].append({"sequence":seq,"previous_digest":prev,"body":ledger._json(event),
        "digest":ledger._hash({"sequence":seq,"previous_digest":prev,"body":event})})
    target["meta"][0]["last_now"]=now
    v2.snapshot_digest(target) # existing bounds; no pruning/reset
    return target,current_policy


def build_transition(*,store,state,operation,proposal,nonce,transaction_id,
                     observed_at,issued_at=None,expires_at=None):
    if type(state) is not LifecycleWitnessState or type(operation) is not str or operation not in OPERATIONS:
        raise ValueError("REFERENCE_STATE_OR_OPERATION_INVALID")
    before=v2.ledger_snapshot(store)
    state.validate_history()
    if v2.snapshot_digest(before)!=state.ledger_head:
        raise ValueError("LEDGER_WITNESS_DIVERGENCE")
    if operation!="ISSUE_CHALLENGE":
        row=next((r for r in before["challenges"] if r["nonce"]==nonce),None)
        if row is None:raise ValueError("CHALLENGE_MISSING")
        record=ledger._decode(row["body"])
        issued_at,expires_at=record["issued_at"],record["expires_at"]
    policy=state.current_policy()
    target,after=_target(before,operation=operation,proposal=proposal,nonce=nonce,
        observed_at=observed_at,issued_at=issued_at,expires_at=expires_at,current_policy=policy)
    head=state.expected_head()
    return _transition({"schema":SCHEMA,"version":3,"operation":operation,
        "purpose":PURPOSES[operation],**state.scope,"nonce":nonce,"transaction_id":transaction_id,
        "checkpoint_sequence":head["sequence"]+1,"previous_ledger_sha256":v2.snapshot_digest(before),
        "ledger_state_sha256":v2.snapshot_digest(target),"previous_checkpoint_sha256":head["digest"],
        "generation":after["generation"],"policy_sha256":after["digest"],"proposal":v2._plain(proposal),
        "collector_binary_sha256":proposal["collector_binary_sha256"],
        "previous_state":None if operation=="ISSUE_CHALLENGE" else "ISSUED","next_state":NEXT[operation],
        "observed_at":observed_at,"issued_at":issued_at,"expires_at":expires_at,"clock_trusted":False})


class LifecycleWitnessState(v2.ReferenceWitnessState):
    """Same V2 independent RAM state/lock, generalized lifecycle + signed history.

    Bootstrap ONLY empty validated fixture, fixed scope/policy/pin supplied
    separately. No migration/reset/repair API or protected-storage assertion.
    V1 SQLite state writes and V2 public crypto/snapshot authority reused.
    """
    def __init__(self,*,scope,initial_snapshot,initial_policy,witness_public_pin):
        empty={"meta":[{"id":1,"version":1,"last_now":0}],"policy":[],"challenges":[],"evidence":[]}
        if initial_snapshot!=empty or v2.snapshot_digest(initial_snapshot)!=v2.snapshot_digest(empty):
            raise ValueError("EMPTY_EXPLICIT_BOOTSTRAP_REQUIRED")
        if type(witness_public_pin) is not str or not re.fullmatch(r"[0-9a-f]{64}",witness_public_pin):
            raise ValueError("SEPARATE_PUBLIC_PIN_REQUIRED")
        super().__init__(scope=scope,initial_ledger_sha256=v2.snapshot_digest(initial_snapshot))
        self.initial_hash=self.ledger_head
        self.initial_policy=_policy(initial_policy)
        self.pin=witness_public_pin
        self.history=[]
        self.pending_request_digest=None

    def current_policy(self):
        with self.lock:
            return deepcopy({"generation":self.head["generation"],"digest":self.head["policy_sha256"]}
                            if self.head else self.initial_policy)

    def validate_history(self):
        with self.lock:
            if len(self.history)>v2._LIMIT or type(self.history) is not list:
                raise v2.ReferenceWitnessError("HISTORY_BOUND")
            prior_hash,prior_ledger,policy,states=ledger.GENESIS,self.initial_hash,self.initial_policy,{}
            used=set()
            for sequence,entry in enumerate(self.history,1):
                if type(entry) is not dict or set(entry)!={"envelope","request_digest"}:
                    raise v2.ReferenceWitnessError("HISTORY_INVALID")
                cp=_checkpoint(entry["envelope"]["checkpoint"])
                if (cp["phase"]!="CONFIRMED" or cp["checkpoint_sequence"]!=sequence
                        or {k:cp[k] for k in v2._SCOPE}!=self.scope
                        or cp["previous_checkpoint_sha256"]!=prior_hash
                        or cp["previous_ledger_sha256"]!=prior_ledger
                        or cp["previous_state"]!=states.get(cp["nonce"])
                        or cp["transaction_id"] in used
                        or not verify_checkpoint(entry["envelope"],pin=self.pin,expected=cp)
                        or type(entry["request_digest"]) is not str
                        or not v2._HEX.fullmatch(entry["request_digest"])
                        or cp["request_sha256"]!=entry["request_digest"]):
                    raise v2.ReferenceWitnessError("HISTORY_INTEGRITY_INVALID")
                candidate={"generation":cp["generation"],"digest":cp["policy_sha256"]}
                if (candidate["generation"]<policy["generation"]
                        or candidate["generation"]==policy["generation"] and candidate["digest"]!=policy["digest"]
                        or cp["operation"]!="CONSUME_CHALLENGE" and candidate!=policy):
                    raise v2.ReferenceWitnessError("HISTORY_POLICY_INVALID")
                states[cp["nonce"]]=cp["next_state"]
                used.add(cp["transaction_id"]);policy=candidate
                prior_hash,prior_ledger=checkpoint_digest(cp),cp["ledger_state_sha256"]
            expected_head=self.history[-1]["envelope"]["checkpoint"] if self.history else None
            if self.head!=expected_head or self.ledger_head!=prior_ledger or self.used!=used:
                raise v2.ReferenceWitnessError("WITNESS_HEAD_DIVERGENCE")
            if self.pending is not None:
                cp=_checkpoint(self.pending)
                if (cp["phase"]!="PREPARED" or cp["checkpoint_sequence"]!=len(self.history)+1
                        or cp["previous_checkpoint_sha256"]!=prior_hash
                        or cp["previous_ledger_sha256"]!=prior_ledger
                        or cp["transaction_id"] in used or {k:cp[k] for k in v2._SCOPE}!=self.scope
                        or self.pending_request_digest is None
                        or cp["request_sha256"]!=self.pending_request_digest):
                    raise v2.ReferenceWitnessError("PENDING_INTEGRITY_INVALID")
            elif self.pending_request_digest is not None:
                raise v2.ReferenceWitnessError("PENDING_ORPHAN")

    def expected_head(self):
        with self.lock:
            self.validate_history()
            return {"sequence":len(self.history),"digest":checkpoint_digest(self.head) if self.head else ledger.GENESIS}

    def prepare(self,*,before_snapshot,request):
        request=verify_request(request,self.scope)
        body=request["transition"]
        with self.lock:
            self.validate_history()
            if self.pending is not None or len(self.history)>=v2._LIMIT:
                raise v2.ReferenceWitnessError("SINGLE_PENDING_OR_BOUND")
            if (body["previous_ledger_sha256"]!=self.ledger_head
                    or v2.snapshot_digest(before_snapshot)!=self.ledger_head
                    or body["transaction_id"] in self.used):
                raise v2.ReferenceWitnessError("ROLLBACK_OR_REPLAY")
            target,after=_target(before_snapshot,operation=body["operation"],proposal=body["proposal"],
                nonce=body["nonce"],observed_at=body["observed_at"],issued_at=body["issued_at"],
                expires_at=body["expires_at"],current_policy=self.current_policy())
            head=self.expected_head()
            if (body["checkpoint_sequence"]!=head["sequence"]+1
                    or body["previous_checkpoint_sha256"]!=head["digest"]
                    or body["ledger_state_sha256"]!=v2.snapshot_digest(target)
                    or body["generation"]!=after["generation"] or body["policy_sha256"]!=after["digest"]):
                raise v2.ReferenceWitnessError("TARGET_NOT_RECOMPUTED")
            self.pending={**body,"checkpoint_schema":CHECKPOINT_SCHEMA,"phase":"PREPARED",
                          "request_sha256":request_digest(request)}
            self.pending_request_digest=request_digest(request)
            return deepcopy(self.pending)

    def matches_pending(self,candidate):
        with self.lock:
            self.validate_history()
            return self.pending==_checkpoint(candidate)

    def confirmation_candidate(self,*,request,ledger_state_sha256):
        request=verify_request(request,self.scope)
        with self.lock:
            self.validate_history()
            cp={**request["transition"],"checkpoint_schema":CHECKPOINT_SCHEMA,"phase":"CONFIRMED",
                "request_sha256":request_digest(request)}
            if cp["ledger_state_sha256"]!=ledger_state_sha256:
                raise v2.ReferenceWitnessError("LEDGER_DIVERGENCE")
            digest=request_digest(request)
            if self.pending is not None:
                if self.pending_request_digest!=digest or self.pending!={**cp,"phase":"PREPARED"}:
                    raise v2.ReferenceWitnessError("ORIGINAL_INTENT_REQUIRED")
            elif (self.head!=cp or not self.history or self.history[-1]["request_digest"]!=digest):
                raise v2.ReferenceWitnessError("NOT_LATEST_ORIGINAL_INTENT")
            return deepcopy(cp)

    def recover(self,*,request,ledger_state_sha256,envelope):
        with self.lock:
            cp=self.confirmation_candidate(request=request,ledger_state_sha256=ledger_state_sha256)
            if not verify_checkpoint(envelope,pin=self.pin,expected=cp):
                raise v2.ReferenceWitnessError("CONFIRM_SIGNATURE_INVALID")
            if self.pending is not None:
                digest=self.pending_request_digest
                # Reuse existing V2 monotonic reservation -> confirmed mutation.
                confirmed=super().confirm(transaction_id=cp["transaction_id"],
                                          ledger_state_sha256=ledger_state_sha256)
                if confirmed!=cp:raise v2.ReferenceWitnessError("CONFIRM_DIVERGENCE")
                self.history.append({"envelope":deepcopy(envelope),"request_digest":digest})
                self.pending_request_digest=None
            self.validate_history()
            return deepcopy(envelope)


def _result(reason,*,math=False,reserved=False,committed=False,checkpoint=False,matches=False,ticket=None,receipt=None):
    return {"schema":SCHEMA,"state":"REFERENCE_TRANSITION_CONFIRMED" if matches else "BLOCKED",
        "reason":reason,"transition_mathematically_verified":math,
        "transition_reserved_by_reference_witness":reserved,"sqlite_transition_committed":committed,
        "checkpoint_mathematically_verified":checkpoint,"reference_ledger_matches_witness":matches,
        "distributed_atomicity_verified":False,"exactly_once_external_execution_verified":False,
        "reference_only":True,"ticket":deepcopy(ticket),"receipt":deepcopy(receipt),**FALSE_GATES}


_ERRORS=(ValueError,TypeError,KeyError,OverflowError,RecursionError,OSError,sqlite3.Error,
         ledger.ReferenceStoreError,v2.ReferenceWitnessError)


class LifecycleAdapter:
    def __init__(self,*,store,witness,trusted_state,trusted_public_pin):
        if (type(store) is not ledger.ReferenceChallengeRegistry
                or type(trusted_state) is not LifecycleWitnessState):
            raise ValueError("EXACT_REFERENCE_TYPES_REQUIRED")
        if trusted_public_pin!=trusted_state.pin:
            raise ValueError("SEPARATE_PIN_MISMATCH")
        self.store,self.witness,self.state,self.pin=store,witness,trusted_state,trusted_public_pin

    def prepare(self,*,request):
        request=verify_request(request,self.state.scope)
        body=request["transition"]
        before=v2.ledger_snapshot(self.store)
        expected={**body,"checkpoint_schema":CHECKPOINT_SCHEMA,"phase":"PREPARED",
                  "request_sha256":request_digest(request)}
        ticket=self.witness.prepare(before_snapshot=before,request=request)
        if (not verify_checkpoint(ticket,pin=self.pin,expected=expected)
                or not self.state.matches_pending(expected)):
            raise v2.ReferenceWitnessError("LIVE_RESERVATION_REQUIRED")
        return deepcopy(ticket)

    def run(self,*,request):
        mathematical,reserved=False,False
        ticket=None
        try:
            request=verify_request(request,self.state.scope);mathematical=True
            ticket=self.prepare(request=request);reserved=True
            b=request["transition"];op=b["operation"]
            if op=="ISSUE_CHALLENGE":
                out=self.store.issue(proposal=b["proposal"],nonce=b["nonce"],
                    issued_at=b["issued_at"],expires_at=b["expires_at"])
                acknowledged=out["state"]=="ISSUED"
            elif op=="REVOKE_CHALLENGE":
                out=self.store.revoke(nonce=b["nonce"],now_ts=b["observed_at"])
                acknowledged=out["state"]=="REVOKED"
            else:
                out=self.store.consume(request=request["v1_request"],now_ts=b["observed_at"])
                acknowledged=(out["nonce_transaction_consumed"] if op=="CONSUME_CHALLENGE"
                              else out["reason"]=="CHALLENGE_EXPIRED")
            if not acknowledged:
                return _result("SQLITE_ACK_UNCERTAIN_SUPERVISED_RECOVERY",math=True,reserved=True,ticket=ticket)
            return self.recover(request=request,ticket=ticket)
        except _ERRORS:
            return _result("TRANSITION_BLOCKED_SUPERVISED_RECOVERY",math=mathematical,reserved=reserved,ticket=ticket)

    def recover(self,*,request,ticket):
        mathematical,reserved,committed=False,False,False
        try:
            request=verify_request(request,self.state.scope);mathematical=True
            body=request["transition"]
            prepared={**body,"checkpoint_schema":CHECKPOINT_SCHEMA,"phase":"PREPARED",
                      "request_sha256":request_digest(request)}
            if not verify_checkpoint(ticket,pin=self.pin,expected=prepared):
                raise v2.ReferenceWitnessError("ORIGINAL_SIGNED_PREPARE_REQUIRED")
            current=v2.snapshot_digest(v2.ledger_snapshot(self.store))
            expected=self.state.confirmation_candidate(request=request,ledger_state_sha256=current)
            reserved=True
            if current!=body["ledger_state_sha256"]:
                raise v2.ReferenceWitnessError("LEDGER_DIVERGENCE")
            committed=True
            envelope=self.witness.recover(request=request,ledger_state_sha256=current)
            verified=verify_checkpoint(envelope,pin=self.pin,expected=expected)
            head=self.state.expected_head()
            matches=verified and head=={"sequence":body["checkpoint_sequence"],"digest":checkpoint_digest(expected)}
            return _result("" if matches else "NOT_LATEST_CONFIRMED_WITNESS",math=True,
                reserved=True,committed=True,checkpoint=verified,matches=matches,ticket=ticket,
                receipt=v2._plain(envelope) if verified else None)
        except _ERRORS:
            return _result("RECOVERY_BLOCKED_NO_REPAIR_OR_FALLBACK",math=mathematical,
                           reserved=reserved,committed=committed,ticket=ticket)
