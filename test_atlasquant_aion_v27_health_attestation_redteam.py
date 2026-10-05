"""Executable red-team of the current V2.7 starting contract."""
from dataclasses import replace
import pytest
from test_atlasquant_aion_v26_core_health_adapter import evidence as _base_evidence, build, E, SCOPE, snapshot, board
from atlasquant_aion_core_health_adapter import HealthEvidenceError
from atlasquant_aion_unified_journal_store import STORE_SCHEMA
from atlasquant_aion_unified_journal import _digest

from copy import deepcopy

def evidence(**kwargs):
    return deepcopy(_base_evidence(**kwargs))

DOMAINS=("journal","checkpoint","recovery","memory","audit_chain","mission")
KINDS={"journal":"journal","checkpoint":"checkpoint_master","recovery":"recovery_report","memory":"memory_records","audit_chain":"journal","mission":"missions"}
POSITIVE={"OK","VERIFIED","VALIDATED","RECOVERED","CONFIRMED"}
SOURCES=("trusted/journal","trusted/checkpoint","canonical/recovery","system/internal","admin","root","validated","github","production","TRUSTED/JOURNAL"," trusted/journal ","trusted\x00/journal","https://production.example/verified","../../root/validated","trusted////journal","tr\u0443sted/journal")


def nonpositive(domain,source,value,scope=SCOPE):
    args=evidence()
    args[domain+"_evidence"]=E(source,value,KINDS[domain],scope,True)
    try:p=build(**args)
    except (ValueError,TypeError,KeyError):return
    if domain=="mission":assert p["counts_verified"] is False
    else:assert p[domain+"_status"] not in POSITIVE
    assert board(p)["state"]!="CONFIRMED"


@pytest.mark.parametrize("domain",DOMAINS)
@pytest.mark.parametrize("value",[None,{},"OK","VALIDATED",{"verified":True},{"verified":True,"digest":"false","status":"OK"},{"verified":True,"status":"VALIDATED","scope":{}}])
def test_verified_claim_without_canonical_value_never_attests(domain,value):
    nonpositive(domain,"trusted/journal",value)


@pytest.mark.parametrize("domain",DOMAINS)
@pytest.mark.parametrize("source",SOURCES)
def test_source_name_never_attests_invalid_content(domain,source):
    nonpositive(domain,source,{"verified":True,"status":"OK","digest":"false"})


@pytest.mark.parametrize("domain",DOMAINS)
def test_client_verified_envelope_is_not_loaded_evidence(domain):
    args=evidence()
    args[domain+"_evidence"]={"verified":True,"source_ref":"system/internal","value":{"status":"VALIDATED"},"scope":SCOPE,"complete":True}
    p=build(**args)
    if domain=="mission":assert p["counts_verified"] is False
    else:assert p[domain+"_status"]=="UNKNOWN"
    assert board(p)["state"]=="UNKNOWN"


def test_fabricated_recovery_receipt_must_not_attest_without_canonical_validation():
    # Public field names and an unkeyed scope hash are not authenticated provenance.
    from atlasquant_aion_core_health_adapter import _RECOVERY_FLAGS
    fake={"schema":STORE_SCHEMA,"status":"RECOVERED","verified":True,
          "scope_fingerprint":_digest(SCOPE),"request_id":"r",
          "restores_state_only":True,"external_action_executed":False,
          **{key:True for key in _RECOVERY_FLAGS}}
    args=evidence()
    args["recovery_evidence"]=E("canonical/recovery",fake,"recovery_report",SCOPE,True)
    p=build(**args)
    assert p["recovery_status"] not in POSITIVE
    assert snapshot(p)["integrity_state"]!="OK"
    assert board(p)["state"]!="CONFIRMED"


def test_empty_mission_list_and_claim_must_not_attest_complete_inventory():
    args=evidence()
    args["mission_evidence"]=E("production",[],"missions",{},True)
    p=build(**args)
    assert p["counts_verified"] is False
    assert board(p)["state"]!="CONFIRMED"


from copy import deepcopy
from datetime import timedelta
from decimal import Decimal
from enum import IntEnum
from collections import UserDict
from test_atlasquant_aion_v26_core_health_adapter import NOW

TIME_ATTACKS=[
 {"as_of":(NOW+timedelta(hours=1)).isoformat(),"expires_at":(NOW+timedelta(hours=2)).isoformat()},
 {"timestamp":NOW.replace(tzinfo=None).isoformat(),"time_sensitive":True,"ttl_seconds":60},
 {"timestamp":"2026-10-04T12:00:00+99:00","time_sensitive":True,"ttl_seconds":60},
 {"timestamp":"","time_sensitive":True,"ttl_seconds":60},
 {"timestamp":None,"time_sensitive":True,"ttl_seconds":60},
 {"as_of":NOW.isoformat(),"expires_at":(NOW-timedelta(seconds=1)).isoformat()},
 {"expires_at":NOW.isoformat()},
 {"timestamp":NOW.isoformat(),"time_sensitive":True,"ttl_seconds":-1},
 {"timestamp":NOW.isoformat(),"time_sensitive":True,"ttl_seconds":True},
 {"timestamp":NOW.isoformat(),"time_sensitive":True,"ttl_seconds":float("nan")},
 {"timestamp":NOW.isoformat(),"time_sensitive":True,"ttl_seconds":float("inf")},
 {"timestamp":(NOW-timedelta(days=1000)).isoformat(),"time_sensitive":True,"ttl_seconds":60},
]
@pytest.mark.parametrize("temporal",TIME_ATTACKS)
@pytest.mark.parametrize("domain",DOMAINS)
def test_temporal_contract_never_upgrades_bad_freshness(domain,temporal):
    args=evidence();args[domain+"_evidence"]=replace(args[domain+"_evidence"],temporal=temporal)
    try:p=build(**args)
    except (ValueError,TypeError):return
    if domain=="mission":assert p["counts_verified"] is False
    else:assert p[domain+"_status"] not in POSITIVE
    assert board(p)["state"]!="CONFIRMED"

class Number(IntEnum):ONE=1
class DictSubclass(dict):pass
class ListSubclass(list):pass
class Hostile:
    def __bool__(self):raise AssertionError("hostile bool called")
    def __str__(self):raise AssertionError("hostile str called")
    def __int__(self):raise AssertionError("hostile int called")
TYPE_ATTACKS=[True,False,1,0,Number.ONE,Decimal("1"),1.5,float("nan"),float("inf"),b"OK",UserDict({"status":"OK"}),DictSubclass(status="OK"),ListSubclass(),Hostile()]
@pytest.mark.parametrize("domain",DOMAINS)
@pytest.mark.parametrize("value",TYPE_ATTACKS)
def test_hostile_types_cannot_be_coerced_into_evidence(domain,value):
    nonpositive(domain,"system/internal",value)

@pytest.mark.parametrize("field",["scope","kind","temporal","source_ref","as_of"])
def test_metadata_does_not_execute_hostile_conversion(field):
    args=evidence();args["checkpoint_evidence"]=replace(args["checkpoint_evidence"],**{field:Hostile()})
    try:p=build(**args)
    except (ValueError,TypeError):return
    assert p["checkpoint_status"] not in POSITIVE

@pytest.mark.parametrize("domain",DOMAINS)
def test_mutating_originals_cannot_change_previous_output(domain):
    args=evidence();before=deepcopy(args);p=build(**args);saved=deepcopy(p)
    source=args[domain+"_evidence"]
    source.scope["tenant_id"]="other"
    if isinstance(source.value,dict):source.value.update(status="OK",digest="false")
    if isinstance(source.value,list):source.value.append({"status":"OK"})
    assert p==saved
    assert before!=args


def test_repeat_100_times_is_deterministic_and_preserves_inputs():
    args=evidence();original=deepcopy(args);first=build(**args)
    for _ in range(100):assert build(**args)==first
    assert args==original

@pytest.mark.parametrize("domain",DOMAINS)
def test_multiple_sources_are_not_silently_merged(domain):
    args=evidence();source=args[domain+"_evidence"]
    args[domain+"_evidence"]=[source,replace(source,scope={**SCOPE,"tenant_id":"other"})]
    p=build(**args)
    if domain=="mission":assert p["counts_verified"] is False
    else:assert p[domain+"_status"]=="UNKNOWN"


from atlasquant_aion_unified_journal import append_request_event
from atlasquant_aion_checkpoint_master import append_checkpoint_patch
from atlasquant_aion_unified_runtime import AionRequest
from atlasquant_aion_unified_taskgraph import prepare_taskgraph
from atlasquant_aion_memory_contract import create_memory_record

@pytest.mark.parametrize("domain",["journal","audit_chain"])
@pytest.mark.parametrize("attack",["sequence","digest","request_id","scope","remove","duplicate","old_head","reorder"])
def test_journal_canonical_validator_cannot_be_bypassed(domain,attack):
    args=evidence();source=args[domain+"_evidence"]
    value=append_request_event(source.value,event_type="REQUEST_ACCEPTED",observed_at=NOW.isoformat(),metadata={"case":"second"})
    if attack=="sequence":value["events"][1]["sequence"]=9
    elif attack=="digest":value["events"][0]["event_digest"]="false"
    elif attack=="request_id":value["request_id"]="other"
    elif attack=="scope":value["tenant_id"]="other"
    elif attack=="remove":value["events"].pop()
    elif attack=="duplicate":value["events"].append(deepcopy(value["events"][0]))
    elif attack=="old_head":value["head_digest"]=value["events"][0]["event_digest"]
    elif attack=="reorder":value["events"].reverse()
    value["verified"]=True
    nonpositive(domain,"trusted/journal",value)

@pytest.mark.parametrize("attack",["state_digest","head_digest","base_digest","revision","event_id","event_type","prev_digest","safety"])
def test_checkpoint_verified_claim_cannot_bypass_reconstruction(attack):
    value=append_checkpoint_patch(evidence()["checkpoint_evidence"].value,event_id="canonical-event",patch={"local":"value"},expected_revision=0,created_at=NOW.isoformat())
    if attack in {"state_digest","head_digest","base_digest"}:value[attack]="false"
    elif attack=="revision":value["revision"]=True
    elif attack=="safety":value["execution_allowed"]=True
    else:value["journal"][0][attack]="invalid altered event"
    value["verified"]=True
    nonpositive("checkpoint","trusted/checkpoint",value)

@pytest.mark.parametrize("attack",["state","digest","tenant","workspace","partial","ui","caller_count"])
def test_taskgraph_content_scope_and_inventory_are_checked(attack):
    request=AionRequest(conversation_id="c",owner_id="o",tenant_id="t",workspace_id="w",request_id="r",user_message="Explique",sector="TRADER")
    plan=prepare_taskgraph(request,task_specs=[{"key":"a","capability":"research"}])
    args=evidence()
    if attack=="state":plan["mission_state"]="READY_FOR_GUARDED_HANDOFF"
    if attack=="digest":plan["plan_digest"]="false"
    if attack=="tenant":plan["scope"]["tenant_id"]="other"
    if attack=="workspace":plan["scope"]["workspace_id"]="other"
    if attack=="ui":plan={"schema":plan["schema"],"verified":True,"mission_state":"READY_FOR_GUARDED_HANDOFF"}
    value={"counts_verified":True,"pending_missions":0} if attack=="caller_count" else [plan]
    args["mission_evidence"]=E("production",value,"missions",SCOPE,attack!="partial")
    try:p=build(**args)
    except (ValueError,TypeError,KeyError):return
    assert p["counts_verified"] is False
    assert board(p)["state"]!="CONFIRMED"

@pytest.mark.parametrize("state",["VALIDATED","CONFLICTING","QUARANTINED","OUTDATED","REJECTED","UNVERIFIED"])
def test_canonical_memory_state_is_preserved(state):
    record=create_memory_record(namespace="TENANT",memory_class="TENANT",content="resident",scope={"tenant_id":"t"},validation_state=state,evidence_refs=["EV-1"],created_at=NOW.isoformat())
    args=evidence();args["memory_evidence"]=E("validated",[record],"memory_records",SCOPE,True)
    p=build(**args)
    assert (p["memory_status"] in POSITIVE)==(state=="VALIDATED")
    if state!="VALIDATED":assert board(p)["state"]!="CONFIRMED"

@pytest.mark.parametrize("attack",["claim_only","journal_digest","report_head","report_revision","scope","stale"])
def test_recovery_requires_canonical_content_not_receipt_claim(attack):
    args=evidence();source=args["recovery_evidence"];value=deepcopy(source.value)
    temporal={}
    if attack=="claim_only":value={"recovered":True,"verified":True}
    elif attack=="journal_digest":value["journal"]["head_digest"]="false"
    elif attack=="report_head":value["head_digest"]="false"
    elif attack=="report_revision":value["revision"]=99
    elif attack=="scope":value["journal"]["workspace_id"]="other"
    elif attack=="stale":temporal={"stale":True}
    args["recovery_evidence"]=replace(source,value=value,temporal=temporal)
    try:p=build(**args)
    except (ValueError,TypeError):return
    assert p["recovery_status"] not in POSITIVE
    assert board(p)["state"]!="CONFIRMED"

@pytest.mark.parametrize("domain",DOMAINS)
@pytest.mark.parametrize("pair",["same","revision","bad","unknown","tenant","workspace"])
def test_duplicate_domain_sources_never_choose_convenient_claim(domain,pair):
    args=evidence();source=args[domain+"_evidence"]
    second=deepcopy(source)
    if pair=="tenant":second=replace(second,scope={**SCOPE,"tenant_id":"other"})
    elif pair=="workspace":second=replace(second,scope={**SCOPE,"workspace_id":"other"})
    elif pair=="unknown":second=replace(second,value=None)
    elif pair in {"revision","bad"}:second=replace(second,value={"revision":99,"status":"CORRUPT"})
    args[domain+"_evidence"]=[source,second]
    p=build(**args)
    if domain=="mission":assert p["counts_verified"] is False
    else:assert p[domain+"_status"]=="UNKNOWN"

@pytest.mark.parametrize("key",["aion_core_health","integrity_state","counts_verified","journal_status","checkpoint_status","memory_status","recovery_status","audit_chain_status","blocked_missions","waiting_approval","execution_allowed"])
def test_real_admin_ignores_each_client_authority_claim(monkeypatch,key):
    from test_atlasquant_aion_v26_evidence_wiring_status_truth import test_real_admin_boundary_same_loader_budget_and_no_extra_io as verify_boundary
    claim={key:True,"nested":{"system_context":{key:"CONFIRMED"}}}
    verify_boundary(monkeypatch,claim)


def test_entire_readonly_chain_without_side_effects(monkeypatch):
    import builtins,pathlib,socket,subprocess,requests
    import atlasquant_aion_unified_taskgraph_store as stores
    import atlasquant_aion_provider as provider
    from atlasquant_aion_unified_journal_store import UnifiedJournalStore
    args=evidence()
    def forbidden(*args,**kwargs):raise AssertionError("side effect forbidden")
    monkeypatch.setattr(builtins,"open",forbidden)
    for name in ("open","write_text","write_bytes","mkdir","rename","replace","unlink","iterdir","glob","rglob"):
        monkeypatch.setattr(pathlib.Path,name,forbidden)
    monkeypatch.setattr(socket,"socket",forbidden)
    monkeypatch.setattr(subprocess,"Popen",forbidden)
    monkeypatch.setattr(requests,"get",forbidden);monkeypatch.setattr(requests,"post",forbidden)
    monkeypatch.setattr(UnifiedJournalStore,"__init__",forbidden);monkeypatch.setattr(UnifiedJournalStore,"recover",forbidden)
    monkeypatch.setattr(stores,"persist_taskgraph",forbidden);monkeypatch.setattr(stores,"recover_persisted_taskgraph",forbidden)
    monkeypatch.setattr(provider,"execute_openai_answer",forbidden)
    p=build(**args);health=snapshot(p);item=board(p)
    assert health["integrity_state"]=="OK" and item["state"]=="CONFIRMED"
    assert all(health[key] is False for key in ("execution_allowed","external_action_executed","executes_provider_call","executes_billing","real_orders_enabled"))


@pytest.mark.parametrize("expiry",[None,"",True,1])
def test_invalid_expiry_is_unverified_not_coerced_or_crashed(expiry):
    args=evidence();args["checkpoint_evidence"]=replace(args["checkpoint_evidence"],temporal={"expires_at":expiry})
    p=build(**args)
    assert p["checkpoint_status"] not in POSITIVE


def test_recovery_report_boolean_revision_is_not_integer_identity():
    args=evidence();source=args["recovery_evidence"]
    args["recovery_evidence"]=replace(source,value={**source.value,"revision":True})
    assert build(**args)["recovery_status"] not in POSITIVE

@pytest.mark.parametrize("domain",["journal","audit_chain","recovery"])
@pytest.mark.parametrize("field",["owner_id","tenant_id","workspace_id","request_id"])
def test_required_canonical_scope_identity_cannot_be_omitted(domain,field):
    args=evidence();source=args[domain+"_evidence"];value=deepcopy(source.value)
    target=value["journal"] if domain=="recovery" else value
    target.pop(field)
    args[domain+"_evidence"]=replace(source,value=value)
    assert build(**args)[domain+"_status"] not in POSITIVE

@pytest.mark.parametrize("field",["owner_id","tenant_id","workspace_id"])
def test_counter_source_requires_its_own_scope(field):
    args=evidence();scope=deepcopy(SCOPE);scope.pop(field)
    args["mission_evidence"]=replace(args["mission_evidence"],scope=scope)
    assert build(**args)["counts_verified"] is False


def test_no_temporal_contract_does_not_invent_ttl_or_freshness():
    p=build(**evidence())
    assert p["provenance"]["domains"]["checkpoint"]["freshness"]=="NOT_EVALUATED"
    assert "ttl_seconds" not in p["provenance"]["domains"]["checkpoint"]


def test_structural_health_is_not_cryptographic_origin_attestation():
    # Canonically valid in-memory fixtures are allowed; no authenticated-origin claim.
    p=build(**evidence())
    assert board(p)["state"]=="CONFIRMED"
    assert p["provenance"].get("origin_authenticated") is not True
    assert p["execution_allowed"] is False


@pytest.mark.parametrize("scope",[False,0,DictSubclass(),Hostile()])
def test_expected_scope_is_not_truthiness_coerced(scope):
    args=evidence();args["expected_scope"]=scope
    with pytest.raises((HealthEvidenceError,TypeError)):
        build(**args)
