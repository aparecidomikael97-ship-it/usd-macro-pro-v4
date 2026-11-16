"""Adversarial synthetic rosters: no real direction, model or GH posting."""
from __future__ import annotations

from datetime import datetime, timezone
from tempfile import TemporaryDirectory
from pathlib import Path
from hashlib import sha256
from copy import deepcopy
import json
import unittest

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_fx28_precommit_roster_archive_lab import (
    INPUT_SCHEMA, SCHEMA, archive_explicit_roster_lab, verify_roster_archive_lab,
    _load_input, MAX_INPUT_BYTES,
)

UTC = timezone.utc
NOW = datetime(2026, 11, 15, 12, tzinfo=UTC)
PREWINDOW = datetime(2026, 11, 15, 10, tzinfo=UTC)
OPEN = datetime(2026, 11, 15, 22, tzinfo=UTC)


def fixture(*, horizon="D1", direction="ABSTAIN"):
    end = "2026-11-16T22:00:00Z" if horizon == "D1" else "2026-11-20T22:00:00Z"
    return {
        "schema": INPUT_SCHEMA, "horizon": horizon,
        "start_utc": "2026-11-15T22:00:00Z", "end_utc": end,
        "forecast_roster": [{
            "pair": pair, "direction": direction,
            "abstain_reason": "UNVERIFIED_SOURCE" if direction == "ABSTAIN" else None,
            "feature_cutoff_utc": "2026-11-15T10:30:00Z",
            "forecast_issued_utc": "2026-11-15T11:00:00Z",
            "model_sha256_claim": "a" * 64,
            "evidence_sha256_claim": "b" * 64,
        } for pair in OFFICIAL_PAIRS],
    }


def encode(doc):
    return json.dumps(doc, separators=(",", ":"), sort_keys=True).encode("utf-8")


class ExplicitRosterArchiveTests(unittest.TestCase):
    def run_archive(self, doc, root, *, at=NOW):
        return archive_explicit_roster_lab(
            raw_input=encode(doc) if isinstance(doc, dict) else doc,
            output_root=root, inspected_at_utc=at)

    def safe(self, result):
        for k in ("external_prewindow_witness_posted",
                  "forecast_original_issued_at_authenticated",
                  "model_source_evidence_authenticated", "broker_prices_read",
                  "publishable", "trade_authorized", "worker_enabled"):
            self.assertFalse(result[k],k)
        self.assertEqual(result["operational_bias"],"AGUARDAR")
        self.assertIsNone(result["validated_accuracy"])

    def test_01_28_original_claims_archived_and_canonical_reverified(self):
        with TemporaryDirectory() as folder:
            root = Path(folder) / "writeonce"
            report=self.run_archive(fixture(),root)
            self.safe(report)
            self.assertEqual(report["schema"],SCHEMA)
            self.assertEqual(report["pairs_supplied"],28)
            self.assertEqual(report["state"],
                             "LAB_FX28_CANONICAL_ROSTER_ARCHIVED_NOT_POSTED_NO_GO")
            archive=Path(report["archive_dir"])
            self.assertEqual(sorted(x.name for x in archive.iterdir()),sorted([
                "original_input.json","canonical_forecasts.json",
                "witness_body_NOT_POSTED.txt","receipt.json"]))
            self.assertEqual(sha256((archive/"canonical_forecasts.json").read_bytes()).hexdigest(),
                             report["roster_sha256"])
            verified=verify_roster_archive_lab(archive)
            self.assertEqual(verified["pairs_reconciled"],28)
            self.assertEqual(verified["manifest_sha256"],report["manifest_sha256"])
            self.assertFalse(verified["github_first_seen_verified"])
            self.assertFalse(verified["trade_authorized"])

    def test_02_writeonce_never_overwrites_same_roster(self):
        with TemporaryDirectory() as folder:
            root=Path(folder)/"archives"
            doc=fixture()
            first=self.run_archive(doc,root)
            second=self.run_archive(doc,root)
            self.assertEqual(second["reason"],"CANONICAL_ROSTER_ALREADY_ARCHIVED_NO_OVERWRITE")
            self.safe(second)
            self.assertEqual(len(list(root.iterdir())),1)
            self.assertEqual(verify_roster_archive_lab(Path(first["archive_dir"]))["pairs_reconciled"],28)

    def test_03_too_early_or_at_start_blocks_without_files(self):
        for now in (datetime(2026,11,15,9,59,59,tzinfo=UTC),OPEN,
                    datetime(2026,11,16,1,tzinfo=UTC)):
            with self.subTest(now=now), TemporaryDirectory() as folder:
                root=Path(folder)/"archives"
                r=self.run_archive(fixture(),root,at=now)
                self.safe(r)
                self.assertEqual(r["state"],"LAB_PREWINDOW_ROSTER_ARCHIVE_BLOCKED_NO_GO")
                self.assertFalse(root.exists())

    def test_04_wrong_window_and_27_or_duplicate_forecasts_blocked(self):
        bad=[]
        d=fixture();d["end_utc"]="2026-11-17T22:00:00Z";bad.append(d)
        d=fixture();d["forecast_roster"].pop();bad.append(d)
        d=fixture();d["forecast_roster"][3]["pair"]=OFFICIAL_PAIRS[2];bad.append(d)
        for d in bad:
            with TemporaryDirectory() as folder:
                root=Path(folder)/"archives"
                r=self.run_archive(d,root)
                self.safe(r)
                self.assertFalse(root.exists())

    def test_05_invalid_issued_feature_cutoff_or_unattested_digest_blocks(self):
        bad=[]
        d=fixture();d["forecast_roster"][0]["forecast_issued_utc"]="2026-11-15T22:00:00Z";bad.append(d)
        d=fixture();d["forecast_roster"][0]["forecast_issued_utc"]="2026-11-15T09:59:59Z";bad.append(d)
        d=fixture();d["forecast_roster"][0]["feature_cutoff_utc"]="2026-11-15T09:59:59Z";bad.append(d)
        d=fixture();d["forecast_roster"][0]["feature_cutoff_utc"]="2026-11-15T11:15:00Z";bad.append(d)
        d=fixture();d["forecast_roster"][0]["evidence_sha256_claim"]="0"*64;bad.append(d)
        d=fixture();d["forecast_roster"][0]["model_sha256_claim"]="AAAA";bad.append(d)
        for i,d in enumerate(bad):
            with self.subTest(i=i),TemporaryDirectory() as folder:
                root=Path(folder)/"archives"
                r=self.run_archive(d,root)
                self.safe(r)
                self.assertEqual(r["state"],"LAB_PREWINDOW_ROSTER_ARCHIVE_BLOCKED_NO_GO")
                self.assertFalse(root.exists())

    def test_06_reject_direction_without_evidence_and_wrong_abstain_reason(self):
        d=fixture(direction="UP");d["forecast_roster"][0]["abstain_reason"]="LOW_CONFIDENCE"
        with TemporaryDirectory() as folder:
            self.assertEqual(self.run_archive(d,Path(folder)/"a")["state"],
                             "LAB_PREWINDOW_ROSTER_ARCHIVE_BLOCKED_NO_GO")
        d=fixture();d["forecast_roster"][0]["abstain_reason"]="THIS_IS_NOT_ALLOWED"
        with TemporaryDirectory() as folder:
            self.assertEqual(self.run_archive(d,Path(folder)/"a")["state"],
                             "LAB_PREWINDOW_ROSTER_ARCHIVE_BLOCKED_NO_GO")

    def test_07_w1_is_distinct_and_never_reuses_d1_hash(self):
        with TemporaryDirectory() as folder:
            root=Path(folder)/"archives"
            d1=self.run_archive(fixture(horizon="D1"),root)
            w1=self.run_archive(fixture(horizon="W1"),root)
            self.assertEqual(d1["pairs_supplied"],28)
            self.assertEqual(w1["pairs_supplied"],28)
            self.assertNotEqual(d1["roster_sha256"],w1["roster_sha256"])
            self.assertEqual(verify_roster_archive_lab(Path(w1["archive_dir"]))["horizon"],"W1")

    def test_08_changes_in_any_direction_change_digest(self):
        with TemporaryDirectory() as folder:
            root=Path(folder)/"archives"
            first=self.run_archive(fixture(),root)
            d=fixture()
            d["forecast_roster"][0]["direction"]="UP"
            d["forecast_roster"][0]["abstain_reason"]=None
            second=self.run_archive(d,root)
            self.assertEqual(second["pairs_supplied"],28)
            self.assertNotEqual(first["roster_sha256"],second["roster_sha256"])

    def test_09_reject_duplicate_json_keys_and_nonfinite(self):
        with TemporaryDirectory() as folder:
            root=Path(folder)/"archives"
            bad=(b'{"schema": "x","schema":"x"}',
                 encode(fixture())+b' NaN',
                 b'0'* (MAX_INPUT_BYTES + 1))
            for raw in bad:
                r=self.run_archive(raw,root)
                self.safe(r)
                self.assertEqual(r["state"],"LAB_PREWINDOW_ROSTER_ARCHIVE_BLOCKED_NO_GO")
            self.assertFalse(root.exists())

    def test_10_reject_extra_key_naive_clock_and_unknown_horizon(self):
        ds=[]
        d=fixture();d["extra"]="bad";ds.append(d)
        d=fixture();d["horizon"]="M15";ds.append(d)
        d=fixture();d["forecast_roster"][0]["extra"]="bad";ds.append(d)
        d=fixture();d["forecast_roster"][0]["forecast_issued_utc"]="2026-11-15T11:00:00+00:00";ds.append(d)
        d=fixture();d["forecast_roster"][0]["forecast_issued_utc"]=True;ds.append(d)
        for doc in ds:
            with TemporaryDirectory() as folder:
                root=Path(folder)/"archives"
                r=self.run_archive(doc,root)
                self.safe(r)
                self.assertEqual(r["state"],"LAB_PREWINDOW_ROSTER_ARCHIVE_BLOCKED_NO_GO")

    def test_11_tamper_canonical_or_witness_body_invalidates_receipt(self):
        for name in ("canonical_forecasts.json","witness_body_NOT_POSTED.txt","original_input.json"):
            with self.subTest(name=name),TemporaryDirectory() as folder:
                r=self.run_archive(fixture(),Path(folder)/"archives")
                f=Path(r["archive_dir"])/name
                f.write_bytes(f.read_bytes()+b"X")
                with self.assertRaises(ValueError):
                    verify_roster_archive_lab(Path(r["archive_dir"]))

    def test_12_receipt_spoofed_external_verification_is_blocked(self):
        with TemporaryDirectory() as folder:
            r=self.run_archive(fixture(),Path(folder)/"archives")
            file=Path(r["archive_dir"])/"receipt.json"
            data=json.loads(file.read_text())
            data["external_comment_posted"]=True
            file.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,"ROSTER_RECEIPT_OR_SHA_MISMATCH"):
                verify_roster_archive_lab(Path(r["archive_dir"]))

    def test_13_prewindow_exact_boundary_requires_legitimate_timestamps(self):
        doc=fixture()
        for row in doc["forecast_roster"]:
            row["feature_cutoff_utc"]="2026-11-15T10:00:00Z"
            row["forecast_issued_utc"]="2026-11-15T10:00:00Z"
        with TemporaryDirectory() as folder:
            r=self.run_archive(doc,Path(folder)/"archives",at=PREWINDOW)
            self.assertEqual(r["pairs_supplied"],28)
            self.assertTrue(Path(r["archive_dir"]).is_dir())
            self.assertIsNone(r["validated_accuracy"])

    def test_14_missing_input_never_fabricates_forecasts(self):
        with TemporaryDirectory() as folder:
            root=Path(folder)/"archives"
            for raw in (b"",b"[]",None,[],fixture()["forecast_roster"]):
                r=self.run_archive(raw,root)
                self.safe(r)
                self.assertEqual(r["pairs_supplied"],0)
            self.assertFalse(root.exists())


    def test_15_receipt_semantic_window_metadata_tampering_rejected(self):
        for key, value in (
            ("horizon","W1"),
            ("start_utc","2026-11-22T22:00:00+00:00"),
            ("end_utc","2026-11-20T22:00:00+00:00"),
            ("research_only",False),
            ("model_prediction_accuracy",1.0),
            ("input_schema","UNKNOWN"),
        ):
            with self.subTest(key=key),TemporaryDirectory() as folder:
                report=self.run_archive(fixture(),Path(folder)/"archives")
                archive=Path(report["archive_dir"])
                receipt=archive/"receipt.json"
                data=json.loads(receipt.read_text(encoding="utf-8"))
                data[key]=value
                receipt.write_text(json.dumps(data),encoding="utf-8")
                with self.assertRaisesRegex(ValueError,
                                            "RECEIPT_CAMPAIGN_WINDOW_METADATA_MISMATCH"):
                    verify_roster_archive_lab(archive)


if __name__ == "__main__":
    unittest.main()
