"""A153: adversarial static IAM *proposal* review, not real cloud enforcement.

No AWS SDK, accounts, tokens, IAM writes, cloud logins or network calls.
"""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools.aion_p0_a153_iam_document_boundary_lab import (
    ROOT, SCHEMA, PolicyInputRejected, audit_static_file, decode_proposal_json,
    inspect_candidate_iam_lab,
)

FIXTURE = ROOT / "docs/aion/evidence/aion_p0_a153_synthetic_iam_scope_candidate_no_go.json"
SCRIPT = ROOT / "tools/aion_p0_a153_iam_document_boundary_lab.py"


class A153IAMPolicyDocumentBoundaryLAB(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = decode_proposal_json(FIXTURE.read_text(encoding="utf-8"))

    def setUp(self):
        self.p = deepcopy(self.fixture)

    def report(self):
        return inspect_candidate_iam_lab(self.p)

    def denied(self, phrase):
        result = self.report()
        self.assertFalse(result["static_proposal_matches_restrictive_template_lab"])
        self.assertTrue(any(phrase in x for x in result["findings"]), result)

    def assert_never_authorized(self, result):
        for key in ("actual_account_separation_verified", "iam_live_enforcement_verified",
                    "immutable_anchor_attested", "real_HUMAN_OWNER_consent_verified",
                    "external_provider_effect_authenticated", "first_effect_allowed",
                    "worker_allowed", "automatic_resend_allowed"):
            self.assertIs(result[key], False, key)
        self.assertEqual(result["homologated_p0_count"], 0)
        self.assertEqual(result["additional_spend_authorized_brl"], 0)
        self.assertIn("HARD_NO_GO", result["verdict"])

    def test_01_synthetic_candidate_passes_static_shape_but_remains_hard_no_go(self):
        r=self.report()
        self.assertTrue(r["static_proposal_matches_restrictive_template_lab"], r)
        self.assertEqual(r["findings"], [])
        self.assert_never_authorized(r)

    def test_02_no_real_admin_proof_from_four_distinct_labels(self):
        r=self.report()
        self.assert_never_authorized(r)
        self.assertIn("NO_VERIFIED_D0_D1_D2_ACCOUNT_ADMINISTRATIVE_INDEPENDENCE",
                      r["trust_limits"])

    def test_03_no_iam_enforcement_from_exact_aws_actions(self):
        self.assertIs(self.report()["iam_live_enforcement_verified"], False)

    def test_04_policy_json_not_considered_real_cost_approval(self):
        self.assertEqual(self.report()["additional_spend_authorized_brl"], 0)

    def test_05_shallow_star_action_rejected(self):
        self.p["proposed_role_policies"]["aws_anchor_writer"]["Statement"][0]["Action"]=["s3:*"]
        self.denied("aws_anchor_writer")

    def test_06_iam_passrole_action_rejected(self):
        self.p["proposed_role_policies"]["aws_anchor_writer"]["Statement"][0]["Action"].append("iam:PassRole")
        self.denied("aws_anchor_writer")

    def test_07_s3_delete_version_rejected(self):
        self.p["proposed_role_policies"]["aws_anchor_writer"]["Statement"][0]["Action"].append("s3:DeleteObjectVersion")
        self.denied("aws_anchor_writer")

    def test_08_notaction_trap_rejected(self):
        stmt=self.p["proposed_role_policies"]["aws_anchor_writer"]["Statement"][0]
        stmt["NotAction"]=["s3:DeleteObject"]
        self.denied("aws_anchor_writer")

    def test_09_notresource_trap_rejected(self):
        stmt=self.p["proposed_role_policies"]["aws_anchor_writer"]["Statement"][0]
        stmt["NotResource"]=["arn:aws:s3:::unrelated/*"]
        self.denied("aws_anchor_writer")

    def test_10_action_as_string_not_list_rejected(self):
        self.p["proposed_role_policies"]["aws_anchor_writer"]["Statement"][0]["Action"]="s3:PutObject"
        self.denied("aws_anchor_writer")

    def test_11_resource_global_star_rejected(self):
        self.p["proposed_role_policies"]["aws_anchor_writer"]["Statement"][0]["Resource"]=["*"]
        self.denied("aws_anchor_writer")

    def test_12_other_s3_bucket_arn_rejected(self):
        self.p["proposed_role_policies"]["aws_anchor_writer"]["Statement"][0]["Resource"]=["arn:aws:s3:::uncontrolled/*"]
        self.denied("aws_anchor_writer")

    def test_13_parent_prefix_path_escape_rejected(self):
        self.p["proposed_role_policies"]["aws_anchor_writer"]["Statement"][0]["Resource"]=["arn:aws:s3:::aion-h0-synthetic-no-go/*"]
        self.denied("aws_anchor_writer")

    def test_14_writer_resource_prefix_double_wildcard_rejected(self):
        stmt=self.p["proposed_role_policies"]["aws_anchor_writer"]["Statement"][0]
        stmt["Resource"]=[stmt["Resource"][0]+"*"]
        self.denied("aws_anchor_writer")

    def test_15_put_object_retention_permission_rejected(self):
        self.p["proposed_role_policies"]["aws_anchor_writer"]["Statement"][0]["Action"].append("s3:PutObjectRetention")
        self.denied("aws_anchor_writer")

    def test_16_writer_cannot_override_bucket_policy(self):
        self.p["proposed_role_policies"]["aws_anchor_writer"]["Statement"][0]["Action"].append("s3:PutBucketPolicy")
        self.denied("aws_anchor_writer")

    def test_17_executor_may_not_read_anchor_directly(self):
        self.p["proposed_role_policies"]["aion_executor"]["Statement"]=[
            {"Sid":"Override", "Effect":"Allow", "Action":["s3:GetObjectVersion"],
             "Resource":["*"]}
        ]
        self.denied("aion_executor")

    def test_18_cloudflare_runtime_may_not_assume_aws_role(self):
        self.p["proposed_role_policies"]["cloudflare_cas_runtime"]["Statement"]=[
            {"Sid":"RoleHop", "Effect":"Allow", "Action":["sts:AssumeRole"],
             "Resource":["*"]}
        ]
        self.denied("cloudflare_cas_runtime")

    def test_19_reader_getobject_latest_forbidden(self):
        self.p["proposed_role_policies"]["aws_anchor_reader"]["Statement"][2]["Action"].append("s3:GetObject")
        self.denied("aws_anchor_reader")

    def test_20_reader_list_vers_condition_removed_denied(self):
        del self.p["proposed_role_policies"]["aws_anchor_reader"]["Statement"][0]["Condition"]
        self.denied("aws_anchor_reader")

    def test_21_reader_list_vers_prefix_changed_to_global_denied(self):
        self.p["proposed_role_policies"]["aws_anchor_reader"]["Statement"][0]["Condition"]["StringLike"]["s3:prefix"]=["*"]
        self.denied("aws_anchor_reader")

    def test_22_reader_condition_stringequals_instead_of_stringlike_denied(self):
        cond=self.p["proposed_role_policies"]["aws_anchor_reader"]["Statement"][0]
        cond["Condition"]={"StringEquals":{"s3:prefix":["aion-h0/v1/*"]}}
        self.denied("aws_anchor_reader")

    def test_23_reader_can_not_use_notprincipal(self):
        self.p["proposed_role_policies"]["aws_anchor_reader"]["Statement"][0]["NotPrincipal"]={"AWS":"*"}
        self.denied("aws_anchor_reader")

    def test_24_policy_cannot_include_principal(self):
        self.p["proposed_role_policies"]["aws_anchor_writer"]["Statement"][0]["Principal"]={"AWS":"*"}
        self.denied("aws_anchor_writer")

    def test_25_policy_cannot_use_deny_statement_as_authority_proof(self):
        self.p["proposed_role_policies"]["aws_anchor_reader"]["Statement"].append({
            "Effect":"Deny","Action":["s3:DeleteObject"],"Resource":["*"],"Sid":"Deny"
        })
        self.denied("aws_anchor_reader")

    def test_26_invalid_policy_version_rejected(self):
        self.p["proposed_role_policies"]["aws_anchor_writer"]["Version"]="2008-10-17"
        self.denied("aws_anchor_writer")

    def test_27_extra_policy_top_level_fields_rejected(self):
        self.p["proposed_role_policies"]["aws_anchor_writer"]["Id"]="self-proclaimed-safe"
        self.denied("aws_anchor_writer")

    def test_28_mutated_anchor_bucket_name_changes_expected_resource_and_denies(self):
        self.p["bucket_name"]="aion-h0-synthetic-altered"
        self.denied("aws_anchor_writer")

    def test_29_expanded_anchor_prefix_rejected(self):
        self.p["object_prefix"]=""
        self.denied("ANCHOR_PREFIX_CHANGED")

    def test_30_same_executor_and_anchor_account_id_rejected(self):
        self.p["d2_anchor_aws_account_id"]=self.p["d0_executor_aws_account_id"]
        self.denied("SAME_ACCOUNT_LABEL_NOT_SEPARATED")

    def test_31_colliding_recovery_and_anchor_admin_label_rejected(self):
        self.p["d2_recovery_administrator_label"]=self.p["d2_anchor_administrator_label"]
        self.denied("ADMIN_CONTROLLER_LABELS_OVERLAP")

    def test_32_foreign_admin_label_type_rejected(self):
        self.p["d1_custodian_administrator_label"]=True
        self.denied("ADMIN_CONTROLLER_LABEL_INVALID")

    def test_33_injected_approved_flag_fails_shape(self):
        self.p["approved_for_live"]=True
        self.denied("PROPOSAL_SHAPE_INVALID")

    def test_34_missing_anchor_reader_role_denied(self):
        self.p["proposed_role_policies"].pop("aws_anchor_reader")
        self.denied("PROPOSED_ROLE_SET_INVALID")

    def test_35_duplicate_json_key_rejected_before_policy_review(self):
        with self.assertRaisesRegex(PolicyInputRejected,"PROPOSAL_JSON_INVALID_OR_AMBIGUOUS"):
            decode_proposal_json('{"schema":"safe","schema":"unsafe"}')

    def test_36_strict_true_false_not_cast_to_strings(self):
        self.p["proposed_role_policies"]["aws_anchor_writer"]["Statement"][0]["Effect"]=True
        self.denied("aws_anchor_writer")

    def test_37_direct_synthetic_file_review_still_no_go(self):
        r=audit_static_file(FIXTURE)
        self.assertTrue(r["static_proposal_matches_restrictive_template_lab"])
        self.assert_never_authorized(r)

    def test_38_cli_clean_fixture_exits_zero_only_for_static_review(self):
        completed=subprocess.run([sys.executable,"-B",str(SCRIPT),str(FIXTURE)],
                                 cwd=ROOT,capture_output=True,text=True,timeout=20)
        self.assertEqual(completed.returncode,0,completed.stderr)
        r=json.loads(completed.stdout)
        self.assert_never_authorized(r)

    def test_39_cli_mutated_fixture_exits_nonzero_without_network(self):
        self.p["proposed_role_policies"]["aws_anchor_writer"]["Statement"][0]["Resource"]=["*"]
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"candidate.json"
            path.write_text(json.dumps(self.p),encoding="utf-8")
            completed=subprocess.run([sys.executable,"-B",str(SCRIPT),str(path)],
                                     cwd=ROOT,capture_output=True,text=True,timeout=20)
            self.assertEqual(completed.returncode,3)
            self.assert_never_authorized(json.loads(completed.stdout))

    def test_40_non_json_literal_not_interpreted_as_policy(self):
        with self.assertRaises(PolicyInputRejected):
            decode_proposal_json("not-a-json-policy")

    def test_41_json_list_not_accepted_as_policy(self):
        self.assertFalse(inspect_candidate_iam_lab([])["static_proposal_matches_restrictive_template_lab"])

    def test_42_numeric_object_key_cannot_grant_authority(self):
        self.p["d0_executor_aws_account_id"]=123456789012
        self.denied("ACCOUNT_ID_SYNTAX_INVALID:D0")

    def test_43_added_invalid_role_policy_not_silently_ignored(self):
        self.p["proposed_role_policies"]["aws_super_admin"]={"Version":"2012-10-17","Statement":[]}
        self.denied("PROPOSED_ROLE_SET_INVALID")

    def test_44_invalid_bucket_with_double_dot_denied(self):
        self.p["bucket_name"]="aion..h0-synthetic-no-go"
        self.denied("BUCKET_NAME_INVALID")

    def test_45_synthetic_correct_shape_does_not_prove_retention(self):
        r=self.report()
        self.assert_never_authorized(r)
        self.assertIn("NO_WORM_OBJECT_LOCK_CONFIGURATION_OR_CURRENT_HEAD_ATTESTED",
                      r["trust_limits"])

    def test_46_d1_admin_label_not_custodian_enrollment(self):
        r=self.report()
        self.assert_never_authorized(r)
        self.assertIn("NO_VERIFIED_D0_D1_D2_ACCOUNT_ADMINISTRATIVE_INDEPENDENCE",
                      r["trust_limits"])

    def test_47_fabricated_expensive_quote_not_considered(self):
        self.p["new_spend_authorized_brl"]=100000
        self.denied("PROPOSAL_SHAPE_INVALID")
        self.assertEqual(self.report()["additional_spend_authorized_brl"],0)

    def test_48_no_provider_receipt_even_when_reader_policy_accepted(self):
        self.assertIs(self.report()["external_provider_effect_authenticated"],False)


if __name__ == "__main__":
    unittest.main()
