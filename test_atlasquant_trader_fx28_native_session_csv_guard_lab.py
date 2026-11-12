"""Synthetic-only offline verification of native MT5 quote/trade CSV receipts."""
from __future__ import annotations

import csv
from datetime import datetime, timezone, timedelta
from io import StringIO
import unittest

from atlasquant_instrument_registry import FX_28
from atlasquant_trader_fx28_native_session_csv_guard_lab import (
    CSV_COLUMNS, SCHEMA, inspect_fx28_native_session_csv_lab as inspect,
)

NOW = datetime(2026, 11, 12, 23, 35, tzinfo=timezone.utc)
STAMP = "2026-11-12T23:30:00Z"


def native_rows():
    """Exact rows that the read-only script would produce; no MT5 connection."""
    rows = []
    hidden = {"NZDUSD", "USDCHF", "USDCAD", "EURGBP"}
    for sym in FX_28:
        for day in range(7):
            for kind in ("QUOTE", "TRADE"):
                base = {
                    "schema": SCHEMA, "observed_utc_os_clock_claim": STAMP,
                    "canonical_symbol": sym, "server_weekday": str(day),
                    "session_kind": kind,
                    "market_watch_visible": ("FALSE" if sym in hidden else "TRUE"),
                    "mt5_last_error_code": "0",
                }
                if day in (1,2,3,4,5):
                    rows.append({
                        **base, "session_index": "0",
                        "status": "SESSION_RETURNED",
                        "from_server_midnight_seconds": "60",
                        "to_server_midnight_seconds": "86340",
                    })
                    rows.append({
                        **base, "session_index": "1",
                        "status": "END_OF_RETURNED_SESSIONS",
                        "from_server_midnight_seconds": "",
                        "to_server_midnight_seconds": "",
                    })
                else:
                    rows.append({
                        **base, "session_index": "0",
                        "status": "NO_SESSION_RETURNED",
                        "from_server_midnight_seconds": "",
                        "to_server_midnight_seconds": "",
                    })
    return rows


def encode(rows):
    buffer = StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=CSV_COLUMNS, delimiter=";",
                            lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


class SessionCsvGuardTests(unittest.TestCase):
    def probe(self, rows=None, *, now=NOW):
        return inspect(encode(native_rows() if rows is None else rows),
                       evaluated_at_utc=now)

    def safety(self, report):
        self.assertEqual(report["operational_bias"], "AGUARDAR")
        self.assertFalse(report["trade_authorized"])
        self.assertFalse(report["publishable"])
        self.assertFalse(report["scheduler_enabled"])
        self.assertFalse(report["worker_enabled"])
        self.assertFalse(report["historical_session_schedule_authenticated"])
        self.assertFalse(report["historical_quote_session_authenticated"])
        self.assertFalse(report["broker_timezone_for_2026_10_and_11_verified"])
        self.assertFalse(report["provider_session_calendar_verified"])
        self.assertFalse(report["session_based_backfill_permitted"])
        self.assertFalse(report["live_trading_session_status_verified"])
        self.assertIsNone(report["calibrated_probability"])
        self.assertIsNone(report["validated_accuracy"])
        self.assertEqual(report["eligible_utc_m15_calendar_exemptions"], [])
        self.assertEqual(report["broker_connections"], 0)
        self.assertEqual(report["files_written"], 0)
        self.assertFalse(report["account_info_accessed"])
        self.assertFalse(report["orders_or_positions_accessed"])

    def test_all_392_pair_weekday_kind_keys_reconcile_but_not_a_calendar_waiver(self):
        r = self.probe()
        self.safety(r)
        self.assertEqual(r["state"],
                         "LAB_FX28_NATIVE_MT5_SESSION_METADATA_CLAIM_ONLY_NO_GO")
        self.assertTrue(r["local_native_session_inventory_structurally_complete"])
        self.assertEqual(r["expected_pair_weekday_kinds"], 392)
        self.assertEqual(r["verified_metadata_keys"], 392)
        self.assertEqual(r["returned_native_session_rows"], 280)
        self.assertEqual(r["no_session_returned_count"], 112)
        self.assertEqual(r["session_claim_timestamp_utc"],
                         "2026-11-12T23:30:00+00:00")
        self.assertEqual(r["hidden_symbols_in_snapshot"],
                         ["NZDUSD", "USDCHF", "USDCAD", "EURGBP"])
        self.assertEqual(r["symbols_with_no_session_returned"], list(FX_28))

    def test_missing_pair_or_full_day_never_counts_as_closed_session(self):
        for predicate in (
            lambda row: row["canonical_symbol"] == "GBPNZD",
            lambda row: row["canonical_symbol"] == "CHFJPY"
                        and row["server_weekday"] == "1",
        ):
            with self.subTest(which=predicate):
                rows = [x for x in native_rows() if not predicate(x)]
                r = self.probe(rows)
                self.safety(r)
                self.assertEqual(r["reason"], "EXPECTED_ALL_28_X_7_X_2_SESSION_KEYS")
                self.assertFalse(r["local_native_session_inventory_structurally_complete"])

    def test_duplicate_end_marker_fails_order_contract(self):
        rows = native_rows()
        row = next(x for x in rows if x["canonical_symbol"] == "EURUSD"
                   and x["server_weekday"] == "1" and x["session_kind"] == "QUOTE"
                   and x["status"] == "END_OF_RETURNED_SESSIONS")
        rows.insert(rows.index(row), dict(row))
        r = self.probe(rows)
        self.safety(r)
        self.assertEqual(r["reason"], "NONCONTIGUOUS_OR_DUPLICATE_SESSION_INDEX")

    def test_truncated_9th_session_must_not_be_silently_dropped(self):
        rows = native_rows()
        row = next(x for x in rows if x["canonical_symbol"] == "USDCHF"
                   and x["server_weekday"] == "1" and x["session_kind"] == "TRADE"
                   and x["status"] == "END_OF_RETURNED_SESSIONS")
        row["status"] = "TRUNCATED_MORE_THAN_8_SESSIONS"
        r = self.probe(rows)
        self.safety(r)
        self.assertEqual(r["reason"], "MISSING_DAY_KIND_END_MARKER_OR_TRUNCATED")

    def test_false_no_session_claim_must_not_follow_returned_session(self):
        rows = native_rows()
        row = next(x for x in rows if x["canonical_symbol"] == "EURNZD"
                   and x["server_weekday"] == "2" and x["session_kind"] == "QUOTE"
                   and x["status"] == "END_OF_RETURNED_SESSIONS")
        row["status"] = "NO_SESSION_RETURNED"
        r = self.probe(rows)
        self.safety(r)
        self.assertEqual(r["reason"], "NO_SESSION_STATUS_INCONSISTENT_WITH_SESSIONS")

    def test_no_session_returned_is_not_independent_proof_of_broker_closed(self):
        rows = native_rows()
        # A single *visible* pair has no returned quote session on Monday.
        sample = [x for x in rows if x["canonical_symbol"] == "EURUSD"
                  and x["server_weekday"] == "1" and x["session_kind"] == "QUOTE"]
        rows = [x for x in rows if x not in sample]
        rows.append({**sample[0], "session_index": "0",
                     "status": "NO_SESSION_RETURNED",
                     "from_server_midnight_seconds": "",
                     "to_server_midnight_seconds": ""})
        r = self.probe(rows)
        self.safety(r)
        self.assertEqual(r["state"],
                         "LAB_FX28_NATIVE_MT5_SESSION_METADATA_CLAIM_ONLY_NO_GO")
        self.assertEqual(r["no_session_returned_count"], 113)
        self.assertFalse(r["historical_quote_session_authenticated"])
        self.assertEqual(r["eligible_utc_m15_calendar_exemptions"], [])

    def test_off_granularity_or_bad_negative_session_bounds_blocks(self):
        for field, val in (
            ("from_server_midnight_seconds", "-1"),
            ("to_server_midnight_seconds", "999999"),
            ("from_server_midnight_seconds", "86340"),
        ):
            with self.subTest(field=field, val=val):
                rows = native_rows()
                row = next(x for x in rows if x["canonical_symbol"] == "NZDUSD"
                           and x["server_weekday"] == "1"
                           and x["session_kind"] == "QUOTE"
                           and x["status"] == "SESSION_RETURNED")
                row[field] = val
                r = self.probe(rows)
                self.safety(r)
                self.assertEqual(r["state"], "LAB_FX28_NATIVE_SESSION_RECEIPT_BLOCKED")

    def test_wrong_symbol_visibility_snapshot_or_version_blocks(self):
        for violation in ("unexpected", "visibility", "schema"):
            with self.subTest(violation=violation):
                rows = native_rows()
                row = next(x for x in rows if x["canonical_symbol"] == "USDJPY"
                           and x["server_weekday"] == "2"
                           and x["session_kind"] == "TRADE")
                if violation == "unexpected":
                    row["canonical_symbol"] = "USDXAU"
                elif violation == "visibility":
                    row["market_watch_visible"] = "FALSE"
                else:
                    row["schema"] = "FORGED"
                r = self.probe(rows)
                self.safety(r)
                self.assertEqual(r["state"], "LAB_FX28_NATIVE_SESSION_RECEIPT_BLOCKED")

    def test_future_stale_naive_and_mixed_clock_claims_block(self):
        for value in (
            "2026-11-13T00:00:00Z",
            "2026-11-01T00:00:00Z",
            "2026-11-12T23:34:59",
            "2025-11-12T23:30:00Z",
        ):
            rows = native_rows()
            for row in rows:
                row["observed_utc_os_clock_claim"] = value
            r = self.probe(rows)
            self.safety(r)
            self.assertEqual(r["state"], "LAB_FX28_NATIVE_SESSION_RECEIPT_BLOCKED")
        rows = native_rows()
        rows[-1]["observed_utc_os_clock_claim"] = "2026-11-12T23:31:00Z"
        self.assertEqual(self.probe(rows)["reason"], "INCONSISTENT_SNAPSHOT_CLOCK")

    def test_no_account_columns_or_extra_fields_accepted(self):
        raw = encode(native_rows())
        r = inspect(raw.replace(b"canonical_symbol", b"account_login"),
                    evaluated_at_utc=NOW)
        self.safety(r)
        self.assertEqual(r["reason"], "NATIVE_CSV_HEADER_MISMATCH")
        r = inspect(raw + b"irrelevant;extra\n", evaluated_at_utc=NOW)
        self.safety(r)
        self.assertEqual(r["state"], "LAB_FX28_NATIVE_SESSION_RECEIPT_BLOCKED")

    def test_invalid_input_not_accepted_or_written(self):
        for inp, now in (
            (b"", NOW), (b"bad", NOW),
            ("text not bytes", NOW), (encode(native_rows()), NOW.replace(tzinfo=None)),
        ):
            r = inspect(inp, evaluated_at_utc=now)
            self.safety(r)
            self.assertEqual(r["state"], "LAB_FX28_NATIVE_SESSION_RECEIPT_BLOCKED")

    def test_8_sessions_with_end_sentinel_are_structurally_ok_but_unattested(self):
        rows = native_rows()
        key = ("GBPCHF", "2", "QUOTE")
        original = [x for x in rows if (x["canonical_symbol"],
                      x["server_weekday"], x["session_kind"]) == key]
        rows = [x for x in rows if (x["canonical_symbol"],
                x["server_weekday"], x["session_kind"]) != key]
        example = original[0]
        for i in range(8):
            rows.append({**example, "session_index": str(i),
                         "from_server_midnight_seconds": str(i*3600),
                         "to_server_midnight_seconds": str(i*3600+1800)})
        rows.append({**original[1], "session_index": "8"})
        r = self.probe(rows)
        self.safety(r)
        self.assertEqual(r["state"],
                         "LAB_FX28_NATIVE_MT5_SESSION_METADATA_CLAIM_ONLY_NO_GO")
        self.assertEqual(r["returned_native_session_rows"], 287)


if __name__ == "__main__":
    unittest.main()
