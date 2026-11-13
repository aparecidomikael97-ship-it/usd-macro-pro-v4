"""Read-only local policy archive source replay tests with synthetic files.

All issuer HTML/CSV/JSON are synthetic fixtures; the temporary files do
not imply that AM12 is connected or that historical data was captured.
No requests, broker calls, account inspection, trades, GitHub comments,
production access or writes outside temporary test folders.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS
from atlasquant_trader_fx28_policy_local_archive_replay_lab import (
    _ARCHIVES, inspect_fx28_official_policy_archive_replay_lab as inspect,
)
from test_atlasquant_trader_fx28_eight_policy_raw_source_join_lab import (
    synthetic_packets,
)

UTC=timezone.utc
NOW=datetime(2026,11,13,11,30,tzinfo=UTC)


def archive_dir(base: str) -> Path:
    out=Path(base)/"AtlasQuant"/"LAB"/"official_macro_receipts"
    out.mkdir(parents=True,exist_ok=True)
    return out


def save_fixture(folder: Path, currency: str, packet: dict,
                 *, override_stamp: str | None = None,
                 override_body: bytes | None = None,
                 override_receipt: dict | None = None) -> tuple[Path,Path]:
    prefix,suffix,_max_bytes=_ARCHIVES[currency]
    body=packet["original_bytes"] if override_body is None else override_body
    rec=deepcopy(packet["receipt"]) if override_receipt is None else deepcopy(override_receipt)
    stamp=override_stamp or rec["finished_at_utc"]
    ts=stamp.replace("-","").replace(":","")
    name=f"{prefix}_{ts}_{rec['body_sha256'][:12]}"
    raw=folder/(name+suffix)
    meta=folder/(name+".receipt.json")
    raw.write_bytes(body)
    meta.write_bytes((json.dumps(rec,sort_keys=True,indent=2)+"\n").encode("utf-8"))
    return raw,meta


class EightIssuerLocalReceiptFolderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.synthetic=synthetic_packets()

    def no_trade(self,r):
        self.assertEqual(r["operational_bias"],"AGUARDAR")
        self.assertFalse(r["trade_authorized"])
        self.assertFalse(r["publishable"])
        self.assertFalse(r["worker_enabled"])
        self.assertFalse(r["scheduler_enabled"])
        self.assertFalse(r["live_alert_allowed"])
        self.assertFalse(r["source_original_bytes_from_AM12_independently_attested"])
        self.assertFalse(r["source_current_issuer_identity_independently_verified"])
        self.assertFalse(r["true_first_seen_time_independently_attested"])
        self.assertFalse(r["historical_point_in_time_vintage_verified"])
        self.assertFalse(r["cpi_for_all_eight_currencies_authenticated"])
        self.assertFalse(r["differing_policy_instruments_harmonized"])
        self.assertFalse(r["pre_event_forecast_witnessed"])
        self.assertFalse(r["outcome_price_available_and_authenticated"])
        self.assertIsNone(r["directional_bias"])
        self.assertIsNone(r["calibrated_probability"])
        self.assertIsNone(r["validated_direction_accuracy"])
        self.assertEqual(r["http_requests"],0)
        self.assertEqual(r["files_written"],0)
        self.assertEqual(r["new_cost_brl"],0)
        for row in r["pair_policy_source_coverage"]:
            self.assertFalse(row["cpi_both_currencies_authenticated"])
            self.assertFalse(row["fx_direction_admissible"])

    def test_missing_folder_does_not_invent_am12_source_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            r=inspect(local_appdata=td,decision_at_utc=NOW)
        self.no_trade(r)
        self.assertEqual(r["state"],"LAB_FX28_POLICY_ARCHIVE_REPLAY_BLOCKED")
        self.assertEqual(r["reason"],"LOCAL_ISSUER_ARCHIVE_FOLDER_MISSING")
        self.assertEqual(r["currencies_with_local_original_bytes_validated"],0)
        self.assertFalse(r["folder_present_on_this_runtime"])
        self.assertEqual(r["pairs_with_both_policy_originals_locally_checked"],0)

    def test_empty_archive_not_same_as_eight_modules_ready(self):
        with tempfile.TemporaryDirectory() as td:
            archive_dir(td)
            r=inspect(local_appdata=td,decision_at_utc=NOW)
        self.no_trade(r)
        self.assertEqual(r["policy_issuer_contracts_available"],8)
        self.assertEqual(r["currencies_with_local_original_bytes_validated"],0)
        self.assertEqual(r["currencies_missing"],sorted(CURRENCIES))
        self.assertEqual(r["pairs_with_both_policy_originals_locally_checked"],0)

    def test_three_synthetic_original_source_files_produce_3_policy_only_pairs(self):
        with tempfile.TemporaryDirectory() as td:
            folder=archive_dir(td)
            for c in ("USD","EUR","CAD"):
                save_fixture(folder,c,self.synthetic[c])
            r=inspect(local_appdata=td,decision_at_utc=NOW)
        self.no_trade(r)
        self.assertEqual(r["state"],
                         "LAB_FX28_POLICY_ARCHIVE_PARTIAL_OR_REJECTED_NO_GO")
        self.assertEqual(r["currencies_with_local_original_bytes_validated"],3)
        self.assertEqual(r["currencies_locally_checked"],sorted(["USD","EUR","CAD"]))
        self.assertEqual(r["pairs_with_both_policy_originals_locally_checked"],3)
        self.assertEqual(r["pairs_lacking_at_least_one_policy_original"],25)
        pairs={entry["pair"] for entry in r["pair_policy_source_coverage"]
               if entry["both_policy_sources_locally_checked"]}
        self.assertEqual(pairs,{"EUR/USD","EUR/CAD","USD/CAD"})

    def test_full_eight_synthetic_files_never_prove_real_pit_or_direction(self):
        with tempfile.TemporaryDirectory() as td:
            folder=archive_dir(td)
            for c,p in self.synthetic.items():
                save_fixture(folder,c,p)
            r=inspect(local_appdata=td,decision_at_utc=NOW)
        self.no_trade(r)
        self.assertEqual(r["state"],
                         "LAB_FX28_POLICY_ARCHIVE_EIGHT_ORIGINALS_LOCAL_ONLY_NO_GO")
        self.assertEqual(r["currency_receipt_files_selected"],8)
        self.assertEqual(r["currencies_with_local_original_bytes_validated"],8)
        self.assertEqual(r["pairs_with_both_policy_originals_locally_checked"],28)
        self.assertEqual(len(r["pair_policy_source_coverage"]),28)
        self.assertEqual(r["currencies_rejected"],{})

    def test_single_original_cannot_make_any_fx_pair_policy_complete(self):
        with tempfile.TemporaryDirectory() as td:
            folder=archive_dir(td)
            save_fixture(folder,"USD",self.synthetic["USD"])
            r=inspect(local_appdata=td,decision_at_utc=NOW)
        self.no_trade(r)
        self.assertEqual(r["currencies_with_local_original_bytes_validated"],1)
        self.assertEqual(r["pairs_with_both_policy_originals_locally_checked"],0)

    def test_corrupted_latest_source_cannot_fallback_to_valid_older_receipt(self):
        with tempfile.TemporaryDirectory() as td:
            folder=archive_dir(td)
            save_fixture(folder,"USD",self.synthetic["USD"])
            newer=deepcopy(self.synthetic["USD"]["receipt"])
            newer["started_at_utc"]="2026-11-13T11:19:00Z"
            newer["finished_at_utc"]="2026-11-13T11:19:01Z"
            save_fixture(folder,"USD",self.synthetic["USD"],
                         override_receipt=newer,
                         override_body=self.synthetic["USD"]["original_bytes"]+b" ",
                         override_stamp=newer["finished_at_utc"])
            r=inspect(local_appdata=td,decision_at_utc=NOW)
        self.no_trade(r)
        self.assertEqual(r["currencies_with_local_original_bytes_validated"],0)
        self.assertEqual(r["currencies_rejected"]["USD"],
                         "SOURCE_FILE_SHA256_OR_FILENAME_MISMATCH")
        self.assertEqual(r["pairs_with_both_policy_originals_locally_checked"],0)

    def test_correct_sha_but_unauthorized_url_is_rejected_by_issuer_parser(self):
        with tempfile.TemporaryDirectory() as td:
            folder=archive_dir(td)
            rec=deepcopy(self.synthetic["CAD"]["receipt"])
            rec["final_url"]="https://attacker.invalid/valet/"
            save_fixture(folder,"CAD",self.synthetic["CAD"],override_receipt=rec)
            r=inspect(local_appdata=td,decision_at_utc=NOW)
        self.no_trade(r)
        self.assertEqual(r["currencies_with_local_original_bytes_validated"],0)
        self.assertTrue(r["currencies_rejected"]["CAD"].startswith(
            "ISSUER_SPECIFIC_VALIDATOR_REJECTED:"))

    def test_only_future_stamped_capture_does_not_backfill_older_cutoff(self):
        with tempfile.TemporaryDirectory() as td:
            folder=archive_dir(td)
            old=deepcopy(self.synthetic["CAD"]["receipt"])
            old["started_at_utc"]="2026-11-13T11:50:00Z"
            old["finished_at_utc"]="2026-11-13T11:50:01Z"
            save_fixture(folder,"CAD",self.synthetic["CAD"],override_receipt=old)
            r=inspect(local_appdata=td,decision_at_utc=NOW)
        self.no_trade(r)
        self.assertEqual(r["currencies_with_local_original_bytes_validated"],0)
        self.assertEqual(r["currency_archive_status"]["CAD"]["status"],
                         "ONLY_FUTURE_STAMPED_RECEIPTS")
        self.assertEqual(r["future_stamped_receipts_ignored"]["CAD"],1)

    def test_future_file_does_not_displace_older_pre_cutoff_capture(self):
        with tempfile.TemporaryDirectory() as td:
            folder=archive_dir(td)
            save_fixture(folder,"USD",self.synthetic["USD"])
            future=deepcopy(self.synthetic["USD"]["receipt"])
            future["started_at_utc"]="2026-11-13T11:49:59Z"
            future["finished_at_utc"]="2026-11-13T11:50:00Z"
            save_fixture(folder,"USD",self.synthetic["USD"],override_receipt=future)
            r=inspect(local_appdata=td,decision_at_utc=NOW)
        self.no_trade(r)
        self.assertEqual(r["currencies_with_local_original_bytes_validated"],1)
        self.assertEqual(r["future_stamped_receipts_ignored"]["USD"],1)

    def test_ambiguous_capture_same_timestamp_two_hashes_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            folder=archive_dir(td)
            save_fixture(folder,"USD",self.synthetic["USD"])
            body=self.synthetic["USD"]["original_bytes"]+b"\n"
            other=deepcopy(self.synthetic["USD"]["receipt"])
            other["body_sha256"]=sha256(body).hexdigest()
            save_fixture(folder,"USD",self.synthetic["USD"],
                         override_body=body,override_receipt=other)
            r=inspect(local_appdata=td,decision_at_utc=NOW)
        self.no_trade(r)
        self.assertEqual(r["currencies_with_local_original_bytes_validated"],0)
        self.assertEqual(r["currencies_rejected"]["USD"],
                         "AMBIGUOUS_MULTIPLE_CAPTURES_AT_SAME_UTC_SECOND")

    def test_tampered_receipt_timestamp_does_not_match_immutable_name(self):
        with tempfile.TemporaryDirectory() as td:
            folder=archive_dir(td)
            _,meta=save_fixture(folder,"EUR",self.synthetic["EUR"])
            rec=json.loads(meta.read_text())
            rec["finished_at_utc"]="2026-11-13T02:13:05Z"
            meta.write_text(json.dumps(rec))
            r=inspect(local_appdata=td,decision_at_utc=NOW)
        self.no_trade(r)
        self.assertEqual(r["currencies_rejected"]["EUR"],
                         "RECEIPT_FINISH_TIME_DIFFERS_FROM_FILENAME")

    def test_receipt_with_duplicate_json_keys_blocks_currency(self):
        with tempfile.TemporaryDirectory() as td:
            folder=archive_dir(td)
            _,meta=save_fixture(folder,"CAD",self.synthetic["CAD"])
            original=meta.read_text()
            meta.write_text(original.replace(
                '"body_sha256":', '"body_sha256": "bad", "body_sha256":',1))
            r=inspect(local_appdata=td,decision_at_utc=NOW)
        self.no_trade(r)
        self.assertIn("CAD",r["currencies_rejected"])
        self.assertEqual(r["currencies_with_local_original_bytes_validated"],0)

    def test_wrong_or_malformed_issuer_receipt_name_blocks_not_silent_fallback(self):
        with tempfile.TemporaryDirectory() as td:
            folder=archive_dir(td)
            save_fixture(folder,"CHF",self.synthetic["CHF"])
            (folder/"CHF_SNB_CURRENT_POLICY_wrong.receipt.json").write_text("{}")
            r=inspect(local_appdata=td,decision_at_utc=NOW)
        self.no_trade(r)
        self.assertEqual(r["currencies_rejected"]["CHF"],
                         "UNSAFE_OR_MALFORMED_ISSUER_RECEIPT_FILENAME")

    def test_missing_source_original_body_does_not_count_receipt(self):
        with tempfile.TemporaryDirectory() as td:
            folder=archive_dir(td)
            raw,_meta=save_fixture(folder,"NZD",self.synthetic["NZD"])
            raw.unlink()
            r=inspect(local_appdata=td,decision_at_utc=NOW)
        self.no_trade(r)
        self.assertEqual(r["currencies_rejected"]["NZD"],
                         "LOCAL_SOURCE_OR_RECEIPT_FILE_MISSING_OR_SYMLINK")

    def test_receipt_oversize_blocks_without_issuer_parser_or_network(self):
        with tempfile.TemporaryDirectory() as td:
            folder=archive_dir(td)
            _,meta=save_fixture(folder,"JPY",self.synthetic["JPY"])
            meta.write_bytes(b"x"*9000)
            r=inspect(local_appdata=td,decision_at_utc=NOW)
        self.no_trade(r)
        self.assertEqual(r["currencies_rejected"]["JPY"],
                         "LOCAL_RECEIPT_JSON_SIZE_INVALID")

    def test_too_many_captures_for_one_currency_are_not_silently_selected(self):
        with tempfile.TemporaryDirectory() as td:
            folder=archive_dir(td)
            prefix=_ARCHIVES["USD"][0]
            for n in range(31):
                (folder/f"{prefix}_20261113T02{n:04d}Z_abcdefabcdef.receipt.json"
                ).write_text("{}")
            r=inspect(local_appdata=td,decision_at_utc=NOW)
        self.no_trade(r)
        self.assertEqual(r["currencies_rejected"]["USD"],
                         "EXCESS_RECEIPT_FILES_FOR_ONE_ISSUER")

    def test_symlinked_source_or_folder_never_read_as_issuer_archive(self):
        with tempfile.TemporaryDirectory() as td:
            folder=archive_dir(td)
            source,meta=save_fixture(folder,"USD",self.synthetic["USD"])
            target=folder/"orig_backup.html"
            source.replace(target)
            try:
                source.symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation not permitted")
            r=inspect(local_appdata=td,decision_at_utc=NOW)
        self.no_trade(r)
        self.assertEqual(r["currencies_rejected"]["USD"],
                         "LOCAL_SOURCE_OR_RECEIPT_FILE_MISSING_OR_SYMLINK")

    def test_root_must_be_absolute_and_decision_aware(self):
        for path,clock in (("",NOW),("relative",NOW),
                           (".",NOW),(None,NOW),
                           ("/missing",NOW.replace(tzinfo=None)),
                           ("/missing",NOW.replace(microsecond=1))):
            with self.subTest(path=path,clock=clock):
                r=inspect(local_appdata=path,decision_at_utc=clock)
                self.no_trade(r)
                self.assertEqual(r["state"],"LAB_FX28_POLICY_ARCHIVE_REPLAY_BLOCKED")

    def test_every_mapped_archive_uses_unique_prefix_and_exact_8_currencies(self):
        self.assertEqual(set(_ARCHIVES),set(CURRENCIES))
        self.assertEqual(len(set(spec[0] for spec in _ARCHIVES.values())),8)
        self.assertEqual(len(OFFICIAL_PAIRS),28)


if __name__=="__main__":
    unittest.main()
