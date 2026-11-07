"""LAB regression tests, real archived documents optional in isolated CI."""
import os
from pathlib import Path
from datetime import datetime, timezone
import unittest

from atlasquant_audnzd_cpi_archive_receipt_lab import (
    AUD_SNAPSHOT_SHA256, NZD_SNAPSHOT_SHA256, inspect_archived_audnzd_cpi_lab as inspect,
)

BASE = Path(os.environ.get('ATLASQUANT_CPI_ARCHIVE_DIRECTORY', Path(__file__).parent))
AUD = BASE / 'AUD_ABS_CPI_2026Q3_Table17.xlsx'
NZD = BASE / 'NZD_CPI_2026Q3_StatsNZ_summary.pdf'
NOW = datetime(2026, 11, 7, tzinfo=timezone.utc)


def audit(aud=b'', nzd=b'', asof=NOW):
    return inspect(aud_xlsx=aud, nzd_pdf=nzd, as_of_utc=asof)


class ArchiveReceiptTests(unittest.TestCase):
    def assert_blocked_from_market(self, result):
        self.assertEqual(result['operational_bias'], 'AGUARDAR')
        self.assertFalse(result['can_feed_live_radar'])
        self.assertFalse(result['automatic_alert_enabled'])
        self.assertFalse(result['trade_authorized'])
        self.assertIsNone(result['score_0_to_10'])
        self.assertIsNone(result['directional_win_probability'])
        self.assertFalse(result['historical_point_in_time_verified'])
        self.assertFalse(result['issuer_origin_independently_authenticated'])
        self.assertEqual(result['new_cost_brl'], 0)

    @unittest.skipUnless(AUD.is_file() and NZD.is_file(), 'Original Library archive files not present in CI')
    def test_two_archives_extract_correct_cells_and_publisher_pdf(self):
        result = audit(AUD.read_bytes(), NZD.read_bytes())
        self.assertEqual(result['state'], 'LAB_TWO_DOCUMENT_VALUES_MATCH_ARCHIVED_BYTES_UNATTESTED')
        self.assertTrue(result['archived_bytes_verified'])
        self.assertEqual(result['source_receipts']['AUD']['archive_sha256'], AUD_SNAPSHOT_SHA256)
        self.assertEqual(result['source_receipts']['NZD']['archive_sha256'], NZD_SNAPSHOT_SHA256)
        self.assertEqual(result['source_receipts']['AUD']['source_series_claim'], 'A2325846C')
        self.assertEqual(result['source_receipts']['AUD']['cells'], ['Data1!J319','Data1!J323'])
        self.assertEqual(result['inflation_comparison']['AUD_annual_yoy_pct_derived_from_rounded_index'], '3.9')
        self.assertEqual(result['inflation_comparison']['NZD_annual_yoy_pct_publisher_reported'], '3.7')
        self.assertFalse(result['inflation_comparison']['methodology_equivalent_proven'])
        self.assert_blocked_from_market(result)

    @unittest.skipUnless(AUD.is_file() and NZD.is_file(), 'Original Library archive files not present in CI')
    def test_mutated_australian_archive_rejected(self):
        altered = bytearray(AUD.read_bytes()); altered[-25] ^= 1
        r = audit(bytes(altered), NZD.read_bytes())
        self.assertEqual(r['reason'], 'ARCHIVE_SNAPSHOT_DIGEST_MISMATCH')
        self.assert_blocked_from_market(r)

    @unittest.skipUnless(AUD.is_file() and NZD.is_file(), 'Original Library archive files not present in CI')
    def test_mutated_nzd_archive_rejected(self):
        altered = bytearray(NZD.read_bytes()); altered[400] ^= 1
        r = audit(AUD.read_bytes(), bytes(altered))
        self.assertEqual(r['reason'], 'ARCHIVE_SNAPSHOT_DIGEST_MISMATCH')
        self.assert_blocked_from_market(r)

    @unittest.skipUnless(AUD.is_file() and NZD.is_file(), 'Original Library archive files not present in CI')
    def test_archives_swapped_rejected(self):
        r = audit(NZD.read_bytes(), AUD.read_bytes())
        self.assertEqual(r['reason'], 'ARCHIVE_SNAPSHOT_DIGEST_MISMATCH')
        self.assert_blocked_from_market(r)

    def test_empty_archives_blocked(self):
        r = audit()
        self.assertEqual(r['reason'], 'ARCHIVE_SNAPSHOT_DIGEST_MISMATCH')
        self.assert_blocked_from_market(r)

    def test_unpinned_fake_documents_blocked(self):
        r = audit(b'A'*900,b'%PDF fake')
        self.assertEqual(r['reason'], 'ARCHIVE_SNAPSHOT_DIGEST_MISMATCH')
        self.assert_blocked_from_market(r)

    def test_naive_clock_not_accepted(self):
        r = audit(asof=datetime(2026, 11, 7))
        self.assertEqual(r['reason'], 'DECISION_CLOCK_INVALID')
        self.assert_blocked_from_market(r)

    def test_wrong_clock_type_not_accepted(self):
        r = audit(asof='2026-11-07T00:00:00Z')
        self.assertEqual(r['reason'], 'DECISION_CLOCK_INVALID')
        self.assert_blocked_from_market(r)

    def test_apparent_backtest_before_release_blocked(self):
        r = audit(asof=datetime(2026, 10, 22, tzinfo=timezone.utc))
        self.assertEqual(r['reason'], 'BEFORE_PUBLICATION_RESEARCH_FLOOR')
        self.assert_blocked_from_market(r)

    def test_unusual_large_file_blocked(self):
        r = audit(b'x'*2_000_001,b'z')
        self.assertEqual(r['state'], 'LAB_BLOCKED')
        self.assert_blocked_from_market(r)

    def test_nonbytes_rejected(self):
        r = audit(aud='not binary')
        self.assertEqual(r['state'], 'LAB_BLOCKED')
        self.assert_blocked_from_market(r)

    def test_snapshot_shas_immutable_format(self):
        self.assertEqual(len(AUD_SNAPSHOT_SHA256),64)
        self.assertEqual(len(NZD_SNAPSHOT_SHA256),64)
        self.assertNotEqual(AUD_SNAPSHOT_SHA256,NZD_SNAPSHOT_SHA256)
        self.assert_blocked_from_market(audit())


if __name__ == '__main__':
    unittest.main(verbosity=2)
