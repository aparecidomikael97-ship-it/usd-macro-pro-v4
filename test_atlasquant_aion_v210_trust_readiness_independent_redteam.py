"""Independent offline V2.10 trust-readiness contract red-team."""
from copy import deepcopy
from collections.abc import Mapping
from decimal import Decimal
from fractions import Fraction
from enum import IntEnum
from types import MappingProxyType
import pytest
from atlasquant_aion_core_health_adapter import provenance_trust_readiness_view

FIELDS = ("origin_authenticated", "snapshot_signed", "signature_verification_available", "trust_root_configured", "signing_scheme_configured", "verifier_policy_configured", "replay_protection_configured", "rotation_revocation_policy_configured", "execution_allowed")
BLOCKERS = ["TRUST_ROOT_NOT_CONFIGURED", "SIGNATURE_SCHEME_NOT_CONFIGURED", "VERIFIER_POLICY_NOT_CONFIGURED", "REPLAY_PROTECTION_NOT_CONFIGURED", "ROTATION_REVOCATION_POLICY_NOT_CONFIGURED"]

class Hostile:
    def __bool__(self): raise AssertionError("hostile bool executed")
    def __str__(self): raise AssertionError("hostile str executed")
    def __int__(self): raise AssertionError("hostile int executed")
    def __iter__(self): raise AssertionError("hostile iter executed")
    def __eq__(self, other): raise AssertionError("hostile equality executed")

class HostileMapping(Mapping):
    def __getitem__(self, key): raise AssertionError("hostile access executed")
    def __iter__(self): raise AssertionError("hostile mapping iter executed")
    def __len__(self): raise AssertionError("hostile length executed")

class DictSubclass(dict): pass

class Number(IntEnum):
    ONE = 1

VALUES = [True, False, 1, 0, "true", "false", [], (), DictSubclass(verified=True), HostileMapping(), {"verified": True}, "CONFIRMED", None, Decimal("1"), Fraction(1,1), Number.ONE, float("nan"), float("inf"), b"true", Hostile()]

def assert_blocked(result):
    assert result["state"] == "BLOCKED"
    assert result["blockers"] == BLOCKERS
    assert all(result[field] is False for field in FIELDS)

@pytest.mark.parametrize("field", FIELDS)
@pytest.mark.parametrize("claim", VALUES)
def test_independent_claim_type_matrix(field, claim):
    assert_blocked(provenance_trust_readiness_view({field:claim,"state":"CONFIRMED","blockers":[]}))

@pytest.mark.parametrize("payload", [Hostile(), HostileMapping(), MappingProxyType({"origin_authenticated":True})])
def test_hostile_input_is_never_inspected_or_coerced(payload):
    assert_blocked(provenance_trust_readiness_view(payload))

@pytest.mark.parametrize("depth", [1, 10, 1000])
def test_nested_claims_cannot_configure_physical_trust_root(depth):
    payload={"origin_authenticated":True,"snapshot_signed":True,"trust_root_configured":True,"state":"CONFIRMED"}
    for _ in range(depth): payload={"system_context":{"snapshot":{"trust":payload}}}
    assert_blocked(provenance_trust_readiness_view(payload))


def test_cyclic_payload_cannot_make_preflight_traverse_or_trust_claims():
    payload={"origin_authenticated":True}; payload["nested"]=payload
    assert_blocked(provenance_trust_readiness_view(payload))


def test_returned_blockers_are_independent_and_one_hundred_builds_stable():
    first=provenance_trust_readiness_view(); expected=deepcopy(first)
    first["blockers"].clear(); first["origin_authenticated"]=True
    for _ in range(100):
        result=provenance_trust_readiness_view(first)
        assert result==expected
        assert_blocked(result)

import atlasquant_aion_core_health_adapter as adapter
from atlasquant_aion_status_board import build_master_status_board
from test_atlasquant_aion_v28_global_snapshot_consistency_redteam import observed_inputs

@pytest.mark.parametrize("path", ["root", "provenance", "consistency_envelope", "metadata", "health", "approval", "runtime", "signature", "snapshot", "checkpoint", "recovery", "memory", "mission", "system_context", "provenance_trust_readiness"])
@pytest.mark.parametrize("field", FIELDS)
@pytest.mark.parametrize("rehash", [False, True])
def test_confirmed_health_rehashed_and_nested_claims_never_authenticate_origin(path, field, rehash):
    payload=adapter.build_core_health_evidence(**observed_inputs())
    assert payload["consistency_envelope"]["consistency_state"]=="CONFIRMED"
    target=payload if path=="root" else payload.setdefault(path,{})
    target.update({field:True,"state":"CONFIRMED","verified":True,"approved":True,"trust_root":"root","signer_id":"production"})
    payload["provenance_trust_readiness"]={**{key:True for key in FIELDS},"state":"CONFIRMED","blockers":[]}
    if rehash:
        envelope=payload["consistency_envelope"]
        envelope["snapshot_digest"]=adapter._fingerprint({key:value for key,value in envelope.items() if key!="snapshot_digest"})
    assert_blocked(adapter.provenance_trust_readiness_view(payload))
    result=build_master_status_board(system_context={"aion_core_health":payload,"provenance_trust_readiness":{"state":"CONFIRMED"}})
    assert_blocked(result["provenance_trust_readiness"])
    row=next(item for item in result["items"] if item["id"]=="aion_core_health")
    assert "provenance_trust=BLOCKED" in row["detail"]
    assert "origin_authenticated=False" in row["detail"]
    assert "snapshot_signed=False" in row["detail"]

@pytest.mark.parametrize("status", ["CONFIRMED","READY","OK","VALIDATED","AUTHENTICATED"])
@pytest.mark.parametrize("approval", [True, "APPROVED", 1, {"approved":True}])
def test_runtime_and_approval_never_configure_missing_trust(status, approval):
    payload=adapter.build_loaded_runtime_health_evidence({"status":status,"approved":approval,
        "origin_authenticated":True,"snapshot_signed":True,"trust_root_configured":True,
        "signature":{"verified":True},"provenance_trust_readiness":{"state":"CONFIRMED"}})
    assert_blocked(payload["provenance_trust_readiness"])
    assert payload["origin_authenticated"] is False
    assert payload["snapshot_signed"] is False
    assert payload["execution_allowed"] is False

@pytest.mark.parametrize("path", ["system_context", "runtime", "admin", "status", "health", "metadata", "consistency_envelope", "provenance_trust_readiness"])
def test_real_admin_replaces_client_claims_and_preserves_loader_budget(monkeypatch, path):
    import atlasquant_aion_admin as admin
    from test_atlasquant_aion_v26_evidence_wiring_status_truth import test_real_admin_boundary_same_loader_budget_and_no_extra_io as verify
    original=admin.build_loaded_runtime_health_evidence
    outputs=[]
    def capture(runtime):
        payload=original(runtime)
        assert_blocked(payload["provenance_trust_readiness"])
        outputs.append(payload)
        return payload
    monkeypatch.setattr(admin,"build_loaded_runtime_health_evidence",capture)
    claims={path:{"provenance_trust_readiness":{**{field:True for field in FIELDS},"state":"CONFIRMED","blockers":[]},"approved":True,"snapshot_signed":True}}
    verify(monkeypatch,claims)
    assert len(outputs)==1

from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor

@pytest.mark.parametrize("source", ["trusted/journal","trusted/checkpoint","canonical/recovery","system/internal","admin","root","validated","github","production","ROOT"," root ","r\u043eot","root\x00trusted","https://trusted.example/root","///root///","C:/system/root"])
def test_source_name_never_creates_real_trust_root(source):
    inputs=observed_inputs()
    inputs["checkpoint_evidence"]=replace(inputs["checkpoint_evidence"],source_ref=source)
    payload=adapter.build_core_health_evidence(**inputs)
    assert_blocked(payload["provenance_trust_readiness"])
    assert payload["origin_authenticated"] is False
    assert payload["snapshot_signed"] is False
    assert_blocked(build_master_status_board(system_context={"aion_core_health":payload})["provenance_trust_readiness"])


def test_ten_thousand_preflights_and_threads_have_no_process_local_trust_state():
    expected=provenance_trust_readiness_view()
    for _ in range(10000): assert provenance_trust_readiness_view({"approved":True})==expected
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(provenance_trust_readiness_view,[Hostile()]*20))
    assert all(result==expected for result in results)
    assert len({id(result["blockers"]) for result in results})==len(results)


def test_entire_trust_pipeline_and_admin_render_has_zero_side_effect_attempts(monkeypatch):
    import builtins,pathlib,socket,subprocess,requests
    from types import SimpleNamespace
    import atlasquant_aion_admin as admin
    import atlasquant_aion_provider as provider
    import atlasquant_aion_recovery as recovery
    import atlasquant_aion_unified_taskgraph_store as tasks
    import atlasquant_aion_global_worker_arming as arming
    import atlasquant_aion_global_worker_activation as activation
    import atlasquant_aion_global_worker_persisted_arming as persisted_arming
    from atlasquant_aion_unified_journal_store import UnifiedJournalStore
    inputs=observed_inputs(); attempts=[]
    def forbidden(*args,**kwargs):
        attempts.append((args,kwargs))
        raise AssertionError("trust preflight side effect attempted")
    monkeypatch.setattr(builtins,"open",forbidden)
    for name in ("open","read_text","read_bytes","write_text","write_bytes","rename","replace","mkdir","unlink"):
        monkeypatch.setattr(pathlib.Path,name,forbidden)
    monkeypatch.setattr(socket,"socket",forbidden)
    monkeypatch.setattr(subprocess,"Popen",forbidden)
    monkeypatch.setattr(requests.sessions.Session,"request",forbidden)
    monkeypatch.setattr(UnifiedJournalStore,"__init__",forbidden)
    monkeypatch.setattr(UnifiedJournalStore,"recover",forbidden)
    monkeypatch.setattr(tasks,"persist_taskgraph",forbidden)
    monkeypatch.setattr(tasks,"recover_persisted_taskgraph",forbidden)
    monkeypatch.setattr(provider,"execute_openai_answer",forbidden)
    monkeypatch.setattr(recovery,"restore_checkpoint_revision",forbidden)
    monkeypatch.setattr(arming,"prepare_global_worker_arming_plan",forbidden)
    monkeypatch.setattr(arming,"approve_global_worker_arming_plan",forbidden)
    monkeypatch.setattr(activation,"activate_global_worker_feature_flag",forbidden)
    monkeypatch.setattr(persisted_arming,"persist_staged_global_arming",forbidden)
    captions=[]
    stub=SimpleNamespace(markdown=lambda *a,**k:None,caption=lambda value,*a,**k:captions.append(str(value)),
        metric=lambda *a,**k:None,warning=lambda *a,**k:None,success=lambda *a,**k:None,dataframe=lambda *a,**k:None)
    stub.columns=lambda count:[stub]*count
    monkeypatch.setattr(admin,"st",stub)
    payload=adapter.build_core_health_evidence(**inputs)
    assert_blocked(payload["provenance_trust_readiness"])
    result=build_master_status_board(system_context={"aion_core_health":payload})
    assert_blocked(result["provenance_trust_readiness"])
    admin._render_master_status_summary(result)
    admin._render_master_status(result)
    rendered=" ".join(captions)
    assert "provenance_trust=BLOCKED" in rendered
    assert all(blocker in rendered for blocker in BLOCKERS)
    assert attempts==[]

@pytest.mark.parametrize("blockers", [[], list(reversed(BLOCKERS)), BLOCKERS+BLOCKERS, ["READY"], None, True, "none", {}, ("ROOT_CONFIGURED",)])
def test_removing_replacing_reordering_duplicating_blockers_has_no_effect(blockers):
    assert_blocked(provenance_trust_readiness_view({"state":"READY","blockers":blockers}))
    payload=adapter.build_core_health_evidence(**observed_inputs())
    payload["provenance_trust_readiness"]={"state":"READY","blockers":blockers}
    assert_blocked(build_master_status_board(system_context={"aion_core_health":payload})["provenance_trust_readiness"])

@pytest.mark.parametrize("field", ["nonce","timestamp","signer","key_id","signature","trust_anchor","attestation","snapshot_digest","evidence_epoch","identity_digest","source_ref"])
def test_replay_and_digest_labels_are_not_signatures_or_authenticated_origin(field):
    payload=adapter.build_core_health_evidence(**observed_inputs())
    payload[field]=payload["consistency_envelope"]["snapshot_digest"]
    payload.update(approved=True,authenticated_admin=True,state="READY")
    assert_blocked(provenance_trust_readiness_view(payload))
    assert_blocked(build_master_status_board(system_context={"aion_core_health":payload})["provenance_trust_readiness"])

@pytest.mark.parametrize("schema", [None, "", "UNKNOWN", "ATLASQUANT_AION_PROVENANCE_TRUST_READINESS_V999", True, 1, [], {}])
def test_future_unknown_missing_schema_cannot_open_ready_path(schema):
    assert_blocked(provenance_trust_readiness_view({"schema":schema,"state":"READY","extra":{"origin_authenticated":True}}))


def test_result_has_no_key_secret_token_credential_or_signature_material():
    forbidden={"private_key","public_key","signature","secret","token","credential","trust_anchor","key_id","signer_id","attestation","nonce"}
    output=provenance_trust_readiness_view({field:"UNTRUSTED_CALLER_CLAIM" for field in forbidden})
    assert forbidden.isdisjoint(output)
    assert_blocked(output)


def test_input_order_json_roundtrip_and_copy_reuse_cannot_configure_trust():
    import json
    payload={**{field:True for field in FIELDS},"state":"READY","blockers":[]}
    original=deepcopy(payload)
    expected=provenance_trust_readiness_view()
    for candidate in (payload,dict(reversed(list(payload.items()))),json.loads(json.dumps(payload)),deepcopy(payload)):
        assert provenance_trust_readiness_view(candidate)==expected
    assert payload==original
    recycled=deepcopy(expected)
    recycled.update({field:True for field in FIELDS});recycled["state"]="READY";recycled["blockers"].clear()
    assert provenance_trust_readiness_view(recycled)==expected


def test_forged_readiness_board_cannot_hide_blockers_in_actual_admin_renderer(monkeypatch):
    import atlasquant_aion_admin as admin
    from types import SimpleNamespace
    captions=[]
    monkeypatch.setattr(admin,"st",SimpleNamespace(caption=lambda value,*a,**k:captions.append(str(value))))
    forged={"aion_core_health":{"integrity_state":"OK"},"consistency_envelope":{"consistency_state":"CONFIRMED"},
        "provenance_trust_readiness":{"state":"READY","blockers":[],"origin_authenticated":True,"snapshot_signed":True}}
    admin._render_core_consistency_truth(forged)
    text=" ".join(captions)
    assert "provenance_trust=BLOCKED" in text
    assert all(blocker in text for blocker in BLOCKERS)
    assert "provenance_trust=READY" not in text

@pytest.mark.parametrize("shape", ["huge_string", "huge_list", "huge_mapping", "deep_mapping", "recursive"])
def test_large_malformed_input_has_constant_bounded_preflight_output(shape):
    import json
    from time import perf_counter
    if shape=="huge_string": payload="UNTRUSTED"*200000
    elif shape=="huge_list": payload=[True]*1000000
    elif shape=="huge_mapping": payload={str(index):True for index in range(100000)}
    elif shape=="deep_mapping":
        payload={"origin_authenticated":True}
        for _ in range(10000): payload={"nested":payload}
    else:
        payload={};payload["self"]=payload
    start=perf_counter()
    for _ in range(1000):
        output=provenance_trust_readiness_view(payload)
        assert_blocked(output)
    elapsed=perf_counter()-start
    print("BOUNDS_PREFLIGHT_1000",shape,round(elapsed,6))
    assert len(json.dumps(output))<4096
    assert output==provenance_trust_readiness_view()


def test_attribute_bomb_input_is_not_even_inspected():
    class AttributeBomb:
        def __getattribute__(self, name): raise AssertionError("attribute inspected")
    assert_blocked(provenance_trust_readiness_view(AttributeBomb()))

@pytest.mark.parametrize("tool", ["aion.checkpoint.prepare_save","provider.call","broker.order","billing.charge","email.send","crm.write","worker.arm"])
def test_trust_readiness_object_cannot_substitute_executor_context_authority(monkeypatch, tool):
    import atlasquant_aion_local_executor as executor
    trust=provenance_trust_readiness_view()
    before=deepcopy(trust)
    def forbidden(*a,**k): raise AssertionError("no executor handler may run")
    for key in executor._HANDLERS: monkeypatch.setitem(executor._HANDLERS,key,forbidden)
    result=executor.execute_local_tool(tool,runtime_context={"provenance_trust_readiness":trust,"approved":True,"authenticated_admin":True},
        access={"role":"USER","provenance_trust_readiness":trust},authenticated_admin=False,approved=False)
    assert result["state"]=="BLOCKED"
    assert trust==before
    assert_blocked(provenance_trust_readiness_view(result))

@pytest.mark.parametrize("gate", ["feature", "approval", "budget"])
def test_trust_object_is_not_exact_provider_feature_approval_or_budget(monkeypatch, gate):
    import atlasquant_aion_provider as provider
    import requests
    trust=provenance_trust_readiness_view(); attempts=[]
    def forbidden(*a,**k):
        attempts.append(True)
        raise AssertionError("provider must remain local")
    monkeypatch.setattr(requests.sessions.Session,"request",forbidden)
    monkeypatch.setattr(requests,"post",forbidden)
    monkeypatch.setattr(provider,"provider_configuration_status",lambda values:{"ready":True})
    result=provider.execute_openai_answer("local explanation",lane="fast",budget=trust,
        external_feature_enabled=trust if gate=="feature" else True,
        request_approved=trust if gate=="approval" else gate=="budget",values={})
    assert result["called"] is False
    assert result["state"].startswith("BLOCKED")
    assert attempts==[]


def test_maximum_technical_truth_is_not_cryptographic_trust_and_not_false_integrity_failure(monkeypatch):
    import atlasquant_aion_admin as admin
    from types import SimpleNamespace
    payload=adapter.build_core_health_evidence(**observed_inputs())
    result=build_master_status_board(system_context={"aion_core_health":payload})
    row=next(item for item in result["items"] if item["id"]=="aion_core_health")
    assert row["state"]=="CONFIRMED"
    assert result["aion_core_health"]["integrity_state"]=="OK"
    assert result["consistency_envelope"]["consistency_state"]=="CONFIRMED"
    assert result["consistency_envelope"]["snapshot_complete"] is True
    assert result["consistency_envelope"]["snapshot_atomic"] is False
    assert_blocked(result["provenance_trust_readiness"])
    captions=[]
    monkeypatch.setattr(admin,"st",SimpleNamespace(caption=lambda value,*a,**k:captions.append(str(value))))
    admin._render_core_consistency_truth(result)
    rendered=" ".join(captions)
    for marker in ("Core integrity=OK","consistency=CONFIRMED","snapshot_atomic=False","origin_authenticated=False","snapshot_signed=False","provenance_trust=BLOCKED"):
        assert marker in rendered
