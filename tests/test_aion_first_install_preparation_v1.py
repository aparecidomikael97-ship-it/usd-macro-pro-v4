"""Offline contract adversarial coverage. All positive results are simulations."""
import ast
from copy import deepcopy
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from atlasquant_aion_first_install_preparation.contracts import (
    MODE, AUTHORITY_FIELDS, BINDING_FIELDS, ContractError, binding, digest,
    production_authority, result,
)
from atlasquant_aion_first_install_preparation.ceremony import prepare_intent, review_ceremony
from atlasquant_aion_first_install_preparation.windows import CONTROLS, review_windows_checks
from atlasquant_aion_first_install_preparation.recovery import review_recovery
from atlasquant_aion_first_install_preparation.governance import COST_CATEGORIES, PRIVACY_CONTROLS, review_governance
from atlasquant_aion_first_install_preparation.plan import DEPENDENCIES, collection_layers, review_evidence_plan

ROOT=Path(__file__).resolve().parents[1]
NOW=1000

def scope():
    return dict(owner_id="fixture-owner",tenant_id="company-a",workspace_id="workspace-a",
                device_id="windows-fixture-a",credential_id="fixture-credential-a",
                repo="fixture/repository",branch="fixture/review",path="data/checkpoint.json",
                resource_id="checkpoint-fixture",artifact_sha256="a"*64,
                operation="INVENTORY_READ_ONLY",permissions=["inventory:read"],policy_generation=3)

def intent():
    return dict(schema="AION_OWNER_DEVICE_INTENT_V1",mode=MODE,binding=scope(),
                request_id="request-fixture-a",nonce="b"*64,not_before=990,expires_at=1100)

def assertion():
    i=intent()
    return dict(schema="AION_OWNER_DEVICE_ASSERTION_FIXTURE_V1",mode=MODE,
                binding_digest=digest(i["binding"]),request_id=i["request_id"],nonce=i["nonce"],
                credential_id="fixture-credential-a",role="OWNER_CEREMONY_FIXTURE",
                decision="APPROVE_THIS_SIMULATION_ONLY",user_presence=True,user_verification=True,
                origin="https://offline-fixture.invalid",rp_id="offline-fixture.invalid",
                issued_at=995,evidence_kind="SIMULATED_NOT_A_SIGNATURE")

def windows():
    return [dict(id=k,binding_digest=digest(scope()),claim="PASS",provenance=MODE,
                 observed_at=990,expires_at=1100) for k in CONTROLS]

def heads():
    base=dict(mode=MODE,binding_digest=digest(scope()),operation_id="operation-fixture",
              request_digest="c"*64,epoch=3,sequence=12,snapshot_digest="d"*64,
              previous_digest="e"*64,nonce="f"*64,observed_at=995,
              outcome="SIMULATED_CAUSAL_EFFECT_FOUND",causal_effect_digest="1"*64)
    return [{**base,"domain_id":"fixture-coordinator","credential_id":"fixture-key-a"},
            {**base,"domain_id":"fixture-anchor","credential_id":"fixture-key-b"}]

def governance():
    return dict(mode=MODE,binding_digest=digest(scope()),
                subject=dict(user_id="member-a",tenant_id="company-a",workspace_id="workspace-a",role="MEMBER_FIXTURE",permissions=["inventory:read"]),
                resource=dict(resource_id="checkpoint-fixture",tenant_id="company-a",workspace_id="workspace-a",required_permission="inventory:read"),
                costs=[dict(category=k,currency="BRL",monthly_cents=1000,provenance=MODE,expires_at=1100) for k in COST_CATEGORIES],
                privacy={k:"SIMULATED_REVIEW" for k in PRIVACY_CONTROLS})

class NoAuthorityCase(unittest.TestCase):
    def check_no_authority(self,out):
        self.assertEqual(out["status"],"HARD_NO_GO")
        for flag in AUTHORITY_FIELDS:
            self.assertIs(out[flag],False,flag)
        self.assertIs(out["network_called"],False)
        self.assertIs(out["physical_checks_performed"],False)

class CeremonyTests(NoAuthorityCase):
    def call(self,i=None,a=None,**kw):
        args=dict(expected_binding=scope(),now=NOW,revoked_credentials=[],consumed_nonces=[]);args.update(kw)
        out=review_ceremony(intent() if i is None else i,assertion() if a is None else a,**args)
        self.check_no_authority(out);return out
    def test_positive_fixture_is_consistency_not_real_owner(self):
        out=self.call();self.assertTrue(out["simulation_binding_consistent"])
        self.assertEqual(out["state"],"REFERENCE_CEREMONY_CONSISTENT_UNTRUSTED")
    def test_each_binding_field_changed_after_approval_blocks(self):
        for k in BINDING_FIELDS:
            with self.subTest(field=k):
                i=intent();v=i["binding"][k]
                i["binding"][k]=["other:permission"] if k=="permissions" else v+1 if type(v) is int else "z"*64 if k=="artifact_sha256" else v+"-changed"
                self.assertEqual(self.call(i=i)["state"],"BLOCKED")
    def test_admin_owner_string_or_synthetic_signature_never_real(self):
        for role in ("ADMIN","HUMAN_OWNER","OWNER",None,True):
            with self.subTest(role=role):
                a=assertion();a["role"]=role;self.assertEqual(self.call(a=a)["state"],"BLOCKED")
    def test_fixture_claiming_real_signature_blocked(self):
        for kind in ("REAL","WEBAUTHN_VERIFIED","ED25519_VERIFIED","SELF_ATTESTED",None):
            a=assertion();a["evidence_kind"]=kind
            with self.subTest(kind=kind):self.assertEqual(self.call(a=a)["state"],"BLOCKED")
    def test_wrong_tenant_and_device_block(self):
        for k in ("owner_id","tenant_id","workspace_id","device_id","credential_id"):
            b=scope();b[k]="another-fixture"
            with self.subTest(k=k):self.assertEqual(self.call(expected_binding=b)["state"],"BLOCKED")
    def test_re_signed_changed_resource_not_same_approval(self):
        i=intent();i["binding"]["artifact_sha256"]="9"*64
        a=assertion();a["binding_digest"]=digest(i["binding"])
        self.assertEqual(self.call(i=i,a=a)["state"],"BLOCKED")
    def test_outside_scope_operations_and_permissions_block(self):
        for op in ("INSTALL","DEPLOY","MERGE","ACTIVATE_WORKER","SPEND"):
            i=intent();i["binding"]["operation"]=op
            with self.subTest(op=op):self.assertEqual(self.call(i=i)["state"],"BLOCKED")
    def test_consent_expired_at_exact_boundary(self):
        self.assertEqual(self.call(now=1100)["state"],"BLOCKED")
    def test_consent_not_yet_valid(self):self.assertEqual(self.call(now=989)["state"],"BLOCKED")
    def test_revoked_credential(self):self.assertEqual(self.call(revoked_credentials=["fixture-credential-a"])["state"],"BLOCKED")
    def test_missing_revocation_or_nonce_history_is_unknown(self):
        for k in ("revoked_credentials","consumed_nonces"):
            with self.subTest(k=k):self.assertEqual(self.call(**{k:None})["state"],"BLOCKED")
    def test_nonce_replay(self):self.assertEqual(self.call(consumed_nonces=["b"*64])["state"],"BLOCKED")
    def test_unknown_consent_decision(self):
        a=assertion();a["decision"]="UNKNOWN";self.assertEqual(self.call(a=a)["state"],"BLOCKED")
    def test_presence_and_verification_require_exact_true(self):
        for k in ("user_presence","user_verification"):
            for v in (False,1,"true",None):
                a=assertion();a[k]=v
                with self.subTest(k=k,v=v):self.assertEqual(self.call(a=a)["state"],"BLOCKED")
    def test_rp_origin_time_request_digest_nonce_conflicts(self):
        for k,v in {"rp_id":"attacker.invalid","origin":"https://attacker.invalid","issued_at":1001,"request_id":"other-request","nonce":"d"*64,"binding_digest":"0"*64,"credential_id":"other-key"}.items():
            a=assertion();a[k]=v
            with self.subTest(k=k):self.assertEqual(self.call(a=a)["state"],"BLOCKED")
    def test_unknown_or_missing_fields_are_closed(self):
        for container in (intent(),assertion()):
            container["owner_approved"]=True
            self.assertEqual(self.call(i=container if "binding" in container else None,a=container if "binding" not in container else None)["state"],"BLOCKED")
    def test_expiry_integer_bounds_and_nonce_bounds(self):
        for k,v in {"expires_at":1200,"not_before":True,"nonce":"0"*64,"request_id":"x"*121}.items():
            i=intent();i[k]=v
            with self.subTest(k=k):self.assertEqual(self.call(i=i)["state"],"BLOCKED")
    def test_permission_collections_are_bounded_and_not_generators(self):
        for value in (["read"]*17,("read" for _ in range(2)),["read","read"]):
            i=intent();i["binding"]["permissions"]=value
            self.assertEqual(self.call(i=i)["state"],"BLOCKED")
    def test_windows_alias_traversal_and_url_not_resource_path(self):
        for path in ("../data","C:/data","a\\b","/absolute","a//b","a/../b","a/./b","https://fixture/x","a:stream","a/NUL.txt","CON","data/file.","COM1","LPT9"):
            i=intent();i["binding"]["path"]=path
            with self.subTest(path=path):self.assertEqual(self.call(i=i)["state"],"BLOCKED")
    def test_prepared_intent_owns_permission_copy(self):
        i=intent();p=prepare_intent(i);i["binding"]["permissions"].append("write")
        self.assertEqual(p["binding"]["permissions"],["inventory:read"])
    def test_outputs_do_not_echo_secrets(self):
        a=assertion();a["credential_id"]="SECRET_SENTINEL_492"
        self.assertNotIn("SECRET_SENTINEL_492",json.dumps(self.call(a=a)))

class WindowsPreparationTests(NoAuthorityCase):
    def call(self,rows,**kw):
        args=dict(expected_binding=scope(),now=NOW);args.update(kw)
        out=review_windows_checks(rows,**args);self.check_no_authority(out);return out
    def test_all_pass_simulation_is_not_physical_readiness(self):
        out=self.call(windows());self.assertEqual(out["state"],"REFERENCE_CHECKLIST_CONSISTENT_UNTRUSTED")
        self.assertEqual(out["physical_control_count_verified"],0)
    def test_each_unknown_remains_unknown(self):
        for idx in range(len(CONTROLS)):
            rows=windows();rows[idx]["claim"]="UNKNOWN"
            with self.subTest(control=CONTROLS[idx]):
                out=self.call(rows);self.assertEqual(out["state"],"BLOCKED");self.assertIn(CONTROLS[idx],out["unknown_controls"])
    def test_each_failure_is_not_hidden(self):
        for idx in range(len(CONTROLS)):
            rows=windows();rows[idx]["claim"]="FAIL"
            with self.subTest(control=CONTROLS[idx]):self.assertIn(CONTROLS[idx],self.call(rows)["failed_controls"])
    def test_claimed_bitlocker_tpm_or_hello_real_evidence_rejected(self):
        rows=windows();rows[0]["provenance"]="PHYSICALLY_VERIFIED";self.assertEqual(self.call(rows)["state"],"BLOCKED")
    def test_stale_or_future_controls(self):
        for k,v in (("expires_at",1000),("observed_at",1001)):
            rows=windows();rows[0][k]=v;self.assertEqual(self.call(rows)["state"],"BLOCKED")
    def test_duplicate_missing_or_extra_control(self):
        rows=windows();rows[-1]=deepcopy(rows[0])
        for v in (rows,windows()[:-1],windows()+[windows()[0]],iter(windows())):
            self.assertEqual(self.call(v)["state"],"BLOCKED")
    def test_wrong_scope_and_closed_row(self):
        rows=windows();rows[0]["binding_digest"]="0"*64;self.assertEqual(self.call(rows)["state"],"BLOCKED")
        rows=windows();rows[0]["private_key"]="SECRET";self.assertEqual(self.call(rows)["state"],"BLOCKED")
    def test_unknown_provenance_cannot_promote_pass(self):
        rows=windows();rows[0]["provenance"]="UNKNOWN";self.assertEqual(self.call(rows)["state"],"BLOCKED")

class RecoveryTests(NoAuthorityCase):
    def call(self,h=None,**kw):
        args=dict(expected_binding=scope(),operation_id="operation-fixture",request_digest="c"*64,nonce="f"*64,
                  floor=dict(epoch=3,sequence=11,snapshot_digest="e"*64),now=NOW,
                  revoked_credentials=[],consumed_nonces=[]);args.update(kw)
        out=review_recovery(heads() if h is None else h,**args);self.check_no_authority(out);return out
    def test_two_heads_only_reference_causal_match(self):
        out=self.call();self.assertTrue(out["simulation_causal_match"]);self.assertTrue(out["needs_independent_reconciliation"])
    def test_unknown_timeout_404_presence_or_not_found_never_retry(self):
        for outcome in ("UNKNOWN_OUTCOME","HTTP_404","TIMEOUT","ALREADY_PRESENT","NOT_FOUND","SAVED","UNKNOWN"):
            h=heads();h[0]["outcome"]=outcome;h[1]["outcome"]=outcome
            with self.subTest(outcome=outcome):self.assertEqual(self.call(h)["state"],"BLOCKED")
    def test_absent_external_head(self):self.assertEqual(self.call([])["state"],"BLOCKED")
    def test_partial_commit_domain_disagreement(self):
        for k,v in (("sequence",11),("snapshot_digest","2"*64),("causal_effect_digest","3"*64)):
            h=heads();h[1][k]=v;self.assertEqual(self.call(h)["state"],"BLOCKED")
    def test_fork_or_altered_checkpoint(self):
        h=heads();h[0]["previous_digest"]="7"*64;self.assertEqual(self.call(h)["state"],"BLOCKED")
    def test_floor_snapshot_fork(self):
        h=heads()
        for row in h:row["sequence"]=11
        self.assertEqual(self.call(h)["state"],"BLOCKED")
    def test_rollback_backup_below_floor(self):
        h=heads()
        for row in h:row["sequence"]=10
        self.assertEqual(self.call(h)["state"],"BLOCKED")
    def test_older_or_new_epoch_requires_separate_recovery(self):
        for epoch in (2,4):
            h=heads()
            for row in h:row["epoch"]=epoch
            self.assertEqual(self.call(h)["state"],"BLOCKED")
    def test_same_head_at_floor_is_local_observation_only(self):
        h=heads()
        for row in h:row["sequence"]=11;row["snapshot_digest"]="e"*64
        self.assertEqual(self.call(h)["state"],"REFERENCE_CAUSAL_MATCH_UNTRUSTED")
    def test_large_sequence_jump_requires_history(self):
        h=heads()
        for row in h:row["sequence"]=13
        self.assertEqual(self.call(h)["state"],"BLOCKED")
    def test_replayed_challenge(self):self.assertEqual(self.call(consumed_nonces=["f"*64])["state"],"BLOCKED")
    def test_revoked_and_missing_revocation_state(self):
        self.assertEqual(self.call(revoked_credentials=["fixture-key-b"])["state"],"BLOCKED")
        self.assertEqual(self.call(revoked_credentials=None)["state"],"BLOCKED")
    def test_autoreferred_witness_or_same_credentials(self):
        for k in ("domain_id","credential_id"):
            h=heads();h[1][k]=h[0][k];self.assertEqual(self.call(h)["state"],"BLOCKED")
    def test_freshness_exact_boundary_and_future(self):
        for observed in (940,1001):
            h=heads();h[0]["observed_at"]=observed;self.assertEqual(self.call(h)["state"],"BLOCKED")
    def test_each_causal_or_scope_field_mutation(self):
        for k in ("binding_digest","operation_id","request_digest","nonce"):
            h=heads();h[0][k]="a"*64
            with self.subTest(field=k):self.assertEqual(self.call(h)["state"],"BLOCKED")
    def test_false_counter_boolean_or_synthetic_real_claim(self):
        h=heads();h[0]["sequence"]=True;self.assertEqual(self.call(h)["state"],"BLOCKED")
        h=heads();h[0]["mode"]="PRODUCTION";self.assertEqual(self.call(h)["state"],"BLOCKED")
    def test_extra_receipt_authority_claim_is_closed(self):
        h=heads();h[0]["signature_verified"]=True;self.assertEqual(self.call(h)["state"],"BLOCKED")

class GovernanceTests(NoAuthorityCase):
    def call(self,p=None,**kw):
        args=dict(expected_binding=scope(),now=NOW);args.update(kw)
        out=review_governance(governance() if p is None else p,**args);self.check_no_authority(out);return out
    def test_consolidated_simulation_never_quote_or_spend_approval(self):
        out=self.call();self.assertEqual(out["state"],"REFERENCE_GOVERNANCE_CONSISTENT_UNTRUSTED")
        self.assertEqual(out["simulated_monthly_brl_cents"],11000);self.assertFalse(out["full_quote_brl_verified"])
    def test_a_to_b_user_or_resource_access_denied(self):
        for where in ("subject","resource"):
            for k in ("tenant_id","workspace_id"):
                p=governance();p[where][k]="company-b"
                with self.subTest(where=where,k=k):self.assertEqual(self.call(p)["state"],"BLOCKED")
    def test_admin_role_does_not_grant_owner_approval(self):
        p=governance();p["subject"]["role"]="ADMIN_FIXTURE";self.check_no_authority(self.call(p))
    def test_real_owner_role_rejected(self):
        p=governance();p["subject"]["role"]="HUMAN_OWNER";self.assertEqual(self.call(p)["state"],"BLOCKED")
    def test_missing_permissions_and_other_resource(self):
        p=governance();p["subject"]["permissions"]=[];self.assertEqual(self.call(p)["state"],"BLOCKED")
        p=governance();p["resource"]["resource_id"]="other";self.assertEqual(self.call(p)["state"],"BLOCKED")
    def test_each_unknown_cost_and_privacy_never_confirmed(self):
        for i in range(len(COST_CATEGORIES)):
            p=governance();p["costs"][i]["monthly_cents"]=None
            with self.subTest(category=COST_CATEGORIES[i]):
                out=self.call(p);self.assertEqual(out["state"],"BLOCKED");self.assertIsNone(out["simulated_monthly_brl_cents"])
        for k in PRIVACY_CONTROLS:
            p=governance();p["privacy"][k]="UNKNOWN"
            with self.subTest(control=k):self.assertEqual(self.call(p)["state"],"BLOCKED")
    def test_budget_exact_cap_and_over_cap(self):
        p=governance();p["costs"][0]["monthly_cents"]=10000
        self.assertEqual(self.call(p)["state"],"REFERENCE_GOVERNANCE_CONSISTENT_UNTRUSTED")
        p["costs"][0]["monthly_cents"]=10001;self.assertEqual(self.call(p)["state"],"BLOCKED")
    def test_cost_missing_duplicate_and_unbounded(self):
        p=governance();p["costs"]=p["costs"][:-1];self.assertEqual(self.call(p)["state"],"BLOCKED")
        p=governance();p["costs"][-1]=deepcopy(p["costs"][0]);self.assertEqual(self.call(p)["state"],"BLOCKED")
    def test_invalid_bool_amount_currency_and_stale_quote(self):
        for k,v in (("monthly_cents",True),("currency","USD"),("expires_at",1000),("provenance","VERIFIED")):
            p=governance();p["costs"][0][k]=v;self.assertEqual(self.call(p)["state"],"BLOCKED")
    def test_self_declared_lgpd_compliance_is_not_legal_approval(self):
        p=governance();p["privacy"][PRIVACY_CONTROLS[0]]="LGPD_COMPLIANT";self.assertEqual(self.call(p)["state"],"BLOCKED")
    def test_no_result_or_mutation_shared_between_sessions(self):
        p=governance();before=deepcopy(p);out=self.call(p);out["spending_approved"]=True
        self.assertEqual(p,before);self.assertFalse(self.call(p)["spending_approved"])

class PlanBoundaryTests(NoAuthorityCase):
    def manifest(self):return json.loads((ROOT/'docs/aion/evidence/AION_WITNESS_EXTERNAL_ENROLLMENT_GATE_V1.json').read_text(encoding='utf-8'))
    def test_real_manifest_twenty_stay_blocked(self):
        out=review_evidence_plan(self.manifest());self.check_no_authority(out)
        self.assertEqual(out["state"],"REFERENCE_COLLECTION_PLAN_UNTRUSTED");self.assertEqual(out["unresolved_gate_count"],20)
    def test_dependency_dag_covers_twenty_without_bootstrap_circle(self):
        done=set()
        for layer in collection_layers():
            for k in layer:self.assertLessEqual(set(DEPENDENCIES[k]),done)
            done.update(layer)
        self.assertEqual(len(done),20);self.assertEqual(set(DEPENDENCIES),done)
    def test_dependency_cycle_rejected_not_silently_ready(self):
        with patch.dict(DEPENDENCIES,{"OWNER_IDENTITY_CEREMONY":("SOURCE_ROOT_ENROLLMENT",)}):
            with self.assertRaises(ValueError):collection_layers()
    def test_oversized_or_generator_evidence_not_materialized(self):
        for rows in ([{}]*21,iter([{}]*20)):
            m=self.manifest();m["evidence_gates"]=rows
            self.assertEqual(review_evidence_plan(m)["state"],"BLOCKED")
    def test_duplicate_omission_extra_field_and_false_receipt(self):
        m=self.manifest();m["evidence_gates"][-1]=deepcopy(m["evidence_gates"][0]);self.assertEqual(review_evidence_plan(m)["state"],"BLOCKED")
        m=self.manifest();m["owner_override"]=True;self.assertEqual(review_evidence_plan(m)["state"],"BLOCKED")
        m=self.manifest();m["evidence_gates"][0]["evidence_uri"]="SECRET_PRIVATE_URI";out=review_evidence_plan(m)
        self.assertEqual(out["state"],"BLOCKED");self.assertNotIn("SECRET_PRIVATE_URI",json.dumps(out))
    def test_every_forged_verified_evidence_never_go(self):
        m=self.manifest()
        for row in m["evidence_gates"]:row["state"]="VERIFIED"
        out=review_evidence_plan(m);self.check_no_authority(out);self.assertEqual(out["state"],"BLOCKED")

class PhysicalAuthorityFirewallTests(NoAuthorityCase):
    def test_non_json_scalars_cannot_execute_implicit_callbacks(self):
        class Bomb:
            def __eq__(self,_):raise AssertionError('IMPLICIT_CALLBACK_FORBIDDEN')
            def __ne__(self,_):raise AssertionError('IMPLICIT_CALLBACK_FORBIDDEN')
            def __hash__(self):raise AssertionError('IMPLICIT_CALLBACK_FORBIDDEN')
        a=assertion();a['mode']=Bomb()
        w=windows();w[0]['binding_digest']=Bomb()
        h=heads();h[0]['outcome']=Bomb()
        g=governance();g['privacy'][PRIVACY_CONTROLS[0]]=Bomb()
        m=PlanBoundaryTests().manifest();m['status']=Bomb()
        calls=[lambda:CeremonyTests().call(a=a),lambda:WindowsPreparationTests().call(w),
               lambda:RecoveryTests().call(h),lambda:GovernanceTests().call(g),lambda:review_evidence_plan(m)]
        for i,call in enumerate(calls):
            with self.subTest(boundary=i):self.assertEqual(call()['state'],'BLOCKED')
    def test_arbitrary_values_environment_and_callbacks_never_unlock(self):
        callback=unittest.mock.Mock(side_effect=AssertionError('MUST_NOT_CALL'))
        with patch.dict(os.environ,{"AION_FIRST_INSTALL_GO":"true","ATLASQUANT_AION_GLOBAL_WORKER_ENABLED":"true"}):
            for v in ({"role":"HUMAN_OWNER","verified":True},assertion(),"GO",object(),None):
                self.check_no_authority(production_authority(v,verifier=callback))
        callback.assert_not_called()
    def test_every_positive_reference_cannot_enter_production(self):
        for out in (result("REFERENCE_MATCH"),{"installation_authorized":True,"signature":"fabricated"}):
            self.assertEqual(production_authority(out)["state"],"BLOCKED")
    def test_fixed_result_authority_fields_cannot_be_overridden(self):
        out=result("REFERENCE_MATCH",**{k:True for k in AUTHORITY_FIELDS});self.check_no_authority(out)
    def test_status_provenance_and_observation_flags_cannot_be_overridden(self):
        out=result("REFERENCE_MATCH",status="FIRST_INSTALL_GO",mode="PRODUCTION",schema="REAL",
                   provenance="INDEPENDENTLY_VERIFIED",network_called=True,physical_checks_performed=True,
                   real_credentials_created=True)
        self.check_no_authority(out);self.assertEqual(out['mode'],MODE)
        self.assertEqual(out['provenance'],'SIMULATED_OR_UNKNOWN_NOT_INDEPENDENT_EVIDENCE')
        self.assertIs(out['real_credentials_created'],False)
    def test_offline_flows_cannot_call_network(self):
        with patch('socket.socket.connect',side_effect=AssertionError('NO_NETWORK')),patch('socket.socket.connect_ex',side_effect=AssertionError('NO_NETWORK')):
            self.check_no_authority(review_evidence_plan(PlanBoundaryTests().manifest()))
            self.check_no_authority(production_authority())
            self.assertEqual(CeremonyTests().call()["state"],"REFERENCE_CEREMONY_CONSISTENT_UNTRUSTED")
    def test_module_imports_have_no_device_or_network_execution_paths(self):
        forbidden={"os","subprocess","socket","ctypes","winreg","requests","urllib","sqlite3"}
        for p in (ROOT/'atlasquant_aion_first_install_preparation').glob('*.py'):
            tree=ast.parse(p.read_text(encoding='utf-8'))
            imports={n.name.split('.')[0] for a in ast.walk(tree) if isinstance(a,ast.Import) for n in a.names}
            imports|={a.module.split('.')[0] for a in ast.walk(tree) if isinstance(a,ast.ImportFrom) and a.module}
            with self.subTest(file=p.name):self.assertFalse(imports&forbidden)

if __name__=='__main__':unittest.main()
