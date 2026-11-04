"""No-activation preflight tests: all claims are evidence, not authority."""
import unittest
from datetime import datetime, timedelta, timezone

from atlasquant_trader_master_activation_gate import (
    SCHEMA, REQUIRED, CHECK_NAMES, assess_activation_preflight,
)

NOW = datetime(2026, 11, 2, 14, tzinfo=timezone.utc)


def proof(*, at=NOW, result="PASS", reference="AUDIT-LAB-001",
          reviewer="independent-reviewer"):
    return {"result": result, "checked_at_utc": at.isoformat(),
            "reference": reference, "reviewer": reviewer}


def complete():
    return {key: proof() for key, _ in REQUIRED}


class ActivationPreflightLabTests(unittest.TestCase):
    def read(self, data=None, *, at=NOW):
        return assess_activation_preflight(data, at=at)

    def test_no_evidence_is_hard_no_go_and_has_no_actions(self):
        p = self.read()
        self.assertEqual(p["schema"], SCHEMA)
        self.assertEqual(p["state"], "HARD_NO_GO")
        self.assertEqual(p["blocking_checks"], list(x for x, _ in REQUIRED))
        self.assertFalse(p["scheduler_enabled"])
        self.assertFalse(p["activation_authorized"])
        self.assertFalse(p["aion_worker_enabled"])
        self.assertFalse(p["trade_authorized"])
        self.assertEqual(p["provider_requests"], 0)

    def test_every_required_gate_is_named_uniquely(self):
        self.assertEqual(len(REQUIRED), len(CHECK_NAMES))
        self.assertGreaterEqual(len(REQUIRED), 12)

    def test_boolean_true_is_not_documented_evidence(self):
        p = self.read({key: True for key, _ in REQUIRED})
        self.assertEqual(p["claims_present"], 0)
        self.assertEqual(p["state"], "HARD_NO_GO")

    def test_single_false_claim_blocks_full_packet(self):
        docs = complete()
        docs["KILL_SWITCH_PROVEN"] = proof(result="FAIL")
        p = self.read(docs)
        self.assertIn("KILL_SWITCH_PROVEN", p["blocking_checks"])
        self.assertEqual(p["state"], "HARD_NO_GO")

    def test_missing_eodhd_timezone_proof_blocks_activation(self):
        docs = complete()
        docs.pop("EODHD_EVENT_TIMEZONE")
        p = self.read(docs)
        self.assertIn("EODHD_EVENT_TIMEZONE", p["blocking_checks"])
        self.assertEqual(p["checks"][1]["state"], "MISSING")

    def test_missing_billable_units_proof_blocks_even_if_requests_counted(self):
        docs = complete()
        docs.pop("EODHD_BILLABLE_UNITS")
        p = self.read(docs)
        self.assertIn("EODHD_BILLABLE_UNITS", p["blocking_checks"])
        self.assertIsNone(p["provider_billable_units"])

    def test_sqlite_only_is_not_central_multi_replica_evidence(self):
        docs = complete()
        docs["CENTRAL_QUOTA_MULTI_REPLICA"] = proof(result="FAIL")
        p = self.read(docs)
        self.assertIn("CENTRAL_QUOTA_MULTI_REPLICA", p["blocking_checks"])
        self.assertFalse(p["distributed_quota_proven"])

    def test_7_day_freshness_is_stricter_than_30_day_infra(self):
        docs = complete()
        docs["EODHD_ENTITLEMENT"] = proof(at=NOW - timedelta(days=8))
        docs["CENTRAL_QUOTA_ATOMICITY"] = proof(at=NOW - timedelta(days=8))
        p = self.read(docs)
        a = {entry["check"]: entry["state"] for entry in p["checks"]}
        self.assertEqual(a["EODHD_ENTITLEMENT"], "EXPIRED")
        self.assertEqual(a["CENTRAL_QUOTA_ATOMICITY"],
                         "CLAIMED_PASS_REQUIRES_AUDIT")

    def test_naive_or_far_future_timestamps_are_rejected(self):
        docs = complete()
        docs["FRED_ACCESS_AND_LIMITS"]["checked_at_utc"] = "2026-11-02T14:00:00"
        docs["BCB_SERIES_SEMANTICS"] = proof(at=NOW + timedelta(hours=1))
        p = self.read(docs)
        a = {entry["check"]: entry["state"] for entry in p["checks"]}
        self.assertEqual(a["FRED_ACCESS_AND_LIMITS"], "INVALID")
        self.assertEqual(a["BCB_SERIES_SEMANTICS"], "FUTURE_EVIDENCE")

    def test_empty_reviewer_or_reference_invalid(self):
        docs = complete()
        docs["KILL_SWITCH_PROVEN"] = proof(reference="")
        docs["OWNER_REVIEW_RECORDED"] = proof(reviewer="")
        p = self.read(docs)
        self.assertIn("KILL_SWITCH_PROVEN", p["blocking_checks"])
        self.assertIn("OWNER_REVIEW_RECORDED", p["blocking_checks"])

    def test_valid_claims_still_never_authorize_scheduler(self):
        p = self.read(complete())
        self.assertEqual(p["state"], "PENDING_INDEPENDENT_REVIEW")
        self.assertEqual(p["blocking_checks"], [])
        self.assertFalse(p["activation_authorized"])
        self.assertFalse(p["scheduler_enabled"])
        self.assertFalse(p["distributed_quota_proven"])
        self.assertFalse(p["new_economic_release_confirmed"])

    def test_secret_like_references_never_echo_back(self):
        docs = complete()
        docs["EODHD_ENTITLEMENT"] = proof(
            reference="sk_private_secret_should_not_appear")
        p = self.read(docs)
        self.assertNotIn("sk_private_secret_should_not_appear", str(p))

    def test_invalid_evaluation_timestamp_rejected(self):
        with self.assertRaises(ValueError):
            assess_activation_preflight({}, at=datetime(2026, 11, 2, 14))
        with self.assertRaises(ValueError):
            assess_activation_preflight({}, at="2026-11-02")

    def test_unrecognized_claim_does_not_bypass_missing_checks(self):
        p = self.read({"skip_all_checks": proof()})
        self.assertEqual(p["claims_present"], 0)
        self.assertEqual(p["state"], "HARD_NO_GO")


if __name__ == "__main__":
    unittest.main()
