"""Contract tests of local-only Copom readiness CLI, with fictitious CSV.

All dates in sample CSV files after Nov3 are TEST FIXTURES, not B3 trades.
"""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest

from atlasquant_trader_copom_readiness_cli_lab import (
    PRE_EVENT_SNAPSHOT, run_copom_readiness_cli_lab as main,
)

NOW = "2026-11-03T20:30:00Z"
POST = "2026-11-05T13:00:00Z"

CSV_HEADER = ("instrument,contract_id,session_role,quote_type,"
              "observed_at_utc,price_points\n")
SYNTHETIC_CSV = (CSV_HEADER +
                 "WIN,SIM_WIN_FAKE_SINGLE_EXPIRY,PRE_20261104,"
                 "SIMULATED_REGULAR_TRADE_TICK,2026-11-04T21:24:00Z,160000\n"
                 "WIN,SIM_WIN_FAKE_SINGLE_EXPIRY,POST_20261105,"
                 "SIMULATED_REGULAR_TRADE_TICK,2026-11-05T12:03:00Z,162000\n"
                 ).encode("utf-8")


def synthetic_manifest(content=SYNTHETIC_CSV, *, synthetic=True):
    return {
        "schema": "ATLASQUANT_TRADER_B3_OFFLINE_USER_EXPORT_INTAKE_LAB_V1",
        "declared_collection_method": (
            "SYNTHETIC_FIXTURE" if synthetic
            else "USER_MANUAL_EXPORT_UNVERIFIED"),
        "declared_origin_label": (
            "SYNTHETIC LOCAL TEST" if synthetic
            else "USER FILE UNVERIFIED"),
        "declared_source_reference": "USER_NOTE:test-fixture-not-real-data",
        "declared_rights_status": "NOT_INDEPENDENTLY_REVIEWED",
        "collection_was_automated": False,
        "csv_sha256": sha256(content).hexdigest(),
        "fixture_mode": synthetic,
    }


def invoke(*args):
    stdout, stderr = StringIO(), StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        rc = main(list(args))
    return rc, stdout.getvalue(), stderr.getvalue()


class CopomReadinessCliLabTests(unittest.TestCase):
    def test_cli_uses_actual_frozen_snapshot_not_a_new_copy(self):
        self.assertEqual(PRE_EVENT_SNAPSHOT.name,
                         "TRADER_COPOM_20261104_FROZEN_PRE_EVENT_20261103.json")
        self.assertTrue(PRE_EVENT_SNAPSHOT.is_file())

    def test_text_pre_event_status_readable_and_no_trading(self):
        rc, out, err = invoke("--as-of", NOW)
        self.assertEqual(rc, 0, err)
        self.assertEqual(err, "")
        self.assertIn("COPOM | CONSULTA LAB / HARD NO-GO", out)
        self.assertIn("LAB_COPOM_EVIDENCE_INCOMPLETE", out)
        self.assertIn("Resultado oficial Copom: NO_AUTHENTICATED_RESULT", out)
        self.assertIn("Viés para negociação: AGUARDAR", out)
        self.assertIn("Pendências independentes (7)", out)

    def test_json_is_machine_readable_but_self_declared_clock(self):
        rc, out, err = invoke("--as-of", NOW, "--format", "json")
        self.assertEqual(rc, 0, err)
        data = json.loads(out)
        self.assertEqual(data["mode"], "LAB_HARD_NO_GO")
        self.assertEqual(data["declared_clock_utc_unattested"], NOW)
        self.assertFalse(data["wall_clock_independently_verified"])
        r = data["report"]
        self.assertTrue(r["pre_event_source_content_matches_original"])
        self.assertEqual(len(r["audit_rows"]), 4)
        self.assertFalse(r["can_feed_live_radar"])
        self.assertFalse(r["trade_authorized"])

    def test_after_decision_calendar_still_pending_without_source(self):
        rc, out, err = invoke("--as-of", POST, "--format", "json")
        self.assertEqual(rc, 0, err)
        data = json.loads(out)["report"]
        self.assertEqual(data["decision_status"], "NO_AUTHENTICATED_RESULT")
        self.assertEqual(data["quote_status"], "NO_AUTHENTICATED_PRICE_DATA")
        self.assertFalse(data["market_session_gap_verified"])

    def test_before_research_cutoff_is_refused(self):
        rc, out, err = invoke("--as-of", "2026-11-02T20:30:00Z")
        self.assertEqual(rc, 2)
        self.assertIn("LAB_COPOM_EVIDENCE_REFUSED", out)

    def test_non_utc_offset_and_naive_clock_denied(self):
        for bad in ("2026-11-03T16:30:00-04:00",
                    "2026-11-03T20:30:00",
                    "2026-11-03", "now", "2026-13-01T12:00:00Z"):
            with self.subTest(value=bad):
                rc, out, err = invoke("--as-of", bad)
                self.assertEqual(rc, 2)
                self.assertEqual(out, "")
                self.assertIn("CONSULTA RECUSADA", err)

    def test_missing_csv_or_manifest_pair_is_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "sample.csv"
            p.write_bytes(SYNTHETIC_CSV)
            rc, _, err = invoke("--as-of", POST, "--csv", str(p))
            self.assertEqual(rc, 2)
            self.assertIn("devem ser fornecidos juntos", err)

    def test_synthetic_csv_with_manifest_is_labeled_unverified(self):
        with tempfile.TemporaryDirectory() as t:
            csvfile = Path(t) / "synthetic.csv"
            info = Path(t) / "manifest.json"
            csvfile.write_bytes(SYNTHETIC_CSV)
            info.write_text(json.dumps(synthetic_manifest()), encoding="utf-8")
            rc, out, err = invoke(
                "--as-of", POST, "--csv", str(csvfile),
                "--manifest", str(info), "--format", "json")
            self.assertEqual(rc, 0, err)
            r = json.loads(out)["report"]
            self.assertEqual(r["state"], "LAB_COPOM_EVIDENCE_CANDIDATES_ONLY")
            self.assertEqual(r["quote_status"], "SYNTHETIC_TEST_ONLY")
            self.assertFalse(r["b3_quotes_and_licensing_independently_verified"])
            self.assertFalse(r["market_session_gap_verified"])

    def test_fake_future_prices_denied_when_asof_pre_event(self):
        with tempfile.TemporaryDirectory() as t:
            csvfile = Path(t) / "synthetic.csv"
            m = Path(t) / "manifest.json"
            csvfile.write_bytes(SYNTHETIC_CSV)
            m.write_text(json.dumps(synthetic_manifest()), encoding="utf-8")
            rc, out, err = invoke(
                "--as-of", NOW, "--csv", str(csvfile),
                "--manifest", str(m), "--format", "json")
            self.assertEqual(rc, 2, err)
            self.assertEqual(json.loads(out)["report"]["state"],
                             "LAB_COPOM_EVIDENCE_REFUSED")

    def test_corrupt_or_missing_files_denied_without_traceback(self):
        with tempfile.TemporaryDirectory() as t:
            nonexistent = Path(t) / "not-found.csv"
            info = Path(t) / "manifest.json"
            info.write_text("{}", encoding="utf-8")
            rc, out, err = invoke(
                "--as-of", POST, "--csv", str(nonexistent), "--manifest", str(info))
            self.assertEqual(rc, 2)
            self.assertIn("CONSULTA RECUSADA", err)
            self.assertNotIn("Traceback", err)

    def test_duplicate_manifest_keys_refused_instead_of_overwritten(self):
        with tempfile.TemporaryDirectory() as t:
            csvfile = Path(t) / "synthetic.csv"
            manifest = Path(t) / "manifest.json"
            csvfile.write_bytes(SYNTHETIC_CSV)
            manifest.write_text('{"schema":"a","schema":"b"}', encoding="utf-8")
            rc, out, err = invoke("--as-of", POST,
                                  "--csv", str(csvfile), "--manifest", str(manifest))
            self.assertEqual(rc, 2)
            self.assertIn("Chave repetida", err)

    def test_json_manifest_invalid_or_wrong_sha_denied(self):
        with tempfile.TemporaryDirectory() as t:
            csvfile = Path(t) / "synthetic.csv"
            info = Path(t) / "manifest.json"
            csvfile.write_bytes(SYNTHETIC_CSV)
            info.write_text("not json", encoding="utf-8")
            rc, out, err = invoke("--as-of", POST, "--csv", str(csvfile), "--manifest", str(info))
            self.assertEqual(rc, 2)
            self.assertIn("CONSULTA RECUSADA", err)
            m = synthetic_manifest()
            m["csv_sha256"] = "0" * 64
            info.write_text(json.dumps(m), encoding="utf-8")
            rc, out, err = invoke("--as-of", POST, "--csv", str(csvfile),
                                  "--manifest", str(info), "--format", "json")
            self.assertEqual(rc, 2, err)
            self.assertEqual(json.loads(out)["report"]["state"],
                             "LAB_COPOM_EVIDENCE_REFUSED")

    def test_oversized_csv_or_manifest_denied(self):
        with tempfile.TemporaryDirectory() as t:
            csvfile = Path(t) / "big.csv"
            info = Path(t) / "manifest.json"
            csvfile.write_bytes(b"x"*5000)
            info.write_text(json.dumps(synthetic_manifest()), encoding="utf-8")
            rc, out, err = invoke("--as-of", POST, "--csv", str(csvfile), "--manifest", str(info))
            self.assertEqual(rc, 2)
            self.assertIn("acima do limite", err)
            csvfile.write_bytes(SYNTHETIC_CSV)
            info.write_bytes(b"{" + b"x"*5000 + b"}")
            rc, out, err = invoke("--as-of", POST, "--csv", str(csvfile), "--manifest", str(info))
            self.assertEqual(rc, 2)
            self.assertIn("acima do limite", err)

    def test_no_raw_prices_leak_in_text_readout(self):
        with tempfile.TemporaryDirectory() as t:
            csvfile=Path(t)/"sample.csv"
            info=Path(t)/"manifest.json"
            csvfile.write_bytes(SYNTHETIC_CSV)
            info.write_text(json.dumps(synthetic_manifest()), encoding="utf-8")
            rc, out, err = invoke("--as-of", POST, "--csv", str(csvfile), "--manifest", str(info))
            self.assertEqual(rc, 0, err)
            self.assertNotIn("160000", out)
            self.assertNotIn("162000", out)
            self.assertNotIn("synthetic.csv", out)
            self.assertNotIn("USER_NOTE", out)
            self.assertIn("AGUARDAR", out)

    def test_manual_export_claim_does_not_promote_source_rights(self):
        manual = SYNTHETIC_CSV.replace(
            b"SIM_WIN_FAKE_SINGLE_EXPIRY", b"WINZ26").replace(
            b"SIMULATED_REGULAR_TRADE_TICK",
            b"PROVIDER_DECLARED_EXECUTED_TRADE_UNVERIFIED")
        with tempfile.TemporaryDirectory() as t:
            csvfile=Path(t)/"declared.csv"
            info=Path(t)/"manifest.json"
            csvfile.write_bytes(manual)
            info.write_text(json.dumps(synthetic_manifest(manual, synthetic=False)),
                            encoding="utf-8")
            rc, out, err=invoke("--as-of", POST, "--csv", str(csvfile),
                                "--manifest", str(info), "--format", "json")
            self.assertEqual(rc, 0, err)
            r=json.loads(out)["report"]
            self.assertEqual(r["quote_status"],"MANUAL_EXPORT_CANDIDATE_UNATTESTED")
            self.assertFalse(r["b3_quotes_and_licensing_independently_verified"])
            self.assertFalse(r["can_feed_real_oos"])

    def test_cli_with_invalid_date_does_not_create_output_files(self):
        with tempfile.TemporaryDirectory() as t:
            before = list(Path(t).iterdir())
            rc, out, err = invoke("--as-of", "invalid")
            self.assertEqual(rc, 2)
            self.assertEqual(before, list(Path(t).iterdir()))


if __name__ == "__main__":
    unittest.main()
