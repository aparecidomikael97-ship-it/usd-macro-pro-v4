"""PPI macro context: synthetic BLS Table 1 only; NO real captured issuer."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_trader_us_ppi_oct2026_actual_table_guard_lab import (
    ClaimedPostReleaseHTTP, RELEASE_UTC,
)
from atlasquant_trader_us_ppi_oct2026_macro_context_lab import (
    SCHEMA, inspect_oct2026_us_ppi_macro_context_lab as bridge,
)
from test_atlasquant_trader_us_ppi_oct2026_actual_table_guard_lab import (
    raw, receipt, td, te, AFTER,
)

UTC = timezone.utc


class UsPpiTypedContextTests(unittest.TestCase):
    def run_it(self, body=None, rec=None, td_snap=None, te_snap=None, at=AFTER):
        body = raw() if body is None else body
        return bridge(
            raw_bls_html=body,
            original_http_receipt=receipt(body) if rec is None else rec,
            td_pre_event_snapshot=td() if td_snap is None else td_snap,
            te_pre_event_snapshot=te() if te_snap is None else te_snap,
            inspected_at_utc=at,
        )

    def safe(self, r):
        self.assertEqual(r["schema"], SCHEMA)
        self.assertEqual(r["currency"],"USD")
        self.assertEqual(r["operational_bias"],"AGUARDAR")
        self.assertIsNone(r["predicted_usd_strength"])
        self.assertIsNone(r["economic_impact_points"])
        self.assertIsNone(r["calibrated_probability"])
        self.assertIsNone(r["realized_fx_return"])
        self.assertFalse(r["eligible_for_fx28_model_impact_points"])
        self.assertFalse(r["issuer_source_independently_authenticated"])
        self.assertFalse(r["true_first_seen_before_decision_independently_attested"])
        self.assertFalse(r["pre_event_prediction_was_recorded"])
        self.assertTrue(r["after_event_arithmetic_is_not_a_pre_event_prediction"])
        for flag in ("trade_authorized","publishable","live_alert_allowed",
                     "scheduler_enabled","worker_enabled"):
            self.assertFalse(r[flag])
        self.assertEqual(r["http_requests"],0)
        self.assertEqual(r["file_writes"],0)
        self.assertEqual(r["new_cost_brl"],0)
        for line in r["series"]:
            self.assertEqual(line["measure"],"MOM")
            self.assertEqual(line["seasonal_adjustment"],"SA")
            self.assertEqual(line["unit"],"PERCENT_CHANGE")
            self.assertFalse(line["issuer_first_seen_independently_attested"])
            self.assertNotIn("FX_SIGNAL",line["id"])
            self.assertNotIn("TRADE_SERVICES",line["id"])

    def blocked(self, **kwargs):
        r=self.run_it(**kwargs)
        self.safe(r)
        self.assertEqual(r["state"],"LAB_US_PPI_MACRO_CONTEXT_BLOCKED")
        self.assertEqual(r["series"],[])
        self.assertFalse(r["pre_event_consensus_locked_locally"])
        return r

    def test_01_two_typed_series_keep_units_and_surprise_separate(self):
        r=self.run_it()
        self.safe(r)
        self.assertEqual(r["state"],
                         "LAB_US_PPI_OCT2026_DOCUMENTARY_SURPRISE_CONTEXT_NO_GO")
        self.assertEqual([x["id"] for x in r["series"]],[
            "PPI_FINAL_DEMAND_ALL_MOM_SA",
            "PPI_FINAL_DEMAND_EX_FOOD_ENERGY_MOM_SA"])
        self.assertEqual(r["series"][0]["actual_pct_documentary_claim"],"0.5")
        self.assertEqual(r["series"][0]["pre_event_consensus_pct_documentary_claim"],"0.4")
        self.assertEqual(r["series"][0]["surprise_percentage_points"],"0.1")
        self.assertEqual(r["series"][1]["surprise_percentage_points"],"-0.1")
        self.assertEqual(r["headline_core_concordance_claim"],
                         "MIXED_OR_UNCONFIRMED_DIRECTION")
        self.assertTrue(r["pre_event_consensus_locked_locally"])
        self.assertTrue(r["actual_raw_html_checked_against_local_sha"])

    def test_02_bls_october_synthetic_03_03_no_false_usd_direction(self):
        r=self.run_it(body=raw(head="0.3",core="0.3"))
        self.safe(r)
        self.assertEqual(r["series"][0]["surprise_percentage_points"],"-0.1")
        self.assertEqual(r["series"][1]["surprise_percentage_points"],"0.0")
        self.assertEqual(r["headline_core_concordance_claim"],
                         "MIXED_OR_UNCONFIRMED_DIRECTION")
        self.assertIsNone(r["economic_impact_points"])
        self.assertFalse(r["eligible_for_fx28_model_impact_points"])

    def test_03_both_positive_is_documentary_not_forecast(self):
        r=self.run_it(body=raw(head="0.6",core="0.6"))
        self.safe(r)
        self.assertEqual(r["headline_core_concordance_claim"],
                         "BOTH_SAME_SURPRISE_DIRECTION")
        self.assertTrue(all(
            x["surprise_relative_to_consensus"]=="ABOVE_CONSENSUS"
            for x in r["series"]))
        self.assertFalse(r["pre_event_prediction_was_recorded"])

    def test_04_both_at_consensus_are_not_one_trade(self):
        r=self.run_it(body=raw(head="0.4",core="0.3"))
        self.safe(r)
        self.assertEqual(r["headline_core_concordance_claim"],
                         "BOTH_AT_CONSENSUS")
        self.assertEqual(r["series"][0]["surprise_percentage_points"],"0.0")
        self.assertEqual(r["series"][1]["surprise_percentage_points"],"0.0")

    def test_05_fake_pre_event_capture_blocks_before_release(self):
        r=self.blocked(at=RELEASE_UTC-timedelta(seconds=1))
        self.assertEqual(r["reason"],
                         "PPI_OCTOBER_NOT_YET_RELEASED_AT_DECISION_CUTOFF")

    def test_06_absent_body_and_receipt_do_not_become_real_source(self):
        r=self.blocked(body=b"")
        self.assertEqual(r["reason"],
                         "BLS_SOURCE_BODY_OR_RECEIPT_NOT_LOCALLY_ACCEPTED")

    def test_07_changed_bytes_with_old_sha_blocks_context(self):
        b=raw()
        r=self.blocked(body=b+b"ATTACK",rec=receipt(b))
        self.assertEqual(r["reason"],
                         "BLS_SOURCE_BODY_OR_RECEIPT_NOT_LOCALLY_ACCEPTED")

    def test_08_bad_issuer_url_or_http_403_blocks(self):
        b=raw()
        for new in (replace(receipt(b),source_url="https://fake.local/ppi"),
                    replace(receipt(b),status_code=403)):
            with self.subTest(new=new):
                r=self.blocked(body=b,rec=new)
                self.assertEqual(r["reason"],
                                 "BLS_SOURCE_BODY_OR_RECEIPT_NOT_LOCALLY_ACCEPTED")

    def test_09_consensus_sha_tamper_blocks_arithmetic(self):
        snap=td();snap["source_body_sha256"]="0"*64
        r=self.blocked(td_snap=snap)
        self.assertEqual(r["reason"],
                         "LOCKED_PRE_EVENT_CONSENSUS_OR_PPI_ARITHMETIC_REJECTED")

    def test_10_consensus_numbers_rewritten_even_with_frozen_sha_blocks(self):
        d,e=td(),te()
        d["headline_consensus_mom_pct"]="0.1"
        e["headline_consensus_mom_pct"]="0.1"
        r=self.blocked(td_snap=d,te_snap=e)
        self.assertEqual(r["reason"],
                         "LOCKED_PRE_EVENT_CONSENSUS_OR_PPI_ARITHMETIC_REJECTED")

    def test_11_bad_asof_nanosecond_naive_or_text_blocks(self):
        for bad in (None,1,"2026-11-13T13:35:00Z",
                    AFTER.replace(tzinfo=None),
                    AFTER.replace(microsecond=1)):
            with self.subTest(bad=bad):
                r=self.blocked(at=bad)
                self.assertEqual(r["reason"],"INVALID_AS_OF_CLOCK")

    def test_12_wrong_core_group_not_confused_with_trade_services(self):
        r=self.blocked(body=raw(swap_core=True))
        self.assertEqual(r["reason"],
                         "BLS_SOURCE_BODY_OR_RECEIPT_NOT_LOCALLY_ACCEPTED")

    def test_13_unchanged_actual_zero_is_not_missing_or_negative_zero(self):
        b=raw(head="0.0",core="0.3").replace(
            b"increased 0.0 percent in October, seasonally adjusted",
            b"was unchanged in October, seasonally adjusted")
        r=self.run_it(body=b)
        self.safe(r)
        self.assertEqual(r["series"][0]["actual_pct_documentary_claim"],"0.0")
        self.assertEqual(r["series"][0]["surprise_percentage_points"],"-0.4")

    def test_14_capture_claim_after_asof_blocks(self):
        b=raw()
        future=replace(receipt(b),finished_utc=AFTER+timedelta(seconds=1))
        r=self.blocked(body=b,rec=future)
        self.assertEqual(r["reason"],
                         "BLS_SOURCE_BODY_OR_RECEIPT_NOT_LOCALLY_ACCEPTED")


if __name__=="__main__":
    unittest.main()
