"""AION H0 LAB: inspect synthetic S3-version/readback *shape*, NEVER its trust.

This is a purely local adversarial verifier of candidate evidence envelopes.
It NEVER performs AWS API calls, verifies signatures, registers any issuer,
tests live retention, or grants execution. Even a perfectly shaped envelope
returns BLOCKED and all authority flags false. A claimed verified=True,
version marker, digest, IAM role, CloudTrail record or retained date is
entirely untrusted until verified under a separate authenticated principal
and independently anchored freshest highwater.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone, timedelta
import unittest

_FALSE = {
    "issuer_enrolled_independently": False,
    "readback_authenticated_independently": False,
    "signatures_cryptographically_verified": False,
    "fresh_highwater_proven": False,
    "object_version_retention_verified_remotely": False,
    "object_version_is_latest_authenticated": False,
    "distributed_rollback_ruled_out": False,
    "producer_effect_receipt_verified": False,
    "no_effect_fenced": False,
    "first_external_effect_allowed": False,
    "worker_arming_allowed": False,
    "automatic_retry_allowed": False,
    "external_api_called": False,
}

def _as_aware_datetime(value):
    if type(value) is not str:
        return None
    try:
        result=datetime.fromisoformat(value.replace("Z","+00:00"))
        return result if result.tzinfo is not None else None
    except (ValueError,TypeError,OverflowError):
        return None

def assess_synthetic_s3_readback_lab(envelope, trusted_expectation):
    """A local consistency *diagnostic*: neither parameter is trusted proof."""
    result = {"state": "BLOCKED", "simulation_only": True,
              "findings": [], **_FALSE}
    findings = result["findings"]
    if type(envelope) is not dict or type(trusted_expectation) is not dict:
        findings.append("INPUTS_NOT_PLAIN_DICT")
        return result
    expected_fields = (
        "bucket_arn", "object_key", "version_id", "scope_digest",
        "epoch", "minimum_sequence", "record_digest",
        "retention_min_until_utc",
    )
    for f in expected_fields:
        if f not in trusted_expectation or type(trusted_expectation[f]) not in (str,int):
            findings.append("EXPECTED_PIN_UNAVAILABLE:" + f)
    if findings:
        return result

    obj=envelope.get("object")
    head=envelope.get("head_object")
    get=envelope.get("get_object")
    retention=envelope.get("get_object_retention")
    versions=envelope.get("list_object_versions")
    if any(type(v) is not dict for v in (obj,head,get,retention,versions)):
        findings.append("MISSING_S3_READBACK_PART")
        return result
    for field in ("bucket_arn","object_key","version_id","scope_digest",
                  "record_digest"):
        if type(obj.get(field)) is not str or obj.get(field)!=trusted_expectation[field]:
            findings.append("PIN_CONFLICT:" + field)
    if (type(obj.get("epoch")) is not int or
            obj["epoch"]!=trusted_expectation["epoch"]):
        findings.append("EPOCH_MISMATCH")
    if (type(obj.get("sequence")) is not int or
            obj["sequence"] < trusted_expectation["minimum_sequence"]):
        findings.append("REWOUND_OR_INVALID_SEQUENCE")

    vid=trusted_expectation["version_id"]
    if any(type(x.get("version_id")) is not str or x.get("version_id")!=vid
           for x in (head,get,retention)):
        findings.append("EXACT_VERSION_READBACK_DISAGREES")
    if type(get.get("sha256")) is not str or get.get("sha256")!=trusted_expectation["record_digest"]:
        findings.append("PINNED_OBJECT_CONTENT_DIGEST_MISMATCH")

    if retention.get("mode") != "COMPLIANCE":
        findings.append("NO_EXACT_VERSION_COMPLIANCE_RETENTION")
    deadline=_as_aware_datetime(retention.get("retain_until_utc"))
    min_retention=_as_aware_datetime(trusted_expectation["retention_min_until_utc"])
    if deadline is None or min_retention is None or deadline < min_retention:
        findings.append("RETENTION_HORIZON_UNKNOWN_OR_TOO_SHORT")
    if (head.get("object_lock_mode") != "COMPLIANCE" or
            head.get("retain_until_utc") != retention.get("retain_until_utc")):
        findings.append("HEAD_RETENTION_METADATA_MISSING_OR_CONFLICT")
    if type(versions.get("is_truncated")) is not bool or versions["is_truncated"]:
        findings.append("VERSION_LIST_PAGINATION_INCOMPLETE")
    if type(versions.get("latest_version_id")) is not str or versions["latest_version_id"]!=vid:
        findings.append("PINNED_VERSION_NOT_LATEST_OBSERVATION")
    if versions.get("current_is_delete_marker") is not False:
        findings.append("LATEST_DELETE_MARKER_OR_UNTRUSTED")
    if versions.get("delete_marker_seen_anywhere") is True:
        findings.append("DELETION_HISTORY_REQUIRES_FORENSIC_REVIEW")

    # A synthetic source-level field or pretend signature is not independent
    # IAM, API-channel authentication, CloudTrail integrity, timestamp or WORM.
    # Not even absence of findings is authority: validity is always false.
    return result


def perfect_but_untrusted_fixture():
    exp={
        "bucket_arn":"arn:aws:s3:::fake-h0-lock-fixture",
        "object_key":"opaque/tenant-1/seq-1",
        "version_id":"fake-version-id-v1",
        "scope_digest":"a"*64,
        "epoch":1,"minimum_sequence":1,
        "record_digest":"b"*64,
        "retention_min_until_utc":"2027-05-01T00:00:00+00:00",
    }
    p={
        "object":{**{k:v for k,v in exp.items() if k in (
            "bucket_arn","object_key","version_id","scope_digest","epoch","record_digest")},
                  "sequence":1, "issuer_verified":True,
                  "signature_verified":True, "s3_object_locked":True},
        "head_object":{"version_id":exp["version_id"],
                       "object_lock_mode":"COMPLIANCE",
                       "retain_until_utc":"2028-05-01T00:00:00+00:00"},
        "get_object":{"version_id":exp["version_id"],
                      "sha256":exp["record_digest"]},
        "get_object_retention":{"version_id":exp["version_id"],
                                "mode":"COMPLIANCE",
                                "retain_until_utc":"2028-05-01T00:00:00+00:00"},
        "list_object_versions":{"is_truncated":False,
                                "latest_version_id":exp["version_id"],
                                "current_is_delete_marker":False,
                                "delete_marker_seen_anywhere":False},
        "account_role":"root-admin-self-asserted",
        "independent_witness_signed":True,
    }
    return p,exp


class S3ReadbackSyntheticEvidenceLAB(unittest.TestCase):
    def setUp(self):
        self.data,self.expected=perfect_but_untrusted_fixture()

    def check(self, data=None, expect=None, finding=None):
        out=assess_synthetic_s3_readback_lab(
            self.data if data is None else data,
            self.expected if expect is None else expect)
        self.assertEqual(out["state"],"BLOCKED")
        self.assertTrue(out["simulation_only"])
        for key in _FALSE:
            self.assertIs(out[key],False,key)
        if finding is not None:
            self.assertIn(finding,out["findings"],out)
        return out

    def test_01_perfect_envelope_remains_untrusted_and_blocked(self):
        self.assertEqual(self.check()["findings"],[])

    def test_02_missing_exact_version_pin_fails_closed(self):
        self.expected.pop("version_id")
        self.check(finding="EXPECTED_PIN_UNAVAILABLE:version_id")

    def test_03_head_read_of_other_version_is_not_pinned_proof(self):
        self.data["head_object"]["version_id"]="new-untrusted-version"
        self.check(finding="EXACT_VERSION_READBACK_DISAGREES")

    def test_04_get_object_other_version_is_not_proof(self):
        self.data["get_object"]["version_id"]="unknown"
        self.check(finding="EXACT_VERSION_READBACK_DISAGREES")

    def test_05_get_retention_other_version_cannot_protect_pinned(self):
        self.data["get_object_retention"]["version_id"]="unrelated"
        self.check(finding="EXACT_VERSION_READBACK_DISAGREES")

    def test_06_missing_head_retention_metadata_is_not_compliance(self):
        self.data["head_object"].pop("object_lock_mode")
        self.check(finding="HEAD_RETENTION_METADATA_MISSING_OR_CONFLICT")

    def test_07_governance_is_not_compliance(self):
        self.data["get_object_retention"]["mode"]="GOVERNANCE"
        self.check(finding="NO_EXACT_VERSION_COMPLIANCE_RETENTION")

    def test_08_retention_expired_or_shorter_than_horizon(self):
        self.data["get_object_retention"]["retain_until_utc"]="2026-10-01T00:00:00+00:00"
        self.check(finding="RETENTION_HORIZON_UNKNOWN_OR_TOO_SHORT")

    def test_09_invalid_naive_retention_date_denied(self):
        self.data["get_object_retention"]["retain_until_utc"]="2027-05-01"
        self.check(finding="RETENTION_HORIZON_UNKNOWN_OR_TOO_SHORT")

    def test_10_missing_permission_as_missing_retention_metadata(self):
        self.data["get_object_retention"].clear()
        self.check(finding="NO_EXACT_VERSION_COMPLIANCE_RETENTION")

    def test_11_old_pinned_version_vs_observed_newer_version(self):
        self.data["list_object_versions"]["latest_version_id"]="fake-v2"
        self.check(finding="PINNED_VERSION_NOT_LATEST_OBSERVATION")

    def test_12_delete_marker_can_hide_retained_version(self):
        self.data["list_object_versions"]["current_is_delete_marker"]=True
        self.check(finding="LATEST_DELETE_MARKER_OR_UNTRUSTED")

    def test_13_deletion_history_is_further_evidence_needed(self):
        self.data["list_object_versions"]["delete_marker_seen_anywhere"]=True
        self.check(finding="DELETION_HISTORY_REQUIRES_FORENSIC_REVIEW")

    def test_14_paginated_versions_not_complete(self):
        self.data["list_object_versions"]["is_truncated"]=True
        self.check(finding="VERSION_LIST_PAGINATION_INCOMPLETE")

    def test_15_missing_pagination_field_not_false(self):
        self.data["list_object_versions"].pop("is_truncated")
        self.check(finding="VERSION_LIST_PAGINATION_INCOMPLETE")

    def test_16_wrong_tenant_scope_digest_denied(self):
        self.data["object"]["scope_digest"]="c"*64
        self.check(finding="PIN_CONFLICT:scope_digest")

    def test_17_rewound_sequence_denied(self):
        self.data["object"]["sequence"]=0
        self.check(finding="REWOUND_OR_INVALID_SEQUENCE")

    def test_18_epoch_fork_denied(self):
        self.data["object"]["epoch"]=2
        self.check(finding="EPOCH_MISMATCH")

    def test_19_body_digest_mismatch_even_if_head_says_compliance(self):
        self.data["get_object"]["sha256"]="c"*64
        self.check(finding="PINNED_OBJECT_CONTENT_DIGEST_MISMATCH")

    def test_20_hostile_mapping_and_self_certified_signature_ignored(self):
        class Dangerous:
            def __bool__(self): raise AssertionError("never inspect")
            def __getattribute__(self, x): raise AssertionError("never inspect")
        self.check(data=Dangerous(),finding="INPUTS_NOT_PLAIN_DICT")
        self.data["object"]["signature_verified"]=Dangerous()
        self.data["independent_witness_signed"]=Dangerous()
        self.assertEqual(self.check()["findings"],[])

    def test_21_three_locally_consistent_heads_still_not_remote_authenticated(self):
        self.data["object"]["local_head_seq"]=1
        self.data["object"]["model_custody_head_seq"]=1
        self.data["object"]["model_third_anchor_head_seq"]=1
        out=self.check()
        self.assertIs(out["fresh_highwater_proven"],False)
        self.assertIs(out["first_external_effect_allowed"],False)

    def test_22_no_actual_external_producer_receipt_after_s3_metadata_check(self):
        self.data["object"]["effect_receipt"]=True
        self.data["object"]["no_effect_fenced"]=True
        out=self.check()
        self.assertIs(out["producer_effect_receipt_verified"],False)
        self.assertIs(out["no_effect_fenced"],False)
        self.assertIs(out["automatic_retry_allowed"],False)


if __name__=="__main__":
    unittest.main()
