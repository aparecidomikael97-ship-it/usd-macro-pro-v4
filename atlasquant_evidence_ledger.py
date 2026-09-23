"""P0 immutable evidence-ledger contract.

Pure append semantics for DECISION / REJECTED_OPPORTUNITY / RESULT records.
No database driver and no broker/live execution.
"""
from __future__ import annotations
from typing import Any,Mapping,Sequence
import json,hashlib

VALID_TYPES={"DECISION","REJECTED_OPPORTUNITY","RESULT"}
VALID_ENVIRONMENTS={"BACKTEST","PAPER","LIVE"}

def _canon(row:Mapping[str,Any])->str:
    return json.dumps(dict(row),sort_keys=True,separators=(",",":"),default=str)

def _fingerprint(row:Mapping[str,Any])->str:
    return hashlib.sha256(_canon(row).encode()).hexdigest()

def validate_evidence_ledger(rows:Sequence[Mapping[str,Any]]|None)->dict[str,Any]:
    data=[dict(x) for x in (rows or [])]; reasons=[]; ids={}; result_by_decision={}
    for i,r in enumerate(data):
        prefix=f"ROW_{i}"
        rid=str(r.get("record_id","")).strip(); typ=str(r.get("record_type","")).upper(); env=str(r.get("environment","")).upper()
        if not rid: reasons.append(f"{prefix}:RECORD_ID_MISSING")
        else: ids.setdefault(rid,[]).append(r)
        if typ not in VALID_TYPES: reasons.append(f"{prefix}:RECORD_TYPE_INVALID")
        if env not in VALID_ENVIRONMENTS: reasons.append(f"{prefix}:ENVIRONMENT_INVALID")
        if r.get("immutable_evidence") is not True: reasons.append(f"{prefix}:IMMUTABLE_FLAG_INVALID")
        if typ=="RESULT":
            did=str(r.get("decision_record_id","")).strip()
            if not did: reasons.append(f"{prefix}:DECISION_LINK_MISSING")
            else: result_by_decision.setdefault(did,[]).append(r)
    for rid,group in ids.items():
        if len(group)>1:
            if len({_fingerprint(x) for x in group})==1: reasons.append(f"DUPLICATE_RECORD_ID:{rid}")
            else: reasons.append(f"CONFLICTING_RECORD_ID:{rid}")
    for did,group in result_by_decision.items():
        if len(group)>1: reasons.append(f"MULTIPLE_RESULTS_FOR_DECISION:{did}")
    idset=set(ids)
    for i,r in enumerate(data):
        if str(r.get("record_type","")).upper()=="RESULT":
            did=str(r.get("decision_record_id","")).strip()
            if did and did not in idset: reasons.append(f"ROW_{i}:ORPHAN_RESULT_DECISION")
    reasons=list(dict.fromkeys(reasons)); ok=not reasons
    return {"ok":ok,"state":"NORMAL" if ok else "PROTECTED","reasons":reasons,"row_count":len(data),
            "new_entries_allowed":ok,"management_allowed":True,"management_mode":"NORMAL" if ok else "SAFE_ONLY",
            "real_orders_enabled":False}

def append_evidence(existing:Sequence[Mapping[str,Any]]|None,record:Mapping[str,Any])->dict[str,Any]:
    rows=[dict(x) for x in (existing or [])]; r=dict(record or {})
    current=validate_evidence_ledger(rows)
    if not current["ok"]:
        return {"state":"RECOVERY_REQUIRED","appended":False,"ledger":rows,"reasons":current["reasons"],"real_orders_enabled":False}
    probe=validate_evidence_ledger([r])
    # A lone RESULT is expected to look orphaned until combined with its DECISION.
    fatal=[x for x in probe["reasons"] if "ORPHAN_RESULT_DECISION" not in x]
    if fatal:
        return {"state":"REJECTED","appended":False,"ledger":rows,"reasons":fatal,"real_orders_enabled":False}
    rid=str(r.get("record_id","")).strip()
    same=[x for x in rows if str(x.get("record_id","")).strip()==rid]
    if same:
        if _fingerprint(same[0])==_fingerprint(r):
            return {"state":"ALREADY_EXISTS","appended":False,"ledger":rows,"reasons":["IDEMPOTENCY_GUARD"],"real_orders_enabled":False}
        return {"state":"RECOVERY_REQUIRED","appended":False,"ledger":rows,"reasons":["CONFLICTING_RECORD_ID"],"real_orders_enabled":False}
    if str(r.get("record_type","")).upper()=="RESULT":
        did=str(r.get("decision_record_id","")).strip()
        parent=[x for x in rows if str(x.get("record_id","")).strip()==did and str(x.get("record_type","")).upper()=="DECISION"]
        if len(parent)!=1:
            return {"state":"REJECTED","appended":False,"ledger":rows,"reasons":["RESULT_PARENT_DECISION_NOT_UNIQUE"],"real_orders_enabled":False}
        prior=[x for x in rows if str(x.get("record_type","")).upper()=="RESULT" and str(x.get("decision_record_id","")).strip()==did]
        if prior:
            return {"state":"RECOVERY_REQUIRED","appended":False,"ledger":rows,"reasons":["MULTIPLE_RESULTS_FOR_DECISION"],"real_orders_enabled":False}
    candidate=rows+[r]; check=validate_evidence_ledger(candidate)
    if not check["ok"]:
        return {"state":"REJECTED","appended":False,"ledger":rows,"reasons":check["reasons"],"real_orders_enabled":False}
    return {"state":"APPENDED","appended":True,"ledger":candidate,"reasons":[],"real_orders_enabled":False}
