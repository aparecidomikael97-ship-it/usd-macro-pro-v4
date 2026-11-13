"""Synthetic documentary contracts; released PPI values never mean predictions."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_trader_us_ppi_sep2026_revision_vintage_lab import (
    INITIAL_RELEASE_UTC, REVISION_RELEASE_UTC, INITIAL_URL, REVISION_URL,
    inspect_sep2026_ppi_revision_lineage_lab as inspect,
)
NOW = REVISION_RELEASE_UTC + timedelta(minutes=5)


def initial():
    # Values correspond to public Sep-2026 first-release claim on 15 Oct 2026.
    # Digests are synthetic placeholders: no original BLS bytes retained here.
    return {
        "reference_month": "2026-09",
        "release_at_utc": INITIAL_RELEASE_UTC.isoformat(),
        "capture_at_utc": (INITIAL_RELEASE_UTC + timedelta(minutes=1)).isoformat(),
        "source_url": INITIAL_URL, "source_sha256_claim": "a"*64,
        "headline_sa_mom_pct": "1.3", "core_ex_food_energy_sa_mom_pct": "0.7",
    }


def revised():
    # Values correspond to public revision in Oct-2026 BLS release on Nov 13.
    return {
        "reference_month": "2026-09",
        "release_at_utc": REVISION_RELEASE_UTC.isoformat(),
        "capture_at_utc": (REVISION_RELEASE_UTC + timedelta(minutes=1)).isoformat(),
        "source_url": REVISION_URL, "source_sha256_claim": "b"*64,
        "headline_sa_mom_pct": "1.4", "core_ex_food_energy_sa_mom_pct": "0.8",
    }


class PpiRevisionVintageLabTests(unittest.TestCase):
    def run_it(self, first=None, second=None, now=NOW):
        return inspect(september_first_print=initial() if first is None else first,
                       november_release_revision=revised() if second is None else second,
                       as_of_utc=now)

    def locked(self, result):
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        for field in ("trade_authorized", "publishable", "live_alert_allowed",
                      "worker_enabled", "scheduler_enabled",
                      "original_issuer_bytes_retained_and_verified",
                      "first_seen_time_independently_attested",
                      "document_originality_authenticated",
                      "revision_eligible_for_prior_date_prediction",
                      "historical_backtest_eligible"):
            self.assertFalse(result[field], field)
        self.assertIsNone(result["calibrated_probability"])
        self.assertIsNone(result["directional_bias"])
        self.assertEqual(result["http_requests"], 0)
        self.assertEqual(result["file_writes"], 0)

    def test_01_two_vintages_keep_initial_and_revised_values(self):
        r = self.run_it()
        self.assertEqual(r["state"], "LAB_PPI_SEP2026_REVISION_COMPARISON_UNATTESTED")
        self.assertEqual(r["first_print_headline_sa_mom_pct_claim"], "1.3")
        self.assertEqual(r["revision_headline_sa_mom_pct_claim"], "1.4")
        self.assertEqual(r["first_print_core_sa_mom_pct_claim"], "0.7")
        self.assertEqual(r["revision_core_sa_mom_pct_claim"], "0.8")
        self.assertEqual(r["headline_revision_delta_pp"], "0.1")
        self.assertEqual(r["core_revision_delta_pp"], "0.1")
        self.assertTrue(r["release_vintages_retained_separately"])
        self.locked(r)

    def test_02_not_yet_released_can_never_see_future_revision(self):
        r = self.run_it(now=REVISION_RELEASE_UTC-timedelta(microseconds=1))
        self.assertEqual(r["state"], "LAB_WAIT_PPI_NOV2026_REVISION")
        self.assertIsNone(r["revision_headline_sa_mom_pct_claim"])
        self.locked(r)

    def test_03_naive_and_text_asof_block(self):
        for now in (NOW.replace(tzinfo=None), NOW.isoformat()):
            r=self.run_it(now=now)
            self.assertEqual(r["reason"], "INVALID_AS_OF_CLOCK")
            self.locked(r)

    def test_04_swapped_or_wrong_publisher_urls_fail_closed(self):
        for is_first in (True, False):
            a,b=initial(),revised()
            if is_first: a["source_url"]=REVISION_URL
            else: b["source_url"]=INITIAL_URL
            r=self.run_it(first=a,second=b)
            self.assertIn("VINTAGE_SOURCE_OR_REFERENCE_MONTH_MISMATCH",r["reason"])
            self.locked(r)

    def test_05_wrong_reference_month_and_cutoff_fail_closed(self):
        for field,value in (("reference_month","2026-10"),
                            ("release_at_utc",REVISION_RELEASE_UTC.isoformat())):
            a=initial();a[field]=value
            r=self.run_it(first=a)
            self.assertEqual(r["state"],"LAB_PPI_VINTAGE_RECONCILIATION_BLOCKED")
            self.locked(r)

    def test_06_first_print_claim_captured_only_after_revision_blocks(self):
        a=initial()
        a["capture_at_utc"]=(REVISION_RELEASE_UTC+timedelta(seconds=1)).isoformat()
        r=self.run_it(first=a)
        self.assertEqual(r["reason"],"FIRST_FIRST_PRINT_NOT_CAPTURED_BEFORE_REVISION")
        self.locked(r)

    def test_07_second_claim_before_publication_blocks(self):
        b=revised()
        b["capture_at_utc"]=(REVISION_RELEASE_UTC-timedelta(seconds=1)).isoformat()
        r=self.run_it(second=b)
        self.assertEqual(r["reason"],"REVISION_VINTAGE_CAPTURE_CLOCK_INVALID")
        self.locked(r)

    def test_08_future_capture_and_naive_clock_block(self):
        for bad in ((NOW+timedelta(seconds=1)).isoformat(),
                    NOW.replace(tzinfo=None).isoformat()):
            b=revised();b["capture_at_utc"]=bad
            r=self.run_it(second=b)
            self.assertEqual(r["reason"],"REVISION_VINTAGE_CAPTURE_CLOCK_INVALID")
            self.locked(r)

    def test_09_bogus_digest_and_shared_digest_block(self):
        for mutation in ("bad_hash","same_hash"):
            b=revised()
            b["source_sha256_claim"]="foo" if mutation=="bad_hash" else "a"*64
            r=self.run_it(second=b)
            self.assertEqual(r["state"],"LAB_PPI_VINTAGE_RECONCILIATION_BLOCKED")
            self.locked(r)

    def test_10_invalid_numeric_or_missing_values_block(self):
        for value in ("NaN","Infinity","-21",1.4,"", "1,4"):
            b=revised();b["headline_sa_mom_pct"]=value
            r=self.run_it(second=b)
            self.assertEqual(r["reason"],"REVISION_VINTAGE_MONTHLY_SA_VALUES_MISSING_OR_INVALID")
            self.locked(r)

    def test_11_duplicate_or_missing_keys_block(self):
        for key,operation in (("attested", "add"),("core_ex_food_energy_sa_mom_pct","delete")):
            b=revised()
            if operation=="add":b[key]=True
            else:b.pop(key)
            r=self.run_it(second=b)
            self.assertEqual(r["reason"],"REVISION_VINTAGE_PACKET_KEYS_MISSING_OR_EXTRA")
            self.locked(r)

    def test_12_even_same_values_are_two_distinct_vintages_not_accuracy(self):
        b=revised()
        b["headline_sa_mom_pct"]="1.3"
        b["core_ex_food_energy_sa_mom_pct"]="0.7"
        r=self.run_it(second=b)
        self.assertEqual(r["headline_revision_delta_pp"],"0.0")
        self.assertEqual(r["core_revision_delta_pp"],"0.0")
        self.assertFalse(r["revision_eligible_for_prior_date_prediction"])
        self.locked(r)


if __name__=="__main__":
    unittest.main()
