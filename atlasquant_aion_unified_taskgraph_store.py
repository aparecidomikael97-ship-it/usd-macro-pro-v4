"""Explicit local snapshots on the existing V2.1D journal; no auto resume."""
from __future__ import annotations

import base64
from aion_chat.models import Scope
from atlasquant_aion_unified_journal import new_request_journal, append_request_event
from atlasquant_aion_unified_taskgraph import (
    AionTaskgraphError, export_taskgraph, recover_taskgraph, MAX_DOCUMENT_BYTES,
)


def _scope(plan):
    return Scope(**{k:plan["scope"][k] for k in ("owner_id", "tenant_id", "workspace_id")})


def _storage_request(plan):
    # The established store scope has three dimensions; add ecosystem to request namespace.
    return "TG24:" + plan["scope"]["ecosystem"] + ":" + plan["request_id"]


def persist_taskgraph(store, plan):
    serialized = export_taskgraph(plan).encode()
    encoded = base64.b64encode(serialized).decode("ascii")
    chunks = [encoded[i:i+960] for i in range(0,len(encoded),960)]
    scope = _scope(plan)
    request_id = _storage_request(plan)
    try:
        previous = store.recover(scope=scope,request_id=request_id)
    except LookupError:
        previous = {"safe_to_resume":True}
    if not previous["safe_to_resume"]:
        raise AionTaskgraphError("STORE_RECOVERY_BLOCKED")
    journal = previous.get("journal") or new_request_journal(scope,request_id,plan["conversation_id"])
    events = journal.get("events",[])
    existing = [e for e in events if e["event_type"] == "TASKGRAPH_CHECKPOINT"]
    if existing:
        last = existing[-1]["metadata"]
        if last["mission_id"] != plan["mission_id"] or last["intent_digest"] != plan["intent_digest"]:
            raise AionTaskgraphError("SNAPSHOT_INTENT_MISMATCH")
        if last["revision"] > plan["revision"]:
            raise AionTaskgraphError("STALE_SNAPSHOT")
        if last["revision"] == plan["revision"]:
            if last["snapshot_digest"] != plan["plan_digest"]:
                raise AionTaskgraphError("SNAPSHOT_REVISION_CONFLICT")
            recover_persisted_taskgraph(store,plan_request=None,expected_plan=plan)
            return {"replay":True,"plan_digest":plan["plan_digest"],"execution_allowed":False}
    groups = [chunks[i:i+24] for i in range(0,len(chunks),24)]
    for index,group in enumerate(groups):
        journal = append_request_event(journal,event_type="TASKGRAPH_CHECKPOINT",
            selected_role="orchestrator",state=plan["mission_state"],observed_at=plan["created_at"],
            metadata={"snapshot_digest":plan["plan_digest"],"revision":plan["revision"],
                "mission_id":plan["mission_id"],"intent_digest":plan["intent_digest"],
                "group":index,"groups":len(groups),"chunks":group})
    for sequence in range(len(events)+1,len(journal["events"])+1):
        result = store.persist_event(journal,scope=scope,request_id=request_id,sequence=sequence,
            idempotency_key="TG24:"+plan["plan_digest"]+":"+str(sequence),origin="aion_taskgraph_explicit_local_snapshot")
    return {"replay":False,"plan_digest":plan["plan_digest"],"persistence_state":result["persistence_state"],"execution_allowed":False}


def recover_persisted_taskgraph(store, plan_request, *, ecosystem=None, access=None, expected_plan=None):
    if expected_plan is not None:
        scope = _scope(expected_plan); rid = _storage_request(expected_plan)
    else:
        from atlasquant_aion_unified_taskgraph import ecosystem_route
        code = ecosystem_route(ecosystem)
        scope = Scope(plan_request.owner_id,plan_request.tenant_id,plan_request.workspace_id)
        rid = "TG24:"+code+":"+plan_request.request_id
    recovered = store.recover(scope=scope,request_id=rid)
    if not recovered["safe_to_resume"]:
        raise AionTaskgraphError("STORE_RECOVERY_BLOCKED")
    events = [e for e in recovered["journal"]["events"] if e["event_type"]=="TASKGRAPH_CHECKPOINT"]
    if not events:
        raise AionTaskgraphError("SNAPSHOT_NOT_FOUND")
    latest = events[-1]["metadata"]
    selected = [e["metadata"] for e in events if e["metadata"]["snapshot_digest"]==latest["snapshot_digest"]]
    if [r["group"] for r in selected] != list(range(latest["groups"])) or any(r["groups"] != latest["groups"] or r["revision"] != latest["revision"] for r in selected):
        raise AionTaskgraphError("SNAPSHOT_INCOMPLETE")
    encoded = "".join(chunk for row in selected for chunk in row["chunks"])
    if len(encoded) > ((MAX_DOCUMENT_BYTES+2)//3)*4:
        raise AionTaskgraphError("RECOVERY_BOUND")
    try:
        serialized = base64.b64decode(encoded,validate=True).decode("utf-8")
    except (ValueError,UnicodeError):
        raise AionTaskgraphError("SNAPSHOT_ENCODING_INVALID") from None
    if expected_plan is not None:
        if serialized != export_taskgraph(expected_plan):
            raise AionTaskgraphError("SNAPSHOT_PAYLOAD_MISMATCH")
        return expected_plan
    return recover_taskgraph(serialized,plan_request,ecosystem=ecosystem,
        access=access,expected_digest=latest["snapshot_digest"])
