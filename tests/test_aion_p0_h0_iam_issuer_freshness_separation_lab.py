"""AION P0 H0 LAB: STATIC identity/IAM/fresh-head proposals, ALWAYS NO-GO.

This module is a negative review of untrusted proposal objects. It does not
execute AWS STS/S3/IAM, validate policy enforcement, verify cryptographic
signatures, attest administrator independence, identify the HUMAN_OWNER,
obtain current head, authorize the Worker, or cause any external effect.
A syntactically perfect proposal ALWAYS returns HARD_NO_GO.
"""
from __future__ import annotations
from copy import deepcopy
import re
import unittest

ROLE_ACTIONS={
    "h0_executor": frozenset(),
    "cloudflare_cas_runtime": frozenset(),
    "aws_anchor_writer": frozenset({"s3:PutObject"}),
    "aws_anchor_reader": frozenset({
        "s3:GetObjectVersion", "s3:GetObjectRetention",
        "s3:GetBucketObjectLockConfiguration", "s3:ListBucketVersions",
    }),
    "external_head_witness": frozenset(),
}
FALSE={
    "independent_administrators_authenticated":False,
    "cross_account_policy_enforced_by_aws":False,
    "actual_sts_principal_authenticated":False,
    "trust_root_enrolled":False,
    "signed_highwater_verified":False,
    "challenge_nonce_authenticated":False,
    "object_retention_verified":False,
    "producer_receipt_verified":False,
    "external_no_effect_fence_verified":False,
    "first_external_effect_allowed":False,
    "worker_arming_allowed":False,
    "automatic_retry_allowed":False,
    "external_service_contacted":False,
}
ACCOUNTS=("executor", "cas", "anchor", "verifier", "witness")
ACC_PATTERN=re.compile(r"^[0-9]{12}$")
ARN_PATTERN=re.compile(r"^arn:aws:iam::([0-9]{12}):role/[A-Za-z0-9+=,.@_-]+$")
SHA_PATTERN=re.compile(r"^[0-9a-f]{64}$")


def synthetic_proposal():
    a={
        "executor":"100000000001",
        "cas":"100000000002",
        "anchor":"100000000003",
        "verifier":"100000000004",
        "witness":"100000000005",
    }
    return {
        "schema":"AION_H0_STATIC_IAM_FRESHNESS_REVIEW_V1",
        "account_domains":a,
        "admin_digests":{k:chr(ord("a")+i)*64 for i,k in enumerate(ACCOUNTS)},
        "role_accounts":{
            "h0_executor":a["executor"],
            "cloudflare_cas_runtime":a["cas"],
            "aws_anchor_writer":a["anchor"],
            "aws_anchor_reader":a["verifier"],
            "external_head_witness":a["witness"],
        },
        "role_actions":{k:sorted(v) for k,v in ROLE_ACTIONS.items()},
        "writer_role_arn":f"arn:aws:iam::{a['anchor']}:role/h0AnchorWriter",
        "reader_role_arn":f"arn:aws:iam::{a['verifier']}:role/h0AnchorReader",
        "cross_account": {
            "resource_account":a["anchor"],
            "principal_role_arn":f"arn:aws:iam::{a['verifier']}:role/h0AnchorReader",
            "identity_policy_actions":sorted(ROLE_ACTIONS["aws_anchor_reader"]),
            "resource_policy_actions":sorted(ROLE_ACTIONS["aws_anchor_reader"]),
            "identity_explicit_deny":False,
            "resource_explicit_deny":False,
        },
        "claim":{
            "source":"untrusted_offline_fixture",
            "sts_get_caller_identity_succeeded":True,
            "mfa_present":True,
            "kms_signature_valid":True,
            "separate_organizations":True,
        },
        "head":{
            "scope_digest":"f"*64,
            "epoch":7,
            "pinned_sequence":12,
            "observed_sequence":12,
            "pinned_version_id":"fake-v12",
            "returned_version_id":"fake-v12",
            "issued_nonce":"single-use-fake-nonce-987",
            "response_nonce":"single-use-fake-nonce-987",
            "max_observation_age_seconds":30,
            "observed_age_seconds":3,
            "issuer_role_arn":f"arn:aws:iam::{a['witness']}:role/h0HeadSigner",
            "self_claimed_signature_valid":True,
        },
    }


def assess_iam_freshness_proposal_lab(value):
    out={"state":"HARD_NO_GO","review_scope":"UNTRUSTED_STATIC_INPUT_ONLY",
         "findings":[],"proposal_structurally_consistent":False,**FALSE}
    errors=out["findings"]
    if type(value) is not dict:
        errors.append("NOT_PLAIN_PROPOSAL")
        return out
    if value.get("schema")!="AION_H0_STATIC_IAM_FRESHNESS_REVIEW_V1":
        errors.append("UNKNOWN_SCHEMA")
    accounts=value.get("account_domains")
    admins=value.get("admin_digests")
    role_accounts=value.get("role_accounts")
    role_actions=value.get("role_actions")
    if any(type(x) is not dict for x in (
        accounts,admins,role_accounts,role_actions)):
        errors.append("ACCOUNT_OR_ROLE_MAP_MISSING")
        return out
    numbers=[]
    for k in ACCOUNTS:
        num=accounts.get(k)
        if type(num) is not str or not ACC_PATTERN.fullmatch(num):
            errors.append("ACCOUNT_ID_INVALID:"+k)
        else:
            numbers.append(num)
        digest=admins.get(k)
        if type(digest) is not str or not SHA_PATTERN.fullmatch(digest):
            errors.append("ADMIN_DIGEST_MISSING:"+k)
    if len(numbers)!=len(set(numbers)):
        errors.append("SAME_ACCOUNT_USED_FOR_DIFFERENT_TRUST_DOMAINS")
    digest_values=[admins.get(k) for k in ACCOUNTS if type(admins.get(k)) is str]
    if len(digest_values)!=len(set(digest_values)):
        errors.append("SAME_ADMIN_DIGEST_ACROSS_TRUST_DOMAINS")
    expected_accounts={
        "h0_executor":"executor",
        "cloudflare_cas_runtime":"cas",
        "aws_anchor_writer":"anchor",
        "aws_anchor_reader":"verifier",
        "external_head_witness":"witness",
    }
    for role,domain in expected_accounts.items():
        if type(role_accounts.get(role)) is not str or role_accounts[role]!=accounts.get(domain):
            errors.append("ROLE_ACCOUNT_SCOPE_CONFLICT:"+role)
        current=role_actions.get(role)
        if type(current) is not list or any(type(k) is not str for k in current):
            errors.append("ROLE_ACTIONS_UNTYPED:"+role)
        elif frozenset(current)!=ROLE_ACTIONS[role] or len(current)!=len(set(current)):
            errors.append("ROLE_PERMISSIONS_OVERBROAD_OR_INCOMPLETE:"+role)
    for name,role in (("writer_role_arn","aws_anchor_writer"),
                      ("reader_role_arn","aws_anchor_reader")):
        v=value.get(name)
        match=ARN_PATTERN.fullmatch(v) if type(v) is str else None
        if match is None or match.group(1)!=role_accounts.get(role):
            errors.append("ROLE_ARN_ACCOUNT_MISMATCH:"+name)
    cross=value.get("cross_account")
    if type(cross) is not dict:
        errors.append("CROSS_ACCOUNT_POLICY_MISSING")
    else:
        if (type(cross.get("resource_account")) is not str or
                cross["resource_account"]!=accounts.get("anchor") or
                type(cross.get("principal_role_arn")) is not str or
                cross["principal_role_arn"]!=value.get("reader_role_arn")):
            errors.append("CROSS_ACCOUNT_PRINCIPAL_RESOURCE_MISMATCH")
        required=ROLE_ACTIONS["aws_anchor_reader"]
        for field in ("identity_policy_actions","resource_policy_actions"):
            acts=cross.get(field)
            if (type(acts) is not list or
                    any(type(x) is not str for x in acts) or
                    frozenset(acts)!=required or len(acts)!=len(set(acts))):
                errors.append("CROSS_ACCOUNT_TWO_SIDED_ALLOW_MISSING_OR_OVERBROAD:"+field)
        for field in ("identity_explicit_deny","resource_explicit_deny"):
            if cross.get(field) is not False:
                errors.append("IAM_DENY_OR_UNKNOWN:"+field)
    head=value.get("head")
    if type(head) is not dict:
        errors.append("HIGHWATER_CLAIM_MISSING")
    else:
        scope=head.get("scope_digest")
        if type(scope) is not str or not SHA_PATTERN.fullmatch(scope):
            errors.append("HEAD_SCOPE_DIGEST_INVALID")
        epoch=head.get("epoch")
        if type(epoch) is not int or epoch<=0:
            errors.append("HEAD_EPOCH_INVALID")
        pin=head.get("pinned_sequence")
        observed=head.get("observed_sequence")
        if (type(pin) is not int or type(observed) is not int or
                pin<0 or observed<pin):
            errors.append("HIGHWATER_ROLLBACK_OR_UNTYPED")
        if (type(head.get("pinned_version_id")) is not str or
                not head["pinned_version_id"] or
                type(head.get("returned_version_id")) is not str or
                head["pinned_version_id"]!=head["returned_version_id"]):
            errors.append("HIGHWATER_PINNED_VERSION_CONFLICT")
        if (type(head.get("issued_nonce")) is not str or
                len(head["issued_nonce"])<16 or
                type(head.get("response_nonce")) is not str or
                head["response_nonce"]!=head["issued_nonce"]):
            errors.append("CHALLENGE_NONCE_MISSING_OR_REPLAY_MISMATCH")
        age=head.get("observed_age_seconds")
        ttl=head.get("max_observation_age_seconds")
        if (type(age) is not int or type(ttl) is not int or
                age<0 or ttl<=0 or age>ttl or ttl>60):
            errors.append("HIGHWATER_STALE_OR_AGE_UNVERIFIED")
        issuer=head.get("issuer_role_arn")
        match=ARN_PATTERN.fullmatch(issuer) if type(issuer) is str else None
        if match is None or match.group(1)!=accounts.get("witness"):
            errors.append("HIGHWATER_ISSUER_ACCOUNT_CONFLICT")
    # NEVER read the claim: STS, MFA, signing and admin independence here
    # are all just unauthenticated strings/booleans from the proposal.
    out["proposal_structurally_consistent"]=not bool(errors)
    return out


class IAMIssuerHighwaterNegativeContractsLAB(unittest.TestCase):
    def setUp(self):
        self.p=synthetic_proposal()

    def check(self, marker=None):
        v=assess_iam_freshness_proposal_lab(self.p)
        self.assertEqual(v["state"],"HARD_NO_GO")
        for key in FALSE:
            self.assertIs(v[key],False,key)
        if marker is not None:
            self.assertIn(marker,v["findings"],v)
        return v

    def test_01_perfect_structure_still_no_authentication_or_effect(self):
        r=self.check()
        self.assertEqual(r["findings"],[])
        self.assertIs(r["proposal_structurally_consistent"],True)
        self.assertIs(r["first_external_effect_allowed"],False)

    def test_02_matching_aws_account_ids_prove_no_admin_independence(self):
        self.p["account_domains"]["witness"]=self.p["account_domains"]["anchor"]
        self.check("SAME_ACCOUNT_USED_FOR_DIFFERENT_TRUST_DOMAINS")

    def test_03_separate_account_ids_same_admin_detected(self):
        self.p["admin_digests"]["witness"]=self.p["admin_digests"]["anchor"]
        self.check("SAME_ADMIN_DIGEST_ACROSS_TRUST_DOMAINS")

    def test_04_cloudflare_cas_has_no_aws_permissions(self):
        self.p["role_actions"]["cloudflare_cas_runtime"]=["s3:GetObjectVersion"]
        self.check("ROLE_PERMISSIONS_OVERBROAD_OR_INCOMPLETE:cloudflare_cas_runtime")

    def test_05_worker_executer_cannot_have_s3_iam_or_kms_star(self):
        self.p["role_actions"]["h0_executor"]=["s3:*","kms:Sign"]
        self.check("ROLE_PERMISSIONS_OVERBROAD_OR_INCOMPLETE:h0_executor")

    def test_06_writer_cannot_delete_change_retention_or_read_as_verifier(self):
        self.p["role_actions"]["aws_anchor_writer"]=["s3:PutObject","s3:DeleteObjectVersion"]
        self.check("ROLE_PERMISSIONS_OVERBROAD_OR_INCOMPLETE:aws_anchor_writer")

    def test_07_reader_cannot_put_or_override_object_version(self):
        self.p["role_actions"]["aws_anchor_reader"].append("s3:PutObject")
        self.check("ROLE_PERMISSIONS_OVERBROAD_OR_INCOMPLETE:aws_anchor_reader")

    def test_08_reader_role_arn_wrong_account_denied(self):
        self.p["reader_role_arn"]="arn:aws:iam::100000000003:role/h0AnchorReader"
        self.check("ROLE_ARN_ACCOUNT_MISMATCH:reader_role_arn")

    def test_09_cross_account_reader_needs_resource_side_allow(self):
        self.p["cross_account"]["resource_policy_actions"]=[]
        self.check("CROSS_ACCOUNT_TWO_SIDED_ALLOW_MISSING_OR_OVERBROAD:resource_policy_actions")

    def test_10_cross_account_reader_needs_identity_side_allow(self):
        self.p["cross_account"]["identity_policy_actions"]=[]
        self.check("CROSS_ACCOUNT_TWO_SIDED_ALLOW_MISSING_OR_OVERBROAD:identity_policy_actions")

    def test_11_explicit_deny_overrides_reported_allow(self):
        self.p["cross_account"]["resource_explicit_deny"]=True
        self.check("IAM_DENY_OR_UNKNOWN:resource_explicit_deny")

    def test_12_false_sts_mfa_signature_or_signed_true_is_ignored(self):
        class Hostile:
            def __bool__(self):
                raise AssertionError("self-asserted authority must not be inspected")
            def __getattribute__(self, value):
                raise AssertionError("self-asserted authority must not be inspected")
        self.p["claim"]=Hostile()
        self.assertEqual(self.check()["findings"],[])

    def test_13_head_below_pinned_highwater_denied(self):
        self.p["head"]["observed_sequence"]=11
        self.check("HIGHWATER_ROLLBACK_OR_UNTYPED")

    def test_14_old_version_pin_and_new_readback_rejected(self):
        self.p["head"]["returned_version_id"]="fake-v13"
        self.check("HIGHWATER_PINNED_VERSION_CONFLICT")

    def test_15_replayed_or_wrong_nonce_rejected(self):
        self.p["head"]["response_nonce"]="replayed-stale-other-request"
        self.check("CHALLENGE_NONCE_MISSING_OR_REPLAY_MISMATCH")

    def test_16_stale_reported_60_second_age_rejected(self):
        self.p["head"]["observed_age_seconds"]=61
        self.check("HIGHWATER_STALE_OR_AGE_UNVERIFIED")

    def test_17_issuer_claim_in_wrong_account_rejected(self):
        self.p["head"]["issuer_role_arn"]="arn:aws:iam::100000000001:role/h0HeadSigner"
        self.check("HIGHWATER_ISSUER_ACCOUNT_CONFLICT")

    def test_18_self_reported_good_structure_cannot_prove_source_independence(self):
        r=self.check()
        self.assertIs(r["actual_sts_principal_authenticated"],False)
        self.assertIs(r["cross_account_policy_enforced_by_aws"],False)
        self.assertIs(r["signed_highwater_verified"],False)

    def test_19_hostile_non_plain_dict_never_executes_lookup(self):
        class Hostile:
            def __bool__(self):raise AssertionError("unsafe bool")
            def __getattr__(self,name):raise AssertionError("unsafe getattr")
        r=assess_iam_freshness_proposal_lab(Hostile())
        self.assertIn("NOT_PLAIN_PROPOSAL",r["findings"])
        self.assertFalse(r["external_service_contacted"])
        self.assertEqual(r["state"],"HARD_NO_GO")

    def test_20_ill_typed_permission_entries_denied(self):
        self.p["cross_account"]["identity_policy_actions"]=[object()]
        self.check("CROSS_ACCOUNT_TWO_SIDED_ALLOW_MISSING_OR_OVERBROAD:identity_policy_actions")

    def test_21_boolean_epoch_and_sequence_rejected(self):
        self.p["head"]["epoch"]=True
        self.p["head"]["observed_sequence"]=False
        self.check("HEAD_EPOCH_INVALID")
        self.check("HIGHWATER_ROLLBACK_OR_UNTYPED")

    def test_22_future_unverified_clock_age_is_not_real_freshness(self):
        # Even an accepted age=0 is just a number from an untrusted proposal.
        self.p["head"]["observed_age_seconds"]=0
        r=self.check()
        self.assertIs(r["proposal_structurally_consistent"],True)
        self.assertIs(r["signed_highwater_verified"],False)
        self.assertIs(r["challenge_nonce_authenticated"],False)
        self.assertIs(r["worker_arming_allowed"],False)


if __name__=="__main__":
    unittest.main()
