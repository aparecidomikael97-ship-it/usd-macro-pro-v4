"""Synthetic official-shaped US Treasury CSV tests. No network or real yields."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_trader_xauusd_us_treasury_yields_lab import (
    OFFICIAL_SOURCE_PAGES, TreasuryCsvReceipt, inspect_xauusd_treasury_yields_lab,
)

UTC = timezone.utc
NOW = datetime(2026, 11, 9, 16, 0, tzinfo=UTC)
FREEZE = NOW - timedelta(minutes=15)


def receipt(kind="NOMINAL_10Y", data=None, publication=NOW-timedelta(hours=2),
            capture=NOW-timedelta(hours=1)):
    if data is None:
        data = ("Date,5 Yr,10 Yr,20 Yr\n"
                "11/05/2026,3.80,4.09,4.50\n"
                "11/06/2026,3.82,4.10,4.51\n" if kind == "NOMINAL_10Y" else
                "Date,5 Yr,10 Yr,20 Yr\n"
                "11/05/2026,1.50,1.72,2.12\n"
                "11/06/2026,1.51,1.70,2.10\n")
    return TreasuryCsvReceipt(kind, OFFICIAL_SOURCE_PAGES[kind],
                              data.encode('utf-8') if isinstance(data,str) else data,
                              publication,capture)


def evaluate(nominal=None,real=None,now=NOW,freeze=FREEZE):
    return inspect_xauusd_treasury_yields_lab(
        receipt() if nominal is None else nominal,
        receipt("REAL_TIPS_10Y") if real is None else real,
        as_of_utc=now,decision_freeze_utc=freeze)


class TreasuryGoldTests(unittest.TestCase):
    def safe(self,x):
        self.assertEqual(x['operational_bias'],'AGUARDAR')
        self.assertFalse(x['publishable'])
        self.assertFalse(x['trade_authorized'])
        self.assertFalse(x['daily_broker_gold_price_verified'])
        self.assertFalse(x['gold_direction_inferred_from_yields'])
        self.assertFalse(x['source_originals_independently_authenticated'])
        self.assertFalse(x['publication_timestamps_independently_authenticated'])
        self.assertIsNone(x['validated_accuracy'])
        self.assertIsNone(x['research_candidate_direction'])
        self.assertEqual((x['http_requests'],x['file_writes'],x['new_cost_brl']),(0,0,0))

    def test_same_date_curve_context_only(self):
        r=evaluate()
        self.assertEqual(r['state'],'LAB_XAUUSD_TREASURY_CONTEXT_DOCUMENTARY_UNATTESTED')
        self.assertEqual(r['observation_dates'],['2026-11-05','2026-11-06'])
        self.assertEqual(r['nominal_latest_10y_pct'],'4.10')
        self.assertEqual(r['real_tips_latest_10y_pct'],'1.70')
        self.assertEqual(r['real_tips_change_percentage_points'],'-0.02')
        self.assertEqual(r['nominal_minus_real_yield_spread_pct_proxy'],'2.40')
        self.assertEqual(len(r['csv_sha256_local_only']),2)
        self.safe(r)

    def test_yield_decline_does_not_generate_gold_buy(self):
        r=evaluate()
        self.assertIsNone(r['research_candidate_direction'])
        self.assertFalse(r['gold_direction_inferred_from_yields'])
        self.safe(r)

    def test_future_publication_blocked(self):
        n=replace(receipt(),published_at_utc_claim=NOW+timedelta(minutes=1))
        self.assertIn('RELEASE_OR_CAPTURE_AFTER',evaluate(nominal=n)['reason'])

    def test_capture_after_forecast_freeze_blocked(self):
        n=replace(receipt(),captured_at_utc_claim=NOW)
        self.assertIn('RELEASE_OR_CAPTURE_AFTER',evaluate(nominal=n)['reason'])

    def test_release_after_capture_blocked(self):
        n=replace(receipt(),published_at_utc_claim=NOW-timedelta(minutes=30),
                  captured_at_utc_claim=NOW-timedelta(hours=1))
        self.assertIn('RELEASE_OR_CAPTURE_AFTER',evaluate(nominal=n)['reason'])

    def test_disagreeing_curve_dates_blocked(self):
        real=receipt('REAL_TIPS_10Y',"Date,10 Yr\n11/04/2026,1.73\n11/06/2026,1.70\n")
        self.assertEqual(evaluate(real=real)['reason'],'NOMINAL_AND_REAL_CURVE_DATES_NOT_ALIGNED')

    def test_missing_10yr_header_blocked(self):
        n=receipt(data='Date,5 Yr,20 Yr\n11/05/2026,3,4\n11/06/2026,3,4\n')
        self.assertIn('CSV_MISSING_UNIQUE',evaluate(nominal=n)['reason'])

    def test_duplicate_header_blocked(self):
        n=receipt(data='Date,10 Yr,10 Yr\n11/05/2026,3,4\n11/06/2026,3,4\n')
        self.assertIn('CSV_MISSING_UNIQUE',evaluate(nominal=n)['reason'])

    def test_duplicate_date_blocked(self):
        n=receipt(data='Date,10 Yr\n11/06/2026,4.1\n11/06/2026,4.2\n')
        self.assertIn('CSV_DATE_DUPLICATE',evaluate(nominal=n)['reason'])

    def test_future_csv_data_blocked(self):
        n=receipt(data='Date,10 Yr\n11/05/2026,4.1\n11/11/2026,4.2\n')
        self.assertIn('CSV_DATE_DUPLICATE_OR_FUTURE',evaluate(nominal=n)['reason'])

    def test_missing_rate_or_na_blocks(self):
        n=receipt(data='Date,10 Yr\n11/05/2026,4.1\n11/06/2026,N/A\n')
        self.assertIn('CSV_10YR_NON_NUMERIC',evaluate(nominal=n)['reason'])

    def test_nonfinite_rate_blocks(self):
        n=receipt(data='Date,10 Yr\n11/05/2026,NaN\n11/06/2026,4.1\n')
        self.assertIn('CSV_10YR_NONFINITE',evaluate(nominal=n)['reason'])

    def test_invalid_source_page_blocks(self):
        n=replace(receipt(),declared_source_page='https://example.com/ust.csv')
        self.assertIn('WRONG_CURVE_KIND',evaluate(nominal=n)['reason'])

    def test_swapped_nominal_and_real_blocks(self):
        self.assertIn('WRONG_CURVE_KIND',evaluate(nominal=receipt('REAL_TIPS_10Y'))['reason'])

    def test_stale_evidence_blocks(self):
        self.assertEqual(evaluate(now=NOW+timedelta(days=9),freeze=NOW+timedelta(days=8))['reason'],
                         'TREASURY_CONTEXT_STALE_FOR_FORECAST_FREEZE')

    def test_bytes_not_text_required(self):
        n=replace(receipt(),csv_bytes='Date,10 Yr\n')
        self.assertIn('INVALID_OR_OVERSIZED',evaluate(nominal=n)['reason'])

    def test_oversize_blocks(self):
        n=replace(receipt(),csv_bytes=b'a' * 1_048_577)
        self.assertIn('INVALID_OR_OVERSIZED',evaluate(nominal=n)['reason'])

    def test_bad_timezone_blocks(self):
        self.assertEqual(evaluate(freeze=FREEZE.replace(tzinfo=None))['reason'],
                         'INVALID_AS_OF_OR_FORECAST_FREEZE')
        self.assertIn('RELEASE_OR_CAPTURE_AFTER',evaluate(nominal=replace(
            receipt(),captured_at_utc_claim=NOW.replace(tzinfo=None)))['reason'])

    def test_missing_two_days_blocks(self):
        n=receipt(data='Date,10 Yr\n11/06/2026,4.10\n')
        self.assertIn('CSV_NEEDS_TWO',evaluate(nominal=n)['reason'])

    def test_csv_fingerprint_changes_if_bytes_change(self):
        a=evaluate()
        b=evaluate(nominal=receipt(data='Date,10 Yr\n11/05/2026,4.09\n11/06/2026,4.10\n'))
        self.assertNotEqual(a['csv_sha256_local_only']['NOMINAL_10Y'],
                            b['csv_sha256_local_only']['NOMINAL_10Y'])
        self.safe(b)

    def test_csv_bom_and_extra_columns_supported(self):
        n=receipt(data=b'\xef\xbb\xbfDate,5 Yr,10 Yr\n11/05/2026,3.80,4.09\n11/06/2026,3.82,4.10\n')
        self.assertEqual(evaluate(nominal=n)['state'],
                         'LAB_XAUUSD_TREASURY_CONTEXT_DOCUMENTARY_UNATTESTED')

    def test_undeclared_timestamp_future_blocks(self):
        n=replace(receipt(),published_at_utc_claim=NOW.replace(tzinfo=None))
        self.assertIn('RELEASE_OR_CAPTURE_AFTER',evaluate(nominal=n)['reason'])

    def test_synthetic_numbers_alone_never_certify_provenance(self):
        r=evaluate()
        self.assertFalse(r['directional_accuracy_validated'])
        self.assertFalse(r['broker_calendar_authenticated'] if 'broker_calendar_authenticated' in r else False)
        self.safe(r)

if __name__=='__main__':
    unittest.main()
