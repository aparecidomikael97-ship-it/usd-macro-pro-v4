"""Synthetic adversarial checks: root binding never proves real prediction skill."""
from dataclasses import replace
from datetime import timedelta
import unittest

from test_atlasquant_trader_selective_precommit_bridge_lab import example, BASE, NOW
from atlasquant_trader_selective_event_root_oos_audit_lab import FrozenOpportunityManifest
from atlasquant_trader_event_root_precommit_guard_lab import (
    PlannedEventRoot, FrozenEventRootPlan, fingerprint_root_plan_lab,
    inspect_precommitted_event_root_binding_lab as inspect, DOCUMENTARY, BLOCKED,
)


def fixture():
    manifest, forecasts, receipts, head, observations = example()
    plan = FrozenEventRootPlan(
        campaign_id=manifest.campaign_id, rule_version=manifest.rule_version,
        frozen_at_utc=BASE-timedelta(days=2),
        assignments=tuple(PlannedEventRoot(
            opportunity_id=row.opportunity_id,
            source_event_id="BLS_US_PPI_OCT_2026",
            event_root_id="PPI_US_TEST") for row in forecasts))
    digest = fingerprint_root_plan_lab(plan)
    assert isinstance(digest, str) and len(digest) == 64
    return manifest, plan, digest, forecasts, receipts, head, observations


def run(args):
    manifest, plan, digest, forecasts, receipts, head, observations = args
    return inspect(frozen_manifest=manifest, root_plan=plan,
                   preserved_root_plan_sha256=digest, forecast_records=forecasts,
                   receipt_entries=receipts, receipt_head_sha256=head,
                   observations=observations, inspected_at_utc=NOW)


class PrecommittedEventRootGuardTests(unittest.TestCase):
    def safe(self, out):
        self.assertEqual(out["operational_bias"], "AGUARDAR")
        self.assertFalse(out["trade_authorized"])
        self.assertFalse(out["publishable"])
        self.assertFalse(out["live_alert_allowed"])
        self.assertFalse(out["pre_event_root_plan_independently_witnessed"])
        self.assertFalse(out["source_release_identity_independently_verified"])
        self.assertFalse(out["root_causality_or_independence_verified"])
        self.assertIsNone(out["validated_accuracy"])
        self.assertIsNone(out["calibrated_probability"])
        self.assertEqual((out["http_requests"],out["file_writes"],out["new_cost_brl"]), (0,0,0))

    def reject(self, args, reason):
        out = run(args)
        self.assertEqual(out["state"], BLOCKED)
        self.assertEqual(out["reason"], reason)
        self.assertIsNone(out["audit"])
        self.safe(out)

    def test_two_pairs_one_named_ppi_root_documentary_no_go(self):
        result = run(fixture())
        self.assertEqual(result["state"], DOCUMENTARY)
        self.assertEqual(result["matched_slots"], 2)
        self.assertEqual(result["claimed_root_count"], 1)
        self.assertTrue(result["root_plan_matches_preserved_digest_claim"])
        self.assertEqual(result["audit"]["descriptive_audit"]["claimed_event_root_count_issued"],1)
        self.safe(result)

    def test_post_event_root_splitting_rejected(self):
        m,p,d,f,r,h,o = fixture()
        o[1] = replace(o[1], event_root_id="NEW_ROOT_TO_INFLATE_COUNTS")
        self.reject((m,p,d,f,r,h,o), "EVENT_ROOT_RELABELED_AFTER_PRECOMMIT")

    def test_same_source_event_cannot_have_two_precommitted_roots(self):
        m,p,d,f,r,h,o = fixture()
        p = replace(p, assignments=(p.assignments[0],
                    replace(p.assignments[1],event_root_id="PPI_FAKE_SECOND_ROOT")))
        self.assertIsNone(fingerprint_root_plan_lab(p))
        self.reject((m,p,d,f,r,h,o), "INVALID_PLAN_CLOCK_OR_PRESERVED_DIGEST_MISMATCH")

    def test_changed_plan_with_old_digest_rejected(self):
        m,p,d,f,r,h,o = fixture()
        p = replace(p,assignments=(p.assignments[0],
                    replace(p.assignments[1],source_event_id="OTHER_RELEASE_BLS")))
        self.reject((m,p,d,f,r,h,o), "INVALID_PLAN_CLOCK_OR_PRESERVED_DIGEST_MISMATCH")

    def test_rehashed_fake_source_names_still_not_attested(self):
        m,p,d,f,r,h,o = fixture()
        p = replace(p,assignments=(p.assignments[0],
                    replace(p.assignments[1],source_event_id="FAKE_SECOND_RELEASE",
                            event_root_id="PPI_SECOND_ROOT")))
        o[1] = replace(o[1],event_root_id="PPI_SECOND_ROOT")
        forged_digest = fingerprint_root_plan_lab(p)
        result = run((m,p,forged_digest,f,r,h,o))
        self.assertEqual(result["state"], DOCUMENTARY)
        self.assertEqual(result["claimed_root_count"], 2)
        self.assertFalse(result["source_release_identity_independently_verified"])
        self.assertFalse(result["pre_event_root_plan_independently_witnessed"])
        self.safe(result)

    def test_plan_after_first_prediction_rejected(self):
        m,p,d,f,r,h,o = fixture()
        p = replace(p,frozen_at_utc=BASE+timedelta(minutes=1))
        d = fingerprint_root_plan_lab(p)
        self.reject((m,p,d,f,r,h,o), "ROOT_PLAN_NOT_FROZEN_BEFORE_FIRST_DECISION")

    def test_plan_before_campaign_manifest_rejected(self):
        m,p,d,f,r,h,o = fixture()
        p = replace(p,frozen_at_utc=m.frozen_at_utc-timedelta(minutes=1))
        d = fingerprint_root_plan_lab(p)
        self.reject((m,p,d,f,r,h,o), "ROOT_PLAN_FREEZE_OUTSIDE_MANIFEST_WINDOW")

    def test_missing_assignment_rejected_before_scoring(self):
        m,p,d,f,r,h,o = fixture()
        p = replace(p, assignments=p.assignments[:1])
        d = fingerprint_root_plan_lab(p)
        self.reject((m,p,d,f,r,h,o), "ROOT_PLAN_CENSUS_OR_CAMPAIGN_MISMATCH")

    def test_reordered_assignment_rejected(self):
        m,p,d,f,r,h,o = fixture()
        p = replace(p,assignments=tuple(reversed(p.assignments)))
        d = fingerprint_root_plan_lab(p)
        self.reject((m,p,d,f,r,h,o), "ROOT_ASSIGNMENT_MISSING_REORDERED_OR_EXTRA")

    def test_campaign_mismatch_rejected(self):
        m,p,d,f,r,h,o = fixture()
        p = replace(p,campaign_id="OTHER_CAMPAIGN_ID")
        d = fingerprint_root_plan_lab(p)
        self.reject((m,p,d,f,r,h,o), "ROOT_PLAN_CENSUS_OR_CAMPAIGN_MISMATCH")

    def test_blank_or_unknown_source_rejected(self):
        for key in ("UNKNOWN","NONE","UNVERIFIED",""):
            with self.subTest(key=key):
                m,p,d,f,r,h,o = fixture()
                p = replace(p,assignments=(replace(p.assignments[0],source_event_id=key),
                                            p.assignments[1]))
                self.assertIsNone(fingerprint_root_plan_lab(p))

    def test_missing_old_receipt_rejected(self):
        m,p,d,f,r,h,o = fixture()
        self.reject((m,p,d,f,r[:-1],h,o),
                    "PRECOMMIT_AND_OUTCOME_JOIN_REJECTED")

    def test_outcome_forged_before_target_end_rejected(self):
        m,p,d,f,r,h,o = fixture()
        o[0] = replace(o[0],outcome_observed_at_utc=BASE+timedelta(hours=3))
        self.reject((m,p,d,f,r,h,o),
                    "PRECOMMIT_AND_OUTCOME_JOIN_REJECTED")

    def test_unregistered_slot_rejected(self):
        m,p,d,f,r,h,o = fixture()
        o[1] = replace(o[1],opportunity_id="SLOT_FRAUD")
        self.reject((m,p,d,f,r,h,o),
                    "ROOT_ASSIGNMENT_MISSING_REORDERED_OR_EXTRA")


if __name__ == "__main__":
    unittest.main()
