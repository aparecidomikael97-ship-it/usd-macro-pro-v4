"""Offline tests: JPY/CHF may be queried, NZD must never GET without permission."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from urllib.error import HTTPError, URLError
import unittest

from atlasquant_trader_three_missing_policy_cloud_probe_lab import (
    ORDER, SCHEMA, STEPS,
    probe_three_missing_policy_sources_once_lab as probe,
    main,
)
from test_atlasquant_trader_jpy_boj_guideline_source_receipt_lab import (
    homepage as boj_html, receipt as boj_receipt,
)
from test_atlasquant_trader_chf_snb_current_policy_receipt_lab import (
    html_page as snb_html, receipt as snb_receipt,
)
from test_atlasquant_trader_nzd_rbnz_ocr_receipt_lab import (
    html_page as rbnz_html, receipt as rbnz_receipt,
)

UTC=timezone.utc
NOW=datetime(2026,11,13,11,0,tzinfo=UTC)


def fixtures():
    htmls=(boj_html(),snb_html(),rbnz_html())
    receipts=(boj_receipt,snb_receipt,rbnz_receipt)
    steps={}
    for index,currency in enumerate(ORDER):
        raw=htmls[index]
        rec=receipts[index](raw)
        _,validator,field=STEPS[currency]
        def collector(raw=raw,rec=rec):
            return raw,rec
        steps[currency]=(collector,validator,field)
    return steps


class ProbeThreeOfficialIssuerSourcesTests(unittest.TestCase):
    def safe(self,r):
        self.assertEqual(r["schema"],SCHEMA)
        self.assertEqual(r["operational_bias"],"AGUARDAR")
        for key in ("trade_authorized","publishable","live_alert_allowed",
                    "worker_enabled","scheduler_enabled",
                    "source_original_bytes_retained",
                    "source_receipt_locally_archived_on_am12",
                    "missing_on_am12_resolved",
                    "independent_issuer_origin_verified",
                    "historical_first_seen_authenticated",
                    "pre_event_consensus_verified",
                    "signed_fx_impact_calibrated"):
            self.assertFalse(r[key],key)
        self.assertTrue(r["policy_decided_rate_is_not_market_expectation"])
        self.assertIsNone(r["out_of_sample_accuracy"])
        self.assertIsNone(r["calibrated_probability"])
        self.assertEqual(r["new_cost_brl"],0)
        self.assertEqual(r["files_written"],0)

    def test_01_explicit_flag_required_zero_requests(self):
        touched=[]
        def touch():
            touched.append(1)
            raise AssertionError("would make network request")
        steps={c:(touch,STEPS[c][1],STEPS[c][2]) for c in ORDER}
        out=probe(explicit_probe=False,clock=lambda:NOW,steps=steps)
        self.safe(out)
        self.assertEqual(out["state"],"LAB_THREE_ISSUER_CLOUD_PROBE_NO_REQUEST")
        self.assertEqual(out["requests_started_claim"],0)
        self.assertEqual(touched,[])

    def test_02_only_jpy_chf_synthetic_originals_pass_nzd_permission_blocked(self):
        out=probe(explicit_probe=True,clock=lambda:NOW,steps=fixtures())
        self.safe(out)
        self.assertEqual(out["state"],"LAB_THREE_ISSUER_CLOUD_PROBE_COMPLETED_NO_GO")
        self.assertEqual(out["requests_started_claim"],2)
        self.assertEqual(out["valid_ephemeral_original_checks"],2)
        self.assertEqual(set(out["source_results"]),set(ORDER))
        self.assertEqual(out["source_results"]["JPY"]["official_policy_pct_claim"],"1.25")
        self.assertEqual(out["source_results"]["CHF"]["official_policy_pct_claim"],"0.00")
        self.assertIsNone(out["source_results"]["NZD"]["official_policy_pct_claim"])
        self.assertEqual(
            out["source_results"]["NZD"]["status"],
            "RBNZ_WRITTEN_PERMISSION_REQUIRED_NO_HTTP_NO_GO")
        self.assertFalse(out["rbnz_automated_access_permission_verified"])
        self.assertEqual(out["planned_official_https_get_max"],2)

    def test_03_one_403_does_not_retry_and_other_two_continue(self):
        steps=fixtures()
        calls=[]
        def rejected():
            calls.append("JPY")
            raise HTTPError("https://www.boj.or.jp/en/",403,"Forbidden",None,None)
        steps["JPY"]=(rejected,steps["JPY"][1],steps["JPY"][2])
        out=probe(explicit_probe=True,clock=lambda:NOW,steps=steps)
        self.safe(out)
        self.assertEqual(calls,["JPY"])
        self.assertEqual(out["requests_started_claim"],2)
        self.assertEqual(out["valid_ephemeral_original_checks"],1)
        self.assertEqual(out["source_results"]["JPY"]["http_status"],403)
        self.assertEqual(out["source_results"]["JPY"]["status"],
                         "OFFICIAL_HTTPS_REQUEST_REJECTED_NO_GO")

    def test_04_network_tls_refusal_not_replaced_by_fake_issuer_rate(self):
        steps=fixtures()
        def rejected():
            raise URLError("fake TLS failure")
        steps["CHF"]=(rejected,steps["CHF"][1],steps["CHF"][2])
        out=probe(explicit_probe=True,clock=lambda:NOW,steps=steps)
        self.safe(out)
        self.assertEqual(out["valid_ephemeral_original_checks"],1)
        self.assertEqual(out["source_results"]["CHF"]["status"],
                         "OFFICIAL_TLS_OR_NETWORK_UNAVAILABLE_NO_GO")
        self.assertIsNone(out["source_results"]["CHF"]["official_policy_pct_claim"])

    def test_05_rbnz_never_collected_even_if_injected_fake_ocr(self):
        steps=fixtures()
        seen=[]
        def unauthorized_get():
            seen.append(True)
            raise AssertionError("RBNZ GET must never run")
        steps["NZD"]=(unauthorized_get,steps["NZD"][1],steps["NZD"][2])
        out=probe(explicit_probe=True,clock=lambda:NOW,steps=steps)
        self.safe(out)
        self.assertEqual(seen,[])
        self.assertEqual(out["requests_started_claim"],2)
        self.assertEqual(out["valid_ephemeral_original_checks"],2)
        self.assertEqual(out["source_results"]["NZD"]["status"],
                         "RBNZ_WRITTEN_PERMISSION_REQUIRED_NO_HTTP_NO_GO")

    def test_06_forged_go_state_refused_even_with_plausible_policy(self):
        steps=fixtures()
        _,real,field=steps["CHF"]
        def fake(**kwargs):
            r=real(**kwargs)
            r["trade_authorized"]=True
            return r
        steps["CHF"]=(steps["CHF"][0],fake,field)
        out=probe(explicit_probe=True,clock=lambda:NOW,steps=steps)
        self.safe(out)
        self.assertEqual(out["valid_ephemeral_original_checks"],1)
        self.assertEqual(out["source_results"]["CHF"]["status"],
                         "SOURCE_VALIDATOR_REJECTED_NO_GO")

    def test_07_collection_oversize_valueerror_keeps_no_go(self):
        steps=fixtures()
        def bad():
            raise ValueError("OVERSIZE_RESPONSE")
        steps["JPY"]=(bad,steps["JPY"][1],steps["JPY"][2])
        out=probe(explicit_probe=True,clock=lambda:NOW,steps=steps)
        self.safe(out)
        self.assertEqual(out["source_results"]["JPY"]["status"],
                         "OFFICIAL_SOURCE_HTTP_OR_RESPONSE_FAILED_NO_GO")

    def test_08_post_capture_clock_rewind_blocks_valid_source(self):
        steps=fixtures()
        clocks=iter((NOW,NOW-timedelta(seconds=1),NOW,NOW))
        out=probe(explicit_probe=True,clock=lambda:next(clocks),steps=steps)
        self.safe(out)
        self.assertEqual(out["source_results"]["JPY"]["status"],
                         "INVALID_POST_GET_CLOCK_NO_GO")
        self.assertEqual(out["valid_ephemeral_original_checks"],1)

    def test_09_post_capture_over_three_minutes_blocks(self):
        steps=fixtures()
        clocks=iter((NOW,NOW+timedelta(minutes=4),NOW,NOW))
        out=probe(explicit_probe=True,clock=lambda:next(clocks),steps=steps)
        self.safe(out)
        self.assertEqual(out["source_results"]["JPY"]["status"],
                         "INVALID_POST_GET_CLOCK_NO_GO")

    def test_10_invalid_input_rejects_without_collecting(self):
        for steps in ({}, {"JPY":STEPS["JPY"]},None):
            # None is the real steps: don't invoke real collectors.
            if steps is None:
                continue
            with self.subTest(step_keys=list(steps)):
                out=probe(explicit_probe=True,clock=lambda:NOW,steps=steps)
                self.safe(out)
                self.assertEqual(out["requests_started_claim"],0)
        for clock in (lambda:None,lambda:NOW.replace(tzinfo=None),
                      lambda:NOW+timedelta(microseconds=1)):
            out=probe(explicit_probe=True,clock=clock,steps=fixtures())
            self.safe(out)
            self.assertEqual(out["requests_started_claim"],0)

    def test_11_chf_validator_exception_does_not_enable_nzd(self):
        steps=fixtures()
        def invalid(**kwargs):
            raise ValueError("untrusted malformed source")
        steps["CHF"]=(steps["CHF"][0],invalid,steps["CHF"][2])
        out=probe(explicit_probe=True,clock=lambda:NOW,steps=steps)
        self.safe(out)
        self.assertEqual(out["requests_started_claim"],2)
        self.assertEqual(out["valid_ephemeral_original_checks"],1)
        self.assertEqual(out["source_results"]["CHF"]["status"],
                         "SOURCE_VALIDATOR_EXCEPTION_NO_GO")
        self.assertEqual(out["source_results"]["NZD"]["status"],
                         "RBNZ_WRITTEN_PERMISSION_REQUIRED_NO_HTTP_NO_GO")

    def test_12_no_flag_cli_makes_no_http_requests(self):
        with patch("atlasquant_trader_three_missing_policy_cloud_probe_lab."
                   "collect_boj_home_once_lab") as c:
            self.assertEqual(main([]),2)
            c.assert_not_called()

    def test_13_finished_probe_is_not_data_on_offline_desktop(self):
        out=probe(explicit_probe=True,clock=lambda:NOW,steps=fixtures())
        self.safe(out)
        self.assertFalse(out["source_receipt_locally_archived_on_am12"])
        self.assertFalse(out["source_original_bytes_retained"])
        self.assertFalse(out["historical_first_seen_authenticated"])
        self.assertIsNone(out["calibrated_probability"])

    def test_14_rbnz_gate_never_counts_cloud_original(self):
        out=probe(explicit_probe=True,clock=lambda:NOW,steps=fixtures())
        self.safe(out)
        self.assertEqual(out["requests_started_claim"],2)
        self.assertEqual(out["planned_official_https_get_max"],2)
        self.assertTrue(out["rbnz_automated_get_skipped_by_terms"])
        self.assertFalse(out["rbnz_automated_access_permission_verified"])
        self.assertNotIn("body_sha256_ephemeral_claim",
                         out["source_results"]["NZD"])


if __name__ == "__main__":
    unittest.main()
