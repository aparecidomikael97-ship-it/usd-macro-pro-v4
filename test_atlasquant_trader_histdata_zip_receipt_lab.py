"""Strictly synthetic ZIP-envelope tests; no downloaded forex quotes."""
from datetime import timedelta
from hashlib import sha256
from io import BytesIO
import unittest
import warnings
from zipfile import ZIP_BZIP2, ZIP_DEFLATED, ZIP_STORED, ZipFile, ZipInfo

from atlasquant_trader_histdata_m1_bid_window_lab import SCHEMA as M1_SCHEMA
from atlasquant_trader_histdata_zip_receipt_lab import (
    MAX_CSV_BYTES,
    SCHEMA,
    inspect_histdata_m1_zip_receipt_lab as inspect,
)
from test_atlasquant_trader_histdata_m1_bid_window_lab import (
    AS_OF, CAPTURE, EVENT, NAME, blob,
)


def make_zip(members=None, compression=ZIP_DEFLATED):
    if members is None:
        members = [(NAME, blob())]
    target = BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with ZipFile(target, "w", compression=compression) as zf:
            for name, payload in members:
                zf.writestr(name, payload)
    return target.getvalue()


_UNSET = object()


def run(archive=_UNSET, **kwargs):
    args = dict(archive_name="HISTDATA_COM_ASCII_EURUSD_M1202610.zip",
                expected_symbol="EURUSD", expected_year_month="202610",
                captured_at_utc=CAPTURE, as_of_utc=AS_OF,
                event_at_utc=EVENT)
    args.update(kwargs)
    return inspect(make_zip() if archive is _UNSET else archive, **args)


class HistDataZipReceiptTests(unittest.TestCase):
    def assert_no_trading(self, result):
        for key in ("downloaded_source_authenticity_verified",
                    "market_data_product_license_verified",
                    "historical_point_in_time_eligible",
                    "m15_execution_price_verified",
                    "historical_backtest_accuracy_verified",
                    "ask_prices_present", "spread_at_event_known",
                    "trade_authorized", "can_feed_live_radar",
                    "publishable", "worker_enabled", "scheduler_enabled",
                    "status_report_independently_verified"):
            self.assertIs(result[key], False, key)
        self.assertIsNone(result["fx_bias"])
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        self.assertEqual(result["new_cost_brl"], 0)

    def test_valid_offline_zip_proves_only_crc_and_structure(self):
        archive = make_zip()
        result = run(archive)
        self.assertEqual(result["schema"], M1_SCHEMA)
        self.assertEqual(result["zip_receipt_schema"], SCHEMA)
        self.assertEqual(result["state"],
                         "LAB_HISTDATA_BID_M15_WINDOW_STRUCTURALLY_COMPLETE_UNVERIFIED")
        self.assertEqual(result["source_zip_sha256"], sha256(archive).hexdigest())
        self.assertEqual(result["source_raw_sha256"], sha256(blob()).hexdigest())
        self.assertEqual(result["source_zip_member_count"], 1)
        self.assertTrue(result["source_zip_crc_checked"])
        self.assertTrue(result["source_zip_archive_structure_checked"])
        self.assertIsNone(result["status_member"])
        self.assert_no_trading(result)

    def test_optional_untrusted_status_is_hashed_not_claimed_verified(self):
        status = b"Status report is not a third-party validation.\n"
        r = run(make_zip([(NAME, blob()), ("EURUSD_M1_202610_status.txt", status)]))
        self.assertEqual(r["status_member"], "EURUSD_M1_202610_status.txt")
        self.assertEqual(r["status_member_sha256"], sha256(status).hexdigest())
        self.assertEqual(r["source_zip_member_count"], 2)
        self.assert_no_trading(r)

    def test_invalid_or_mismatched_archive_name_denied(self):
        for name in ("../eurusd.zip", "EURUSD.ZIP", "EURUSD.txt", "x\\y.zip", "é.zip", ""):
            self.assertEqual(run(archive_name=name)["state"], "LAB_BLOCKED")

    def test_wrong_file_symbol_month_or_type_denied(self):
        for name in ("DAT_ASCII_GBPUSD_M1_202610.csv",
                     "DAT_ASCII_EURUSD_M1_202609.csv",
                     "DAT_MT_EURUSD_M1_202610.csv"):
            self.assertEqual(run(make_zip([(name, blob())]))["state"], "LAB_BLOCKED")

    def test_unknown_third_member_denied(self):
        r = run(make_zip([(NAME, blob()), ("status.txt", b"hi"), ("extra.txt", b"hi")]))
        self.assertEqual(r["reason"], "UNEXPECTED_ZIP_MEMBER_COUNT")

    def test_no_code_or_unexpected_binary_member(self):
        for other in ("malware.py", "archive.exe", "a.csv", "a.txt.exe"):
            r = run(make_zip([(NAME, blob()), (other, b"hello")]))
            self.assertEqual(r["state"], "LAB_BLOCKED")

    def test_reject_zip_traversal_and_nested_paths(self):
        for path in ("../status.txt", "/absolute.txt", "nested/status.txt",
                     "folder\\status.txt", "./status.txt"):
            r = run(make_zip([(NAME, blob()), (path, b"hello")]))
            self.assertEqual(r["state"], "LAB_BLOCKED", path)

    def test_duplicate_members_deny_and_do_not_resolve_ambiguously(self):
        self.assertEqual(run(make_zip([(NAME, blob()), (NAME, blob())]))["reason"],
                         "DUPLICATE_ZIP_MEMBER")

    def test_zero_length_status_or_oversize_status_denied(self):
        for status in (b"", b"x" * (64 * 1024 + 1)):
            self.assertEqual(run(make_zip([(NAME, blob()), ("status.txt", status)]))["state"],
                             "LAB_BLOCKED")

    def test_oversize_csv_rejected_using_zip_metadata_without_decompression(self):
        payload = b"x" * (MAX_CSV_BYTES + 1)
        result = run(make_zip([(NAME, payload)]))
        self.assertEqual(result["reason"], "UNSAFE_ZIP_CSV_MEMBER")

    def test_reject_symlink_record(self):
        link = ZipInfo("status.txt")
        link.create_system = 3
        link.external_attr = 0o120777 << 16
        self.assertEqual(run(make_zip([(NAME, blob()), (link, b"foo")]))["reason"],
                         "UNSAFE_ZIP_STATUS_MEMBER")

    def test_reject_unsupported_compression(self):
        self.assertEqual(run(make_zip(compression=ZIP_BZIP2))["reason"],
                         "UNSAFE_ZIP_CSV_MEMBER")

    def test_stored_zip_crc_corruption_never_accepted(self):
        archive = make_zip(compression=ZIP_STORED)
        self.assertIn(b"1.110000", archive)
        corrupt = archive.replace(b"1.110000", b"1.120000", 1)
        self.assertEqual(run(corrupt)["reason"], "ZIP_CORRUPT_OR_UNREADABLE")

    def test_truncated_and_nonzip_bytes_denied(self):
        archive = make_zip()
        for raw in (archive[:150], archive[:-50], b"0" * 200, b"", None, "ZIP"):
            self.assertEqual(run(raw)["state"], "LAB_BLOCKED")

    def test_reject_invalid_target_month_or_symbol(self):
        for month in ("202613", "20260", "2026ab", "2026100", ""):
            self.assertEqual(run(expected_year_month=month)["state"], "LAB_BLOCKED")
        self.assertEqual(run(expected_symbol="XAUUSD")["state"], "LAB_BLOCKED")

    def test_missing_m1_in_inner_csv_remains_blocked(self):
        rows = blob().splitlines()
        del rows[7]
        r = run(make_zip([(NAME, b"\n".join(rows) + b"\n")]))
        self.assertEqual(r["reason"], "M1_MISSING_IN_REQUIRED_M15_WINDOW_NO_FILL")
        self.assertTrue(r["source_zip_crc_checked"])
        self.assert_no_trading(r)

    def test_naive_capture_clock_remains_blocked_even_if_crc_valid(self):
        r = run(captured_at_utc=CAPTURE.replace(tzinfo=None))
        self.assertEqual(r["state"], "LAB_BLOCKED")
        self.assert_no_trading(r)

    def test_post_event_gap_remains_blocked(self):
        rows = blob().splitlines()
        del rows[100]
        r = run(make_zip([(NAME, b"\n".join(rows) + b"\n")]))
        self.assertEqual(r["reason"], "M1_MISSING_IN_REQUIRED_M15_WINDOW_NO_FILL")


if __name__ == "__main__":
    unittest.main()
