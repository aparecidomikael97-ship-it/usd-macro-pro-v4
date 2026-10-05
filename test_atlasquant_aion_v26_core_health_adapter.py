"""Adversarial, offline tests for the single V2.6 evidence bridge."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone, timedelta
import builtins
import pathlib
import socket
import subprocess
import pytest

from aion_chat.models import Scope
import atlasquant_aion_core_health_adapter as adapter
from atlasquant_aion_core_health_adapter import LoadedEvidence as E, build_core_health_evidence as build, HealthEvidenceError
from atlasquant_aion_unified_journal import new_request_journal, append_request_event
from atlasquant_aion_checkpoint_master import new_checkpoint_master, append_checkpoint_patch
from atlasquant_aion_memory_contract import create_memory_record
from atlasquant_aion_unified_journal_store import UnifiedJournalStore, STORE_SCHEMA
from atlasquant_aion_observability import core_health_snapshot, _health_count
from atlasquant_aion_status_board import build_master_status_board
from atlasquant_aion_unified_runtime import AionRequest
from atlasquant_aion_unified_taskgraph import prepare_taskgraph

NOW=datetime(2026,10,4,12,tzinfo=timezone.utc)
SCOPE={"owner_id":"o","tenant_id":"t","workspace_id":"w"}


def evidence(**overrides):
    j=new_request_journal(Scope("o","t","w"),"r","c")
    j=append_request_event(j,event_type="REQUEST_ACCEPTED",observed_at=NOW.isoformat(),metadata={"bounded":"fixture"})
    master=new_checkpoint_master({"task":{"state":"PLANNED"}},created_at=NOW.isoformat())
    memory=create_memory_record(namespace="TENANT",memory_class="TENANT",content="fixture",
        scope={"tenant_id":"t"},validation_state="VALIDATED",evidence_refs=["EV-1"],created_at=NOW.isoformat())
    recovery={"schema":STORE_SCHEMA,"status":"RECOVERED","restores_state_only":True,
        "scope_fingerprint":j["scope_fingerprint"],"request_id":"r","journal":j,
        "external_action_executed":False,"hard_failures":[],"quarantine_pending_count":0,
        **{flag:True for flag in adapter._RECOVERY_FLAGS}}
    inputs={"journal_evidence":E("resident/journal",j,"journal",SCOPE,True),
        "audit_chain_evidence":E("resident/journal",j,"journal",SCOPE,True),
        "checkpoint_evidence":E("resident/checkpoint",master,"checkpoint_master",SCOPE,True),
        "memory_evidence":E("resident/memory",(memory,),"memory_records",SCOPE,True),
        "recovery_evidence":E("verified/recovery",recovery,"recovery_report",SCOPE,True,as_of=NOW.isoformat()),
        "mission_evidence":E("resident/missions",[],"missions",SCOPE,True),
        "expected_scope":SCOPE,"now":NOW}
    inputs.update(overrides)
    return inputs


def snapshot(payload):
    return core_health_snapshot(**{k:payload[k] for k in (
        "journal_status","checkpoint_status","recovery_status","memory_status","audit_chain_status",
        "pending_missions","blocked_missions","waiting_approval","ready_handoffs","events")})


def board(payload):
    result=build_master_status_board(system_context={"aion_core_health":payload})
    return next(item for item in result["items"] if item["id"]=="aion_core_health")


def test_five_verified_domains_and_zero_counts():
    p=build(**evidence())
    assert snapshot(p)["integrity_state"]=="OK"
    assert board(p)["state"]=="CONFIRMED"
    assert p["evidence_complete"] is True and p["counts_verified"] is True
    assert all(type(p[k]) is int and p[k]==0 for k in ("pending_missions","blocked_missions","waiting_approval","ready_handoffs"))
    assert all(p[k] is v and snapshot(p)[k] is v for k,v in adapter.INVARIANTS.items())


@pytest.mark.parametrize("domain",["journal","checkpoint","recovery","memory","audit_chain"])
def test_missing_domain_stays_unknown(domain):
    p=build(**evidence(**{domain+"_evidence":None}))
    assert p[domain+"_status"]=="UNKNOWN"
    assert snapshot(p)["integrity_state"]=="UNKNOWN"
    assert board(p)["state"]=="UNKNOWN"


@pytest.mark.parametrize("field",["head_digest","revision","sequence","digest","link","row"])
@pytest.mark.parametrize("domain",["journal","audit_chain"])
def test_journal_chain_tamper(domain,field):
    args=evidence();source=args[domain+"_evidence"];value=deepcopy(source.value)
    if field=="head_digest": value[field]="changed"
    elif field=="revision":value[field]+=1
    elif field=="sequence":value["events"][0][field]=2
    elif field=="digest":value["events"][0]["event_digest"]="changed"
    elif field=="link":value["events"][0]["prev_digest"]="missing"
    else:value["events"][0]=[]
    args[domain+"_evidence"]=replace(source,value=value)
    assert snapshot(build(**args))["integrity_state"]=="DEGRADED"


@pytest.mark.parametrize("field",["base_digest","head_digest","state_digest","revision","schema","unsafe"])
def test_checkpoint_integrity_failures(field):
    args=evidence();source=args["checkpoint_evidence"];value=deepcopy(source.value)
    if field=="revision":value[field]+=1
    elif field=="unsafe":value["execution_allowed"]=True
    else:value[field]="changed"
    args["checkpoint_evidence"]=replace(source,value=value)
    assert snapshot(build(**args))["integrity_state"]=="DEGRADED"


@pytest.mark.parametrize("field",["patch_digest","prev_digest","event_digest","event_type","sequence"])
def test_checkpoint_event_tamper(field):
    args=evidence();source=args["checkpoint_evidence"]
    value=append_checkpoint_patch(source.value,event_id="e",patch={"local":"change"},expected_revision=0,created_at=NOW.isoformat())
    value=deepcopy(value);value["journal"][0][field]=99 if field=="sequence" else "changed"
    args["checkpoint_evidence"]=replace(source,value=value)
    assert snapshot(build(**args))["integrity_state"]=="DEGRADED"


@pytest.mark.parametrize("state,expected",[("QUARANTINED","DEGRADED"),("CONFLICTING","DEGRADED"),("REJECTED","DEGRADED"),("OUTDATED","UNKNOWN"),("UNVERIFIED","UNKNOWN"),("PROPOSED","UNKNOWN"),("DOUBTFUL","UNKNOWN")])
def test_memory_states_not_masked(state,expected):
    args=evidence();source=args["memory_evidence"]
    record=create_memory_record(namespace="TENANT",memory_class="TENANT",content="fixture",
        scope={"tenant_id":"t"},validation_state=state,evidence_refs=["EV-1"],created_at=NOW.isoformat())
    args["memory_evidence"]=replace(source,value=(*source.value,record))
    p=build(**args)
    assert snapshot(p)["integrity_state"]==expected
    assert p["memory_status"]!="VALIDATED"


@pytest.mark.parametrize("invalid",[False,"true",1,None])
def test_recovery_verified_flags_require_exact_true(invalid):
    args=evidence();source=args["recovery_evidence"]
    args["recovery_evidence"]=replace(source,value={**source.value,"chain_valid":invalid})
    assert snapshot(build(**args))["integrity_state"]==("DEGRADED" if invalid is False else "UNKNOWN")


@pytest.mark.parametrize("status",["INVALID","ERROR","QUARANTINED","purple","ＶＡＬＩＤ","VΑLID","VALID"])
def test_unverified_recovery_status_claims(status):
    args=evidence();source=args["recovery_evidence"]
    args["recovery_evidence"]=replace(source,value={"schema":STORE_SCHEMA,"status":status})
    p=build(**args)
    assert snapshot(p)["integrity_state"]==("DEGRADED" if status in {"INVALID","ERROR","QUARANTINED"} else "UNKNOWN")


@pytest.mark.parametrize("value,expected",[(True,0),(False,0),("1",1),(1,1),(1.0,1),(1.5,0),(-1,0),(float("nan"),0),(float("inf"),0),(None,0),({},0),([],0)])
def test_health_count_no_bool_fractional_or_nonfinite(value,expected):
    assert _health_count(value)==expected
    assert type(_health_count(value)) is int


@pytest.mark.parametrize("domain",["journal","checkpoint","recovery","memory","audit_chain"])
def test_untrusted_nested_payload_cannot_forge_a_domain(domain):
    fake={"system_context":{"aion_core_health":{"integrity_state":"OK"}},
        "source_ref":"client","complete":True,"status":"VALID","validated":True}
    p=build(**evidence(**{domain+"_evidence":fake}))
    assert p[domain+"_status"]=="UNKNOWN"
    assert snapshot(p)["integrity_state"]=="UNKNOWN"


@pytest.mark.parametrize("complete",[False,"true",1,None])
def test_completeness_is_exact_bool_and_not_positive_default(complete):
    args=evidence();args["checkpoint_evidence"]=replace(args["checkpoint_evidence"],complete=complete)
    p=build(**args)
    assert p["checkpoint_status"]=="UNKNOWN" and p["evidence_complete"] is False
    assert board(p)["state"]=="UNKNOWN"


def test_bad_source_dominates_even_if_incomplete_and_another_unknown():
    args=evidence(journal_evidence=None);source=args["checkpoint_evidence"]
    value=deepcopy(source.value);value["base_digest"]="changed"
    args["checkpoint_evidence"]=replace(source,value=value,complete=False)
    assert snapshot(build(**args))["integrity_state"]=="DEGRADED"


@pytest.mark.parametrize("field,value",[("tenant_id","other"),("workspace_id","other"),("owner_id","other"),("ecosystem","NEGOCIOS"),("sector","other"),("project","other")])
def test_scope_mismatch_fails_closed(field,value):
    args=evidence(expected_scope={**SCOPE,"ecosystem":"TRADER","sector":"central","project":"p"})
    args["checkpoint_evidence"]=replace(args["checkpoint_evidence"],scope={**SCOPE,field:value})
    with pytest.raises(HealthEvidenceError,match="CROSS_SCOPE"):build(**args)


def test_missing_scope_journal_cannot_be_verified():
    args=evidence();value=deepcopy(args["journal_evidence"].value);value.pop("tenant_id")
    args["journal_evidence"]=replace(args["journal_evidence"],value=value)
    assert build(**args)["journal_status"]=="UNKNOWN"


@pytest.mark.parametrize("temporal",[{"freshness":"STALE"},{"stale":True},{"time_sensitive":True,"timestamp":(NOW-timedelta(hours=2)).isoformat(),"ttl_seconds":60},{"expires_at":(NOW-timedelta(seconds=1)).isoformat()}])
def test_stale_evidence_never_becomes_current(temporal):
    args=evidence();args["checkpoint_evidence"]=replace(args["checkpoint_evidence"],temporal=temporal)
    p=build(**args)
    assert p["checkpoint_status"]=="STALE" and snapshot(p)["integrity_state"]=="UNKNOWN"


def test_freshness_requires_existing_temporal_contract_and_explicit_now():
    args=evidence();source=args["checkpoint_evidence"]
    temporal={"time_sensitive":True,"timestamp":NOW.isoformat(),"ttl_seconds":60}
    args["checkpoint_evidence"]=replace(source,temporal=temporal)
    assert build(**args)["checkpoint_status"]=="VERIFIED"
    args["now"]=None
    assert build(**args)["checkpoint_status"]=="UNKNOWN"
    args["checkpoint_evidence"]=replace(source,temporal={"freshness":"FRESH"})
    args["now"]=NOW
    assert build(**args)["checkpoint_status"]=="UNKNOWN"


def test_no_input_mutation_determinism_and_redaction():
    args=evidence(events=[{"event_type":"test","message":"password=short","created_at":NOW.isoformat(),"evidence":{"api_key":"short"}}, {"message":"missing time"}])
    original=deepcopy(args);p=build(**args);q=build(**args)
    assert args==original and p==q
    assert len(p["events"])==1 and "short" not in str(p)
    p["provenance"]["domains"]["journal"]["revision"]=900
    assert build(**args)==q


def test_source_missing_is_unknown():
    args=evidence();args["checkpoint_evidence"]=replace(args["checkpoint_evidence"],source_ref="")
    assert build(**args)["checkpoint_status"]=="UNKNOWN"


def test_adapter_has_no_side_effects(monkeypatch):
    import requests
    import atlasquant_aion_provider
    args=evidence()
    def forbidden(*args,**kwargs):raise AssertionError("SIDE EFFECT ATTEMPT")
    monkeypatch.setattr(builtins,"open",forbidden)
    monkeypatch.setattr(socket,"socket",forbidden)
    monkeypatch.setattr(socket,"create_connection",forbidden)
    monkeypatch.setattr(subprocess,"Popen",forbidden)
    monkeypatch.setattr(pathlib.Path,"open",forbidden)
    for name in ("mkdir","rename","replace","unlink","write_text","write_bytes","iterdir","glob","rglob"):
        monkeypatch.setattr(pathlib.Path,name,forbidden)
    monkeypatch.setattr(UnifiedJournalStore,"recover",forbidden)
    monkeypatch.setattr(UnifiedJournalStore,"__init__",forbidden)
    monkeypatch.setattr(requests,"get",forbidden)
    monkeypatch.setattr(requests,"post",forbidden)
    for name in ("execute_openai_answer","provider_configuration_status"):
        if hasattr(atlasquant_aion_provider,name):monkeypatch.setattr(atlasquant_aion_provider,name,forbidden)
    assert snapshot(build(**args))["integrity_state"]=="OK"


@pytest.mark.parametrize("value",[{"x":"a"*16001},{"x":float("nan")},{"x":[{}]*257},{"x":object()}])
def test_bounded_plain_inputs(value):
    args=evidence();args["checkpoint_evidence"]=replace(args["checkpoint_evidence"],value=value)
    with pytest.raises(HealthEvidenceError):build(**args)


def test_mission_counts_derive_from_validated_plans():
    req=AionRequest(conversation_id="c",owner_id="o",tenant_id="t",workspace_id="w",request_id="r",user_message="Explique um conceito",sector="TRADER")
    p=prepare_taskgraph(req,task_specs=[{"key":"a","capability":"research"}])
    payload=build(**evidence(mission_evidence=E("resident/missions",[p],"missions",SCOPE,True)))
    assert payload["pending_missions"]==1 and payload["blocked_missions"]==1
    assert board(payload)["state"]=="BLOCKED"
    p=deepcopy(p);p["mission_state"]="WAITING_APPROVAL"
    # Mutated plan is rejected; counters cannot come from edited state claims.
    with pytest.raises(ValueError):build(**evidence(mission_evidence=E("resident/missions",[p],"missions",SCOPE,True)))


def test_waiting_approval_is_operational_block_even_with_integrity_ok():
    payload=build(**evidence())
    payload["waiting_approval"]=1
    assert snapshot(payload)["integrity_state"]=="OK" and board(payload)["state"]=="BLOCKED"


def test_bad_operational_count_completeness_does_not_confirm_board():
    payload=build(**evidence(mission_evidence=None))
    assert payload["counts_verified"] is False
    assert board(payload)["state"]=="UNKNOWN"


@pytest.mark.parametrize("domain",["journal","checkpoint","recovery","memory","audit_chain"])
def test_no_resident_value_means_unknown(domain):
    args=evidence();args[domain+"_evidence"]=replace(args[domain+"_evidence"],value=None)
    assert build(**args)[domain+"_status"]=="UNKNOWN"


@pytest.mark.parametrize("value",[True,False,1.5,float("nan"),float("inf"),{},[]])
def test_direct_board_invalid_counters_cannot_confirm(value):
    p=build(**evidence());p["blocked_missions"]=value
    assert board(p)["state"]=="UNKNOWN"


def test_recovery_scope_fingerprint_mismatch_and_missing():
    args=evidence();source=args["recovery_evidence"]
    args["recovery_evidence"]=replace(source,value={**source.value,"scope_fingerprint":"changed"})
    assert snapshot(build(**args))["integrity_state"]=="DEGRADED"
    value=deepcopy(source.value);value.pop("scope_fingerprint")
    args["recovery_evidence"]=replace(source,value=value)
    assert build(**args)["recovery_status"]=="UNKNOWN"


def test_waiting_approval_counter_comes_from_bound_taskgraph():
    refs=("objective","canonical_memory","wisdom_journal","runtime_checkpoint","expected_sha","integrity","provider_ready","pricing","budget")
    ev=tuple({"ref":ref,"claim":ref,"value":"fixture","source":"test","truth_state":"CONFIRMED","time_sensitive":False,"ecosystem":"TRADER",**SCOPE} for ref in refs)
    req=AionRequest(conversation_id="c",owner_id="o",tenant_id="t",workspace_id="w",request_id="r",user_message="Explique um conceito",sector="TRADER",evidence=ev)
    plan=prepare_taskgraph(req,access={"role":"ADMIN","memory":True,"wisdom":True},feature_flags={"provider_calls":True},task_specs=[{"key":"a","capability":"provider_calls"}])
    assert plan["mission_state"]=="WAITING_APPROVAL"
    p=build(**evidence(mission_evidence=E("resident/missions",[plan],"missions",SCOPE,True)))
    assert p["waiting_approval"]==1 and snapshot(p)["integrity_state"]=="OK"
    assert board(p)["state"]=="BLOCKED"


@pytest.mark.parametrize("status",["ERROR","MISMATCH","CORRUPT","UNAVAILABLE","NOT_FOUND",None])
def test_runtime_loader_failure_cannot_be_hidden(status):
    from atlasquant_aion_core_health_adapter import build_loaded_runtime_health_evidence
    p=build_loaded_runtime_health_evidence({"status":status})
    expected="DEGRADED" if status in {"ERROR","MISMATCH","CORRUPT"} else "UNKNOWN"
    assert snapshot(p)["integrity_state"]==expected
    assert p["counts_verified"] is False


def test_real_admin_builder_replaces_client_claim_and_loads_only_once():
    from streamlit.testing.v1 import AppTest
    script = r"""
import os
os.environ["GITHUB_TOKEN_HISTORICO"]=""
os.environ["GITHUB_REPO_HISTORICO"]=""
os.environ["AION_MODEL_PROVIDER"]="offline"
import streamlit as st
import atlasquant_aion_admin as admin
import requests
from atlasquant_aion_unified_journal_store import UnifiedJournalStore
calls=[]
original=admin.build_master_status_board
captured=[]
def resident_loader(*args,**kwargs):
    calls.append(1)
    return {"status":"UNAVAILABLE","checkpoint":None,"source":""}
def capture(**kwargs):
    captured.append(kwargs["system_context"]["aion_core_health"])
    return original(**kwargs)
def forbidden(*args,**kwargs):
    raise AssertionError("external/store action forbidden")
from contextlib import ExitStack
from unittest.mock import patch
with ExitStack() as guards:
    guards.enter_context(patch.object(admin,"load_runtime_checkpoint",resident_loader))
    guards.enter_context(patch.object(admin,"build_master_status_board",capture))
    guards.enter_context(patch.object(requests,"get",forbidden))
    guards.enter_context(patch.object(requests,"post",forbidden))
    guards.enter_context(patch.object(UnifiedJournalStore,"recover",forbidden))
    result=admin.render_aion_admin_console(
        {"role":"ADMIN","username":"admin.test"},
        system_context={"aion_core_health":{"journal_status":"OK","execution_allowed":True}},
    )
    assert len(calls)==1
    assert len(captured)==1
    health=captured[0]
    assert health["journal_status"]=="UNKNOWN"
    assert health["checkpoint_status"]=="UNKNOWN"
    assert health["counts_verified"] is False
    assert health["execution_allowed"] is False
st.write("V26_CANONICAL_BUILDER_VERIFIED")
"""
    app=AppTest.from_string(script).run(timeout=45)
    assert len(app.exception)==0
    assert any("V26_CANONICAL_BUILDER_VERIFIED" in str(row.value) for row in app.markdown)


@pytest.mark.parametrize("bad_first",[True,False])
def test_bad_memory_dominates_ambiguous_record_in_same_view(bad_first):
    args=evidence()
    record=args["memory_evidence"].value[0]
    bad=replace(record,validation_state="QUARANTINED")
    # recreate identity, rather than treating a tampered memory id as validated
    from atlasquant_aion_memory_contract import create_memory_record
    raw=vars(bad)
    bad=create_memory_record(**{k:raw[k] for k in ("namespace","memory_class","content","scope","provenance_ids","version","previous_version","evidence_refs","validation_state","retention","sensitivity","rollback_pointer","tombstone","created_at","metadata")})
    records=[bad,{}] if bad_first else [{},bad]
    args["memory_evidence"]=replace(args["memory_evidence"],value=records)
    assert snapshot(build(**args))["integrity_state"]=="DEGRADED"


@pytest.mark.parametrize("temporal",[{"stale":True},{"freshness":"FRESH"}])
def test_operational_counts_freshness_cannot_confirm_without_proof(temporal):
    args=evidence()
    args["mission_evidence"]=replace(args["mission_evidence"],temporal=temporal)
    p=build(**args)
    assert snapshot(p)["integrity_state"]=="OK"
    assert p["counts_verified"] is False
    assert board(p)["state"]=="UNKNOWN"


@pytest.mark.parametrize("source",[{"status":"verified"},"x"*241])
def test_mission_provenance_is_bounded_explicit_text(source):
    args=evidence()
    args["mission_evidence"]=replace(args["mission_evidence"],source_ref=source)
    p=build(**args)
    assert p["counts_verified"] is False
    assert board(p)["state"]=="UNKNOWN"


@pytest.mark.parametrize("stamp",[""," "])
def test_missing_memory_timestamp_never_calls_implicit_clock(monkeypatch,stamp):
    import atlasquant_aion_memory_contract as memory_contract
    args=evidence()
    args["memory_evidence"]=replace(args["memory_evidence"],value=[replace(args["memory_evidence"].value[0],created_at=stamp)])
    def forbidden():
        raise AssertionError("implicit clock forbidden")
    monkeypatch.setattr(memory_contract,"_now",forbidden)
    p=build(**args)
    assert p["memory_status"]=="UNKNOWN"
    assert snapshot(p)["integrity_state"]=="UNKNOWN"
