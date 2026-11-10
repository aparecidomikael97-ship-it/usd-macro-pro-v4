"""Synthetic only: test CME Chicago publication floors, never quote validity."""
from datetime import date, datetime, timedelta, timezone
import unittest
from zoneinfo import ZoneInfo

from atlasquant_trader_cme_settlement_release_gate_lab import (
    conservative_first_public_floor_utc, inspect_cme_settlement_release_gate_lab as inspect,
)
UTC = timezone.utc
CT = ZoneInfo('America/Chicago')


def sample(day, channel, pub=None, cap=None, asof=None):
    floor = conservative_first_public_floor_utc(day, channel)
    pub = floor if pub is None else pub
    cap = (pub + timedelta(minutes=10)) if cap is None else cap
    asof = (cap + timedelta(minutes=10)) if asof is None else asof
    return inspect(trade_date=day, channel=channel, published_at_utc=pub,
                   captured_at_utc=cap, as_of_utc=asof)


class CmeSettlementReleaseGateTests(unittest.TestCase):
    def assert_untrusted(self, r):
        self.assertEqual(r['operational_bias'], 'AGUARDAR')
        for k in ('floor_is_official_release_timestamp', 'exchange_holiday_calendar_attested',
                  'actual_first_seen_independently_attested', 'issuer_payload_archived',
                  'licensed_reuse_verified', 'eligible_as_authenticated_market_quote',
                  'trade_authorized'):
            self.assertFalse(r[k], k)
        self.assertEqual((r['http_requests'], r['file_writes'], r['new_cost_brl']), (0, 0, 0))

    def test_dst_summer_public_website_floor_0500_utc(self):
        floor=conservative_first_public_floor_utc(date(2026,7,14), 'CME_PUBLIC_WEBSITE_SETTLEMENT')
        self.assertEqual(floor, datetime(2026,7,15,5,tzinfo=UTC))
        self.assert_untrusted(sample(date(2026,7,14), 'CME_PUBLIC_WEBSITE_SETTLEMENT'))

    def test_winter_public_website_floor_0600_utc(self):
        floor=conservative_first_public_floor_utc(date(2026,11,11), 'CME_PUBLIC_WEBSITE_SETTLEMENT')
        self.assertEqual(floor, datetime(2026,11,12,6,tzinfo=UTC))
        self.assert_untrusted(sample(date(2026,11,11), 'CME_PUBLIC_WEBSITE_SETTLEMENT'))

    def test_friday_to_monday_conservative_floor(self):
        self.assertEqual(conservative_first_public_floor_utc(date(2026,11,13), 'CME_PUBLIC_WEBSITE_SETTLEMENT'),
                         datetime(2026,11,16,6,tzinfo=UTC))

    def test_final_bulletin_10_ct_16_utc_november(self):
        self.assertEqual(conservative_first_public_floor_utc(date(2026,11,11), 'CME_DAILY_BULLETIN_FINAL'),
                         datetime(2026,11,12,16,tzinfo=UTC))

    def test_final_bulletin_10_ct_15_utc_july(self):
        self.assertEqual(conservative_first_public_floor_utc(date(2026,7,14), 'CME_DAILY_BULLETIN_FINAL'),
                         datetime(2026,7,15,15,tzinfo=UTC))

    def test_early_publication_claim_rejected_for_every_channel(self):
        for channel in ('CME_PUBLIC_WEBSITE_SETTLEMENT', 'CME_DAILY_BULLETIN_PRELIM',
                        'CME_DAILY_BULLETIN_FINAL'):
            with self.subTest(channel=channel):
                day=date(2026,11,11)
                floor=conservative_first_public_floor_utc(day,channel)
                r=sample(day,channel,pub=floor-timedelta(seconds=1),cap=floor+timedelta(hours=1))
                self.assertEqual(r['state'], 'BLOCKED_BEFORE_PUBLIC_DISSEMINATION_FLOOR')
                self.assert_untrusted(r)

    def test_at_floor_only_plausible_not_authenticated(self):
        r=sample(date(2026,11,11), 'CME_DAILY_BULLETIN_FINAL')
        self.assertEqual(r['state'], 'SELF_CLAIMED_PUBLIC_TIMING_PLAUSIBLE_NOT_AUTHENTICATED')
        self.assert_untrusted(r)

    def test_unknown_channel_no_assumed_paid_access(self):
        for channel in ('UNVERIFIED','PAID_EARLY_FEED',None):
            with self.subTest(channel=channel):
                r=inspect(trade_date=date(2026,11,11),channel=channel,
                          published_at_utc=datetime(2026,11,12,16,tzinfo=UTC),
                          captured_at_utc=datetime(2026,11,12,17,tzinfo=UTC),
                          as_of_utc=datetime(2026,11,12,18,tzinfo=UTC))
                self.assertEqual(r['state'], 'BLOCKED_INVALID_EVIDENCE')
                self.assert_untrusted(r)

    def test_invalid_date_and_naive_clock(self):
        self.assertIsNone(conservative_first_public_floor_utc('2026-11-11','CME_PUBLIC_WEBSITE_SETTLEMENT'))
        self.assertIsNone(conservative_first_public_floor_utc(date(2026,11,14),'CME_PUBLIC_WEBSITE_SETTLEMENT'))
        r=inspect(trade_date=date(2026,11,11),channel='CME_DAILY_BULLETIN_FINAL',
                  published_at_utc=datetime(2026,11,12,16),
                  captured_at_utc=datetime(2026,11,12,17,tzinfo=UTC),
                  as_of_utc=datetime(2026,11,12,18,tzinfo=UTC))
        self.assertEqual(r['state'], 'BLOCKED_INVALID_EVIDENCE')
        self.assert_untrusted(r)

    def test_not_yet_captured_at_query_time(self):
        day=date(2026,11,11)
        floor=conservative_first_public_floor_utc(day,'CME_PUBLIC_WEBSITE_SETTLEMENT')
        r=sample(day,'CME_PUBLIC_WEBSITE_SETTLEMENT',pub=floor,cap=floor+timedelta(minutes=5),asof=floor)
        self.assertEqual(r['state'], 'BLOCKED_INVALID_TIME_SEQUENCE')
        self.assert_untrusted(r)


if __name__ == '__main__': unittest.main()