"""Offline rejection/shortlist tests. No cloud, keys, token, HTTP, or spend."""
from __future__ import annotations

import ast
from pathlib import Path
import unittest
from dataclasses import replace
from copy import deepcopy

from atlasquant_aion_witness_architecture_review_reference_v1 import (
    SCHEMA, FIELDS, NO_AUTHORITY, review_witness_architecture,
)

ROOT = Path(__file__).resolve().parent


def candidate():
    return {
        "schema": SCHEMA,
        "coordinator": "CLOUDFLARE_SQLITE_DURABLE_OBJECT",
        "coordinator_control_domain": "research-only-CF-account",
        "retention_anchor": "AWS_S3_OBJECT_LOCK_COMPLIANCE",
        "retention_control_domain": "research-only-AWS-account",
        "admin_separation": True,
        "key_custody_separation": True,
        "tenant_resource_binding": True,
        "nonce_fresh_head_protocol": "SIGNED_NONCE_BOUND_CURRENT_HEAD",
        "serialized_cas": True,
        "protected_append_history": True,
        "rollback_recovery": "BLOCK_UNKNOWN_RECONCILE_BOTH_DOMAINS",
        "restore_risk": "COORDINATOR_CAN_BE_ADMIN_RESTORED",
        "expiry_and_revocation": True,
        "cost_review": "UNQUOTED",
        "owner_approval": "NOT_REQUESTED",
    }


class WitnessArchitectureReviewReferenceTests(unittest.TestCase):
    def assert_no_go(self, result):
        for name, value in NO_AUTHORITY.items():
            self.assertIs(result[name], False, name)
        self.assertIs(result["independently_verified_evidence"], False)
        self.assertIs(result["production_no_go"], True)
        self.assertIs(result["requires_separate_owner_decision"], True)

    def test_exact_candidate_looks_researchable_but_never_admits_production(self):
        d = review_witness_architecture(candidate())
        self.assertEqual(d["state"], "RESEARCH_CANDIDATE_UNTRUSTED")
        self.assertIn("REAL_PROVIDER_NOT_ENROLLED", d["blockers"])
        self.assertIn("SECOND_ORIGIN_HEAD_NOT_INDEPENDENTLY_VERIFIED", d["blockers"])
        self.assertIn("COST_LGPD_OWNER_DECISIONS_PENDING", d["blockers"])
        self.assert_no_go(d)

    def test_missing_and_extra_fields_are_closed(self):
        for raw in (None, {}, [], "approved", {"schema":SCHEMA}):
            with self.subTest(raw=str(raw)):
                d=review_witness_architecture(raw)
                self.assertEqual(d["state"], "REJECTED_DESIGN")
                self.assert_no_go(d)
        example=candidate()
        example["production_approved"] = True
        self.assertEqual(review_witness_architecture(example)["state"], "REJECTED_DESIGN")
        example=candidate()
        example.pop("owner_approval")
        self.assertEqual(review_witness_architecture(example)["state"], "REJECTED_DESIGN")
        self.assertEqual(FIELDS,set(candidate()))

    def test_cloudflare_only_or_coordinator_restore_is_insufficient(self):
        d=candidate()
        d["retention_anchor"] = "CLOUDFLARE_SQLITE_DURABLE_OBJECT"
        self.assertIn("NO_REVIEWED_WORM_SECOND_PROVIDER",
                      review_witness_architecture(d)["blockers"])
        d=candidate()
        d["restore_risk"] = "NO_ADMINISTRATIVE_RESTORE_POSSIBLE"
        self.assertIn("RESTORE_THREAT_NOT_MODELED",
                      review_witness_architecture(d)["blockers"])

    def test_aws_worm_alone_is_not_coordinator_or_fresh_head(self):
        d=candidate()
        d["coordinator"] = "AWS_S3_OBJECT_LOCK_COMPLIANCE"
        self.assertEqual(review_witness_architecture(d)["state"],"REJECTED_DESIGN")
        d=candidate()
        d["nonce_fresh_head_protocol"] = "S3_VERSION_EXISTS"
        self.assertIn("FRESH_SIGNED_HEAD_PROTOCOL_ABSENT",
                      review_witness_architecture(d)["blockers"])

    def test_same_admin_or_same_account_fails_design_review(self):
        for field, bad in (
            ("retention_control_domain","research-only-CF-account"),
            ("admin_separation",False),("key_custody_separation",False),
            ("coordinator_control_domain","  research-only-CF-account"),
        ):
            with self.subTest(field=field):
                plan=candidate()
                plan[field]=bad
                self.assertEqual(review_witness_architecture(plan)["state"],"REJECTED_DESIGN")
                self.assert_no_go(review_witness_architecture(plan))

    def test_bool_str_approved_and_integer_one_are_not_trusted(self):
        for k in ("admin_separation","key_custody_separation",
                  "tenant_resource_binding","serialized_cas",
                  "protected_append_history","expiry_and_revocation"):
            for bad in ("true","approved",1,None):
                with self.subTest(k=k, bad=bad):
                    plan=candidate()
                    plan[k]=bad
                    result=review_witness_architecture(plan)
                    self.assertEqual(result["state"],"REJECTED_DESIGN")
                    self.assert_no_go(result)

    def test_unknown_outcome_auto_retry_is_always_rejected(self):
        for value in ("RETRY_ON_TIMEOUT","RESTORE_CLOUD_HEAD_TO_LOCAL",
                      "REPLACE_EXTERNAL_HEAD_WITH_GITHUB",True):
            with self.subTest(value=value):
                plan=candidate()
                plan["rollback_recovery"]=value
                x=review_witness_architecture(plan)
                self.assertIn("UNKNOWN_OUTCOME_RECOVERY_NOT_SPECIFIED",x["blockers"])
                self.assertIs(x["automatic_retry_allowed"],False)

    def test_same_tenant_file_or_missing_ownership_blocks(self):
        plan=candidate()
        plan["tenant_resource_binding"]=False
        self.assertIn("MISSING_DESIGN_CONTROL_TENANT_RESOURCE_BINDING",
                      review_witness_architecture(plan)["blockers"])

    def test_no_owner_or_cost_claim_can_grant_authority(self):
        for field, value in (
            ("owner_approval","APPROVED"),
            ("owner_approval", True),
            ("cost_review","UNDER_200_BRL"),
            ("cost_review","CLOUDFLARE_FREE_MEANS_ALL_FREE"),
        ):
            with self.subTest(field=field):
                plan=candidate()
                plan[field]=value
                result=review_witness_architecture(plan)
                self.assertEqual(result["state"],"REJECTED_DESIGN")
                self.assert_no_go(result)

    def test_vendor_unavailable_and_key_revocation_do_not_enable_execution(self):
        plan=candidate()
        plan["expiry_and_revocation"]=False
        self.assertEqual(review_witness_architecture(plan)["state"],"REJECTED_DESIGN")
        self.assert_no_go(review_witness_architecture(plan))

    def test_reference_has_no_network_storage_signer_or_worker_calls(self):
        src=(ROOT/"atlasquant_aion_witness_architecture_review_reference_v1.py").read_text("utf-8")
        tree=ast.parse(src)
        imports=set()
        for n in ast.walk(tree):
            if isinstance(n,ast.Import):
                imports.update(a.name.split(".")[0] for a in n.names)
            if isinstance(n,ast.ImportFrom) and n.module:
                imports.add(n.module.split(".")[0])
        self.assertFalse(imports & {
            "requests","httpx","urllib","socket","subprocess","os","sqlite3",
            "streamlit","boto3","cloudflare","cryptography"
        })
        self.assertNotIn("run_global_worker_once(",src)
        self.assertNotIn("load_runtime_checkpoint(",src)

    def test_real_worker_and_readiness_remain_hard_denied_not_using_review(self):
        worker=(ROOT/"atlasquant_aion_global_worker.py").read_text("utf-8")
        readiness=(ROOT/"atlasquant_aion_global_worker_readiness.py").read_text("utf-8")
        gate=(ROOT/"atlasquant_aion_global_worker_source_gate_v1.py").read_text("utf-8")
        for src in (worker,readiness,gate):
            self.assertNotIn("review_witness_architecture(",src)
        self.assertIn("independent_worker_source_preflight(cfg)",worker)
        self.assertIn("independent_worker_source_preflight(config)",readiness)
        self.assertIn('"source_verified": False',gate)
        self.assertIn("if not source_admitted:",readiness)

if __name__=="__main__":
    unittest.main()
