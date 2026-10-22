"""A167 exact 24 negative scenario tests; never query or write to providers."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import unittest

from aion_p0_a167_provider_semantics_lab import (
    OPEN_GATES, SCHEMA, SCENARIOS, assess_documented_counterexample,
)

def example(name):
    spec = SCENARIOS[name]
    return {"scenario": name, "provider": spec["provider"],
            "observation": deepcopy(spec["observation"])}

class A167VendorCapabilityBoundariesLAB(unittest.TestCase):
    def blocked(self, record):
        r = assess_documented_counterexample(record)
        self.assertEqual(r["verdict"], "LAB_HARD_BLOCKED", r)
        self.assertEqual(r["homologated_p0_count"], 0)
        self.assertFalse(r["worker_allowed"])
        self.assertFalse(r["automatic_resend_allowed"])
        return r

    def test_19_missing_envelope_is_not_proof(self):
        r = self.blocked({})
        self.assertFalse(r["synthetic_documented_risk_recognized"])

    def test_20_missing_observation_is_not_proof(self):
        r = self.blocked({"scenario": "S3_DELETE_MARKER_404",
                          "provider": "AWS_S3_OBJECT_LOCK"})
        self.assertFalse(r["synthetic_documented_risk_recognized"])

    def test_21_extra_authority_flag_is_rejected(self):
        record = example("DDB_RESTORE_NEW_TABLE")
        record["H0_GO"] = True
        r = self.blocked(record)
        self.assertFalse(r["synthetic_documented_risk_recognized"])

    def test_22_every_recognized_hazard_still_denies_all_authority(self):
        for name in SCENARIOS:
            with self.subTest(scenario=name):
                r = self.blocked(example(name))
                self.assertTrue(r["synthetic_documented_risk_recognized"])
                for k, val in r.items():
                    if (k.endswith("_allowed") or k.endswith("_authenticated")
                            or k.endswith("_approved") or k.endswith("_verified")
                            or k.endswith("_fenced")):
                        self.assertIs(val, False, k)
                self.assertEqual(r["historical_provider_proofs_open"], 32)
                self.assertEqual(r["open_gates"], OPEN_GATES)

    def test_23_independent_clock_or_receipt_cannot_be_introduced(self):
        record = example("ONESIGNAL_WITHIN_TTL")
        record["provider_effect_confirmed"] = True
        r = self.blocked(record)
        self.assertFalse(r["real_effect_receipt_authenticated"])

    def test_24_checked_in_evidence_registry_all_open(self):
        root = Path(__file__).resolve().parents[1]
        path = root / "docs/aion/evidence/aion_p0_a167_vendor_capability_no_go_20261022.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data["schema"], SCHEMA)
        self.assertEqual(data["status"], "DOCUMENTARY_ONLY_HARD_NO_GO")
        self.assertEqual([x["scenario"] for x in data["examples"]], list(SCENARIOS))
        self.assertTrue(all(x["source_url"].startswith(
            ("https://docs.aws.amazon.com/", "https://developers.cloudflare.com/",
             "https://documentation.onesignal.com/")) for x in data["examples"]))
        self.assertEqual(data["open_gates"], list(OPEN_GATES))
        self.assertEqual(data["historical_provider_proofs_open"], 32)
        self.assertFalse(data["actual_provider_receipt_verified"])
        self.assertFalse(data["independent_custodian_verified"])
        self.assertFalse(data["worker_allowed"])
        self.assertFalse(data["automatic_resend_allowed"])

def recognized_case(code):
    def check(self):
        r = self.blocked(example(code))
        self.assertEqual(r["reason"], SCENARIOS[code]["risk"])
        self.assertTrue(r["synthetic_documented_risk_recognized"])
    return check

for i, name in enumerate(SCENARIOS, start=1):
    setattr(A167VendorCapabilityBoundariesLAB,
            f"test_{i:02d}_documented_{name.lower()}", recognized_case(name))

_MUTATIONS = [
    ("s3_wrong_provider", "S3_DELETE_MARKER_404",
     lambda d: d.__setitem__("provider", "AWS_DYNAMODB")),
    ("s3_false_marker_string", "S3_DELETE_MARKER_404",
     lambda d: d["observation"].__setitem__("current_is_delete_marker", "true")),
    ("s3_missing_version", "S3_WORM_VERSION",
     lambda d: d["observation"].pop("protected_version_exists")),
    ("cf_extra_immutable_flag", "CF_DO_DELETE_ALL",
     lambda d: d["observation"].__setitem__("certified_immutable", True)),
    ("ddb_bool_read", "DDB_RESTORE_NEW_TABLE",
     lambda d: d["observation"].__setitem__("consistent_read_on_restored_table", 1)),
    ("onesignal_negative_age", "ONESIGNAL_AFTER_TTL",
     lambda d: d["observation"].__setitem__("key_age_days", -1)),
    ("onesignal_false_no_effect", "ONESIGNAL_WITHIN_TTL",
     lambda d: d["observation"].__setitem__("terminal_no_effect", True)),
]
assert len(_MUTATIONS) == 7

def mutated_case(name, mutator):
    def check(self):
        d = example(name)
        mutator(d)
        r = self.blocked(d)
        self.assertFalse(r["synthetic_documented_risk_recognized"])
    return check

for i, (label, name, mutator) in enumerate(_MUTATIONS, start=8):
    setattr(A167VendorCapabilityBoundariesLAB,
            f"test_{i:02d}_{label}", mutated_case(name, mutator))

_MIXUPS = [
    ("S3_DELETE_MARKER_404", "S3_WORM_VERSION"),
    ("CF_DO_PITR", "CF_DO_DELETE_ALL"),
    ("DDB_RESTORE_NEW_TABLE", "ONESIGNAL_WITHIN_TTL"),
    ("ONESIGNAL_WITHIN_TTL", "ONESIGNAL_AFTER_TTL"),
]
assert len(_MIXUPS) == 4

def mixup_case(target, source):
    def check(self):
        d = example(target)
        d["observation"] = example(source)["observation"]
        r = self.blocked(d)
        self.assertFalse(r["synthetic_documented_risk_recognized"])
    return check

for i, (target, source) in enumerate(_MIXUPS, start=15):
    setattr(A167VendorCapabilityBoundariesLAB,
            f"test_{i:02d}_mixed_{target.lower()}", mixup_case(target, source))

if __name__ == "__main__":
    unittest.main()
