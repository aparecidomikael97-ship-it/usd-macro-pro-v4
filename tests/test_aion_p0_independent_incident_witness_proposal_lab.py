"""AION P0 independent incident witness proposal LAB — 26 tests.

Never authorizes Worker, feature flag, provider, receipt, automatic retry or
first effect. No crypto enrolment, network, accounts, platform credentials.
Any PASS is a pure, untrusted-fixture *denial*, not H0 readiness.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import unittest

from atlasquant_aion_p0_incident_external_witness_proposal_lab import (
    BLOCKED, CONTROLLERS, NO_GO_FLAGS,
    screen_external_incident_witness_proposal as review,
)
import atlasquant_aion_global_worker_reactivation_gate as gate
import atlasquant_aion_global_worker_activation as activation
import test_atlasquant_aion_global_worker_activation as activation_fixture
import test_atlasquant_aion_global_worker_reactivation_gate as incident_fixture


class IndependentIncidentWitnessContractLAB(unittest.TestCase):
    def setUp(self):
        self.packet={
            "issuer_id":"separate-incident-issuer",
            "key_id":"offline-unenrolled-key-id",
            "scope":"repo/tenant/workspace",
            "head_digest":"a"*64,
            "epoch":12,
            "sequence":455,
            "credential_revocation_epoch":8,
            "nonce":"challenge-nonce-001",
            "incident_state":"NO_OPEN_INCIDENTS",
        }
        self.head={
            key:self.packet[key] for key in (
                "issuer_id","scope","head_digest","epoch","sequence",
                "credential_revocation_epoch",
            )
        }
        self.head["latest_external_version_id"]="synthetic-version-2026"
        self.head["witnessed_nonce"]=self.packet["nonce"]
        self.domains={k:"separate-domain-"+k for k in CONTROLLERS}

    def result(self,packet=None,head=None,domains=None):
        return review(
            self.packet if packet is None else packet,
            self.head if head is None else head,
            self.domains if domains is None else domains,
        )

    def denied(self, result):
        self.assertEqual(result["status"],BLOCKED)
        self.assertIs(result["allowed"],False)
        self.assertTrue(result["blockers"])
        self.assertEqual(result["blockers"],sorted(set(result["blockers"])))
        self.assertEqual(result["reason"],result["blockers"][0] if not result["blockers"] else result["reason"])
        self.assertIn("INDEPENDENT_EXTERNAL_WITNESS_NOT_ENROLLED",result["blockers"])
        self.assertIn("EXTERNAL_SIGNER_AND_REVOCATION_ROOT_NOT_ENROLLED",result["blockers"])
        self.assertIn("LATEST_HEAD_AND_NONCE_REPLAY_PROOF_NOT_ENROLLED",result["blockers"])
        for field in NO_GO_FLAGS:
            self.assertIs(result[field],False,field)
        self.assertIs(result["lab_structural_review_only"],True)

    def test_01_even_perfect_consistent_fixture_is_hard_no_go(self):
        r=self.result()
        self.denied(r)
        self.assertEqual(r["observations"],("CONTROLLERS_CLAIMED_DISTINCT_NOT_VERIFIED",))

    def test_02_claimed_signature_and_external_verifier_flags_are_ignored(self):
        p={**self.packet,**{k:True for k in (
            "signed","verified","issuer_signature_verified",
            "external_authority_verified","source_fresh","no_incident_confirmed")}}
        h={**self.head,**{k:True for k in (
            "readback_authenticated","independent_issuer_verified","latest_head_verified")}}
        r=self.result(p,h)
        self.denied(r)
        self.assertIn("UNTRUSTED_BOOLEAN_SIGNATURE_CLAIMS_IGNORED",r["observations"])
        self.assertIn("UNTRUSTED_READBACK_CLAIMS_IGNORED",r["observations"])

    def test_03_missing_packet_blocked(self):
        r=review(None,self.head,self.domains)
        self.denied(r)
        self.assertIn("PACKET_NOT_PLAIN_DICT",r["blockers"])

    def test_04_missing_independent_head_blocked(self):
        r=review(self.packet,None,self.domains)
        self.denied(r)
        self.assertIn("PINNED_HEAD_NOT_PLAIN_DICT",r["blockers"])

    def test_05_missing_admin_graph_blocked(self):
        r=review(self.packet,self.head,None)
        self.denied(r)
        self.assertIn("TRUST_DOMAINS_NOT_PLAIN_DICT",r["blockers"])

    def test_06_subclass_dict_with_hostile_iteration_is_not_trusted(self):
        class HostileDict(dict):
            def get(self,*args,**kwargs):
                raise RuntimeError("hostile .get")
        for slot in range(3):
            fields=[self.packet,self.head,self.domains]
            fields[slot]=HostileDict(fields[slot])
            with self.subTest(slot=slot):
                self.denied(review(*fields))

    def test_07_invalid_required_fields_explicitly_identified(self):
        for key in self.packet:
            p=dict(self.packet)
            p.pop(key)
            with self.subTest(field=key):
                r=self.result(p)
                self.denied(r)
                self.assertIn("PACKET_MISSING:"+key,r["blockers"])

    def test_08_all_scope_issuer_nonce_ids_require_plain_valid_strings(self):
        for field in ("issuer_id","key_id","nonce","scope"):
            for value in ("",None,True,5,{},"bad key!"):
                with self.subTest(field=field,kind=str(type(value))):
                    p={**self.packet,field:value}
                    r=self.result(p)
                    self.denied(r)
                    self.assertIn("PACKET_INVALID:"+field,r["blockers"])

    def test_09_monotonic_values_never_accept_bool_float_negative_or_overflow(self):
        for field in ("epoch","sequence","credential_revocation_epoch"):
            for value in (True,False,1.0,-1,2**64,"50",None):
                with self.subTest(field=field,value=value):
                    self.denied(self.result({**self.packet,field:value}))
                    self.assertIn("PACKET_INVALID:"+field,
                                  self.result({**self.packet,field:value})["blockers"])

    def test_10_incorrect_digest_uppercase_short_and_nonhex_blocked(self):
        for value in ("B"*64,"abc","g"*64,True,b"a"*64,None):
            with self.subTest(value=repr(value)[:35]):
                r=self.result({**self.packet,"head_digest":value})
                self.denied(r)
                self.assertIn("PACKET_INVALID:head_digest",r["blockers"])

    def test_11_open_incident_is_explicitly_not_safe(self):
        p={**self.packet,"incident_state":"OPEN_INCIDENT"}
        r=self.result(p)
        self.denied(r)
        self.assertIn("INCIDENT_STATE_UNSAFE_OR_UNKNOWN",r["blockers"])

    def test_12_unknown_incident_state_is_explicitly_not_safe(self):
        p={**self.packet,"incident_state":"UNKNOWN"}
        r=self.result(p)
        self.denied(r)
        self.assertIn("INCIDENT_STATE_UNSAFE_OR_UNKNOWN",r["blockers"])

    def test_13_self_reported_no_incident_not_an_external_absence_proof(self):
        r=self.result()
        self.denied(r)
        self.assertIs(r["fresher_incident_absence_verified"],False)

    def test_14_wrong_issuer_rejected_by_claimed_pinned_head(self):
        p={**self.packet,"issuer_id":"wrong-signer-from-attacker"}
        r=self.result(p)
        self.denied(r)
        self.assertIn("HEAD_MISMATCH:issuer_id",r["blockers"])

    def test_15_wrong_scope_tenant_repo_branch_denied(self):
        for value in ("other-tenant/workspace","other-repo/main","other-branch"):
            with self.subTest(scope=value):
                self.denied(self.result({**self.packet,"scope":value}))
                self.assertIn("HEAD_MISMATCH:scope",
                              self.result({**self.packet,"scope":value})["blockers"])

    def test_16_rollback_epoch_or_sequence_mismatch(self):
        for field,stale in (("epoch",11),("sequence",454)):
            with self.subTest(field=field):
                r=self.result({**self.packet,field:stale})
                self.denied(r)
                self.assertIn("HEAD_MISMATCH:"+field,r["blockers"])

    def test_17_revocation_generation_mismatch_no_authority(self):
        r=self.result({**self.packet,"credential_revocation_epoch":7})
        self.denied(r)
        self.assertIn("CREDENTIAL_REVOCATION_EPOCH_MISMATCH",r["blockers"])

    def test_18_head_replaced_digest_fork_detected_as_shape_mismatch(self):
        r=self.result({**self.packet,"head_digest":"b"*64})
        self.denied(r)
        self.assertIn("HEAD_MISMATCH:head_digest",r["blockers"])

    def test_19_nonce_reuse_or_unbound_nonce_not_treated_as_fresh(self):
        r=self.result({**self.packet,"nonce":"stale-replayed-nonce"})
        self.denied(r)
        self.assertIn("NONCE_NOT_BOUND_TO_HEAD",r["blockers"])

    def test_20_witness_readback_missing_version_or_nonce(self):
        for field in ("latest_external_version_id","witnessed_nonce"):
            h=dict(self.head)
            h.pop(field)
            with self.subTest(field=field):
                r=self.result(head=h)
                self.denied(r)
                self.assertIn("LATEST_HEAD_READBACK_MISSING:"+field,r["blockers"])

    def test_21_same_admin_for_two_domains_denied_even_if_account_ids_differ(self):
        d={**self.domains,"head_issuer":self.domains["executor"]}
        r=self.result(domains=d)
        self.denied(r)
        self.assertIn("CLAIMED_ADMIN_DOMAINS_NOT_DISTINCT",r["blockers"])

    def test_22_independent_admin_controller_claim_is_not_real_independence(self):
        r=self.result()
        self.denied(r)
        self.assertIn("CONTROLLERS_CLAIMED_DISTINCT_NOT_VERIFIED",r["observations"])
        self.assertFalse(r["signer_trust_root_enrolled"])

    def test_23_all_inputs_are_immutable_and_repeatable(self):
        before=deepcopy((self.packet,self.head,self.domains))
        r1=self.result()
        r2=self.result()
        self.assertEqual(r1,r2)
        self.assertEqual((self.packet,self.head,self.domains),before)

    def test_24_real_a53_activation_still_denied_without_independent_authority(self):
        f=activation_fixture.GlobalWorkerActivationCeremonyTests()
        f.setUp()
        response=activation.prepare_global_worker_activation_plan(
            f.access,f.runtime,f.readiness,activation_fixture._safe_flag("UNSET"),
            now=activation_fixture.NOW)
        self.assertEqual(response["status"],"BLOCKED")
        self.assertEqual(response["reason"],"INDEPENDENT_ACTIVATION_AUTHORITY_NOT_ENROLLED")
        self.assertFalse(response["feature_flag_modified"])
        self.assertFalse(response["global_worker_executed"])

    def test_25_a76_execution_does_not_take_untrusted_head_fixture_as_authority(self):
        runtime, _=incident_fixture._post_incident_runtime()
        readiness,flag=incident_fixture._readiness(),incident_fixture._safe_flag()
        observed=incident_fixture._safe_reconciled_snapshot(runtime)
        g=gate.assess_post_incident_reactivation_gate(
            runtime,observed,readiness,flag,now=incident_fixture.NOW)
        ticket={"post_incident_gate_required":True,
                "post_incident_closure_ledger_digest":g["closure_ledger_digest"],
                "post_incident_latest_closure_record_id":g["latest_closure_record_id"],
                "independent_head_verified":True,
                "issuer_signature_verified":True}
        response=gate.validate_reactivation_gate_for_execution(
            runtime,flag,ticket,g,now=incident_fixture.NOW)
        self.assertEqual(response["state"],"BLOCKED")
        self.assertEqual(response["reason"],"FRESH_INDEPENDENT_INCIDENT_SOURCE_NOT_ENROLLED")
        self.assertFalse(response["reactivation_authorized"])

    def test_26_no_production_execution_or_source_enrollment_in_lab_code(self):
        root=Path(__file__).resolve().parents[1]
        source=(root/"atlasquant_aion_p0_incident_external_witness_proposal_lab.py").read_text()
        for forbidden in ("requests.post(", "boto3.", "s3.put_object(", "dispatch_claimed(",
                          "write_repository_feature_flag_enabled(", "automatic_retry_allowed\": True"):
            self.assertNotIn(forbidden,source)
        self.denied(self.result())


if __name__=="__main__":
    unittest.main()
