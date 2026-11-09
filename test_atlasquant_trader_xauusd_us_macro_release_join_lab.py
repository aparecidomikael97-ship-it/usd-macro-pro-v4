"""Synthetic-only integration tests: no network, no live XAU/USD or trades."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import unittest

from atlasquant_trader_xauusd_us_macro_release_join_lab import (
    EVENT_KINDS, MacroDocument, ScheduledMacroEvent,
    inspect_xauusd_us_macro_join_lab as inspect,
)
from atlasquant_trader_xauusd_us_treasury_yields_lab import (
    OFFICIAL_SOURCE_PAGES, TreasuryCsvReceipt,
)

UTC=timezone.utc
NOW=datetime(2026,11,9,18,tzinfo=UTC)
FREEZE=NOW-timedelta(minutes=20)
URLS={
    "FOMC_POLICY":"https://www.federalreserve.gov/newsevents/pressreleases/monetary20261028a.htm",
    "BLS_CPI":"https://www.bls.gov/news.release/archives/cpi_10142026.htm",
    "BLS_NFP":"https://www.bls.gov/news.release/archives/empsit_11062026.htm",
}
RELEASES={
    "FOMC_POLICY":datetime(2026,10,28,18,tzinfo=UTC),
    "BLS_CPI":datetime(2026,10,14,12,30,tzinfo=UTC),
    "BLS_NFP":datetime(2026,11,6,13,30,tzinfo=UTC),
}
PERIODS={"FOMC_POLICY":"2026-10","BLS_CPI":"2026-09","BLS_NFP":"2026-10"}
BODIES={
    "FOMC_POLICY":b"<html><title>Federal Reserve</title>Federal Open Market Committee issued monetary statement with dummy value placeholders.</html>",
    "BLS_CPI":b"<html><title>Consumer Price Index</title>Consumer Price Index synthetic archive example without real values.</html>",
    "BLS_NFP":b"<html><title>Employment Situation</title>Employment Situation synthetic archive example without real values.</html>",
}

def doc(kind):
    body=BODIES[kind]
    return MacroDocument(kind,URLS[kind],PERIODS[kind],RELEASES[kind],
                         RELEASES[kind]+timedelta(hours=1),body,sha256(body).hexdigest())

def treasury(kind):
    raw=("Date,10 Yr\n11/05/2026,4.02\n11/06/2026,4.04\n" if kind=="NOMINAL_10Y"
         else "Date,10 Yr\n11/05/2026,1.90\n11/06/2026,1.88\n").encode()
    return TreasuryCsvReceipt(kind,OFFICIAL_SOURCE_PAGES[kind],raw,
                datetime(2026,11,6,21,tzinfo=UTC),datetime(2026,11,6,22,tzinfo=UTC))

def call(documents=None,nominal=None,real=None,freeze=FREEZE,now=NOW,events=()):
    return inspect(
        (doc(k) for k in EVENT_KINDS) if documents is None else documents,
        nominal_treasury=treasury("NOMINAL_10Y") if nominal is None else nominal,
        real_treasury=treasury("REAL_TIPS_10Y") if real is None else real,
        forecast_frozen_at_utc=freeze,as_of_utc=now,known_future_events=events,
    )

class MacroJoinTests(unittest.TestCase):
    def good(self,**changes):
        documents=changes.pop("documents",tuple(doc(k) for k in EVENT_KINDS))
        return call(documents=documents,**changes)

    def safety(self,r):
        self.assertEqual(r["operational_bias"],"AGUARDAR")
        self.assertFalse(r["trade_authorized"])
        self.assertFalse(r["publishable"])
        self.assertFalse(r["live_alert_allowed"])
        self.assertIsNone(r["research_candidate_direction"])
        self.assertIsNone(r["validated_directional_accuracy"])
        self.assertFalse(r["original_bls_and_fed_pages_authenticated"])
        self.assertFalse(r["independent_first_publication_instants_verified"])
        self.assertFalse(r["usd_dxy_vendor_context_verified"])
        self.assertFalse(r["macro_calendar_completeness_verified"])
        self.assertEqual((r["http_requests"],r["file_writes"],r["new_cost_brl"]),(0,0,0))

    def test_complete_three_release_plus_treasury_still_no_go(self):
        r=self.good()
        self.assertEqual(r["state"],"LAB_XAUUSD_US_MACRO_CONTEXT_DOCUMENTARY_NO_GO")
        self.assertTrue(r["predecision_fomc_cpi_nfp_join_documentary_complete"])
        self.assertEqual(r["macro_documents_accepted"],3)
        self.assertEqual(r["treasury_real_10y_context_pct"],"1.88")
        self.assertEqual([x["event_kind"] for x in r["macro_documentary_rows"]],list(EVENT_KINDS))
        self.safety(r)

    def test_missing_documents_block(self):
        self.assertEqual(self.good(documents=(doc("FOMC_POLICY"),doc("BLS_CPI")))["reason"],
                         "MISSING_OR_EXTRA_US_OFFICIAL_MACRO_DOCUMENTS")

    def test_duplicate_release_block(self):
        self.assertEqual(self.good(documents=(doc("FOMC_POLICY"),doc("FOMC_POLICY"),doc("BLS_NFP")))["reason"],
                         "DUPLICATE_OFFICIAL_MACRO_DOCUMENT_KIND")

    def test_wrong_host_and_subdomain_block(self):
        rows=list(doc(k) for k in EVENT_KINDS)
        for link in ("https://federalreserve.gov/newsevents/pressreleases/monetary20261028a.htm",
                     "https://www.federalreserve.gov.evil.test/newsevents/pressreleases/monetary20261028a.htm",
                     "http://www.federalreserve.gov/newsevents/pressreleases/monetary20261028a.htm"):
            with self.subTest(link=link):
                r=self.good(documents=(replace(rows[0],source_url=link),*rows[1:]))
                self.assertIn("NOT_AN_ALLOWED_OFFICIAL",r["reason"])
                self.safety(r)

    def test_current_mutable_bls_page_is_not_archived_proof(self):
        rows=list(doc(k) for k in EVENT_KINDS)
        r=self.good(documents=(rows[0],replace(rows[1],source_url="https://www.bls.gov/news.release/cpi.htm"),rows[2]))
        self.assertIn("NOT_AN_ALLOWED_OFFICIAL",r["reason"])

    def test_url_date_must_match_declared_release_date(self):
        rows=list(doc(k) for k in EVENT_KINDS)
        r=self.good(documents=(rows[0],replace(rows[1],released_at_utc_claim=rows[1].released_at_utc_claim+timedelta(days=1)),rows[2]))
        self.assertIn("URL_DATE",r["reason"])

    def test_future_reported_release_does_not_rewrite_past(self):
        rows=list(doc(k) for k in EVENT_KINDS)
        r=self.good(documents=(rows[0],rows[1],replace(rows[2],captured_at_utc_claim=NOW+timedelta(days=1))))
        self.assertIn("NOT_PREDECISION",r["reason"])

    def test_reference_month_cannot_be_future(self):
        rows=list(doc(k) for k in EVENT_KINDS)
        r=self.good(documents=(rows[0],replace(rows[1],reference_period="2026-11"),rows[2]))
        self.assertIn("FUTURE_REFERENCE",r["reason"])

    def test_hash_change_rejected(self):
        rows=list(doc(k) for k in EVENT_KINDS)
        r=self.good(documents=(rows[0],rows[1],replace(rows[2],sha256_claim="0"*64)))
        self.assertIn("BODY_BYTES_OR_HASH",r["reason"])

    def test_unrelated_html_content_rejected(self):
        rows=list(doc(k) for k in EVENT_KINDS)
        body=b"<html>Nothing about employment data. This is a harmless unrelated article, not a report.</html>"
        changed=replace(rows[2],html_body=body,sha256_claim=sha256(body).hexdigest())
        r=self.good(documents=(*rows[:2],changed))
        self.assertIn("DOCUMENT_CONTENT_DOES_NOT_MATCH",r["reason"])

    def test_treasury_missing_or_mismatched_dates_block(self):
        bad=replace(treasury("REAL_TIPS_10Y"),csv_bytes=b"Date,10 Yr\n11/04/2026,1.90\n11/06/2026,1.88\n")
        r=self.good(real=bad)
        self.assertEqual(r["state"],"LAB_XAUUSD_US_MACRO_JOIN_BLOCKED")
        self.assertIn("NOMINAL_AND_REAL_CURVE_DATES_NOT_ALIGNED",r["reason"])
        self.safety(r)

    def test_high_impact_cpi_blackout_blocks(self):
        event=ScheduledMacroEvent("BLS_CPI",FREEZE+timedelta(minutes=25))
        r=self.good(events=(event,))
        self.assertEqual(r["reason"],"HIGH_IMPACT_FOMC_CPI_OR_NFP_RELEASE_BLACKOUT")
        self.safety(r)

    def test_high_impact_fomc_and_nfp_blackout_block(self):
        for kind in ("FOMC_POLICY","BLS_NFP"):
            with self.subTest(kind=kind):
                event=ScheduledMacroEvent(kind,FREEZE-timedelta(minutes=25))
                self.assertEqual(self.good(events=(event,))["reason"],
                                 "HIGH_IMPACT_FOMC_CPI_OR_NFP_RELEASE_BLACKOUT")

    def test_scheduled_event_after_blackout_does_not_certify_calendar(self):
        r=self.good(events=(ScheduledMacroEvent("BLS_CPI",FREEZE+timedelta(hours=8)),))
        self.assertEqual(r["state"],"LAB_XAUUSD_US_MACRO_CONTEXT_DOCUMENTARY_NO_GO")
        self.assertFalse(r["macro_calendar_completeness_verified"])

    def test_duplicate_high_impact_calendar_entry_rejected(self):
        ev=ScheduledMacroEvent("BLS_CPI",FREEZE+timedelta(hours=8))
        r=self.good(events=(ev,ev))
        self.assertEqual(r["reason"],"INVALID_OR_DUPLICATE_EVENT_TIME_CLAIM")

    def test_event_after_freeze_is_never_predecision_data(self):
        rows=list(doc(k) for k in EVENT_KINDS)
        cpi=replace(rows[1],captured_at_utc_claim=FREEZE+timedelta(seconds=1))
        self.assertIn("NOT_PREDECISION",self.good(documents=(rows[0],cpi,rows[2]))["reason"])

    def test_fomc_old_source_rejected(self):
        # Same dated document at a much later decision cannot be called fresh.
        r=self.good(freeze=NOW+timedelta(days=151),now=NOW+timedelta(days=151))
        self.assertEqual(r["state"],"LAB_XAUUSD_US_MACRO_JOIN_BLOCKED")
        self.assertIn("AGE_EXCEEDS",r["reason"])

    def test_future_freeze_rejected(self):
        r=self.good(freeze=NOW+timedelta(seconds=1))
        self.assertEqual(r["reason"],"INVALID_AS_OF_OR_FORECAST_FREEZE")

    def test_invalid_known_event_type_rejected(self):
        r=self.good(events=(ScheduledMacroEvent("BLS_PPI",FREEZE),))
        self.assertEqual(r["reason"],"INVALID_HIGH_IMPACT_CALENDAR_CLAIM")

    def test_order_independent_and_reproducible(self):
        a=self.good()
        b=self.good(documents=tuple(reversed(tuple(doc(k) for k in EVENT_KINDS))))
        self.assertEqual(a,b)
        self.safety(b)

    def test_duplicate_source_url_wrong_kind_block(self):
        rows=list(doc(k) for k in EVENT_KINDS)
        changed=replace(rows[1],source_url=rows[2].source_url)
        self.assertIn("NOT_AN_ALLOWED_OFFICIAL",self.good(documents=(rows[0],changed,rows[2]))["reason"])

    def test_no_live_xau_price_or_dxy_certification(self):
        r=self.good()
        self.assertFalse(r["gold_price_and_spread_from_broker_verified"])
        self.assertFalse(r["all_gold_predecision_factors_ready"])
        self.assertFalse(r["out_of_sample_gold_accuracy_validated"])
        self.safety(r)

if __name__=='__main__':
    unittest.main()
