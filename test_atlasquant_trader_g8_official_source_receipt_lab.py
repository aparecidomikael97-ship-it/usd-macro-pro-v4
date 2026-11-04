"""Offline contract tests: official G8 source leads do not prove real receipts."""
import copy
from datetime import datetime, timezone
from hashlib import sha256
from urllib.parse import urlsplit
import unittest

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS
from atlasquant_trader_g8_official_source_receipt_lab import (
    SCHEMA, SOURCES, FAMILIES, MAX_TEXT_BYTES,
    official_g8_source_catalog_lab, inspect_claimed_macro_receipt_lab,
)
from atlasquant_trader_g8_bilateral_receipt_coverage_lab import (
    audit_g8_bilateral_macro_receipts_lab,
)

CUTOFF = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)
AFTER = datetime(2026, 11, 2, 12, 1, tzinfo=timezone.utc)
TEXT = "LAB-only synthetic fake calendar excerpt. It is NOT an official download."


def sample():
    return {
        "state": "LAB_CALLER_SUPPLIED_TEXT", "source_id": "US_BLS_CPI",
        "event_id": "CPI_202611", "kind": "SCHEDULED",
        "event_at_utc": "2026-11-10T13:30:00Z",
        "published_at_utc": "2026-11-01T12:00:00Z",
        "captured_at_utc": "2026-11-01T12:05:00Z",
        "document_url": "https://www.bls.gov/schedule/2026/",
        "excerpt_utf8": TEXT,
        "claimed_sha256": sha256(TEXT.encode()).hexdigest(),
    }


def inspect(item):
    return inspect_claimed_macro_receipt_lab(
        item, forecast_issued_at=CUTOFF, evaluated_at=AFTER,
    )


class OfficialSourceReceiptLabTests(unittest.TestCase):
    def test_8x2_catalog_completeness(self):
        cat = official_g8_source_catalog_lab()
        self.assertEqual(cat["schema"], SCHEMA)
        self.assertEqual(cat["state"], "LAB_DOCUMENTATION_LEADS_ONLY")
        self.assertEqual(cat["currency_count"], 8)
        self.assertEqual(cat["family_count"], 2)
        self.assertEqual(cat["lead_count"], 16)
        self.assertEqual(set(cat["sources"]), set(SOURCES))
        self.assertEqual({v["currency"] for v in SOURCES.values()}, set(CURRENCIES))
        self.assertEqual({v["family"] for v in SOURCES.values()}, set(FAMILIES))
        self.assertEqual({(v["currency"], v["family"]) for v in SOURCES.values()},
                         {(c, f) for c in CURRENCIES for f in FAMILIES})

    def test_urls_have_https_exact_host_and_no_credentials(self):
        for item in SOURCES.values():
            url = urlsplit(item["documentation_url"])
            self.assertEqual(url.scheme, "https")
            self.assertEqual(url.hostname, item["hostname"])
            self.assertIsNone(url.username)
            self.assertIsNone(url.password)

    def test_catalog_does_not_claim_real_data_or_license(self):
        cat = official_g8_source_catalog_lab()
        for key in ("historical_payloads_downloaded", "original_receipt_attested",
                    "intraday_availability_attested", "commercial_redistribution_rights_verified",
                    "real_forex_bias_verified", "trade_authorized",
                    "worker_enabled", "scheduler_enabled"):
            self.assertFalse(cat[key], key)

    def test_claimed_future_schedule_quarantined(self):
        result = inspect(sample())
        self.assertEqual(result["state"], "LAB_OFFICIAL_RECEIPT_QUARANTINED_UNATTESTED")
        self.assertTrue(result["structural_asof_consistent"])
        self.assertEqual(result["receipt"]["currency"], "USD")
        self.assertEqual(result["receipt"]["family"], "INFLATION")
        self.assertEqual(result["receipt"]["content_sha256"], sample()["claimed_sha256"])
        self.assertEqual(len(result["receipt"]["record_sha256"]), 64)

    def test_past_release_context_quarantined(self):
        item = sample()
        item["kind"] = "RELEASED_CONTEXT"
        item["event_at_utc"] = "2026-10-20T12:30:00Z"
        item["published_at_utc"] = "2026-10-20T12:31:00Z"
        item["captured_at_utc"] = "2026-10-20T13:10:00Z"
        self.assertEqual(inspect(item)["state"], "LAB_OFFICIAL_RECEIPT_QUARANTINED_UNATTESTED")

    def test_future_published_time_rejected(self):
        item = sample()
        item["published_at_utc"] = "2026-11-02T12:01:00Z"
        self.assertEqual(inspect(item)["state"], "LAB_OFFICIAL_RECEIPT_REFUSED")

    def test_future_claimed_capture_rejected(self):
        item = sample()
        item["captured_at_utc"] = "2026-11-02T12:01:00Z"
        self.assertEqual(inspect(item)["state"], "LAB_OFFICIAL_RECEIPT_REFUSED")

    def test_scheduled_event_already_occurred_rejected(self):
        item = sample()
        item["event_at_utc"] = "2026-11-02T11:00:00Z"
        self.assertEqual(inspect(item)["state"], "LAB_OFFICIAL_RECEIPT_REFUSED")

    def test_release_context_published_before_event_rejected(self):
        item = sample()
        item["kind"] = "RELEASED_CONTEXT"
        item["event_at_utc"] = "2026-11-01T13:00:00Z"
        self.assertEqual(inspect(item)["state"], "LAB_OFFICIAL_RECEIPT_REFUSED")

    def test_http_rejected(self):
        item = sample()
        item["document_url"] = "http://www.bls.gov/schedule/2026/"
        self.assertEqual(inspect(item)["state"], "LAB_OFFICIAL_RECEIPT_REFUSED")

    def test_lookalike_subdomain_rejected(self):
        item = sample()
        item["document_url"] = "https://www.bls.gov.evil.example/schedule/2026/"
        self.assertEqual(inspect(item)["state"], "LAB_OFFICIAL_RECEIPT_REFUSED")

    def test_same_official_host_arbitrary_unreviewed_path_is_rejected(self):
        item = sample()
        for url in (
            "https://www.bls.gov/news.release/cpi.t01.htm",
            "https://www.bls.gov/schedule/2025/",
            "https://www.bls.gov/schedule/2026/unreviewed",
            "https://www.bls.gov/schedule/2026//",
        ):
            with self.subTest(url=url):
                item["document_url"] = url
                result = inspect(item)
                self.assertEqual(result["state"], "LAB_OFFICIAL_RECEIPT_REFUSED")
                self.assertFalse(result["official_document_authenticity_verified"])

    def test_catalogue_lead_query_and_encoded_url_variants_rejected(self):
        item = sample()
        for url in (
            "https://www.bls.gov/schedule/2026/?ref=claimed",
            "https://www.bls.gov/schedule/%32%30%32%36/",
            "https://www.bls.gov/schedule/2026/#release",
            "https://www.bls.gov:443/schedule/2026/",
        ):
            with self.subTest(url=url):
                item["document_url"] = url
                self.assertEqual(inspect(item)["state"],
                                 "LAB_OFFICIAL_RECEIPT_REFUSED")

    def test_approved_catalog_url_is_structural_only_not_attestation(self):
        for source_id, source in SOURCES.items():
            with self.subTest(source_id=source_id):
                item = sample()
                item["source_id"] = source_id
                item["document_url"] = source["documentation_url"]
                r = inspect(item)
                self.assertEqual(r["state"],
                                 "LAB_OFFICIAL_RECEIPT_QUARANTINED_UNATTESTED")
                self.assertTrue(r["receipt"]["url_matches_curated_documentation_lead_only"])
                self.assertFalse(r["receipt"]["page_content_or_release_authenticated"])
                self.assertFalse(r["historical_capture_attested"])

    def test_official_different_host_rejected(self):
        item = sample()
        item["document_url"] = "https://www.federalreserve.gov/newsevents/pressreleases/2026-press-fomc.htm"
        self.assertEqual(inspect(item)["state"], "LAB_OFFICIAL_RECEIPT_REFUSED")

    def test_url_credentials_and_nonstandard_port_rejected(self):
        for url in ("https://u:p@www.bls.gov/schedule/2026/",
                    "https://www.bls.gov:444/schedule/2026/"):
            with self.subTest(url=url):
                item = sample()
                item["document_url"] = url
                self.assertEqual(inspect(item)["state"], "LAB_OFFICIAL_RECEIPT_REFUSED")

    def test_wrong_text_hash_rejected(self):
        item = sample()
        item["claimed_sha256"] = "0" * 64
        self.assertEqual(inspect(item)["state"], "LAB_OFFICIAL_RECEIPT_REFUSED")

    def test_hash_not_attestation_even_when_valid(self):
        result = inspect(sample())
        for key in ("official_document_authenticity_verified",
                    "historical_capture_attested", "macro_direction_inferred",
                    "can_feed_exante_bias", "real_oos_authorized",
                    "trade_authorized", "worker_enabled", "scheduler_enabled"):
            self.assertFalse(result[key], key)

    def test_unknown_source_id_rejected(self):
        item = sample()
        item["source_id"] = "SOURCE_UNKNOWN"
        self.assertEqual(inspect(item)["state"], "LAB_OFFICIAL_RECEIPT_REFUSED")

    def test_extra_retrospective_actual_rejected(self):
        item = sample()
        item["actual"] = 5.0
        self.assertEqual(inspect(item)["state"], "LAB_OFFICIAL_RECEIPT_REFUSED")

    def test_wrong_state_rejected(self):
        item = sample()
        item["state"] = "REAL_SOURCE_VERIFIED"
        self.assertEqual(inspect(item)["state"], "LAB_OFFICIAL_RECEIPT_REFUSED")

    def test_empty_and_large_text_rejected(self):
        for value in ("", "X" * (MAX_TEXT_BYTES + 1)):
            with self.subTest(size=len(value)):
                item = sample()
                item["excerpt_utf8"] = value
                item["claimed_sha256"] = sha256(value.encode()).hexdigest()
                self.assertEqual(inspect(item)["state"], "LAB_OFFICIAL_RECEIPT_REFUSED")

    def test_timezone_ambiguity_rejected(self):
        item = sample()
        item["captured_at_utc"] = "2026-11-01T12:05:00-04:00"
        self.assertEqual(inspect(item)["state"], "LAB_OFFICIAL_RECEIPT_REFUSED")

    def test_future_issue_rejected(self):
        result = inspect_claimed_macro_receipt_lab(
            sample(),
            forecast_issued_at=datetime(2026, 11, 2, 12, 2, tzinfo=timezone.utc),
            evaluated_at=AFTER)
        self.assertEqual(result["state"], "LAB_OFFICIAL_RECEIPT_REFUSED")

    def test_naive_issuance_rejected(self):
        with self.assertRaises(ValueError):
            inspect_claimed_macro_receipt_lab(
                sample(), forecast_issued_at=datetime(2026, 11, 2, 12, 0),
                evaluated_at=AFTER)

    def test_snapshot_hash_is_reproducible_and_text_sensitive(self):
        original = inspect(sample())["receipt"]
        self.assertEqual(original, inspect(sample())["receipt"])
        modified = sample()
        modified["excerpt_utf8"] += "!"
        modified["claimed_sha256"] = sha256(modified["excerpt_utf8"].encode()).hexdigest()
        changed = inspect(modified)["receipt"]
        self.assertNotEqual(original["record_sha256"], changed["record_sha256"])


def released(source_id="US_BLS_CPI", event_id=None, *, stale=False):
    row = sample()
    row["source_id"] = source_id
    row["event_id"] = event_id or (source_id + "_EVENT")
    row["document_url"] = SOURCES[source_id]["documentation_url"]
    row["kind"] = "RELEASED_CONTEXT"
    if stale:
        row["event_at_utc"] = "2026-05-20T10:00:00Z"
        row["published_at_utc"] = "2026-05-20T10:05:00Z"
        row["captured_at_utc"] = "2026-05-20T11:00:00Z"
    else:
        row["event_at_utc"] = "2026-10-20T10:00:00Z"
        row["published_at_utc"] = "2026-10-20T10:05:00Z"
        row["captured_at_utc"] = "2026-10-20T11:00:00Z"
    return row


def audit_receipts(items, *, issued=CUTOFF, at=AFTER):
    return audit_g8_bilateral_macro_receipts_lab(
        items, forecast_issued_at=issued, evaluated_at=at)


def coverage_pair(report, pair="EUR/USD"):
    return next(x for x in report["pairs"] if x["pair"] == pair)


class G8BilateralReceiptCoverageLabTests(unittest.TestCase):
    def test_empty_document_batch_reports_all_28_pairs_and_required_gaps(self):
        report = audit_receipts([])
        self.assertEqual(report["state"],
                         "LAB_G8_BILATERAL_DOCUMENTARY_COVERAGE_ONLY")
        self.assertEqual((report["currency_count"], report["pair_count"]), (8, 28))
        self.assertEqual({p["pair"] for p in report["pairs"]}, set(OFFICIAL_PAIRS))
        self.assertEqual(report["released_context_claims_received"], 0)
        for currency in CURRENCIES:
            context = report["currencies"][currency]
            self.assertEqual(context["recent_release_family_claim_count"], 0)
            self.assertTrue(context["missing_claims_do_not_mean_no_real_event"])
            self.assertEqual(set(context["families"]), set(FAMILIES))
        for pair in report["pairs"]:
            self.assertEqual([pair[h] for h in ("D1", "W1", "MN1")],
                             ["AGUARDAR"] * 3)
            self.assertFalse(pair["explanation_causality_verified"])
            self.assertFalse(pair["trade_authorized"])

    def test_future_schedule_cannot_be_published_historical_macro_context(self):
        report = audit_receipts([sample()])
        self.assertEqual(report["state"],
                         "LAB_G8_BILATERAL_DOCUMENTARY_COVERAGE_ONLY")
        self.assertEqual(report["scheduled_claims_not_counted_as_releases"], 1)
        self.assertEqual(report["released_context_claims_received"], 0)
        self.assertEqual(report["currencies"]["USD"]["families"]["INFLATION"]["state"],
                         "NO_RELEASE_DOCUMENT_CLAIM_SUPPLIED")

    def test_one_us_inflation_document_only_covers_usd_inflation(self):
        report = audit_receipts([released()])
        self.assertEqual(report["released_context_claims_received"], 1)
        self.assertEqual(report["currencies"]["USD"]["recent_release_family_claim_count"], 1)
        pair = coverage_pair(report)
        self.assertFalse(pair["documentary_families"]["INFLATION"]
                         ["both_currencies_have_recent_document_claims"])
        self.assertEqual(pair["documented_family_count_claim_only"], 0)
        self.assertEqual(report["currencies"]["EUR"]["recent_release_family_claim_count"], 0)
        self.assertFalse(report["macro_explanation_verified"])

    def test_both_currencies_two_families_still_have_only_claimed_documents(self):
        sources = ("US_BLS_CPI", "US_FED_FOMC", "EU_EUROSTAT_HICP", "EU_ECB_POLICY")
        report = audit_receipts([released(x) for x in sources])
        pair = coverage_pair(report)
        self.assertEqual(pair["documented_family_count_claim_only"], 2)
        self.assertEqual(report["currencies"]["USD"]["recent_release_family_claim_count"], 2)
        self.assertEqual(report["currencies"]["EUR"]["recent_release_family_claim_count"], 2)
        self.assertEqual(report["currencies"]["JPY"]["recent_release_family_claim_count"], 0)
        self.assertFalse(report["source_original_authenticated"])
        self.assertEqual(report["operational_bias"], "AGUARDAR")

    def test_all_sixteen_releases_still_do_not_attest_eight_currencies(self):
        all_items = [released(k) for k in SOURCES]
        original = copy.deepcopy(all_items)
        report = audit_receipts(all_items)
        self.assertEqual(all_items, original)
        self.assertEqual(report["released_context_claims_received"], 16)
        self.assertTrue(report["all_eight_currencies_have_two_recent_claims"])
        self.assertEqual({p["documented_family_count_claim_only"]
                          for p in report["pairs"]}, {2})
        for key in ("source_original_authenticated", "all_economic_events_verified",
                    "macro_explanation_verified", "spot_fx_price_verified",
                    "counterevidence_verified", "trade_authorized", "publishable",
                    "can_feed_live_radar", "worker_enabled", "scheduler_enabled",
                    "complete_actual_calendar_coverage_proven"):
            self.assertFalse(report[key], key)
        self.assertEqual((report["external_http_requests"], report["new_cost_brl"]), (0, 0))

    def test_old_publication_is_visible_as_old_not_recent_research(self):
        report = audit_receipts([released(stale=True)])
        usd = report["currencies"]["USD"]["families"]["INFLATION"]
        self.assertEqual(usd["state"], "OLDER_RELEASE_DOCUMENT_CLAIM_ONLY")
        self.assertEqual(usd["received_release_context_claim_count"], 1)
        self.assertEqual(usd["not_older_than_90_days_claim_count"], 0)
        self.assertFalse(report["all_eight_currencies_have_two_recent_claims"])

    def test_recent_publication_of_old_event_stays_old(self):
        item = released()
        item["event_at_utc"] = "2026-04-01T10:00:00Z"
        item["published_at_utc"] = "2026-10-20T10:05:00Z"
        item["captured_at_utc"] = "2026-10-20T11:00:00Z"
        report = audit_receipts([item])
        self.assertEqual(report["state"],
                         "LAB_G8_BILATERAL_DOCUMENTARY_COVERAGE_ONLY")
        usd = report["currencies"]["USD"]["families"]["INFLATION"]
        self.assertEqual(usd["state"], "OLDER_RELEASE_DOCUMENT_CLAIM_ONLY")
        self.assertEqual(usd["not_older_than_90_days_claim_count"], 0)
        self.assertTrue(usd["recency_requires_event_and_publication_within_90_days"])
        self.assertEqual(usd["newest_claimed_event_utc"],
                         "2026-04-01T10:00:00+00:00")
        self.assertFalse(report["macro_explanation_verified"])

    def test_recent_event_and_publication_are_documentary_recent_not_authentic(self):
        report = audit_receipts([released()])
        usd = report["currencies"]["USD"]["families"]["INFLATION"]
        self.assertEqual(usd["state"], "RECENT_RELEASE_DOCUMENT_CLAIM_ONLY")
        self.assertEqual(usd["not_older_than_90_days_claim_count"], 1)
        self.assertEqual(usd["newest_claimed_event_utc"],
                         "2026-10-20T10:00:00+00:00")
        self.assertFalse(usd["source_original_authenticated"])

    def test_one_old_event_cannot_upgrade_recent_one_to_two_documents(self):
        new_item = released()
        old_item = released(event_id="CPI_OLD_REPRINT")
        old_item["event_at_utc"] = "2026-01-05T10:00:00Z"
        old_item["published_at_utc"] = "2026-10-21T10:05:00Z"
        old_item["captured_at_utc"] = "2026-10-21T11:00:00Z"
        result = audit_receipts([new_item, old_item])
        usd = result["currencies"]["USD"]["families"]["INFLATION"]
        self.assertEqual(usd["received_release_context_claim_count"], 2)
        self.assertEqual(usd["not_older_than_90_days_claim_count"], 1)
        self.assertEqual(usd["state"], "RECENT_RELEASE_DOCUMENT_CLAIM_ONLY")
        self.assertFalse(result["source_original_authenticated"])

    def test_invalid_domain_hash_or_claimed_authority_fail_closed(self):
        for kind in ("domain", "hash", "authority", "extra", "time"):
            with self.subTest(kind=kind):
                item = released()
                if kind == "domain":
                    item["document_url"] = "https://www.bls.gov.attacker.test/else"
                elif kind == "hash":
                    item["claimed_sha256"] = "0" * 64
                elif kind == "authority":
                    item["state"] = "REAL_AUTHENTICATED_SOURCE"
                elif kind == "extra":
                    item["actual"] = 4.9
                else:
                    item["captured_at_utc"] = "2026-11-03T10:00:00Z"
                out = audit_receipts([item])
                self.assertEqual(out["state"], "LAB_BLOCKED")
                self.assertFalse(out["trade_authorized"])

    def test_same_source_event_time_cannot_be_counted_twice_under_new_id(self):
        first = released(event_id="CPI_FIRST_NAME")
        second = released(event_id="CPI_SECOND_NAME")
        second["excerpt_utf8"] += " Different claimed content."
        second["claimed_sha256"] = sha256(
            second["excerpt_utf8"].encode()).hexdigest()
        result = audit_receipts([first, second])
        self.assertEqual(result["state"], "LAB_BLOCKED")
        self.assertEqual(result["reason"],
                         "DUPLICATE_SOURCE_EVENT_TIME_WITH_DIFFERENT_ID")
        self.assertFalse(result["trade_authorized"])

    def test_same_source_instant_z_and_utc_offset_are_one_event(self):
        first = released(event_id="CPI_EVENT_A")
        second = released(event_id="CPI_EVENT_B")
        second["event_at_utc"] = "2026-10-20T10:00:00+00:00"
        result = audit_receipts([first, second])
        self.assertEqual(result["reason"],
                         "DUPLICATE_SOURCE_EVENT_TIME_WITH_DIFFERENT_ID")

    def test_scheduled_receipts_cannot_duplicate_same_event_with_new_id(self):
        first = sample()
        second = sample()
        second["event_id"] = "CPI_SCHEDULE_B"
        result = audit_receipts([first, second])
        self.assertEqual(result["reason"],
                         "DUPLICATE_SOURCE_EVENT_TIME_WITH_DIFFERENT_ID")
        self.assertEqual(result["state"], "LAB_BLOCKED")

    def test_two_distinct_instant_claims_from_one_source_not_conflated(self):
        first = released(event_id="CPI_OLD")
        second = released(event_id="CPI_NEW")
        second["event_at_utc"] = "2026-10-21T10:00:00Z"
        second["published_at_utc"] = "2026-10-21T10:05:00Z"
        second["captured_at_utc"] = "2026-10-21T11:00:00Z"
        report = audit_receipts([first, second])
        self.assertEqual(report["state"],
                         "LAB_G8_BILATERAL_DOCUMENTARY_COVERAGE_ONLY")
        self.assertEqual(report["released_context_claims_received"], 2)
        self.assertTrue(report["same_source_event_instant_dedup_checked"])
        self.assertTrue(report["declared_event_ids_are_not_independent_evidence"])
        self.assertFalse(report["source_original_authenticated"])

    def test_different_source_leads_may_report_same_event_time_unattested(self):
        report = audit_receipts([
            released("US_BLS_CPI", event_id="USD_CPI"),
            released("EU_EUROSTAT_HICP", event_id="EUR_HICP"),
        ])
        self.assertEqual(report["state"],
                         "LAB_G8_BILATERAL_DOCUMENTARY_COVERAGE_ONLY")
        self.assertEqual(report["released_context_claims_received"], 2)
        self.assertFalse(report["macro_explanation_verified"])

    def test_duplicate_source_event_or_invalid_batch_is_rejected(self):
        item = released()
        self.assertEqual(audit_receipts([item, copy.deepcopy(item)])["reason"],
                         "DUPLICATE_SOURCE_EVENT_RECEIPT")
        for bad in (None, {}, "source", [item] * 65):
            self.assertEqual(audit_receipts(bad)["state"], "LAB_BLOCKED")

    def test_forecast_clock_or_naive_timestamp_is_rejected(self):
        self.assertEqual(audit_receipts(
            [], issued=AFTER, at=CUTOFF)["reason"], "FORECAST_AFTER_EVALUATION")
        with self.assertRaises(ValueError):
            audit_receipts([], issued=CUTOFF.replace(tzinfo=None))
        with self.assertRaises(ValueError):
            audit_receipts([], at=AFTER.replace(tzinfo=None))

    def test_no_transport_or_live_bias_from_manually_supplied_documents(self):
        from unittest.mock import patch
        with patch("urllib.request.urlopen", side_effect=AssertionError("HTTP forbidden")):
            out = audit_receipts([released()])
        self.assertEqual(out["state"],
                         "LAB_G8_BILATERAL_DOCUMENTARY_COVERAGE_ONLY")
        self.assertFalse(out["source_original_authenticated"])
        self.assertFalse(out["all_economic_events_verified"])
        self.assertFalse(out["three_daily_refreshes_running"])
        self.assertEqual(out["operational_bias"], "AGUARDAR")

class ManualSingleHttpsObservationLabTests(unittest.TestCase):
    """Mocked HTTP. THESE TESTS NEVER CONTACT AN OFFICIAL WEBSITE."""

    def _fake_opener(self, *, body=b"<html>fictional LAB fixture</html>",
                     url=None, status=200, headers=None, error=None):
        from atlasquant_trader_g8_official_source_receipt_lab import SOURCES
        url = url or SOURCES["US_BLS_CPI"]["documentation_url"]

        class Response:
            def __init__(self):
                self.status = status
                self.headers = headers if headers is not None else {
                    "Content-Type": "text/html; charset=utf-8",
                    "Content-Length": str(len(body)),
                    "Date": "Tue, 03 Nov 2026 08:00:00 GMT",
                }

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def geturl(self):
                return url

            def read(self, size=-1):
                return body if size < 0 else body[:size]

        class Opener:
            def open(self, request, timeout):
                self.request = request
                self.timeout = timeout
                if error is not None:
                    raise error
                return Response()

        return Opener()

    def test_manual_probe_disabled_by_default_does_not_touch_network(self):
        from unittest.mock import patch
        from atlasquant_trader_g8_single_https_probe_lab import (
            probe_g8_documentation_lead_once_lab,
        )
        with patch("atlasquant_trader_g8_single_https_probe_lab.build_opener",
                   side_effect=AssertionError("no HTTP without opt-in")):
            out = probe_g8_documentation_lead_once_lab("US_BLS_CPI")
        self.assertEqual(out["state"], "LAB_HTTP_OBSERVATION_BLOCKED")
        self.assertEqual(out["reason"], "MANUAL_HTTP_OPT_IN_REQUIRED")
        self.assertEqual(out["external_http_requests"], 0)
        self.assertFalse(out["trade_authorized"])

    def test_unknown_source_and_invalid_timeout_fail_before_http(self):
        from unittest.mock import patch
        from atlasquant_trader_g8_single_https_probe_lab import (
            probe_g8_documentation_lead_once_lab as probe,
        )
        with patch("atlasquant_trader_g8_single_https_probe_lab.build_opener",
                   side_effect=AssertionError("must not call network")):
            for name in ("UNKNOWN", "US_BLS_CPI_EVIL", None):
                self.assertEqual(probe(name, manually_authorized=True)
                                 ["external_http_requests"], 0)
            for t in (-1, 0, 16, True, 3.5, None):
                self.assertEqual(probe("US_BLS_CPI", manually_authorized=True,
                                       timeout_seconds=t)["reason"],
                                 "UNBOUNDED_HTTP_TIMEOUT")

    def test_manual_one_response_is_observation_not_economic_release(self):
        from unittest.mock import patch
        from atlasquant_trader_g8_single_https_probe_lab import (
            probe_g8_documentation_lead_once_lab as probe,
        )
        data = b"<html>LAB dummy page; not a CPI release</html>"
        fake = self._fake_opener(body=data)
        started = datetime.now(timezone.utc)
        with patch("atlasquant_trader_g8_single_https_probe_lab.build_opener",
                   return_value=fake) as opened:
            out = probe("US_BLS_CPI", manually_authorized=True, timeout_seconds=4)
        self.assertEqual(out["state"],
                         "LAB_CURRENT_OFFICIAL_HOST_HTTP_RESPONSE_OBSERVED")
        self.assertEqual(out["external_http_requests"], 1)
        self.assertEqual(out["http_response_content_sha256"], sha256(data).hexdigest())
        self.assertEqual(out["http_response_bytes"], len(data))
        self.assertEqual(fake.request.get_method(), "GET")
        self.assertEqual(fake.request.full_url, SOURCES["US_BLS_CPI"]["documentation_url"])
        self.assertEqual(fake.timeout, 4)
        self.assertEqual(opened.call_count, 1)
        self.assertLess((datetime.fromisoformat(out["observed_at_local_system_utc"])
                         - started).total_seconds(), 10)
        for key in ("original_publisher_payload_authenticated",
                    "historical_point_in_time_availability_verified",
                    "economic_indicator_value_extracted", "trade_authorized",
                    "publishable", "can_feed_live_radar", "worker_enabled",
                    "scheduler_enabled"):
            self.assertFalse(out[key], key)
        self.assertTrue(out["tls_standard_ca_validation_requested"])
        self.assertFalse(out["http_redirects_followed"])
        self.assertEqual(out["new_cost_brl"], 0)

    def test_each_catalogued_documentation_url_can_be_requested_once(self):
        from unittest.mock import patch
        from atlasquant_trader_g8_single_https_probe_lab import (
            probe_g8_documentation_lead_once_lab as probe,
        )
        for source_id, lead in SOURCES.items():
            with self.subTest(source_id=source_id):
                fake = self._fake_opener(url=lead["documentation_url"])
                with patch("atlasquant_trader_g8_single_https_probe_lab.build_opener",
                           return_value=fake):
                    out = probe(source_id, manually_authorized=True)
                self.assertEqual(out["state"],
                                 "LAB_CURRENT_OFFICIAL_HOST_HTTP_RESPONSE_OBSERVED")
                self.assertEqual(fake.request.full_url, lead["documentation_url"])
                self.assertFalse(out["original_publisher_payload_authenticated"])

    def test_redirects_are_not_followed_and_final_url_is_pinned(self):
        from unittest.mock import patch
        from atlasquant_trader_g8_single_https_probe_lab import (
            _RejectRedirect, probe_g8_documentation_lead_once_lab as probe,
        )
        self.assertIsNone(_RejectRedirect().redirect_request(
            None, None, 302, "Found", {}, "https://example.org/outside"))
        fake = self._fake_opener(url="https://www.bls.gov/unreviewed")
        with patch("atlasquant_trader_g8_single_https_probe_lab.build_opener",
                   return_value=fake):
            out = probe("US_BLS_CPI", manually_authorized=True)
        self.assertEqual(out["reason"], "HTTP_FINAL_URL_DIFFERS_FROM_ALLOWLIST")
        self.assertEqual(out["external_http_requests"], 1)
        self.assertFalse(out["http_endpoint_observed_this_session"])

    def test_http_status_and_malformed_media_are_refused(self):
        from unittest.mock import patch
        from atlasquant_trader_g8_single_https_probe_lab import (
            probe_g8_documentation_lead_once_lab as probe,
        )
        for kind, opts, reason in (
            ("status", {"status": 503}, "HTTP_STATUS_NOT_200"),
            ("media", {"headers": {"Content-Type": "image/svg+xml"}},
             "UNSUPPORTED_RESPONSE_MEDIA_TYPE"),
            ("gzip", {"headers": {
                "Content-Type": "text/html", "Content-Encoding": "gzip"}},
             "ENCODED_HTTP_BODY_NOT_SUPPORTED"),
        ):
            with self.subTest(kind=kind):
                with patch("atlasquant_trader_g8_single_https_probe_lab.build_opener",
                           return_value=self._fake_opener(**opts)):
                    out = probe("US_BLS_CPI", manually_authorized=True)
                self.assertEqual(out["reason"], reason)
                self.assertEqual(out["external_http_requests"], 1)

    def test_body_size_and_declared_content_length_fail_closed(self):
        from unittest.mock import patch
        from atlasquant_trader_g8_single_https_probe_lab import (
            MAX_BODY_BYTES, probe_g8_documentation_lead_once_lab as probe,
        )
        for kind, opts, reason in (
            ("empty", {"body": b""}, "HTTP_BODY_TOO_LARGE_OR_EMPTY"),
            ("huge", {"body": b"Z" * (MAX_BODY_BYTES + 2)},
             "HTTP_BODY_TOO_LARGE_OR_EMPTY"),
            ("lying", {"body": b"abc", "headers": {
                "Content-Type": "text/html", "Content-Length": "8"}},
             "HTTP_CONTENT_LENGTH_MISMATCH"),
            ("invalid", {"headers": {
                "Content-Type": "text/html", "Content-Length": "fake"}},
             "INVALID_HTTP_CONTENT_LENGTH"),
        ):
            with self.subTest(kind=kind):
                with patch("atlasquant_trader_g8_single_https_probe_lab.build_opener",
                           return_value=self._fake_opener(**opts)):
                    out = probe("US_BLS_CPI", manually_authorized=True)
                self.assertEqual(out["reason"], reason)
                self.assertEqual(out["external_http_requests"], 1)

    def test_transport_failure_is_not_misreported_as_valid_response(self):
        from unittest.mock import patch
        from urllib.error import URLError
        from atlasquant_trader_g8_single_https_probe_lab import (
            probe_g8_documentation_lead_once_lab as probe,
        )
        with patch("atlasquant_trader_g8_single_https_probe_lab.build_opener",
                   return_value=self._fake_opener(error=URLError("no connection"))):
            out = probe("US_BLS_CPI", manually_authorized=True)
        self.assertEqual(out["state"], "LAB_HTTP_OBSERVATION_BLOCKED")
        self.assertEqual(out["reason"], "HTTPS_REQUEST_FAILED_URLError")
        self.assertEqual(out["external_http_requests"], 1)
        self.assertFalse(out["http_endpoint_observed_this_session"])


if __name__ == "__main__":
    unittest.main()
