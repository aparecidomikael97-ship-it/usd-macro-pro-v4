"""V2.4 adversarial contracts: local planning, never an executor."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
import pytest

from atlasquant_aion_unified_runtime import AionRequest
from atlasquant_aion_role_authority import official_role_authority_matrix
import atlasquant_aion_unified_taskgraph as tg
from atlasquant_aion_unified_taskgraph_store import persist_taskgraph, recover_persisted_taskgraph
from atlasquant_aion_unified_journal_store import UnifiedJournalStore

NOW = datetime.now(timezone.utc)
ACCESS = {"role":"ADMIN","memory":True,"wisdom":True}
REFS = ("objective","canonical_memory","wisdom_journal","runtime_checkpoint","expected_sha","integrity","provider_ready","pricing","budget")


def request(ecosystem="TRADER", **changes):
    evidence = tuple({"ref":ref,"claim":ref,"value":"fixture only","source":"test-owner",
        "truth_state":"CONFIRMED","time_sensitive":False,"ecosystem":ecosystem,
        "owner_id":"o","tenant_id":"t","workspace_id":"w"} for ref in REFS)
    values = dict(conversation_id="c",owner_id="o",tenant_id="t",workspace_id="w",
        user_message="Explique um conceito",request_id="r",sector=ecosystem,evidence=evidence)
    values.update(changes)
    return AionRequest(**values)


def spec(key="a",capability="research",**values):
    return dict(key=key,capability=capability,evidence_required=["objective"],**values)


def plan(specs=None, req=None, **options):
    return tg.prepare_taskgraph(req or request(),access=ACCESS,task_specs=specs or [spec()],now=NOW,**options)


def move(p,key,target,**options):
    task = next(t for t in p["tasks"] if t["key"]==key)
    return tg.transition_task(p,task["task_id"],target,expected_revision=p["revision"],now=NOW,**options)


def ready(p,key="a"):
    task = next(t for t in p["tasks"] if t["key"]==key)
    if task["approval_required"]:
        p = tg.approve_task(p,task["task_id"],approved=True,approved_scope=p["scope"],expected_revision=p["revision"],now=NOW)
    p = move(p,key,"QUEUED")
    return move(p,key,"RUNNABLE")


def safety(p):
    assert tg.validate_taskgraph(p)["valid"] is True
    for row in [p,*p["tasks"],*p["audit"],*p["handoffs"]]:
        assert all(row[k] is False for k in tg.INVARIANTS)


@pytest.mark.parametrize("cap,role",[("coordenacao","orchestrator"),("arquitetura","architect"),("auditoria","guardian"),("execucao","prime"),("pesquisa","shadow"),("monitoramento","sentinel"),("lead","commercial"),("treinamento","educator")])
def test_eight_roles_system_routing(cap,role):
    assert tg.route_task_role(cap,"NEGÓCIOS")["role"]==role
    rows = official_role_authority_matrix()["roles"]
    assert len(rows)==8
    for row in rows:
        assert set(("role","capabilities","allowed_inputs","allowed_outputs","forbidden_actions","requires_approval","escalation_target","audit_requirements")) <= row.keys()


def test_client_role_and_policy_forgery_ignored():
    p = plan([spec(role="prime",risk="NONE",approved=True,approval_required=False)],
        req=request(authorization_context={"role":"ADMIN","approved":True},source_context={"role":"prime","execution_allowed":True}))
    task = p["tasks"][0]
    assert task["role"]=="shadow" and task["approved"] is False
    without_access = tg.prepare_taskgraph(request(authorization_context={"role":"ADMIN"}),task_specs=[spec()])
    assert without_access["base_mission"]["blockers"]
    safety(p)


def test_stable_ids_graph_and_duplicate_request():
    specs=[spec("b",depends_on=["a"]),spec("a")]
    p=plan(specs); q=plan(list(reversed(specs)))
    assert p["intent_digest"]==q["intent_digest"]
    assert p["tasks"]==q["tasks"] and p["graph"]==q["graph"]
    assert tg.prepare_taskgraph(request(),access=ACCESS,task_specs=specs,prior_plan=p)==p


@pytest.mark.parametrize("specs,code",[([spec(),spec()],"DUPLICATE_TASK"),([spec(depends_on=["missing"])],"MISSING_DEPENDENCY"),([spec("a",depends_on=["b"]),spec("b",depends_on=["a"])],"DEPENDENCY_CYCLE"),([spec(depends_on=["a"])],"DEPENDENCY_CYCLE"),([spec(depends_on=["b","b"]),spec("b")],"DUPLICATE_REFERENCE")])
def test_bad_graph(specs,code):
    with pytest.raises(tg.AionTaskgraphError,match=code): plan(specs)


@pytest.mark.parametrize("terminal",["FAILED","BLOCKED","CANCELLED","SUPERSEDED"])
def test_dependency_terminal_blockers(terminal):
    p=plan([spec("a"),spec("b",depends_on=["a"])])
    p=ready(p)
    p=move(p,"a",terminal,reason="test local failure")
    assert "DEPENDENCY_"+terminal+":a" in tg.evaluate_taskgraph(p)[1]["blockers"]
    p=move(p,"b","QUEUED")
    with pytest.raises(tg.AionTaskgraphError,match="GATES"): move(p,"b","RUNNABLE")


def test_dependency_completion_and_local_output():
    p=plan([spec("a"),spec("b",depends_on=["a"])])
    p=move(p,"b","QUEUED");p=move(p,"b","WAITING_DEPENDENCY")
    with pytest.raises(tg.AionTaskgraphError,match="GATES"): move(p,"b","RUNNABLE")
    p=ready(p);p=move(p,"a","COMPLETED",output={"summary":"local research supplied"})
    p=move(p,"b","RUNNABLE")
    assert p["tasks"][0]["output"]["summary"]=="local research supplied"
    safety(p)


@pytest.mark.parametrize("target",["EXECUTED","RUNNING","RUNNABLE","COMPLETED","FAILED","WAITING_APPROVAL"])
def test_no_illegal_planned_transition(target):
    with pytest.raises(tg.AionTaskgraphError,match="INVALID_TRANSITION"): move(plan(),"a",target)


@pytest.mark.parametrize("approved",[False,"true","yes","approved",1,0,None,{},[]])
def test_exact_boolean_approval(approved):
    p=plan()
    with pytest.raises(tg.AionTaskgraphError,match="EXACT_APPROVAL"):
        tg.approve_task(p,p["tasks"][0]["task_id"],approved=approved,approved_scope=p["scope"],expected_revision=p["revision"])


def test_approval_binding_payload_scope_and_action():
    p=plan([spec(capability="provider_calls")],feature_flags={"provider_calls":True})
    task=p["tasks"][0]
    p=tg.approve_task(p,task["task_id"],approved=True,approved_scope=p["scope"],expected_revision=0,now=NOW)
    assert p["tasks"][0]["approved"] is True
    assert tg.approve_task(p,task["task_id"],approved=True,approved_scope=p["scope"],expected_revision=1)==p
    changed=deepcopy(p);changed["tasks"][0]["payload"]={"action":"other"};changed["tasks"][0]["payload_digest"]=tg._digest(changed["tasks"][0]["payload"]);tg._seal(changed)
    with pytest.raises(tg.AionTaskgraphError): tg.validate_taskgraph(changed)
    with pytest.raises(tg.AionTaskgraphError,match="APPROVED_SCOPE"):
        tg.approve_task(plan(),task["task_id"],approved=True,approved_scope={"owner_id":"other"},expected_revision=0)
    with pytest.raises(tg.AionTaskgraphError,match="PAYLOAD_MISMATCH"):
        tg.prepare_taskgraph(request(),access=ACCESS,task_specs=[spec(capability="calendar_write")],prior_plan=p)


@pytest.mark.parametrize("flag",tg.DANGEROUS_FLAGS)
def test_future_flags_disabled_and_external_completion_forbidden(flag):
    eco="TRADER" if flag in {"real_orders","broker_execution"} else "NEGOCIOS"
    p=plan([spec(capability=flag)],req=request(eco))
    assert all(v is False for v in p["feature_flags"].values())
    assert "FEATURE_DISABLED:"+flag in tg.evaluate_taskgraph(p)[0]["blockers"]
    p=plan([spec(capability=flag)],req=request(eco),feature_flags={flag:True})
    p=ready(p)
    with pytest.raises(tg.AionTaskgraphError,match="EXTERNAL_COMPLETION"):move(p,"a","COMPLETED",output={"done":True})
    h=tg.prepare_guarded_task_handoff(p,p["tasks"][0]["task_id"],expected_revision=p["revision"],now=NOW)
    assert h["handoff"]["approval_state"]=="APPROVED_BOUND"
    safety(h["plan"])


@pytest.mark.parametrize("mode,paid,cost,limit,blocked",[("ZERO_COST_LOCAL",False,0,0,False),("ZERO_COST_LOCAL",False,1,0,True),("FREE_TIER",False,0,0,False),("FREE_TIER",False,1,0,True),("PAID_ALLOWED",False,1,10,True),("PAID_ALLOWED",True,1,10,False),("PAID_ALLOWED",True,11,10,True),("PAID_BLOCKED",True,0,10,True)])
def test_budget_estimates_never_charge(mode,paid,cost,limit,blocked):
    p=plan([spec(estimated_cost=cost)],budget={"mode":mode,"paid_authorized":paid,"authorized_limit":limit})
    assert ("PAID_BLOCKED" in tg.evaluate_taskgraph(p)[0]["blockers"]) is blocked
    assert p["budget"]["billing_executed"] is False
    safety(p)


def test_handoff_idempotency_and_stop():
    p=ready(plan());tid=p["tasks"][0]["task_id"]
    first=tg.prepare_guarded_task_handoff(p,tid,expected_revision=p["revision"],now=NOW)
    repeat=tg.prepare_guarded_task_handoff(first["plan"],tid,expected_revision=first["plan"]["revision"])
    assert repeat["replay"] is True and repeat["plan"]==first["plan"]
    assert repeat["handoff"]==first["handoff"]
    assert first["plan"]["mission_state"]=="READY_FOR_GUARDED_HANDOFF"
    assert first["plan"]["tasks"][0]["state"]=="RUNNABLE"
    safety(first["plan"])


def test_expired_evidence_blocks_even_handoff_replay():
    req=request();records=list(req.evidence)
    records[0]={**records[0],"time_sensitive":True,"timestamp":NOW.isoformat(),"ttl_seconds":3600}
    p=ready(plan(req=replace(req,evidence=tuple(records))))
    h=tg.prepare_guarded_task_handoff(p,p["tasks"][0]["task_id"],expected_revision=p["revision"],now=NOW)
    later=NOW+timedelta(hours=2)
    assert "MISSING_EVIDENCE" in tg.evaluate_taskgraph(h["plan"],now=later)[0]["blockers"]
    with pytest.raises(tg.AionTaskgraphError,match="HANDOFF_GATES"):
        tg.prepare_guarded_task_handoff(h["plan"],p["tasks"][0]["task_id"],expected_revision=h["plan"]["revision"],now=later)


@pytest.mark.parametrize("field,value",[("owner_id","x"),("tenant_id","x"),("workspace_id","x"),("ecosystem","NEGOCIOS")])
def test_cross_scope_evidence_rejected(field,value):
    req=request();ev=list(req.evidence);ev[0]={**ev[0],field:value}
    with pytest.raises(tg.AionTaskgraphError,match="EVIDENCE_.*MISMATCH"): plan(req=replace(req,evidence=tuple(ev)))


@pytest.mark.parametrize("eco",tg.ECOSYSTEMS)
def test_ecosystems_recovery_isolation(eco):
    req=request(eco);p=plan(req=req)
    assert tg.recover_taskgraph(tg.export_taskgraph(p),req,ecosystem=eco,access=ACCESS,expected_digest=p["plan_digest"])==p
    wrong="NEGOCIOS" if eco!="NEGOCIOS" else "TRADER"
    with pytest.raises(tg.AionTaskgraphError):tg.recover_taskgraph(tg.export_taskgraph(p),request(wrong),ecosystem=wrong,access=ACCESS,expected_digest=p["plan_digest"])


@pytest.mark.parametrize("state",["PLANNED","WAITING_DEPENDENCY","WAITING_APPROVAL","BLOCKED","FAILED","CANCELLED","SUPERSEDED","COMPLETED","RUNNABLE","QUEUED"])
def test_recovery_preserves_every_task_state(tmp_path,state):
    specs=[spec("a",capability="provider_calls"),spec("b",depends_on=["a"])] if state in {"WAITING_APPROVAL","WAITING_DEPENDENCY"} else [spec()]
    p=plan(specs,feature_flags={"provider_calls":True})
    key="b" if state=="WAITING_DEPENDENCY" else "a"
    if state in {"RUNNABLE","COMPLETED","FAILED"}:p=ready(p,key)
    elif state not in {"PLANNED","CANCELLED","SUPERSEDED"}:p=move(p,key,"QUEUED")
    if state not in {"PLANNED","RUNNABLE","QUEUED"}:p=move(p,key,state,reason="local blocked fixture",output={"local":"result"})
    store=UnifiedJournalStore(tmp_path/"spool")
    persist_taskgraph(store,p)
    recovered=recover_persisted_taskgraph(UnifiedJournalStore(tmp_path/"spool"),request(),ecosystem="TRADER",access=ACCESS)
    assert recovered==p
    assert persist_taskgraph(store,p)["replay"] is True
    safety(recovered)


def test_changed_request_and_untrusted_digest_recovery_blocked():
    p=plan();serialized=tg.export_taskgraph(p)
    for req in (replace(request(),requested_action="email"),replace(request(),attachments=("different",))):
        with pytest.raises(tg.AionTaskgraphError,match="RECOVERY_REQUEST_CHANGED"):
            tg.recover_taskgraph(serialized,req,ecosystem="TRADER",access=ACCESS,expected_digest=p["plan_digest"])
    with pytest.raises(tg.AionTaskgraphError,match="RECOVERY_DIGEST"):
        tg.recover_taskgraph(serialized,request(),ecosystem="TRADER",access=ACCESS,expected_digest="untrusted")


@pytest.mark.parametrize("change",[lambda p:p.update(execution_allowed=True),lambda p:p["tasks"][0].update(role="prime"),lambda p:p["tasks"][0].update(state="COMPLETED",output={"local":True}),lambda p:p.update(revision=1),lambda p:p["graph"].update(order=[]),lambda p:p["feature_flags"].update(provider_calls="true"),lambda p:p["budget"].update(billing_executed=True),lambda p:p["tasks"][0].update(approved=1)])
def test_resealed_structural_forgeries_rejected(change):
    p=plan();change(p);tg._seal(p)
    with pytest.raises(tg.AionTaskgraphError):tg.validate_taskgraph(p)


@pytest.mark.parametrize("bad",[{"x":float("nan")},{"x":float("inf")},{"api_key":"not-a-key"},{"x":"a"*2001},{"x":list(range(65))},{"x":object()},{"x":{"x":{"x":{"x":{"x":{"x":{"x":1}}}}}}}])
def test_malformed_payloads(bad):
    with pytest.raises(tg.AionTaskgraphError):plan([spec(payload=bad)])


def test_bounds_revisions_and_json_duplicates():
    for specs in ([],[spec(str(i)) for i in range(33)]):
        with pytest.raises(tg.AionTaskgraphError):tg.prepare_taskgraph(request(),task_specs=specs)
    with pytest.raises(tg.AionTaskgraphError):plan(req=replace(request(),user_message="x"*2001))
    p=plan()
    with pytest.raises(tg.AionTaskgraphError,match="REVISION_CONFLICT"):
        tg.transition_task(p,p["tasks"][0]["task_id"],"QUEUED",expected_revision=True)
    with pytest.raises(tg.AionTaskgraphError,match="DUPLICATE_JSON_KEY"):
        tg.recover_taskgraph('{"schema":1,"schema":2}',request(),ecosystem="TRADER",expected_digest="x")


def test_commercial_decomposition_and_no_implicit_market_data():
    # Explicitly exercise the public deterministic default, without fixture task overrides.
    p=tg.prepare_taskgraph(request("NEGOCIOS",user_message="Preparar implantação de automação comercial de cliente."),access=ACCESS)
    assert p["graph"]["order"]==["diagnostico","levantamento","proposta","configuracao","testes","aprovacao","implantacao"]
    assert all(t["state"]=="PLANNED" for t in p["tasks"])
    assert any(t["key"]=="implantacao" and t["feature_flag"]=="crm_write" and t["approval_required"] for t in p["tasks"])
    with pytest.raises(tg.AionTaskgraphError,match="ECOSYSTEM_CAPABILITY"):
        tg.route_task_role("crm_context","TRADER")
    safety(p)


def test_multiple_local_snapshots_preserve_latest_and_reject_stale(tmp_path):
    store=UnifiedJournalStore(tmp_path/"spool");p=plan()
    persist_taskgraph(store,p)
    q=move(p,"a","QUEUED");persist_taskgraph(store,q)
    assert recover_persisted_taskgraph(UnifiedJournalStore(tmp_path/"spool"),request(),ecosystem="TRADER",access=ACCESS)==q
    with pytest.raises(tg.AionTaskgraphError,match="STALE_SNAPSHOT"):persist_taskgraph(store,p)


def test_handoff_binding_forgery_and_terminal_replay_rejected():
    p=ready(plan());tid=p["tasks"][0]["task_id"]
    h=tg.prepare_guarded_task_handoff(p,tid,expected_revision=p["revision"],now=NOW)
    forged=deepcopy(h["plan"]);forged["handoffs"][0]["capability"]="crm_write";tg._seal(forged)
    with pytest.raises(tg.AionTaskgraphError,match="HANDOFF_BINDING"):tg.validate_taskgraph(forged)
    cancelled=move(h["plan"],"a","CANCELLED")
    assert cancelled["mission_state"]=="PREPARED"
    with pytest.raises(tg.AionTaskgraphError,match="HANDOFF_GATES"):
        tg.prepare_guarded_task_handoff(cancelled,tid,expected_revision=cancelled["revision"])


def test_missing_unknown_and_conflicting_evidence_fail_closed():
    req=request();ev=list(req.evidence)
    ev[0]={**ev[0],"truth_state":"HYPOTHESIS"}
    p=plan(req=replace(req,evidence=tuple(ev)))
    assert "MISSING_EVIDENCE" in tg.evaluate_taskgraph(p)[0]["blockers"]
    conflict={**req.evidence[0],"value":"contradiction","source":"other"}
    p=plan(req=replace(req,evidence=(*req.evidence,conflict)))
    assert p["mission_state"]=="BLOCKED" and "EVIDENCE_CONFLICT" in tg.evaluate_taskgraph(p)[0]["blockers"]


def test_snapshot_incomplete_latest_never_falls_back(tmp_path):
    from aion_chat.models import Scope
    from atlasquant_aion_unified_journal import append_request_event
    store=UnifiedJournalStore(tmp_path/"spool");p=plan();persist_taskgraph(store,p)
    s=Scope("o","t","w");rid="TG24:TRADER:r"
    journal=store.recover(scope=s,request_id=rid)["journal"]
    journal=append_request_event(journal,event_type="TASKGRAPH_CHECKPOINT",selected_role="orchestrator",
        metadata={"snapshot_digest":"sha256:incomplete","revision":1,"group":0,"groups":2,"chunks":["AAAA"]})
    store.persist_event(journal,scope=s,request_id=rid,sequence=len(journal["events"]),idempotency_key="partial",origin="test")
    with pytest.raises(tg.AionTaskgraphError,match="SNAPSHOT_INCOMPLETE"):
        recover_persisted_taskgraph(store,request(),ecosystem="TRADER",access=ACCESS)


def test_planning_apis_have_no_io_or_provider_dispatch(monkeypatch):
    import socket
    import subprocess
    def forbidden(*args,**kwargs):raise AssertionError("external side effect attempted")
    monkeypatch.setattr(socket,"create_connection",forbidden)
    monkeypatch.setattr(subprocess,"Popen",forbidden)
    p=ready(plan([spec(capability="provider_calls")],feature_flags={"provider_calls":True}))
    h=tg.prepare_guarded_task_handoff(p,p["tasks"][0]["task_id"],expected_revision=p["revision"])
    recovered=tg.recover_taskgraph(tg.export_taskgraph(h["plan"]),request(),ecosystem="TRADER",access=ACCESS,expected_digest=h["plan"]["plan_digest"])
    assert recovered==h["plan"]
    safety(recovered)
