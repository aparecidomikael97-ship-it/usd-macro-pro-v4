"""Synthetic body-to-PIT joins only. Never actual historical evidence."""
from __future__ import annotations

from dataclasses import replace
from datetime import timedelta, timezone
from hashlib import sha256
import unittest

from atlasquant_trader_us_cpi_ppi_official_body_join_lab import (
    inspect_us_cpi_ppi_official_body_join_lab as join,
)
from atlasquant_trader_us_cpi_ppi_pit_visibility_cutoff_lab import EventVintageClaim
from atlasquant_trader_us_cpi_source_custody_lab import RELEASE as CPI_RELEASE
from atlasquant_trader_us_ppi_oct2026_actual_table_guard_lab import (
    RELEASE_UTC as PPI_RELEASE, MAX_BYTES as PPI_MAX,
)
from test_atlasquant_trader_us_cpi_ppi_pit_visibility_cutoff_lab import macro_cases
from test_atlasquant_trader_us_oct2026_cpi_release_text_guard_lab import (
    raw as cpi_html, receipt as cpi_receipt,
)
from test_atlasquant_trader_us_ppi_oct2026_actual_table_guard_lab import (
    raw as ppi_html, receipt as ppi_receipt,
)

UTC = timezone.utc


def cases(*, cpi=None, ppi=None):
    bodies = {"CPI": cpi_html() if cpi is None else cpi,
              "PPI": ppi_html() if ppi is None else ppi}
    receipts = {"CPI": cpi_receipt(bodies["CPI"]),
                "PPI": ppi_receipt(bodies["PPI"])}
    rows = []
    for row in macro_cases():
        kind = row.kind
        r = receipts[kind]
        finish = r.captured_at_utc if kind == "CPI" else r.finished_utc
        value = "0.4" if kind == "CPI" else "0.5"
        actual = replace(row.actual, numeric_value=value,
                         original_sha256_claim=sha256(bodies[kind]).hexdigest(),
                         locally_captured_at_utc=finish)
        rows.append(replace(row, actual=actual, actual_source_bytes=bodies[kind]))
    return tuple(rows), receipts


def audit(rows=None, receipts=None, *, at=None, horizon="D1"):
    if rows is None or receipts is None:
        rows, receipts = cases()
    return join(decision_cutoff_utc=PPI_RELEASE+timedelta(minutes=4) if at is None else at,
                research_horizon=horizon, event_claims=rows,
                actual_http_receipts=receipts)


class OfficialBodyPitJoinTests(unittest.TestCase):
    def safety(self, report):
        self.assertEqual(report["schema"],
                         "ATLASQUANT_US_CPI_PPI_ORIGINAL_BODY_PIT_JOIN_LAB_V1")
        self.assertFalse(report["official_body_join_is_publisher_authentication"])
        self.assertFalse(report["consensus_source_values_semantically_parsed_by_this_join"])
        self.assertFalse(report["ppi_and_cpi_issuer_first_seen_witnessed"])
        self.assertFalse(report["source_first_seen_independently_authenticated"])
        self.assertFalse(report["trade_authorized"])
        self.assertFalse(report["publishable"])
        self.assertFalse(report["scheduler_enabled"])
        self.assertEqual(report["operational_bias"], "AGUARDAR")
        self.assertEqual(report["mt5_calls"], 0)
        self.assertEqual(report["http_requests"], 0)
        self.assertEqual(report["file_writes"], 0)
        self.assertIsNone(report["validated_fx_accuracy"])
        self.assertIsNone(report["directional_bias"])

    def test_01_both_official_parsers_match_locally_claimed_numbers(self):
        r = audit()
        self.safety(r)
        self.assertEqual(r["state"], "LAB_CPI_PPI_OFFICIAL_BODY_JOIN_UNATTESTED_NO_GO")
        self.assertEqual(r["original_actual_value_checked_against_document_body"],
                         ["CPI", "PPI"])
        self.assertEqual(r["economic_events_reconciled"], 2)
        self.assertEqual(r["research_events_with_first_print_visible_at_cutoff_claim_only"], 2)
        self.assertEqual(r["documentary_surprises_comparable_after_release_only"], 2)
        self.assertEqual([x["actual_first_print_percent_local_claim_visible"]
                          for x in r["feature_rows"]], ["0.4", "0.5"])

    def test_02_before_releases_hide_both_results(self):
        r = audit(at=CPI_RELEASE-timedelta(minutes=1))
        self.safety(r)
        self.assertEqual(r["original_actual_value_checked_against_document_body"], [])
        self.assertEqual(r["research_events_with_first_print_visible_at_cutoff_claim_only"], 0)
        self.assertEqual([x["actual_first_print_percent_local_claim_visible"]
                          for x in r["feature_rows"]], [None, None])

    def test_03_exact_cpi_schedule_does_not_mean_data_collected(self):
        r = audit(at=CPI_RELEASE)
        self.safety(r)
        self.assertEqual(r["original_actual_value_checked_against_document_body"], [])

    def test_04_cpi_collected_ppi_still_future(self):
        r = audit(at=CPI_RELEASE+timedelta(hours=8))
        self.safety(r)
        self.assertEqual(r["original_actual_value_checked_against_document_body"], ["CPI"])
        self.assertEqual([x["actual_first_print_percent_local_claim_visible"]
                          for x in r["feature_rows"]], ["0.4", None])

    def test_05_ppi_release_instant_not_equivalent_to_capture(self):
        r = audit(at=PPI_RELEASE)
        self.safety(r)
        self.assertEqual(r["original_actual_value_checked_against_document_body"], ["CPI"])
        self.assertIsNone(r["feature_rows"][1]["actual_first_print_percent_local_claim_visible"])

    def test_06_mutated_actual_number_with_same_original_digest_is_blocked(self):
        rows, rec = cases()
        rows = (replace(rows[0], actual=replace(rows[0].actual,
                                               numeric_value="0.9")), rows[1])
        r = audit(rows, rec)
        self.safety(r)
        self.assertEqual(r["state"], "LAB_CPI_PPI_OFFICIAL_BODY_JOIN_BLOCKED_NO_GO")
        self.assertEqual(r["reason"], "CPI_OFFICIAL_BODY_METRIC_OR_DIGEST_MISMATCH")
        self.assertEqual(r["feature_rows"], [])

    def test_07_ppi_declared_wrong_monthly_number_fails_closed(self):
        rows, rec = cases()
        rows = (rows[0], replace(rows[1], actual=replace(rows[1].actual,
                                                        numeric_value="0.9")))
        r = audit(rows, rec)
        self.safety(r)
        self.assertEqual(r["reason"], "PPI_OFFICIAL_BODY_METRIC_OR_DIGEST_MISMATCH")

    def test_08_cpi_forged_digest_and_html_still_needs_parser(self):
        rows, rec = cases()
        fake = b"<html>fake CPI monthly 0.4</html>"
        rows = (replace(rows[0], actual_source_bytes=fake,
                        actual=replace(rows[0].actual,
                                       original_sha256_claim=sha256(fake).hexdigest())),
                rows[1])
        rec = {**rec, "CPI":replace(rec["CPI"],
                                    body_sha256_claim=sha256(fake).hexdigest())}
        r = audit(rows, rec)
        self.safety(r)
        self.assertEqual(r["reason"], "CPI_OFFICIAL_BODY_METRIC_OR_DIGEST_MISMATCH")

    def test_09_ppi_table_missing_prevents_value_join(self):
        rows, rec = cases(ppi=ppi_html(include_table=False))
        r = audit(rows, rec)
        self.safety(r)
        self.assertEqual(r["reason"], "PPI_OFFICIAL_BODY_METRIC_OR_DIGEST_MISMATCH")

    def test_10_ppi_million_byte_official_style_html_fits_parser_limit(self):
        base=ppi_html()
        large=base+b" " * (1_612_602-len(base))
        rows, rec = cases(ppi=large)
        r = audit(rows, rec)
        self.safety(r)
        self.assertEqual(r["original_actual_value_checked_against_document_body"],
                         ["CPI", "PPI"])

    def test_11_over_ppi_parser_four_mb_limit_is_blocked(self):
        big=ppi_html()+b" " * PPI_MAX
        rows, rec = cases(ppi=big)
        r = audit(rows, rec)
        self.safety(r)
        self.assertEqual(r["reason"], "PPI_OFFICIAL_BODY_METRIC_OR_DIGEST_MISMATCH")

    def test_12_receipt_capture_clock_cannot_disagree_with_actual(self):
        rows, rec = cases()
        rec = {**rec, "PPI": replace(rec["PPI"],
                                     finished_utc=rec["PPI"].finished_utc+timedelta(seconds=1))}
        r = audit(rows, rec)
        self.safety(r)
        self.assertEqual(r["reason"], "PPI_HTTP_RECEIPT_CLOCK_OR_ORIGIN_MISMATCH")

    def test_13_bad_http_origin_blocks_even_matched_value_and_digest(self):
        rows, rec = cases()
        rec = {**rec, "CPI":replace(rec["CPI"],source_url="https://example.com/cpi")}
        r = audit(rows, rec)
        self.safety(r)
        self.assertEqual(r["reason"], "CPI_HTTP_RECEIPT_CLOCK_OR_ORIGIN_MISMATCH")

    def test_14_visible_result_without_receipt_refused(self):
        rows, rec = cases()
        rec = {**rec, "PPI":None}
        r = audit(rows, rec)
        self.safety(r)
        self.assertEqual(r["reason"], "PPI_HTTP_RECEIPT_CLOCK_OR_ORIGIN_MISMATCH")

    def test_15_future_document_in_payload_never_leaks_into_past(self):
        rows, rec = cases()
        rows=(replace(rows[0],actual=replace(rows[0].actual,
                                            numeric_value="99.9")),rows[1])
        r = audit(rows,rec,at=CPI_RELEASE-timedelta(seconds=1))
        self.safety(r)
        self.assertEqual(r["original_actual_value_checked_against_document_body"],[])
        self.assertTrue(all(x["actual_first_print_percent_local_claim_visible"] is None
                            for x in r["feature_rows"]))

    def test_16_lookahead_at_ppi_only_cannot_inflate_seven_independent_events(self):
        r=audit()
        self.safety(r)
        self.assertEqual((r["us_release_direct_leg_pairs"],
                          r["non_usd_direct_leg_pairs"]),(7,21))
        self.assertTrue(r["ppi_event_not_seven_independent_fx_trials"])

    def test_17_invalid_horizon_blocks(self):
        rows, rec = cases()
        r = audit(rows, rec, horizon="M15")
        self.safety(r)
        self.assertEqual(r["state"], "LAB_CPI_PPI_OFFICIAL_BODY_JOIN_BLOCKED_NO_GO")

    def test_18_duplicate_event_blocks(self):
        rows, rec=cases()
        r=audit((rows[0],rows[0]),rec)
        self.safety(r)
        self.assertEqual(r["reason"], "INVALID_OR_DUPLICATED_ECONOMIC_EVENT")

    def test_19_missing_consensus_still_never_fake_surprise(self):
        rows, rec=cases()
        rows=tuple(replace(x,consensus=None,consensus_source_bytes=None) for x in rows)
        r=audit(rows,rec)
        self.safety(r)
        self.assertEqual(r["documentary_surprises_comparable_after_release_only"],0)

    def test_20_pre_release_unpaired_receipt_with_no_actual_blocks(self):
        rows, rec=cases()
        rows=(replace(rows[0],actual=None,actual_source_bytes=None),rows[1])
        r=audit(rows,rec)
        self.safety(r)
        self.assertEqual(r["reason"], "CPI_UNPAIRED_ACTUAL_SOURCE_OR_RECEIPT")


if __name__ == "__main__":
    unittest.main()
