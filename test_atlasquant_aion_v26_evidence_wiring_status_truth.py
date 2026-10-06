"""Resident-flow and truth regression; no new collector or loader."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
import builtins
import pathlib
import socket
import subprocess
import pytest

from test_atlasquant_aion_v26_core_health_adapter import (
    evidence, build, snapshot, board, E, SCOPE, NOW,
)
from atlasquant_aion_core_health_adapter import build_loaded_runtime_health_evidence, HealthEvidenceError
from atlasquant_aion_memory import default_checkpoint, checkpoint_integrity_report
from atlasquant_aion_unified_runtime import AionRequest
from atlasquant_aion_unified_taskgraph import prepare_taskgraph
from atlasquant_aion_unified_mission import prepare_aion_mission


@pytest.mark.parametrize("verified,blocked,waiting,integrity,expected",[
    (True,0,0,"OK","CONFIRMED"), (False,0,0,"OK","UNKNOWN"),
    (True,0,1,"OK","BLOCKED"), (True,1,0,"OK","BLOCKED"),
    (False,0,1,"OK","BLOCKED"), (False,1,0,"OK","BLOCKED"),
    (True,0,0,"DEGRADED","BLOCKED"), (True,0,0,"UNKNOWN","UNKNOWN"),
])
def test_status_truth_matrix(verified,blocked,waiting,integrity,expected):
    p=build(**evidence())
    p.update(counts_verified=verified,blocked_missions=blocked,waiting_approval=waiting)
    if integrity=="DEGRADED":p["checkpoint_status"]="MISMATCH"
    if integrity=="UNKNOWN":p["journal_status"]="UNKNOWN"
    assert snapshot(p)["integrity_state"]==integrity
    assert board(p)["state"]==expected
    assert all(p[key] is False for key in ("external_action_executed","execution_allowed","executes_provider_call","executes_billing","real_orders_enabled"))


@pytest.mark.parametrize("available",[(),("checkpoint",),("journal","checkpoint")])
def test_partial_knowledge_never_confirms(available):
    args=evidence()
    for domain in ("journal","checkpoint","recovery","memory","audit_chain"):
        if domain not in available:args[domain+"_evidence"]=None
    p=build(**args)
    assert snapshot(p)["integrity_state"]=="UNKNOWN"
    assert board(p)["state"]=="UNKNOWN"


def test_bad_checkpoint_dominates_other_missing_domains():
    args=evidence(journal_evidence=None,recovery_evidence=None,memory_evidence=None,audit_chain_evidence=None)
    cp=deepcopy(args["checkpoint_evidence"].value);cp["head_digest"]="altered"
    args["checkpoint_evidence"]=replace(args["checkpoint_evidence"],value=cp)
    p=build(**args)
    assert snapshot(p)["integrity_state"]=="DEGRADED"
    assert board(p)["state"]=="BLOCKED"


def test_resident_sealed_taskgraph_can_be_counted_by_existing_adapter():
    request=AionRequest(conversation_id="c",owner_id="o",tenant_id="t",workspace_id="w",request_id="r",user_message="Explique um conceito",sector="TRADER")
    plan=prepare_taskgraph(request,task_specs=[{"key":"a","capability":"research"}])
    p=build(**evidence(mission_evidence=E("trusted/resident/tasks",[plan],"missions",SCOPE,True)))
    assert p["counts_verified"] is True
    assert p["pending_missions"]==1 and p["blocked_missions"]==1
    mutated=deepcopy(plan);mutated["mission_state"]="READY_FOR_GUARDED_HANDOFF"
    with pytest.raises(ValueError):
        build(**evidence(mission_evidence=E("trusted/resident/tasks",[mutated],"missions",SCOPE,True)))


def test_legacy_mission_does_not_certify_counters():
    request=AionRequest(conversation_id="c",owner_id="o",tenant_id="t",workspace_id="w",request_id="r",user_message="Explique um conceito",sector="TRADER")
    legacy=prepare_aion_mission(request)
    p=build(**evidence(mission_evidence=E("trusted/legacy",[legacy],"missions",SCOPE,True)))
    assert p["counts_verified"] is False
    assert p["pending_missions"]==0
    assert board(p)["state"]=="UNKNOWN"


def test_resident_journal_contract_and_cross_scope_without_store():
    args=evidence(recovery_evidence=None,memory_evidence=None)
    p=build(**args)
    assert p["journal_status"]=="VERIFIED" and p["audit_chain_status"]=="VERIFIED"
    assert snapshot(p)["integrity_state"]=="UNKNOWN"
    args["journal_evidence"]=replace(args["journal_evidence"],scope={**SCOPE,"tenant_id":"other"})
    with pytest.raises(HealthEvidenceError,match="CROSS_SCOPE"):
        build(**args)


@pytest.mark.parametrize("field",["operating","continuity","durable_tasks","aion","events","audit","request_journal","taskgraphs","memory_records","recovery_report","integrity"])
def test_extra_runtime_fields_are_not_canonical_health_authority(field):
    p=build_loaded_runtime_health_evidence({"status":"CONFIRMED","source":"trusted/already-loaded","checkpoint":default_checkpoint(),field:{"status":"VALIDATED","counts_verified":True,"blocked_missions":0}})
    assert p["checkpoint_status"]=="VERIFIED"
    assert all(p[d+"_status"]=="UNKNOWN" for d in ("journal","recovery","memory","audit_chain"))
    assert p["counts_verified"] is False
    assert board(p)["state"]=="UNKNOWN"


@pytest.mark.parametrize("domain",["recovery","memory"])
def test_absent_resident_domain_remains_unknown(domain):
    p=build_loaded_runtime_health_evidence({"status":"UNAVAILABLE","checkpoint":None})
    assert p[domain+"_status"]=="UNKNOWN"


@pytest.mark.parametrize("blocked,waiting",[(0,0),(1,0),(0,1)])
def test_unknown_counts_never_display_unproved_zero(blocked,waiting):
    p=build(**evidence(mission_evidence=None))
    p.update(blocked_missions=blocked,waiting_approval=waiting)
    item=board(p)
    assert "pendentes=não comprovado" in item["detail"]
    if not blocked and not waiting:
        assert "contadores" in item["next_action"]


@pytest.mark.parametrize("claims",[
    {},
    {"aion_core_health":{**{d+"_status":"OK" for d in ("journal","checkpoint","recovery","memory","audit_chain")},"integrity_state":"OK","execution_allowed":True,"counts_verified":True}},
    {"journal_status":"OK","memory_status":"VALIDATED","recovery_status":"RECOVERED","counts_verified":True,"blocked_missions":0},
    {"nested":{"system_context":{"aion_core_health":{"integrity_state":"OK","counts_verified":True}}},"aion":{"taskgraphs":[{"mission_state":"READY_FOR_GUARDED_HANDOFF"}]}},
])
def test_real_admin_boundary_same_loader_budget_and_no_extra_io(monkeypatch,claims):
    import requests
    import atlasquant_aion_admin as admin
    import atlasquant_aion_memory as memory
    import atlasquant_aion_provider as provider
    from atlasquant_aion_unified_journal_store import UnifiedJournalStore
    import atlasquant_aion_unified_taskgraph_store as taskgraph_store
    cp=default_checkpoint()
    assert checkpoint_integrity_report(cp)["state"]=="CONFIRMED"
    resident={"status":"CONFIRMED","source":"trusted/already-loaded","checkpoint":cp,"checked_at":NOW.isoformat()}
    before=deepcopy(resident);incoming=deepcopy(claims)
    calls={"runtime":0,"memory_summary":0,"accounts":0,"board":0}
    def forbidden(*args,**kwargs):raise AssertionError("extra IO/load forbidden")
    def loader(*args,**kwargs):calls["runtime"]+=1;return resident
    def summary(*args,**kwargs):calls["memory_summary"]+=1;return {"status":"CONFIRMED","document_count":12}
    def accounts(*args,**kwargs):calls["accounts"]+=1;return {}
    class BoundaryReached(BaseException):pass
    def capture(**kwargs):
        calls["board"]+=1
        p=kwargs["system_context"]["aion_core_health"]
        assert p["checkpoint_status"]=="VERIFIED"
        assert all(p[d+"_status"]=="UNKNOWN" for d in ("journal","recovery","memory","audit_chain"))
        assert p["counts_verified"] is False
        assert snapshot(p)["integrity_state"]=="UNKNOWN"
        assert p["execution_allowed"] is False
        raise BoundaryReached()
    monkeypatch.setattr(admin,"st",SimpleNamespace(session_state={},error=lambda *args:None))
    monkeypatch.setattr(admin,"_flag_overrides",lambda:{})
    monkeypatch.setattr(admin,"_provider_env",lambda:{})
    monkeypatch.setattr(admin,"provider_status",lambda **kwargs:{})
    monkeypatch.setattr(admin,"_runtime_config",lambda:None)
    monkeypatch.setattr(admin,"load_runtime_checkpoint",loader)
    monkeypatch.setattr(admin,"canonical_memory_summary",summary)
    monkeypatch.setattr(admin,"configured_users",accounts)
    monkeypatch.setattr(admin,"build_master_status_board",capture)
    monkeypatch.setattr(memory,"canonical_documents",forbidden)
    monkeypatch.setattr(builtins,"open",forbidden)
    monkeypatch.setattr(pathlib.Path,"open",forbidden)
    for name in ("mkdir","rename","replace","unlink","write_text","write_bytes","iterdir","glob","rglob"):
        monkeypatch.setattr(pathlib.Path,name,forbidden)
    monkeypatch.setattr(socket,"socket",forbidden)
    monkeypatch.setattr(subprocess,"Popen",forbidden)
    monkeypatch.setattr(requests,"get",forbidden)
    monkeypatch.setattr(requests,"post",forbidden)
    monkeypatch.setattr(UnifiedJournalStore,"__init__",forbidden)
    monkeypatch.setattr(UnifiedJournalStore,"recover",forbidden)
    monkeypatch.setattr(taskgraph_store,"persist_taskgraph",forbidden)
    monkeypatch.setattr(taskgraph_store,"recover_persisted_taskgraph",forbidden)
    monkeypatch.setattr(provider,"execute_openai_answer",forbidden)
    with pytest.raises(BoundaryReached):
        admin.render_aion_admin_console({"role":"ADMIN","username":"test"},system_context=claims)
    assert calls=={"runtime":1,"memory_summary":1,"accounts":1,"board":1}
    assert resident==before and claims==incoming


@pytest.mark.parametrize("field",["pending_missions","blocked_missions","waiting_approval"])
@pytest.mark.parametrize("invalid",[True,False,1.5,float("nan"),float("inf"),{},[]])
def test_invalid_counters_never_display_confirmed_zero(field,invalid):
    p=build(**evidence());p[field]=invalid
    item=board(p)
    assert item["state"]=="UNKNOWN"
    assert "pendentes=n\u00e3o comprovado" in item["detail"]


def test_forged_runtime_integrity_cannot_hide_raw_checkpoint_mismatch():
    cp=default_checkpoint();cp["operating"]["task_digest"]="corrupt"
    p=build_loaded_runtime_health_evidence({"status":"CONFIRMED","source":"resident","checkpoint":cp,"integrity":{"state":"CONFIRMED","write_safe":True}})
    assert p["checkpoint_status"]=="MISMATCH"
    assert snapshot(p)["integrity_state"]=="DEGRADED"
    assert board(p)["state"]=="BLOCKED"
