"""READ ONLY: resident canonical evidence -> existing Core health classifier.

LoadedEvidence is a trusted application boundary, not a client JSON envelope.
It asserts origin/completeness only; raw journal/checkpoint/memory still pass the
existing pure validators. This module has no loader, store, worker or executor.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import json
import math

from aion_chat.models import Scope
from atlasquant_aion_unified_journal import verify_request_journal, _digest as journal_digest
from atlasquant_aion_unified_journal_store import STORE_SCHEMA
from atlasquant_aion_checkpoint_master import reconstruct_checkpoint, SCHEMA as MASTER_SCHEMA
from atlasquant_aion_memory import checkpoint_integrity_report
from atlasquant_aion_memory_contract import (
    MemoryContractRecord, create_memory_record, operational_decision,
)
from atlasquant_aion_unified_taskgraph import validate_taskgraph, SCHEMA as TASKGRAPH_SCHEMA
from atlasquant_aion_truth import normalize_evidence_record, FUTURE_TOLERANCE_SECONDS
from atlasquant_aion_observability import core_health_snapshot, normalize_events, redact_text

SCHEMA = "ATLASQUANT_AION_CORE_HEALTH_EVIDENCE_V26"
MAX_BYTES = 2_000_000
MAX_ROWS = 64
INVARIANTS = {"health_snapshot_is_read_only":True,"external_action_executed":False,
    "execution_allowed":False,"executes_provider_call":False,"executes_billing":False,
    "real_orders_enabled":False}
_SCOPE_NAMES = {"owner_id":"owner_id","tenant_id":"tenant_id","workspace_id":"workspace_id",
    "ecosystem":"ecosystem","ecosystem_id":"ecosystem","sector":"sector",
    "sector_id":"sector","project":"project","project_id":"project","request_id":"request_id"}
_RECOVERY_FLAGS = ("scope_valid","request_valid","version_accepted","chain_valid",
    "head_consistent","idempotency_consistent","ack_consistent","quarantine_clear",
    "deterministic_recovery","safe_to_resume")


class HealthEvidenceError(ValueError):
    """Bounded, malformed or mixed-scope resident evidence."""


@dataclass(frozen=True)
class LoadedEvidence:
    """Construct in trusted code from resident inputs, never deserialize client claims.

    kind: journal, checkpoint_master, checkpoint_legacy, recovery_report,
    memory_records, missions. scope is source provenance, not inferred identity.
    complete=True means the caller loaded the entire represented view.
    temporal is an existing component freshness record; no TTL is supplied here.
    """
    source_ref: str
    value: object
    kind: str
    scope: dict = field(default_factory=dict)
    complete: bool = False
    temporal: dict = field(default_factory=dict)
    as_of: str = ""


def _bounded(value, depth=0, budget=None):
    budget=[0,0] if budget is None else budget
    budget[0]+=1
    if budget[0]>20_000:
        raise HealthEvidenceError("NODE_BOUND")
    if depth > 24:
        raise HealthEvidenceError("DEPTH_BOUND")
    if value is None or type(value) is bool:
        return value
    if type(value) in (int,float):
        if not math.isfinite(value) or abs(value)>1e18:
            raise HealthEvidenceError("NUMBER_INVALID")
        return value
    if type(value) is str:
        budget[1]+=len(value)
        if budget[1]>MAX_BYTES:
            raise HealthEvidenceError("DOCUMENT_BOUND")
        if len(value)>16_000 or "\x00" in value:
            raise HealthEvidenceError("STRING_BOUND")
        return value
    if type(value) in (list,tuple):
        if len(value)>256:
            raise HealthEvidenceError("ROWS_BOUND")
        return [_bounded(v,depth+1,budget) for v in value]
    if type(value) is dict:
        if len(value)>128 or any(type(k) is not str for k in value):
            raise HealthEvidenceError("MAPPING_BOUND")
        return {_bounded(k,depth+1,budget):_bounded(v,depth+1,budget) for k,v in value.items()}
    raise HealthEvidenceError("PLAIN_RESIDENT_DATA_REQUIRED")


def _checked(value):
    row=_bounded(value)
    if len(json.dumps(row,ensure_ascii=True,allow_nan=False).encode())>MAX_BYTES:
        raise HealthEvidenceError("DOCUMENT_BOUND")
    return row


def _scope(raw):
    if type(raw) is not dict:
        raise HealthEvidenceError("SCOPE_INVALID")
    result={}
    for key,name in _SCOPE_NAMES.items():
        if key not in raw:
            continue
        value=raw[key]
        if value is None or (type(value) is str and value==""):
            continue
        if type(value) is not str or len(value)>160 or value!=value.strip():
            raise HealthEvidenceError("SCOPE_INVALID")
        if name in result and result[name]!=value:
            raise HealthEvidenceError("SCOPE_ALIAS_MISMATCH")
        result[name]=value
    return result


def _bind_scope(known, raw):
    for key,value in _scope(raw).items():
        if key in known and known[key]!=value:
            raise HealthEvidenceError("CROSS_SCOPE:"+key)
        known[key]=value


def _bad_status(value):
    # Reuse the classifier's negative vocabulary; no parallel health state table.
    status=redact_text(value).strip()[:80]
    return status if core_health_snapshot(journal_status=status)["integrity_state"]=="DEGRADED" else "UNKNOWN"


def _timeliness(evidence, now):
    temporal=_checked(evidence.temporal)
    if type(temporal) is not dict:
        raise HealthEvidenceError("TEMPORAL_MAPPING_REQUIRED")
    if not temporal:
        return "NOT_EVALUATED"
    if temporal.get("stale") is True or temporal.get("freshness") in {"STALE","OUTDATED"}:
        return "STALE"
    # A precomputed claim of FRESH alone is not proof. Use existing truth semantics.
    if now is None:
        return "UNVERIFIED"
    # Timestamp and TTL types must not be rescued by coercion or expiry claims.
    observed=None
    for key in ("timestamp","as_of"):
        if key in temporal:
            value=temporal[key]
            if type(value) is not str or not value.strip():
                return "UNVERIFIED"
            try:
                stamp=datetime.fromisoformat(value.replace("Z","+00:00"))
            except ValueError:
                return "UNVERIFIED"
            if stamp.tzinfo is None:
                return "UNVERIFIED"
            if (stamp-now).total_seconds()>FUTURE_TOLERANCE_SECONDS:
                return "UNVERIFIED"
            if observed is not None and observed!=stamp:
                return "UNVERIFIED"
            observed=stamp
    for key in ("ttl","ttl_seconds"):
        if key in temporal:
            ttl=temporal[key]
            if type(ttl) not in (int,float) or not math.isfinite(ttl) or ttl<0:
                return "UNVERIFIED"
    if "expires_at" in temporal:
        if type(temporal["expires_at"]) is not str or not temporal["expires_at"].strip():
            return "UNVERIFIED"
        try:
            expiry=datetime.fromisoformat(temporal["expires_at"].replace("Z","+00:00"))
            if expiry.tzinfo is None:
                return "UNVERIFIED"
            if observed is not None and expiry<observed:
                return "UNVERIFIED"
            return "STALE" if now>=expiry else "FRESH"
        except (TypeError,ValueError):
            return "UNVERIFIED"
    record={**temporal,"source":evidence.source_ref,"truth_state":"CONFIRMED"}
    if "timestamp" not in record and record.get("as_of"):
        record["timestamp"]=record["as_of"]
    if "ttl_seconds" not in record and "ttl" in record:
        record["ttl_seconds"]=record["ttl"]
    return normalize_evidence_record(record,now=now)["freshness"]


def _journal(value, known):
    if type(value) is not dict:
        return "INVALID",{}
    _bind_scope(known,value)
    required=("owner_id","tenant_id","workspace_id","request_id")
    if not all(value.get(k) and known.get(k)==value[k] for k in required):
        return "UNKNOWN",{}
    report=verify_request_journal(value,scope=Scope(**{k:known[k] for k in required[:3]}),request_id=known["request_id"])
    return ("VERIFIED" if report["valid"] is True else "MISMATCH"),report


def _memory(records, known):
    if type(records) not in (tuple,list) or not records:
        return "UNKNOWN",{}
    if len(records)>MAX_ROWS:
        raise HealthEvidenceError("MEMORY_ROWS_BOUND")
    statuses=[]; revisions=[]
    for record in records:
        if type(record) is not MemoryContractRecord:
            statuses.append("UNKNOWN")
            continue
        raw=_checked(vars(record))
        _bind_scope(known,raw["scope"])
        if type(raw.get("created_at")) is not str or not raw["created_at"].strip():
            statuses.append("UNKNOWN")
            continue
        recreated=create_memory_record(**{k:raw[k] for k in (
            "namespace","memory_class","content","scope","provenance_ids","version",
            "previous_version","evidence_refs","validation_state","retention","sensitivity",
            "rollback_pointer","tombstone","created_at","metadata")})
        if recreated.memory_id!=record.memory_id:
            return "MISMATCH",{}
        decision=operational_decision(recreated)
        state=record.validation_state
        if state=="CONFLICTING": statuses.append("CONFLICTING_MISMATCH")
        elif state=="REJECTED" or record.tombstone is True: statuses.append("REJECTED_INVALID")
        elif state=="QUARANTINED": statuses.append(state)
        elif state=="OUTDATED": statuses.append("OUTDATED")
        elif decision["allowed_for_operational_use"] is True: statuses.append("VALIDATED")
        else: statuses.append("UNKNOWN")
        revisions.append(record.version)
    failure=next((s for s in statuses if _bad_status(s)!="UNKNOWN"),None)
    return failure or ("VALIDATED" if all(s=="VALIDATED" for s in statuses) else next(s for s in statuses if s!="VALIDATED")),{"revision":max(revisions) if revisions else 0,"record_states":statuses}


def _domain(evidence, domain, known, now):
    meta={"source_ref":"","evidence_complete":False,"freshness":"NOT_EVALUATED"}
    if type(evidence) is not LoadedEvidence:
        return "UNKNOWN",meta
    if type(evidence.source_ref) is not str or type(evidence.kind) is not str or type(evidence.as_of) is not str:
        return "UNKNOWN",meta
    source=redact_text(evidence.source_ref).strip()[:240]
    meta.update(source_ref=source,as_of=redact_text(evidence.as_of)[:80] if type(evidence.as_of) is str else "")
    if type(evidence.source_ref) is not str or len(evidence.source_ref)>240 or not source:
        return "UNKNOWN",meta
    _bind_scope(known,evidence.scope)
    if evidence.value is None:
        return "UNKNOWN",meta
    try:
        if domain=="memory" and evidence.kind=="memory_records":
            status,report=_memory(evidence.value,known)
        else:
            value=_checked(evidence.value)
            if type(value) is dict:
                _bind_scope(known,value)
                if "scope" in value: _bind_scope(known,value["scope"])
            if domain in {"journal","audit_chain"} and evidence.kind=="journal":
                status,report=_journal(value,known)
            elif domain=="checkpoint" and evidence.kind=="checkpoint_master":
                if type(value) is not dict or value.get("schema")!=MASTER_SCHEMA:
                    status,report=("UNKNOWN" if type(value) is dict and "schema" not in value else "INVALID"),{}
                else:
                    report=reconstruct_checkpoint(value)
                    status="VERIFIED" if (report.get("schema")==MASTER_SCHEMA and type(report.get("revision")) is int and report.get("state_digest") and report.get("execution_allowed") is False) else "UNKNOWN"
            elif domain=="checkpoint" and evidence.kind=="checkpoint_legacy":
                report=checkpoint_integrity_report(value)
                status="VERIFIED" if report.get("state")=="CONFIRMED" and report.get("write_safe") is True and report.get("checks") else _bad_status(report.get("state"))
            elif domain=="recovery" and evidence.kind=="recovery_report" and type(value) is dict:
                report=value
                if report.get("schema")!=STORE_SCHEMA:
                    status="UNKNOWN"
                elif all(known.get(k) for k in ("owner_id","tenant_id","workspace_id")) and report.get("scope_fingerprint") and report["scope_fingerprint"]!=journal_digest({k:known[k] for k in ("owner_id","tenant_id","workspace_id")}):
                    status="MISMATCH"
                elif any(report.get(k) is not False for k in ("execution_allowed","executes_provider_call","executes_billing","real_orders_enabled","automatic_resume_executes") if k in report):
                    status="UNSAFE"
                elif any(report.get(k) is False for k in _RECOVERY_FLAGS) or report.get("hard_failures") or report.get("quarantine_pending_count",0):
                    status="UNSAFE"
                elif report.get("status")=="RECOVERED" and all(report.get(k) is True for k in _RECOVERY_FLAGS) and report.get("restores_state_only") is True and report.get("external_action_executed") is False and report.get("scope_fingerprint") and all(known.get(k) for k in ("owner_id","tenant_id","workspace_id")):
                    # A receipt claim must carry the actual canonical journal it reports.
                    status,logical=_journal(report.get("journal"),known) if type(report.get("journal")) is dict else ("UNKNOWN",{})
                    if status=="VERIFIED":
                        for key in ("revision","head_digest"):
                            if key in report and (type(report[key]) is not type(logical.get(key)) or report[key]!=logical.get(key)):
                                status="MISMATCH"
                                break
                else: status=_bad_status(report.get("status"))
            else:
                status,report="UNKNOWN",{}
        meta.update({k:report[k] for k in ("revision","head_digest","state_digest","record_states") if k in report})
        freshness=_timeliness(evidence,now)
        meta.update(freshness=freshness,evidence_complete=evidence.complete is True)
        if _bad_status(status)=="UNKNOWN":
            if evidence.complete is not True: status="UNKNOWN"
            elif freshness=="STALE": status="STALE"
            elif freshness=="UNVERIFIED": status="UNKNOWN"
        return status,meta
    except HealthEvidenceError:
        raise
    except (ValueError,TypeError,KeyError,OverflowError,RecursionError):
        # A supplied canonical structure failing its pure integrity validator is bad evidence.
        return "INVALID",meta


def _mission_counts(evidence, known):
    counts={"pending_missions":0,"blocked_missions":0,"waiting_approval":0,"ready_handoffs":0}
    if type(evidence) is not LoadedEvidence or type(evidence.kind) is not str or evidence.kind!="missions" or evidence.complete is not True or type(evidence.source_ref) is not str or not evidence.source_ref.strip() or len(evidence.source_ref)>240:
        return counts,False
    own_scope=_scope(evidence.scope)
    if not all(own_scope.get(k) for k in ("owner_id","tenant_id","workspace_id")):
        return counts,False
    _bind_scope(known,evidence.scope)
    values=_checked(evidence.value)
    if type(values) is not list or len(values)>MAX_ROWS:
        raise HealthEvidenceError("MISSIONS_BOUND_OR_TYPE")
    seen=set()
    for value in values:
        if type(value) is not dict:
            raise HealthEvidenceError("MISSION_INVALID")
        _bind_scope(known,value.get("scope",{}))
        if value.get("schema")==TASKGRAPH_SCHEMA:
            validate_taskgraph(value)
        else:
            # V2.2 mission digest does not bind mission_state: cannot certify counters.
            return counts,False
        mission_id=value.get("mission_id")
        if mission_id in seen: raise HealthEvidenceError("DUPLICATE_MISSION")
        seen.add(mission_id)
        state=value.get("mission_state")
        if state not in {"PREPARED","WAITING_EVIDENCE","WAITING_APPROVAL","BLOCKED","READY_FOR_GUARDED_HANDOFF"}:
            raise HealthEvidenceError("MISSION_STATE_INVALID")
        counts["pending_missions"]+=1
        counts["blocked_missions"]+=int(state=="BLOCKED")
        counts["waiting_approval"]+=int(state=="WAITING_APPROVAL")
        counts["ready_handoffs"]+=int(state=="READY_FOR_GUARDED_HANDOFF")
    return counts,True


def build_core_health_evidence(*, journal_evidence=None,checkpoint_evidence=None,
        recovery_evidence=None,memory_evidence=None,audit_chain_evidence=None,
        mission_evidence=None,events=(),core_version="",schema_version="",now=None,expected_scope=None):
    """Return board-compatible payload plus provenance; never return raw resident data.

    Absence/JSON claims remain UNKNOWN. Callers own authenticated provenance.
    Time-dependent evidence requires explicit aware now for deterministic checks.
    """
    if now is not None and (type(now) is not datetime or now.tzinfo is None):
        raise HealthEvidenceError("AWARE_NOW_REQUIRED")
    known=_scope({} if expected_scope is None else expected_scope)
    payload={"core_version":redact_text(core_version)[:80] if type(core_version) is str else "",
        "schema_version":redact_text(schema_version)[:80] if type(schema_version) is str else ""}
    provenance={}
    for domain,evidence in (("journal",journal_evidence),("checkpoint",checkpoint_evidence),
            ("recovery",recovery_evidence),("memory",memory_evidence),("audit_chain",audit_chain_evidence)):
        status,meta=_domain(evidence,domain,known,now)
        payload[domain+"_status"]=status;provenance[domain]=meta
    j=provenance["journal"];a=provenance["audit_chain"]
    if j.get("head_digest") and a.get("head_digest") and (j["head_digest"]!=a["head_digest"] or j.get("revision")!=a.get("revision")):
        payload["audit_chain_status"]="MISMATCH"
    counts,verified=_mission_counts(mission_evidence,known)
    counts_freshness=_timeliness(mission_evidence,now) if verified else "NOT_EVALUATED"
    verified=verified and counts_freshness not in {"STALE","UNVERIFIED"}
    payload.update(counts,counts_verified=verified)
    payload["last_recovery"]=provenance["recovery"].get("as_of","")
    payload["last_checkpoint"]=provenance["checkpoint"].get("as_of","")
    rows=_checked(events)
    if type(rows) is not list or len(rows)>MAX_ROWS:
        raise HealthEvidenceError("EVENTS_BOUND_OR_TYPE")
    # Never generate wall-clock event timestamps from incomplete display events.
    supplied=[r for r in rows if type(r) is dict and type(r.get("created_at")) is str and r["created_at"].strip()]
    payload["events"]=normalize_events(supplied)
    payload["evidence_complete"]=all(p["evidence_complete"] is True for p in provenance.values())
    payload["provenance"]={"schema":SCHEMA,"domains":provenance,"scope":known,
        "as_of":now.isoformat() if now else "","counts_freshness":counts_freshness,"counts_source_ref":redact_text(mission_evidence.source_ref)[:240] if type(mission_evidence) is LoadedEvidence and type(mission_evidence.source_ref) is str else ""}
    payload.update(INVARIANTS)
    return payload


def build_loaded_runtime_health_evidence(runtime_result):
    """Connect only the existing resident runtime checkpoint; do not use normalized seed."""
    runtime=runtime_result if type(runtime_result) is dict else {}
    checkpoint=None
    if runtime.get("status")=="CONFIRMED" and type(runtime.get("checkpoint")) is dict and runtime.get("source"):
        checkpoint=LoadedEvidence(source_ref=runtime["source"],value=runtime["checkpoint"],
            kind="checkpoint_legacy",complete=True,as_of=runtime.get("checked_at",""))
    try:
        payload=build_core_health_evidence(checkpoint_evidence=checkpoint)
        if checkpoint is None and type(runtime.get("status")) is str:
            payload["checkpoint_status"]=_bad_status(runtime["status"])
        return payload
    except HealthEvidenceError as exc:
        payload=build_core_health_evidence()
        payload["checkpoint_status"]="INVALID"
        payload["provenance"]["checkpoint_error"]=str(exc)[:120]
        return payload
