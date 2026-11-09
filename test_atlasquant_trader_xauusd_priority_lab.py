"""No trading or broker calls. XAUUSD priority tests on the real FX registry."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest
from atlasquant_instrument_registry import FX_28, normalize_fx_symbol
from atlasquant_trader_xauusd_priority_lab import (
    BIASES, EVIDENCE_DOMAINS, PRE_DECISION_DOMAINS, POST_OUTCOME_DOMAINS, EvidenceReceipt, inspect_xauusd_evidence_lab,
    plan_xauusd_priority_lab,
)

NOW = datetime(2026, 11, 9, 14, tzinfo=timezone.utc)
FREEZE = NOW - timedelta(hours=1)

def receipts():
    return tuple(EvidenceReceipt(d, NOW-timedelta(days=4), NOW-timedelta(days=3), "a"*64)
                 for d in PRE_DECISION_DOMAINS)

class GoldPriorityLabTests(unittest.TestCase):
    def safe(self, result):
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        self.assertIs(result["publishable"], False)
        self.assertIs(result["trade_authorized"], False)
        self.assertIs(result["research_only"], True)
        self.assertEqual(result["new_cost_brl"], 0)

    def test_xau_is_priority_but_not_29th_fx_pair(self):
        p=plan_xauusd_priority_lab()
        self.assertEqual(p["priority"], "P0_RESEARCH_PRIORITY")
        self.assertEqual(p["canonical_id"], "METAL:XAUUSD")
        self.assertEqual(p["market"], "SPOT_GOLD_USD")
        self.assertEqual(len(FX_28),28)
        self.assertNotIn("XAUUSD",FX_28)
        self.assertTrue(p["fx_28_universe_unchanged"])
        self.safe(p)

    def test_normalizer_must_still_reject_gold_as_fx_cross(self):
        with self.assertRaises(ValueError): normalize_fx_symbol("XAU/USD")

    def test_biases_d1_w1_and_monthly_context(self):
        p=plan_xauusd_priority_lab()
        self.assertEqual(tuple(p["primary_bias_horizons"]), BIASES)
        self.assertEqual(p["context_horizons"],["MN1"])
        self.assertFalse(p["grade_0_to_10_is_probability"])
        self.assertEqual(p["possible_biases"],["ALTA","BAIXA","AGUARDAR"])

    def test_outcomes_are_post_target_not_predecision(self):
        self.assertEqual(POST_OUTCOME_DOMAINS, ("XAUUSD_PROSPECTIVE_OUTCOMES",))
        self.assertEqual(len(PRE_DECISION_DOMAINS), 7)
        self.assertTrue(set(PRE_DECISION_DOMAINS).isdisjoint(POST_OUTCOME_DOMAINS))
        p = plan_xauusd_priority_lab()
        self.assertEqual(p["pre_decision_domains"], list(PRE_DECISION_DOMAINS))
        self.assertEqual(p["post_outcome_domains"], list(POST_OUTCOME_DOMAINS))

    def test_leaking_outcome_receipt_into_prediction_is_rejected(self):
        row=EvidenceReceipt("XAUUSD_PROSPECTIVE_OUTCOMES", NOW-timedelta(days=4),
                            NOW-timedelta(days=3), "b"*64)
        r=inspect_xauusd_evidence_lab((*receipts(),row),as_of_utc=NOW,decision_freeze_utc=FREEZE)
        self.assertEqual(r["state"], "LAB_XAUUSD_EVIDENCE_BLOCKED")
        self.assertEqual(r["reason"], "INVALID_OR_UNSUPPORTED_DOMAIN")
        self.safe(r)

    def test_missing_evidence_blocks(self):
        r=inspect_xauusd_evidence_lab([],as_of_utc=NOW,decision_freeze_utc=FREEZE)
        self.assertEqual(r["state"],"LAB_XAUUSD_EVIDENCE_BLOCKED")
        self.assertEqual(r["domain_count_accepted"],0)
        self.assertEqual(set(r["missing_or_invalid_domains"]),set(PRE_DECISION_DOMAINS))
        self.safe(r)

    def test_all_seven_predecision_receipts_are_only_documentary(self):
        r=inspect_xauusd_evidence_lab(receipts(),as_of_utc=NOW,decision_freeze_utc=FREEZE)
        self.assertEqual(r["state"],"LAB_XAUUSD_DOCUMENTARY_COVERAGE_UNATTESTED")
        self.assertEqual(r["domain_count_accepted"],7)
        self.assertEqual(r["missing_or_invalid_domains"],[])
        self.assertFalse(r["broker_symbol_and_session_authenticated"])
        self.assertFalse(r["prospective_outcomes_independently_verified"])
        self.assertIsNone(r["validated_accuracy"])
        self.safe(r)

    def test_partial_evidence_still_blocks(self):
        r=inspect_xauusd_evidence_lab(receipts()[:6],as_of_utc=NOW,decision_freeze_utc=FREEZE)
        self.assertEqual(r["domain_count_accepted"],6)
        self.assertEqual(len(r["missing_or_invalid_domains"]),1)
        self.safe(r)

    def test_post_freeze_capture_rejected(self):
        rows=receipts()
        bad=replace(rows[0],captured_at_utc=FREEZE+timedelta(seconds=1))
        r=inspect_xauusd_evidence_lab((bad,*rows[1:]),as_of_utc=NOW,decision_freeze_utc=FREEZE)
        self.assertEqual(r["reason"],"INVALID_SOURCE_VINTAGE_OR_HASH_CLAIM")
        self.safe(r)

    def test_future_publication_rejected(self):
        rows=receipts()
        bad=replace(rows[0],published_at_utc=NOW)
        r=inspect_xauusd_evidence_lab((bad,*rows[1:]),as_of_utc=NOW,decision_freeze_utc=FREEZE)
        self.assertEqual(r["reason"],"INVALID_SOURCE_VINTAGE_OR_HASH_CLAIM")

    def test_duplicate_domains_rejected(self):
        rows=receipts()
        r=inspect_xauusd_evidence_lab((*rows,rows[0]),as_of_utc=NOW,decision_freeze_utc=FREEZE)
        self.assertEqual(r["reason"],"DUPLICATE_EVIDENCE_DOMAIN")

    def test_missing_or_naive_clock_rejected(self):
        for audit,freeze in [(NOW,None),(None,FREEZE),(NOW,FREEZE.replace(tzinfo=None)),(NOW, NOW+timedelta(seconds=1))]:
            with self.subTest(audit=audit,freeze=freeze):
                r=inspect_xauusd_evidence_lab(receipts(),as_of_utc=audit,decision_freeze_utc=freeze)
                self.assertEqual(r["reason"],"INVALID_DECISION_OR_AUDIT_CLOCK")
                self.safe(r)

    def test_unsupported_and_invalid_receipts_rejected(self):
        rows=receipts()
        for wrong in [replace(rows[0],domain="CRYPTO"), object()]:
            with self.subTest(wrong=wrong):
                r=inspect_xauusd_evidence_lab((wrong,*rows[1:]),as_of_utc=NOW,decision_freeze_utc=FREEZE)
                self.assertEqual(r["reason"],"INVALID_OR_UNSUPPORTED_DOMAIN")

    def test_invalid_hash_rejected(self):
        rows=receipts()
        for sha in ("x"*64,"A"*64,True,""):
            with self.subTest(sha=sha):
                r=inspect_xauusd_evidence_lab((replace(rows[0],sha256_claim=sha),*rows[1:]),as_of_utc=NOW,decision_freeze_utc=FREEZE)
                self.assertEqual(r["reason"],"INVALID_SOURCE_VINTAGE_OR_HASH_CLAIM")

    def test_receipts_do_not_rely_on_order(self):
        a=inspect_xauusd_evidence_lab(receipts(),as_of_utc=NOW,decision_freeze_utc=FREEZE)
        b=inspect_xauusd_evidence_lab(tuple(reversed(receipts())),as_of_utc=NOW,decision_freeze_utc=FREEZE)
        self.assertEqual(a,b)

if __name__ == "__main__": unittest.main()
