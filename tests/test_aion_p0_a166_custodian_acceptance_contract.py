"""A166: forty offline adversarial checks for a *non-authorizing* dossier shape."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import unittest

from aion_p0_a166_review_contract import (
    AUDIENCE, OPEN_GATES, ROLES, SCHEMA, SOURCE_FOR_KIND,
    assess_candidate_inventory,
)

NOW = 2_000_000_000

def fake_dossier():
    """Every 'external' value is manufactured by one test process."""
    floor = {
        "ledger_id": "ledger_a166", "epoch": "a" * 32,
        "policy_generation": 5, "policy_digest": "b" * 64,
        "challenge_nonce": "c" * 32, "observed_ns": 1_000_000_000,
        "expires_ns": 10_000_000_000, "audience": AUDIENCE,
    }
    custodians = [
        {
            "role": role, "organization_id": "org_" + role,
            "administrator_id": "admin_" + role,
            "provider_account_id": "acct_" + role,
            "storage_failure_domain_id": "domain_" + role,
            "custody_request_id": "request_" + role,
        } for role in ROLES
    ]
    records = []
    for role in ROLES:
        for kind, channel in SOURCE_FOR_KIND.items():
            records.append({
                "role": role, "kind": kind,
                "subject_org_id": "org_" + role,
                "source_org_id": "issuer_" + role + "_" + kind,
                "source_record_id": "rid_" + role + "_" + kind,
                "source_channel": channel,
                "content_sha256": sha256((role + "|" + kind).encode()).hexdigest(),
                "ledger_id": floor["ledger_id"], "epoch": floor["epoch"],
                "policy_generation": floor["policy_generation"],
                "policy_digest": floor["policy_digest"],
                "challenge_nonce": floor["challenge_nonce"],
                "observed_ns": floor["observed_ns"],
                "expires_ns": floor["expires_ns"],
            })
    return {"schema": SCHEMA, "floor": floor,
            "custodians": custodians, "records": records}

class A166CandidateAcceptanceContractLAB(unittest.TestCase):
    def deny(self, doc, now=NOW):
        review = assess_candidate_inventory(doc, now_ns=now)
        self.assertEqual(review["verdict"], "LAB_HARD_BLOCKED", review)
        self.assertFalse(review["worker_allowed"])
        self.assertFalse(review["automatic_resend_allowed"])
        self.assertEqual(review["homologated_p0_count"], 0)
        return review

    def quarantine(self, doc=None):
        review = assess_candidate_inventory(fake_dossier() if doc is None else doc,
                                             now_ns=NOW)
        self.assertEqual(review["verdict"], "LAB_QUARANTINE_MANUAL_REVIEW", review)
        self.assertTrue(review["structural_inventory_complete"])
        self.assertEqual(review["historical_provider_proof_obligations"], 32)
        return review

    def test_01_empty_dossier_blocks(self):
        self.deny({})

    def test_02_one_caller_can_forge_all_sixteen_records(self):
        self.quarantine()

    def test_03_every_authority_flag_remains_false_even_if_complete(self):
        review = self.quarantine()
        for key, val in review.items():
            if key.endswith("_verified") or key.endswith("_allowed") or key.endswith("_authenticated"):
                self.assertIs(val, False, key)

    def test_04_same_claimed_organization_blocks(self):
        doc = fake_dossier()
        doc["custodians"][1]["organization_id"] = "org_r1"
        self.deny(doc)

    def test_05_same_claimed_administrator_blocks(self):
        doc = fake_dossier()
        doc["custodians"][1]["administrator_id"] = "admin_r1"
        self.deny(doc)

    def test_06_same_claimed_account_blocks(self):
        doc = fake_dossier()
        doc["custodians"][1]["provider_account_id"] = "acct_r1"
        self.deny(doc)

    def test_07_same_claimed_storage_domain_blocks(self):
        doc = fake_dossier()
        doc["custodians"][1]["storage_failure_domain_id"] = "domain_r1"
        self.deny(doc)

    def test_08_same_claimed_request_reference_blocks(self):
        doc = fake_dossier()
        doc["custodians"][1]["custody_request_id"] = "request_r1"
        self.deny(doc)

    def test_09_shared_hsm_source_cross_role_blocks(self):
        doc = fake_dossier()
        r1 = next(x for x in doc["records"]
                  if x["role"] == "r1" and x["kind"] == "KEY_PROVENANCE")
        r2 = next(x for x in doc["records"]
                  if x["role"] == "r2" and x["kind"] == "KEY_PROVENANCE")
        r2["source_org_id"] = r1["source_org_id"]
        self.deny(doc)

    def test_10_duplicate_source_record_blocks(self):
        doc = fake_dossier()
        doc["records"][1]["source_record_id"] = doc["records"][0]["source_record_id"]
        self.deny(doc)

    def test_11_missing_required_evidence_blocks(self):
        doc = fake_dossier()
        doc["records"].pop()
        self.deny(doc)

    def test_12_duplicate_kind_displacing_other_kind_blocks(self):
        doc = fake_dossier()
        doc["records"][-1]["kind"] = doc["records"][-2]["kind"]
        self.deny(doc)

    def test_13_unrecognized_top_level_grant_flag_blocks(self):
        doc = fake_dossier()
        doc["ready_for_live"] = True
        self.deny(doc)

    def test_14_wrong_dossier_schema_blocks(self):
        doc = fake_dossier()
        doc["schema"] = "UNREVIEWED"
        self.deny(doc)

    def test_15_expired_external_floor_claim_blocks(self):
        doc = fake_dossier()
        self.deny(doc, now=doc["floor"]["expires_ns"])

    def test_16_future_floor_claim_blocks(self):
        doc = fake_dossier()
        self.deny(doc, now=doc["floor"]["observed_ns"] - 1)

    def test_17_unbounded_floor_window_blocks(self):
        doc = fake_dossier()
        doc["floor"]["expires_ns"] = 40_000_000_000
        self.deny(doc)

    def test_18_missing_custodian_blocks(self):
        doc = fake_dossier()
        doc["custodians"].pop()
        self.deny(doc)

    def test_19_self_signed_provider_source_claim_blocks(self):
        doc = fake_dossier()
        doc["records"][0]["source_org_id"] = "org_r1"
        self.deny(doc)

    def test_20_checked_in_registry_is_entirely_missing_not_enrolled(self):
        path = (Path(__file__).resolve().parents[1]
                / "docs/aion/evidence/aion_p0_a166_custodian_acceptance_open_20261022.json")
        record = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(record["schema"], SCHEMA)
        self.assertEqual(record["status"], "NOT_ENROLLED")
        self.assertEqual(record["required_evidence_kinds"], list(SOURCE_FOR_KIND))
        self.assertEqual(set(record["missing_by_role"]), set(ROLES))
        for role in ROLES:
            self.assertEqual(record["missing_by_role"][role], list(SOURCE_FOR_KIND))
        self.assertEqual(record["open_gates"], list(OPEN_GATES))
        self.assertEqual(record["historical_external_provider_proofs_open"], 32)
        self.assertFalse(record["external_issuer_authenticated"])
        self.assertFalse(record["custodian_independence_verified"])
        self.assertFalse(record["owner_approved"])
        self.assertFalse(record["worker_allowed"])

_MUTATIONS = [
    ("role_unknown", lambda d: d["records"][0].__setitem__("role", "r3")),
    ("kind_unknown", lambda d: d["records"][0].__setitem__("kind", "ADMIN_APPROVED")),
    ("subject_mismatch", lambda d: d["records"][0].__setitem__("subject_org_id", "org_else")),
    ("source_empty", lambda d: d["records"][0].__setitem__("source_org_id", "")),
    ("source_record_space", lambda d: d["records"][0].__setitem__("source_record_id", "bad record")),
    ("sha_uppercase", lambda d: d["records"][0].__setitem__("content_sha256", "F" * 64)),
    ("ledger_mismatch", lambda d: d["records"][0].__setitem__("ledger_id", "ledger_old")),
    ("epoch_mismatch", lambda d: d["records"][0].__setitem__("epoch", "d" * 32)),
    ("generation_boolean", lambda d: d["records"][0].__setitem__("policy_generation", True)),
    ("digest_mismatch", lambda d: d["records"][0].__setitem__("policy_digest", "d" * 64)),
    ("nonce_mismatch", lambda d: d["records"][0].__setitem__("challenge_nonce", "e" * 32)),
    ("observed_boolean", lambda d: d["records"][0].__setitem__("observed_ns", False)),
    ("expiry_string", lambda d: d["records"][0].__setitem__("expires_ns", "100")),
    ("observation_future", lambda d: d["records"][0].__setitem__("observed_ns", NOW + 1)),
    ("expiry_before_observation", lambda d: d["records"][0].__setitem__("expires_ns", 1)),
    ("expiry_exceeds_floor", lambda d: d["records"][0].__setitem__("expires_ns", 11_000_000_000)),
    ("channel_self_asserted", lambda d: d["records"][0].__setitem__("source_channel", "SELF")),
    ("source_explicitly_local", lambda d: d["records"][0].__setitem__("source_org_id", "AION_LOCAL")),
    ("unexpected_verified_flag", lambda d: d["records"][0].__setitem__("verified", True)),
    ("source_record_missing", lambda d: d["records"][0].pop("source_record_id")),
]
assert len(_MUTATIONS) == 20

def mutation_case(fn):
    def check(self):
        doc = fake_dossier()
        fn(doc)
        self.deny(doc)
    return check

for i, (name, mutation) in enumerate(_MUTATIONS, start=21):
    setattr(A166CandidateAcceptanceContractLAB,
            f"test_{i:02d}_{name}", mutation_case(mutation))

if __name__ == "__main__":
    unittest.main()
