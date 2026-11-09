"""Synthetic, independent clock arithmetic tests; no broker access."""
from dataclasses import replace
from datetime import datetime, timezone, timedelta
import unittest

from atlasquant_trader_fx_nyclose_clock_audit_lab import FxClockSample, audit_fx_nyclose_clock_lab

UTC = timezone.utc
NOW = datetime(2026, 11, 9, 12, tzinfo=UTC)

def u(text):
    return datetime.fromisoformat(text.replace('Z','+00:00'))

def sample(tf="D1", stamp="2026-11-08T22:00:00Z", symbol="EURUSD", now=NOW):
    return FxClockSample(symbol, tf, u(stamp), now, 'a'*64)

def run(*records, now=NOW):
    return audit_fx_nyclose_clock_lab(records, as_of_utc=now)

class ClockAuditTests(unittest.TestCase):
    def safe(self, r):
        self.assertFalse(r['publishable'])
        self.assertFalse(r['trade_authorized'])
        self.assertFalse(r['broker_calendar_verified'])
        self.assertFalse(r['pepperstone_server_association_verified'])
        self.assertIsNone(r['validated_directional_accuracy'])
        self.assertIsNone(r['calibrated_direction_probability'])
        self.assertEqual(r['operational_bias'],'AGUARDAR')
        self.assertEqual((r['new_cost_brl'],r['http_requests'],r['file_writes']),(0,0,0))

    def test_winter_reference_both_match(self):
        r=run(sample(),sample(tf='W1',symbol='GBPUSD'))
        self.assertEqual(r['state'],'LAB_NYCLOSE_REFERENCE_MATCH_UNATTESTED')
        self.assertEqual(r['match_count'],2)
        self.safe(r)

    def test_summer_reference_both_match(self):
        r=run(sample(stamp='2026-03-08T21:00:00Z'), sample(tf='W1',stamp='2026-03-08T21:00:00Z'))
        self.assertEqual(r['match_count'],2)
        self.safe(r)

    def test_archive_documentary_utc_midnight_discrepancy(self):
        r=run(sample(stamp='2026-11-05T00:00:00Z'), sample(tf='W1',stamp='2026-10-25T00:00:00Z'))
        self.assertEqual(r['discrepancy_count'],2)
        self.assertEqual(r['state'],'LAB_SESSION_CLOCK_REFERENCE_DISCREPANCY_REVIEW')
        names={x['timeframe']:x['bar_open_new_york'] for x in r['samples']}
        self.assertEqual(names['D1'],'2026-11-04T19:00:00-05:00')
        self.assertEqual(names['W1'],'2026-10-24T20:00:00-04:00')
        self.safe(r)

    def test_summer_midnight_discrepancy(self):
        r=run(sample(stamp='2026-06-10T00:00:00Z'),sample(tf='W1',stamp='2026-06-07T00:00:00Z'))
        self.assertEqual(r['discrepancy_count'],2)
        self.safe(r)

    def test_winter_dst_off_by_hour(self):
        r=run(sample(stamp='2026-11-08T21:00:00Z'),sample(tf='W1'))
        self.assertEqual(r['discrepancy_count'],1)
        self.safe(r)

    def test_summer_dst_off_by_hour(self):
        r=run(sample(stamp='2026-03-08T22:00:00Z'),sample(tf='W1',stamp='2026-03-08T21:00:00Z'))
        self.assertEqual(r['discrepancy_count'],1)
        self.safe(r)

    def test_weekly_sunday_only(self):
        r=run(sample(),sample(tf='W1',stamp='2026-11-05T22:00:00Z'))
        self.assertEqual(r['discrepancy_count'],1)
        self.safe(r)

    def test_d1_friday_new_close_is_not_new_candle(self):
        r=run(sample(stamp='2026-11-06T22:00:00Z'),sample(tf='W1'))
        self.assertEqual(r['discrepancy_count'],1)
        self.safe(r)

    def test_holidays_not_verified_even_when_match(self):
        r=run(sample(), sample(tf='W1'))
        self.assertFalse(r['broker_calendar_verified'])
        self.safe(r)

    def test_partial_scope_blocked(self):
        r=run(sample(),sample(symbol='GBPUSD'))
        self.assertEqual(r['reason'],'D1_W1_BOTH_REQUIRED_TO_ASSESS_COHORT')
        self.safe(r)

    def test_naive_clock_rejected(self):
        a=replace(sample(),bar_open_at_utc=u('2026-11-08T22:00:00Z').replace(tzinfo=None))
        r=run(a,sample(tf='W1'))
        self.assertEqual(r['state'],'LAB_BAR_CLOCK_BLOCKED')
        self.safe(r)

    def test_wrong_sha_rejected(self):
        r=run(replace(sample(),csv_sha256_claim='bad'),sample(tf='W1'))
        self.assertEqual(r['reason'],'INVALID_SAMPLE_PROVENANCE_OR_CHRONOLOGY')
        self.safe(r)

    def test_missing_and_repeated(self):
        self.assertEqual(run()['reason'],'INVALID_CLOCK_OR_SAMPLE_COLLECTION')
        self.assertEqual(run(sample(),sample(),sample(tf='W1'))['reason'],'DUPLICATED_SAMPLE')

    def test_unrecognized_symbol_rejected(self):
        r=run(replace(sample(),symbol='EXOTIC'),sample(tf='W1'))
        self.assertEqual(r['reason'],'INVALID_SAMPLE_PROVENANCE_OR_CHRONOLOGY')

    def test_invalid_timeframe_rejected(self):
        r=run(replace(sample(),timeframe='M15'),sample(tf='W1'))
        self.assertEqual(r['reason'],'INVALID_SAMPLE_PROVENANCE_OR_CHRONOLOGY')

    def test_capture_precedes_open_rejected(self):
        r=run(replace(sample(),snapshot_observed_at_utc=u('2026-11-08T20:00:00Z')),sample(tf='W1'))
        self.assertEqual(r['reason'],'INVALID_SAMPLE_PROVENANCE_OR_CHRONOLOGY')

    def test_future_capture_rejected(self):
        r=run(replace(sample(),snapshot_observed_at_utc=NOW+timedelta(days=1)),sample(tf='W1'))
        self.assertEqual(r['reason'],'INVALID_SAMPLE_PROVENANCE_OR_CHRONOLOGY')

    def test_future_asof_rejected(self):
        r=run(sample(),sample(tf='W1'),now=NOW.replace(tzinfo=None))
        self.assertEqual(r['reason'],'INVALID_CLOCK_OR_SAMPLE_COLLECTION')

    def test_microseconds_rejected(self):
        r=run(replace(sample(),bar_open_at_utc=sample().bar_open_at_utc+timedelta(microseconds=1)),sample(tf='W1'))
        self.assertEqual(r['reason'],'INVALID_SAMPLE_PROVENANCE_OR_CHRONOLOGY')

    def test_bool_hash_and_duplicate_key_malformed(self):
        r=run(sample(),replace(sample(tf='W1'),csv_sha256_claim=True))
        self.assertEqual(r['reason'],'INVALID_SAMPLE_PROVENANCE_OR_CHRONOLOGY')

    def test_order_independent(self):
        a,b=sample(),sample(tf='W1')
        self.assertEqual(run(a,b)['samples'],run(b,a)['samples'])

    def test_no_rewrite_of_original_utc(self):
        original=sample(stamp='2026-11-05T00:00:00Z')
        r=run(original,sample(tf='W1'))
        self.assertEqual(original.bar_open_at_utc,u('2026-11-05T00:00:00Z'))
        self.assertEqual(next(x for x in r['samples'] if x['timeframe']=='D1')['bar_open_utc'],original.bar_open_at_utc.isoformat())
        self.safe(r)

if __name__=='__main__': unittest.main()
