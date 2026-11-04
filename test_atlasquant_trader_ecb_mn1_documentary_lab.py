"""Retrospective 32-day ECB reference case, not FX forecast performance."""
from __future__ import annotations

import copy
import json
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS
from atlasquant_trader_ecb_mn1_documentary_lab import (
    SCHEMA, STATE, DENIED, EXPECTED,
    build_ecb_mn1_two_official_anchors_lab as build,
)

ROOT = Path(__file__).resolve().parent
DOC = ROOT / 'docs/continuidade/TRADER_ECB_MN1_TWO_OFFICIAL_ANCHORS_20261103.json'
ARCHIVE = ROOT / 'docs/continuidade/ecb_exr_g8_20261026_20261102_raw.csv'
ARCHIVE_MANIFEST = (ROOT / 'docs/continuidade/'
                    'TRADER_ECB_SDMX_ARCHIVE_MANIFEST_LAB_20261102.json')
NOW = datetime(2026, 11, 3, 15, tzinfo=timezone.utc)


def sample():
    return json.loads(DOC.read_text(encoding='utf-8'))


_UNSET = object()


def report(record=_UNSET, *, at=NOW):
    return build(sample() if record is _UNSET else record, evaluated_at=at)


def row(result, pair):
    return next(r for r in result['rows'] if r['pair'] == pair)


class ECBMN1DocumentaryLabTests(unittest.TestCase):
    def test_original_two_official_sources_are_fixed(self):
        r = sample()
        self.assertEqual(r['schema'], SCHEMA)
        self.assertEqual(r['state'], STATE)
        self.assertEqual(r['documents'][0], EXPECTED[0])
        self.assertEqual(r['documents'][1], EXPECTED[1])

    def test_28_real_reference_monthly_expost_changes_and_no_signal(self):
        r = report()
        self.assertEqual(r['state'], STATE)
        self.assertEqual(len(r['rows']), 28)
        self.assertEqual(r['observed_pairs'], 28)
        self.assertEqual({x['pair'] for x in r['rows']}, set(OFFICIAL_PAIRS))
        self.assertEqual({x['horizon'] for x in r['rows']}, {'MN1'})
        self.assertEqual(r['elapsed_calendar_days'], 32)
        for x in r['rows']:
            self.assertFalse(x['direction_is_forecast'])
            self.assertFalse(x['spot_price_independently_verified'])
            self.assertEqual(x['source_type'], 'ECB_REFERENCES_REPRINTED_BY_OFFICIAL_INSTITUTIONS')

    def test_eurusd_orientation_and_numeric_return(self):
        x = row(report(), 'EUR/USD')
        expected = (Decimal('1.1216') / Decimal('1.1298') - 1) * 10000
        self.assertLess(abs(Decimal(x['reference_return_bp']) - expected), Decimal('0.006'))
        self.assertEqual(x['realized_reference_side'], 'BAIXA')

    def test_usdjpy_cross_quotation_orientation(self):
        x = row(report(), 'USD/JPY')
        start = Decimal('178.49') / Decimal('1.1298')
        end = Decimal('177.1000') / Decimal('1.1216')
        expected = (end / start - 1) * 10000
        self.assertLess(abs(Decimal(x['reference_return_bp']) - expected), Decimal('0.006'))

    def test_eurgbp_uses_five_decimal_official_eu_journal_anchor(self):
        x = row(report(), 'EUR/GBP')
        expected = (Decimal('0.8358') / Decimal('0.85373') - 1) * 10000
        self.assertLess(abs(Decimal(x['reference_return_bp']) - expected), Decimal('0.006'))
        self.assertNotEqual(sample()['documents'][0]['eur_quotes']['GBP'], '0.8537')

    def test_november_quote_levels_match_archived_original_ecb_bytes(self):
        from atlasquant_trader_ecb_sdmx_archive_lab import (
            STATE as ARCHIVE_STATE, validate_ecb_archived_csv_lab,
        )
        raw = ARCHIVE.read_bytes()
        manifest = json.loads(ARCHIVE_MANIFEST.read_text(encoding='utf-8'))
        validated = validate_ecb_archived_csv_lab(raw, manifest, evaluated_at=NOW)
        self.assertEqual(validated['state'], ARCHIVE_STATE)
        actual = validated['reference_quotes_by_date']['2026-11-02']
        for c, value in sample()['documents'][1]['eur_quotes'].items():
            self.assertEqual(Decimal(actual[c]), Decimal(value), c)
        self.assertTrue(validated['raw_bytes_sha256_matched'])
        self.assertFalse(validated['historical_vintage_attested'])

    def test_no_probabilities_or_historical_prediction_claims(self):
        r = report()
        for key in ('original_october_source_bytes_archived',
                    'historical_data_known_before_anchor_proven',
                    'forecast_issued_before_move', 'real_predictive_accuracy_proven',
                    'can_feed_real_oos', 'can_feed_live_radar', 'trade_authorized',
                    'worker_enabled', 'scheduler_enabled'):
            self.assertFalse(r[key], key)
        self.assertIsNone(r['probability_calibrated'])
        self.assertEqual(r['independent_broker_spot_quotes_verified'], 0)
        self.assertEqual(r['derived_crosses_not_independent'], 21)

    def test_all_8_currency_universe_is_in_two_snapshot_quotes(self):
        for doc in sample()['documents']:
            self.assertEqual(set(doc['eur_quotes']) | {'EUR'}, set(CURRENCIES))

    def test_injected_spot_or_authorization_permission_is_refused(self):
        r = sample()
        r['trade_authorized'] = True
        self.assertEqual(report(r)['state'], DENIED)

    def test_changed_anchor_and_changed_reference_date_refused(self):
        for field in ('reference_date', 'publication_date'):
            r = sample()
            r['documents'][0][field] = '2026-10-03'
            self.assertEqual(report(r)['state'], DENIED)

    def test_wrong_eu_journal_url_refused(self):
        r = sample()
        r['documents'][0]['source_url'] = 'https://somewhere.example.net'
        self.assertEqual(report(r)['state'], DENIED)

    def test_wrong_bdf_url_or_source_type_refused(self):
        for field in ('source_url', 'source_kind'):
            r = sample()
            r['documents'][1][field] = 'different'
            self.assertEqual(report(r)['state'], DENIED)

    def test_strict_all_7_currencies_required(self):
        for day in (0, 1):
            r = sample()
            r['documents'][day]['eur_quotes'].pop('JPY')
            self.assertEqual(report(r)['state'], DENIED)

    def test_unexpected_currency_and_duplicate_document_denied(self):
        r = sample()
        r['documents'][0]['eur_quotes']['BRL'] = '6.00'
        self.assertEqual(report(r)['state'], DENIED)
        r = sample()
        r['documents'][1] = copy.deepcopy(r['documents'][0])
        self.assertEqual(report(r)['state'], DENIED)

    def test_modifying_the_real_source_value_is_refused_even_if_plausible(self):
        r = sample()
        r['documents'][0]['eur_quotes']['USD'] = '1.1299'
        self.assertEqual(report(r)['state'], DENIED)
        r = sample()
        r['documents'][1]['eur_quotes']['JPY'] = '177.2'
        self.assertEqual(report(r)['state'], DENIED)

    def test_numeric_nan_formula_booleans_zero_and_locale_comma_denied(self):
        for candidate in ('nan', '=1+1', '0', '-1.1', '1,23', None, True, 1.1298, 'Infinity'):
            with self.subTest(candidate=candidate):
                r = sample()
                r['documents'][0]['eur_quotes']['USD'] = candidate
                self.assertEqual(report(r)['state'], DENIED)

    def test_malformed_document_and_unknown_schema_refused(self):
        for bad in (None, [], {}, {'schema': 'x'}, 'x'):
            self.assertEqual(report(bad)['state'], DENIED)
        r = sample()
        r['schema'] = 'WRONG'
        self.assertEqual(report(r)['state'], DENIED)

    def test_research_date_does_not_claim_retrospective_pre_event_capture(self):
        r = sample()
        r['research_date_utc'] = '2026-10-01'
        self.assertEqual(report(r)['state'], DENIED)
        early = datetime(2026, 11, 2, 23, tzinfo=timezone.utc)
        self.assertEqual(report(at=early)['state'], DENIED)

    def test_naive_time_is_rejected(self):
        with self.assertRaises(ValueError):
            report(at=datetime(2026, 11, 3, 15))

    def test_even_with_valid_mn1_outcomes_cannot_claim_market_accuracy(self):
        r = report()
        self.assertEqual(r['reference_original_eur_legs_per_date'], 7)
        self.assertFalse(r['real_predictive_accuracy_proven'])
        self.assertFalse(r['can_feed_real_oos'])
        self.assertIn('No complete historical time series', r['research_note'])


if __name__ == '__main__':
    unittest.main()
