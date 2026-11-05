"""Red-team internal ZIP replay, entirely offline with synthetic CSV fixtures."""
from __future__ import annotations

from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from zipfile import ZipFile, ZIP_DEFLATED, ZIP_STORED

import atlasquant_trader_eurusd_policy_capture_once_lab as capture
from atlasquant_trader_eurusd_policy_archive_verify_lab import (
    verify_policy_capture_zip_offline_lab as verify, main,
)

ECB = (b"KEY,FREQ,REF_AREA,CURRENCY,TIME_PERIOD,OBS_VALUE,OBS_STATUS\n"
       b"FM.D.U2.EUR.4F.KR.DFR.LEV,D,U2,EUR,2025-06-11,2.0000000,A\n")
FED = (b"observation_date,DFEDTARL,DFEDTARU\n"
       b"2026-11-01,3.75,4.00\n")
NOW = datetime.now(timezone.utc) + timedelta(minutes=1)


class Response:
    status = 200

    def __init__(self, url: str, raw: bytes):
        self.url = url
        self.raw = raw
        self.headers = {"Content-Type": "text/csv", "Date": "claimed"}

    def geturl(self):
        return self.url

    def read(self, n):
        return self.raw[:n]

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class Opener:
    def __init__(self, response):
        self.response = response

    def open(self, *_args, **_kwargs):
        return self.response


def create_zip(directory, source="ECB_EUR_DFR_EFFECTIVE", raw=ECB):
    url = capture.SOURCES[source][0]
    with patch.object(capture, "build_opener", return_value=Opener(Response(url, raw))):
        out = capture.capture_policy_csv_once_lab(
            source, manually_authorized=True, archive_dir=directory)
    return Path(out["raw_snapshot_archive_path"]), out["raw_snapshot_archive_sha256"]


def mutate_zip(directory, path, *, replacement_csv=None, mutate_receipt=None,
               extra=None, compressed=False):
    with ZipFile(path) as original:
        raw = original.read("response.csv")
        receipt = json.loads(original.read("observation_receipt.json"))
    if replacement_csv is not None:
        raw = replacement_csv
    if mutate_receipt is not None:
        mutate_receipt(receipt)
    other = Path(directory) / "repacked.zip"
    with ZipFile(other, "w", compression=ZIP_DEFLATED if compressed else ZIP_STORED) as z:
        z.writestr("response.csv", raw)
        z.writestr("observation_receipt.json", json.dumps(receipt))
        if extra is not None:
            z.writestr(extra, b"unexpected")
    return other, sha256(other.read_bytes()).hexdigest()


class ArchiveReplayTests(unittest.TestCase):
    def test_valid_ecb_replay_is_integrity_only(self):
        with TemporaryDirectory() as d:
            path, digest = create_zip(d)
            out = verify(path, expected_zip_sha256=digest, evaluated_at_utc=NOW)
            self.assertEqual(out["state"],
                             "LAB_ARCHIVE_INTERNAL_INTEGRITY_REPLAYED_QUARANTINED")
            self.assertTrue(out["archive_sha256_matched"])
            self.assertTrue(out["raw_response_sha256_matched"])
            self.assertTrue(out["replay_parser_consistent"])
            self.assertTrue(out["parser_accepted"])
            self.assertFalse(out["source_origin_independently_authenticated"])
            self.assertFalse(out["publication_instant_independently_verified"])
            self.assertFalse(out["trade_authorized"])
            self.assertEqual(out["operational_bias"], "AGUARDAR")

    def test_valid_fed_replay_with_no_fx_bias(self):
        with TemporaryDirectory() as d:
            path, digest = create_zip(d, "FED_USD_TARGET_RANGE_EFFECTIVE", FED)
            out = verify(path, expected_zip_sha256=digest, evaluated_at_utc=NOW)
            self.assertEqual(out["source_id"], "FED_USD_TARGET_RANGE_EFFECTIVE")
            self.assertTrue(out["replay_parser_consistent"])
            self.assertIsNone(out["fx_bias"])
            self.assertFalse(out["can_feed_live_radar"])

    def test_invalid_source_csv_replays_as_invalid_not_approved(self):
        with TemporaryDirectory() as d:
            path, digest = create_zip(d, raw=b"not,a,policy,rate\n")
            out = verify(path, expected_zip_sha256=digest, evaluated_at_utc=NOW)
            self.assertTrue(out["archive_sha256_matched"])
            self.assertFalse(out["parser_accepted"])
            self.assertEqual(out["parser_state"], "LAB_BLOCKED")
            self.assertFalse(out["trade_authorized"])

    def test_hash_required_and_single_byte_mutation_rejected(self):
        with TemporaryDirectory() as d:
            path, digest = create_zip(d)
            for invalid in (None, "", "x" * 64, digest.upper(), digest[:-1]):
                with self.subTest(invalid=invalid):
                    self.assertEqual(verify(path, expected_zip_sha256=invalid,
                                            evaluated_at_utc=NOW)["state"],
                                     "LAB_ARCHIVE_VERIFY_BLOCKED")
            path.write_bytes(path.read_bytes() + b"x")
            self.assertEqual(verify(path, expected_zip_sha256=digest,
                                    evaluated_at_utc=NOW)["reason"],
                             "ARCHIVE_EXTERNAL_SHA256_MISMATCH")

    def test_repacked_csv_even_with_new_hash_cannot_fake_old_receipt(self):
        with TemporaryDirectory() as d:
            path, _ = create_zip(d)
            repacked, digest = mutate_zip(d, path,
                                          replacement_csv=ECB.replace(b"2.0000000", b"9.0000000"))
            out = verify(repacked, expected_zip_sha256=digest, evaluated_at_utc=NOW)
            self.assertEqual(out["reason"], "ZIP_RECEIPT_IDENTITY_OR_FLAGS_MISMATCH")

    def test_forged_parser_receipt_rejected_even_when_new_zip_hash_matches(self):
        with TemporaryDirectory() as d:
            path, _ = create_zip(d)
            repacked, digest = mutate_zip(
                d, path, mutate_receipt=lambda x: x["parser_receipt"].update(
                    {"rate_percent": "25.00"}))
            out = verify(repacked, expected_zip_sha256=digest, evaluated_at_utc=NOW)
            self.assertEqual(out["reason"], "ZIP_PARSER_REPLAY_MISMATCH")

    def test_forged_trade_permission_and_url_rejected(self):
        for mutate in (
            lambda x: x.update({"trade_authorized": True}),
            lambda x: x.update({"requested_url": "https://evil.example/"}),
            lambda x: x.update({"source_id": "OTHER"}),
            lambda x: x.update({"external_http_requests": 0}),
        ):
            with self.subTest(mutate=mutate), TemporaryDirectory() as d:
                path, _ = create_zip(d)
                repacked, digest = mutate_zip(d, path, mutate_receipt=mutate)
                out = verify(repacked, expected_zip_sha256=digest, evaluated_at_utc=NOW)
                self.assertEqual(out["state"], "LAB_ARCHIVE_VERIFY_BLOCKED")

    def test_future_clock_and_naive_evaluation_rejected(self):
        with TemporaryDirectory() as d:
            path, digest = create_zip(d)
            with self.assertRaises(ValueError):
                verify(path, expected_zip_sha256=digest,
                       evaluated_at_utc=NOW.replace(tzinfo=None))
            repacked, digest2 = mutate_zip(
                d, path, mutate_receipt=lambda x: x.update({
                    "observed_at_local_system_utc": (NOW + timedelta(days=3)).isoformat()}))
            self.assertEqual(verify(repacked, expected_zip_sha256=digest2,
                                    evaluated_at_utc=NOW)["reason"],
                             "ZIP_COLLECTION_CLOCK_INVALID_OR_FUTURE")

    def test_zip_extra_or_compressed_member_rejected(self):
        for extra, compressed in (("../trick", False), (None, True)):
            with self.subTest(extra=extra, compressed=compressed), TemporaryDirectory() as d:
                path, _ = create_zip(d)
                repacked, digest = mutate_zip(d, path, extra=extra, compressed=compressed)
                self.assertEqual(verify(repacked, expected_zip_sha256=digest,
                                        evaluated_at_utc=NOW)["reason"],
                                 "ZIP_ENTRIES_OR_COMPRESSION_INVALID")

    def test_missing_or_huge_zip_is_blocked(self):
        with TemporaryDirectory() as d:
            missing = Path(d) / "not-found.zip"
            out = verify(missing, expected_zip_sha256="0" * 64, evaluated_at_utc=NOW)
            self.assertEqual(out["state"], "LAB_ARCHIVE_VERIFY_BLOCKED")
            huge = Path(d) / "huge.zip"
            huge.write_bytes(b"x" * (1024 * 1024 + 1))
            out = verify(huge, expected_zip_sha256=sha256(huge.read_bytes()).hexdigest(),
                         evaluated_at_utc=NOW)
            self.assertEqual(out["reason"], "ARCHIVE_NOT_REGULAR_BOUNDED_FILE")

    def test_cli_replay_is_read_only_and_no_http(self):
        with TemporaryDirectory() as d:
            path, digest = create_zip(d)
            before = path.read_bytes()
            stdout = StringIO()
            with patch.object(capture, "build_opener") as opening:
                with redirect_stdout(stdout):
                    code = main(["--archive", str(path), "--expected-sha256", digest])
                opening.assert_not_called()
            self.assertEqual(code, 0)
            self.assertEqual(path.read_bytes(), before)
            self.assertFalse(json.loads(stdout.getvalue())["trade_authorized"])


if __name__ == "__main__":
    unittest.main()
