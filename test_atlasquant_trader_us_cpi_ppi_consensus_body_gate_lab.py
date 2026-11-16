"""Synthetic TD/TE source-body consensus tests; no real poll source archived.

Public locked SHA256 constants stay frozen. Test-only patching those hashes
checks parser composition but never asserts that any synthetic HTML was
captured, published, or witnessed by a real source before the event.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from unittest.mock import patch
import unittest

from atlasquant_trader_us_cpi_ppi_consensus_body_gate_lab import (
    PpiPreEventOriginalPair,
    inspect_us_cpi_ppi_source_bound_consensus_lab as inspect,
    _inspect_original_pair,
)
from atlasquant_trader_us_cpi_ppi_pit_visibility_cutoff_lab import EventVintageClaim
from atlasquant_trader_us_ppi_pre_event_preview_lab import EVENT_RELEASE_UTC
from atlasquant_trader_us_ppi_te_second_consensus_lab import EVENT as TE_RELEASE
from atlasquant_trader_fx28_macro_event_surprise_reaction_contract_lab import (
    MetricIdentity, PreEventConsensus,
)
from test_atlasquant_trader_us_ppi_pre_event_preview_lab import html as td_html, rec as td_rec, END as TD_END
from test_atlasquant_trader_us_ppi_te_second_consensus_lab import fixture as te_html, cap as te_rec, END as TE_END
from test_atlasquant_trader_us_cpi_ppi_official_body_join_lab import cases as original_body_cases
from test_atlasquant_trader_us_cpi_ppi_pit_visibility_cutoff_lab import macro_cases

UTC=timezone.utc


def pair(td=None, te=None):
    td = td_html() if td is None else td
    te = te_html() if te is None else te
    return PpiPreEventOriginalPair(td, td_rec(td), te, te_rec(te))


def roster_without_actual():
    return (
        EventVintageClaim("CPI", None, None, None, None),
        EventVintageClaim("PPI", None, None, None, None),
    )


def receipts_without_actual():
    return {"CPI": None, "PPI": None}


@contextmanager
def synthetic_digest_fixture_lock(p):
    # Patching only during isolated tests; the public GitHub source retains
    # the pre-event pinned real TD/TE SHA-256 constants.
    with patch("atlasquant_trader_us_cpi_ppi_consensus_body_gate_lab.TD_PRE_EVENT_HTML_SHA256",
               sha256(p.td_original_html).hexdigest()), patch(
         "atlasquant_trader_us_cpi_ppi_consensus_body_gate_lab.TE_PRE_EVENT_HTML_SHA256",
               sha256(p.te_original_html).hexdigest()):
        yield


def audit(p=None, *, at=None, rows=None, receipts=None, horizon="D1"):
    return inspect(
        decision_cutoff_utc=EVENT_RELEASE_UTC+timedelta(minutes=6) if at is None else at,
        research_horizon=horizon,
        event_claims=roster_without_actual() if rows is None else rows,
        actual_http_receipts=receipts_without_actual() if receipts is None else receipts,
        ppi_original_pair=p,
    )


class CpiPpiConsensusBodyGateTests(unittest.TestCase):
    def safety(self, r):
        self.assertEqual(r["schema"],
                         "ATLASQUANT_CPI_PPI_PRE_EVENT_CONSENSUS_SOURCE_BOUND_PIT_LAB_V1")
        self.assertFalse(r["cpi_pre_event_consensus_admitted"])
        self.assertTrue(r["cpi_retrospectively_found_preview_blocked_from_historical_forecast"])
        self.assertTrue(r["ppi_td_and_te_are_one_event_not_two_independent_economic_trials"])
        self.assertFalse(r["publisher_first_seen_independently_attested"])
        self.assertFalse(r["market_effect_calibrated"])
        self.assertFalse(r["trade_authorized"])
        self.assertFalse(r["publishable"])
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        self.assertIsNone(r["validated_fx_accuracy"])
        self.assertIsNone(r["directional_bias"])

    def test_01_missing_raw_pre_event_consensus_never_admitted(self):
        r=audit(None)
        self.safety(r)
        self.assertFalse(r["ppi_consensus_admitted_from_two_pinned_pre_event_html"])
        self.assertEqual(r["ppi_pre_event_original_pair"]["reason"],
                         "ORIGINAL_PRE_EVENT_TD_TE_SOURCE_BYTES_UNAVAILABLE")
        self.assertEqual(r["research_events_with_pre_release_consensus_visible"],0)
        self.assertEqual(r["documentary_surprises_comparable_after_release_only"],0)

    def test_02_unpinned_synthetic_html_never_passes_public_sha_lock(self):
        r=audit(pair())
        self.safety(r)
        self.assertEqual(r["ppi_pre_event_original_pair"]["reason"],
                         "PRECOMMITTED_TD_TE_ORIGINAL_DIGEST_MISMATCH")
        self.assertFalse(r["ppi_consensus_admitted_from_two_pinned_pre_event_html"])

    def test_03_pair_semantics_under_test_only_mock_lock(self):
        p=pair()
        res=_inspect_original_pair(
            sources=p,cutoff=TE_END+timedelta(minutes=10),
            expected_td_digest=sha256(p.td_original_html).hexdigest(),
            expected_te_digest=sha256(p.te_original_html).hexdigest())
        self.assertEqual(res["state"],
                         "LAB_PPI_PRE_EVENT_TD_TE_BYTES_AND_METRICS_LOCALLY_RECONCILED_NO_GO")
        self.assertEqual(res["headline_consensus_from_two_original_bodies_pct"],"0.4")
        self.assertEqual(res["core_consensus_from_two_original_bodies_pct"],"0.3")
        self.assertTrue(res["both_source_local_capture_claims_pre_event"])
        self.assertFalse(res["publisher_first_seen_independently_authenticated"])

    def test_04_source_claims_not_visible_before_second_capture(self):
        p=pair()
        with synthetic_digest_fixture_lock(p):
            r=audit(p,at=TE_END-timedelta(seconds=1))
        self.safety(r)
        self.assertFalse(r["ppi_consensus_admitted_from_two_pinned_pre_event_html"])
        self.assertEqual(r["ppi_pre_event_original_pair"]["reason"],
                         "SOURCE_CAPTURE_AFTER_RESEARCH_CUTOFF_NOT_VISIBLE")
        self.assertEqual(r["research_events_with_pre_release_consensus_visible"],0)

    def test_05_source_claims_visible_after_second_capture_only(self):
        p=pair()
        with synthetic_digest_fixture_lock(p):
            r=audit(p,at=TE_END+timedelta(seconds=1))
        self.safety(r)
        self.assertTrue(r["ppi_consensus_admitted_from_two_pinned_pre_event_html"])
        self.assertEqual(r["feature_rows"][1]["consensus_percent_local_claim_visible"],"0.4")
        self.assertEqual(r["feature_rows"][0]["consensus_percent_local_claim_visible"],None)
        self.assertIsNone(r["feature_rows"][1]["actual_minus_consensus_percentage_points_documentary"])
        self.assertFalse(r["ppi_pre_event_original_pair"]["te_own_forecast_counted_as_consensus"])

    def test_06_one_economic_ppi_event_no_double_count_td_and_te(self):
        p=pair()
        with synthetic_digest_fixture_lock(p):
            r=audit(p,at=TE_END+timedelta(seconds=1))
        self.safety(r)
        self.assertEqual(r["economic_events_reconciled"],2)
        self.assertEqual(r["research_events_with_pre_release_consensus_visible"],1)
        self.assertEqual(r["research_events_with_first_print_visible_at_cutoff_claim_only"],0)
        self.assertEqual(r["documentary_surprises_comparable_after_release_only"],0)

    def test_07_cpi_post_discovered_poll_claim_even_forged_pre_event_is_stripped(self):
        p=pair()
        rows=list(macro_cases())
        rows[0]=replace(rows[0], actual=None,actual_source_bytes=None)
        rows[1]=replace(rows[1], actual=None,actual_source_bytes=None)
        with synthetic_digest_fixture_lock(p):
            r=audit(p,rows=tuple(rows),at=TE_END+timedelta(seconds=1))
        self.safety(r)
        self.assertEqual(r["feature_rows"][0]["consensus_percent_local_claim_visible"],None)
        self.assertEqual(r["feature_rows"][1]["consensus_percent_local_claim_visible"],"0.4")

    def test_08_td_last_period_not_consensus(self):
        p=pair(td=td_html(previous="1.9"))
        with synthetic_digest_fixture_lock(p):
            r=audit(p,at=TE_END+timedelta(seconds=1))
        self.safety(r)
        self.assertTrue(r["ppi_consensus_admitted_from_two_pinned_pre_event_html"])
        self.assertEqual(r["feature_rows"][1]["consensus_percent_local_claim_visible"],"0.4")

    def test_09_te_own_forecast_not_consensus(self):
        p=pair(te=te_html(own="1.9%"))
        with synthetic_digest_fixture_lock(p):
            r=audit(p,at=TE_END+timedelta(seconds=1))
        self.safety(r)
        self.assertEqual(r["feature_rows"][1]["consensus_percent_local_claim_visible"],"0.4")
        self.assertFalse(r["ppi_pre_event_original_pair"]["te_own_forecast_counted_as_consensus"])

    def test_10_two_provider_consensus_disagreement_blocks(self):
        p=pair(te=te_html(h="0.5%"))
        with synthetic_digest_fixture_lock(p):
            r=audit(p,at=TE_END+timedelta(seconds=1))
        self.safety(r)
        self.assertFalse(r["ppi_consensus_admitted_from_two_pinned_pre_event_html"])
        self.assertEqual(r["ppi_pre_event_original_pair"]["reason"],
                         "TD_TE_CONSENSUS_DISAGREEMENT_OR_PRE_EVENT_VALUES_CHANGED")

    def test_11_both_sources_agree_on_modified_wrong_frozen_value_blocks(self):
        p=pair(td=td_html(head="0.5"),te=te_html(h="0.5%"))
        with synthetic_digest_fixture_lock(p):
            r=audit(p,at=TE_END+timedelta(seconds=1))
        self.safety(r)
        self.assertFalse(r["ppi_consensus_admitted_from_two_pinned_pre_event_html"])
        self.assertEqual(r["ppi_pre_event_original_pair"]["reason"],
                         "TD_TE_CONSENSUS_DISAGREEMENT_OR_PRE_EVENT_VALUES_CHANGED")

    def test_12_td_wrong_series_or_unit_blocks_even_matching_consensus(self):
        p=pair(td=td_html(unit="Y/Y % Chg."))
        with synthetic_digest_fixture_lock(p):
            r=audit(p,at=TE_END+timedelta(seconds=1))
        self.safety(r)
        self.assertEqual(r["ppi_pre_event_original_pair"]["reason"],
                         "TD_TE_ORIGINAL_HTML_PARSER_OR_CAPTURE_VALIDATION_FAILED")

    def test_13_te_actual_column_populated_does_not_masquerade_as_poll(self):
        p=pair(te=te_html(actual="0.5%"))
        with synthetic_digest_fixture_lock(p):
            r=audit(p,at=TE_END+timedelta(seconds=1))
        self.safety(r)
        self.assertEqual(r["ppi_pre_event_original_pair"]["reason"],
                         "TD_TE_ORIGINAL_HTML_PARSER_OR_CAPTURE_VALIDATION_FAILED")

    def test_14_td_hash_mismatch_blocks(self):
        p=pair()
        with synthetic_digest_fixture_lock(p):
            corrupted=replace(p,td_original_html=p.td_original_html+b"changed")
            r=audit(corrupted,at=TE_END+timedelta(seconds=1))
        self.safety(r)
        self.assertEqual(r["ppi_pre_event_original_pair"]["reason"],
                         "PRECOMMITTED_TD_TE_ORIGINAL_DIGEST_MISMATCH")

    def test_15_te_hash_mismatch_blocks(self):
        p=pair()
        with synthetic_digest_fixture_lock(p):
            corrupted=replace(p,te_original_html=p.te_original_html+b"changed")
            r=audit(corrupted,at=TE_END+timedelta(seconds=1))
        self.safety(r)
        self.assertEqual(r["ppi_pre_event_original_pair"]["reason"],
                         "PRECOMMITTED_TD_TE_ORIGINAL_DIGEST_MISMATCH")

    def test_16_td_clock_after_release_blocked(self):
        p=pair()
        p=replace(p,td_http_capture=replace(p.td_http_capture,
                                            finished_at_utc=EVENT_RELEASE_UTC+timedelta(seconds=1)))
        with synthetic_digest_fixture_lock(p):
            r=audit(p,at=EVENT_RELEASE_UTC+timedelta(minutes=10))
        self.safety(r)
        self.assertEqual(r["ppi_pre_event_original_pair"]["reason"],
                         "SOURCE_CAPTURE_NOT_PRE_RELEASE")

    def test_17_te_clock_after_release_blocked(self):
        p=pair()
        p=replace(p,te_http_capture=replace(p.te_http_capture,
                                            finished_utc=EVENT_RELEASE_UTC+timedelta(seconds=1)))
        with synthetic_digest_fixture_lock(p):
            r=audit(p,at=EVENT_RELEASE_UTC+timedelta(minutes=10))
        self.safety(r)
        self.assertEqual(r["ppi_pre_event_original_pair"]["reason"],
                         "SOURCE_CAPTURE_NOT_PRE_RELEASE")

    def test_18_unknown_caller_injected_consensus_value_cannot_overwrite_sources(self):
        p=pair()
        rows=list(roster_without_actual())
        forged=PreEventConsensus(
            MetricIdentity("USD","US_PPI_FINAL_DEMAND","2026-10","MOM","SA","PERCENT"),
            "9.9","https://economics.td.com/example",sha256(b"f").hexdigest(),
            datetime(2026,11,6,tzinfo=UTC),TD_END)
        rows[1]=replace(rows[1],consensus=forged,consensus_source_bytes=b"f")
        with synthetic_digest_fixture_lock(p):
            r=audit(p,rows=tuple(rows),at=TE_END+timedelta(seconds=1))
        self.safety(r)
        self.assertFalse(r["ppi_consensus_admitted_from_two_pinned_pre_event_html"])
        self.assertTrue(r["supplied_ppi_consensus_not_from_original_source_rejected"])
        self.assertIsNone(r["feature_rows"][1]["consensus_percent_local_claim_visible"])

    def test_19_wrong_caller_supplied_bytes_cannot_redefine_td_document(self):
        p=pair()
        rows=list(roster_without_actual())
        rows[1]=replace(rows[1],consensus_source_bytes=b"injected wrong")
        with synthetic_digest_fixture_lock(p):
            r=audit(p,rows=tuple(rows),at=TE_END+timedelta(seconds=1))
        self.safety(r)
        self.assertTrue(r["supplied_ppi_consensus_not_from_original_source_rejected"])
        self.assertIsNone(r["feature_rows"][1]["consensus_percent_local_claim_visible"])

    def test_20_consensus_and_actual_same_ppi_event_documentary_not_usd_signal(self):
        p=pair()
        rows,rec=original_body_cases()
        with synthetic_digest_fixture_lock(p):
            r=audit(p,rows=rows,receipts=rec,at=EVENT_RELEASE_UTC+timedelta(minutes=4))
        self.safety(r)
        self.assertTrue(r["ppi_consensus_admitted_from_two_pinned_pre_event_html"])
        self.assertEqual(r["feature_rows"][1]["consensus_percent_local_claim_visible"],"0.4")
        self.assertEqual(r["feature_rows"][1]["actual_first_print_percent_local_claim_visible"],"0.5")
        self.assertEqual(r["feature_rows"][1]["actual_minus_consensus_percentage_points_documentary"],"0.1")
        self.assertEqual(r["documentary_surprises_comparable_after_release_only"],1)

    def test_21_future_results_blocked_even_when_pre_event_consensus_passes(self):
        p=pair()
        rows,rec=original_body_cases()
        with synthetic_digest_fixture_lock(p):
            r=audit(p,rows=rows,receipts=rec,at=TE_END+timedelta(seconds=1))
        self.safety(r)
        self.assertTrue(r["ppi_consensus_admitted_from_two_pinned_pre_event_html"])
        self.assertEqual(r["research_events_with_first_print_visible_at_cutoff_claim_only"],0)
        self.assertEqual(r["documentary_surprises_comparable_after_release_only"],0)

    def test_22_invalid_event_roster_blocks(self):
        p=pair()
        with synthetic_digest_fixture_lock(p):
            r=audit(p,rows=(roster_without_actual()[0],),at=TE_END+timedelta(seconds=1))
        self.safety(r)
        self.assertFalse(r["ppi_consensus_admitted_from_two_pinned_pre_event_html"])
        self.assertEqual(r["feature_rows"],[])

    def test_23_wrong_horizon_blocks(self):
        p=pair()
        with synthetic_digest_fixture_lock(p):
            r=audit(p,horizon="M15",at=TE_END+timedelta(seconds=1))
        self.safety(r)
        self.assertFalse(r["ppi_consensus_admitted_from_two_pinned_pre_event_html"])
        self.assertEqual(r["feature_rows"],[])

    def test_24_source_missing_te_never_admits_td_alone(self):
        p=pair()
        p=replace(p,te_original_html=None)
        with synthetic_digest_fixture_lock(pair()):
            r=audit(p,at=TE_END+timedelta(seconds=1))
        self.safety(r)
        self.assertFalse(r["ppi_consensus_admitted_from_two_pinned_pre_event_html"])

    def test_25_td_server_http_clock_bad_never_admits(self):
        p=pair()
        p=replace(p,td_http_capture=replace(p.td_http_capture,
                                            server_date_http="Fri, 13 Nov 2026 08:30:00 GMT"))
        with synthetic_digest_fixture_lock(p):
            r=audit(p,at=TE_END+timedelta(seconds=1))
        self.safety(r)
        self.assertFalse(r["ppi_consensus_admitted_from_two_pinned_pre_event_html"])
        self.assertEqual(r["ppi_pre_event_original_pair"]["reason"],
                         "TD_TE_ORIGINAL_HTML_PARSER_OR_CAPTURE_VALIDATION_FAILED")


if __name__ == "__main__":
    unittest.main()
