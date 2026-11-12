"""Synthetic archive custody for the three frozen US PPI-day official schedules."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from atlasquant_trader_ppi_official_schedule_archive_lab import (
    PINNED_SOURCES, inspect_ppi_three_official_schedule_files_lab as inspect,
)
from atlasquant_trader_ppi_usd_fx_forward_reaction_lab import (
    EVENT_UTC, LAST_REQUIRED_CLOSE_UTC,
)

CAPTURE = datetime(2026, 11, 12, 0, 34, 32, 488940, tzinfo=timezone.utc)
OBSERVE = LAST_REQUIRED_CLOSE_UTC + timedelta(minutes=15)
RAW = {
    "EIA_NATGAS_HOLIDAY": (
        b"<html><body><table><tr><td>November 13, 2026</td>"
        b"<td>Friday</td><td>10:30 a.m.</td><td>Veterans Day</td>"
        b"</tr></table></body></html>"
    ),
    "FED_BOARD_NOVEMBER": (
        b"<html><body>10:50 a.m. Discussion - Vice Chair for Supervision "
        b"Michelle W. Bowman Supervision and Regulation at meeting 13</body></html>"
    ),
    "SF_FED_DALY_UNLV": (
        b"<html><body>A Conversation with Mary C. Daly Friday, Nov 13, 2026 "
        b"Time 9:00 a.m. PT at UNLV</body></html>"
    ),
}


def synthetic_official_archive(root: Path):
    """Synthetic ONLY: return local fixture source pins, manifest, and records."""
    pins = deepcopy(PINNED_SOURCES)
    sources = [{
        "source_id": "BLS_NOVEMBER",
        "url": "https://www.bls.gov/schedule/2026/11_sched_list.htm",
        "status": "DOWNLOAD_EXCEPTION_HTTPError",
        "source_bytes_saved_locally": False,
        "sha256_original_bytes": None,
    }]
    for key, cfg in pins.items():
        raw = RAW[key]
        cfg["sha"] = sha256(raw).hexdigest()
        (root / (key + ".html")).write_bytes(raw)
        sources.append({
            "source_id": key, "url": cfg["url"], "final_url": cfg["url"],
            "http_status": 200,
            "status": "ORIGINAL_BYTES_FROZEN_LOCAL_DOCUMENTARY",
            "source_bytes_saved_locally": True,
            "sha256_original_bytes": cfg["sha"],
            "captured_at_utc_local_clock_claim": CAPTURE.isoformat(),
            "raw_file_name": key + ".html", "raw_byte_size": len(raw),
        })
    manifest = {
        "schema": "ATLASQUANT_US_PPI_OFFICIAL_COMPETING_CALENDAR_CUSTODY_LAB_V1",
        "local_clock_pre_event_claim_not_third_party_attested": True,
        "whole_market_calendar_completeness_verified": False,
        "operational_bias": "AGUARDAR", "trade_authorized": False,
        "publishable": False, "sources": sources,
    }
    (root / "OFFICIAL_SCHEDULE_SOURCE_MANIFEST.json").write_text(
        json.dumps(manifest), encoding="utf-8")
    return pins, manifest


class OfficialCalendarArchiveTests(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.pins, self.manifest = synthetic_official_archive(self.root)
        self.source_manifest = self.manifest["sources"]

    def write_manifest(self):
        (self.root / "OFFICIAL_SCHEDULE_SOURCE_MANIFEST.json").write_text(
            json.dumps(self.manifest), encoding="utf-8")

    def run_lab(self, root=None, now=OBSERVE):
        with patch.dict(PINNED_SOURCES, self.pins, clear=True):
            row = inspect(archive_root=self.root if root is None else root,
                          as_of_utc=now)
        self.assertEqual(row["operational_bias"], "AGUARDAR")
        self.assertFalse(row["trade_authorized"])
        self.assertFalse(row["publishable"])
        self.assertFalse(row["complete_forex_or_geopolitical_calendar_proven"])
        self.assertFalse(row["independently_attested_publication_clock"])
        self.assertTrue(row["documentary_schedule_and_event_effect_not_causal"])
        self.assertTrue(row["bls_schedule_file_not_locally_captured"])
        self.assertIsNone(row["validated_accuracy"])
        self.assertIsNone(row["directional_bias"])
        self.assertEqual((row["http_requests"], row["file_writes"], row["new_cost_brl"]),
                         (0, 0, 0))
        return row

    def test_three_source_original_bytes_hashes_match_and_inform_h4_only(self):
        result = self.run_lab()
        self.assertEqual(result["state"],
                         "LAB_PPI_THREE_OFFICIAL_SCHEDULES_LOCAL_SHA_MATCH_NO_GO")
        self.assertEqual(result["files_with_pinned_original_sha"], 3)
        self.assertEqual(result["primary_source_partial_schedule_count"], 3)
        audit = result["competing_window_audit"]
        self.assertEqual(audit["state"],
                         "LAB_PPI_PARTIAL_COMPETING_ROOTS_DOCUMENTARY_REVIEW_REQUIRED")
        self.assertEqual(audit["candidate_competing_root_count_documentary"], 3)
        self.assertFalse(audit["calendar_period_claims_complete_unattested"])
        self.assertEqual(audit["candidate_competing_roots_by_reaction_window"]["M15"], [])
        self.assertEqual(audit["candidate_competing_roots_by_reaction_window"]["H1"], [])
        self.assertEqual(audit["candidate_baseline_contamination_roots_documentary"], [])
        self.assertEqual(len(audit["candidate_competing_roots_by_reaction_window"]["H4"]), 3)
        self.assertFalse(audit["causal_isolation_of_ppi_verified"])
        claim = result["calendar_claim"]
        self.assertFalse(claim.claims_complete_for_covered_period)
        self.assertEqual(claim.captured_at_utc, CAPTURE)
        self.assertEqual(len(claim.events), 3)

    def test_local_realistic_subsecond_capture_receipt_does_not_fail(self):
        result = self.run_lab(now=OBSERVE.replace(microsecond=123456))
        self.assertEqual(
            result["state"],
            "LAB_PPI_THREE_OFFICIAL_SCHEDULES_LOCAL_SHA_MATCH_NO_GO")
        self.assertTrue(result["latest_captured_at_utc_local_clock_claim"]
                        .endswith("488940+00:00"))

    def test_tampered_page_rejected_against_pinned_sha(self):
        file = self.root / "EIA_NATGAS_HOLIDAY.html"
        file.write_bytes(file.read_bytes()+b" ")
        self.assertEqual(self.run_lab()["reason"],
                         "ORIGINAL_SOURCE_BYTES_DIFFER_FROM_PINNED_SHA256")

    def test_wrong_official_schedule_time_text_rejected_even_if_hash_changed(self):
        file = self.root / "EIA_NATGAS_HOLIDAY.html"
        data = file.read_bytes().replace(b"10:30 a.m.", b"11:30 a.m.")
        file.write_bytes(data)
        self.pins["EIA_NATGAS_HOLIDAY"]["sha"] = sha256(data).hexdigest()
        self.source_manifest[1]["sha256_original_bytes"] = sha256(data).hexdigest()
        self.source_manifest[1]["raw_byte_size"] = len(data)
        self.write_manifest()
        self.assertEqual(self.run_lab()["reason"],
                         "ISSUER_SCHEDULE_DATE_TIME_CONTEXT_MISSING")

    def test_post_release_capture_cannot_be_pre_event_receipt(self):
        self.source_manifest[1]["captured_at_utc_local_clock_claim"] = (
            EVENT_UTC+timedelta(seconds=1)).isoformat()
        self.write_manifest()
        self.assertEqual(self.run_lab()["reason"],
                         "SOURCE_OR_CAPTURE_CLOCK_NOT_MATCHING_PRE_EVENT_MANIFEST")

    def test_manifest_cannot_claim_blS_page_success_without_bytes(self):
        self.source_manifest[0]["source_bytes_saved_locally"] = True
        self.write_manifest()
        self.assertEqual(self.run_lab()["reason"],
                         "BLS_CAPTURE_STATUS_CONTRADICTS_SOURCE_MANIFEST")

    def test_declared_complete_market_calendar_fails_closed(self):
        self.manifest["whole_market_calendar_completeness_verified"] = True
        self.write_manifest()
        self.assertEqual(self.run_lab()["reason"],
                         "SNAPSHOT_MANIFEST_SAFETY_OR_SCHEMA_MISMATCH")

    def test_missing_official_page_rejects_full_source_receipt(self):
        (self.root / "SF_FED_DALY_UNLV.html").unlink()
        self.assertEqual(self.run_lab()["reason"],
                         "SOURCE_OR_CAPTURE_CLOCK_NOT_MATCHING_PRE_EVENT_MANIFEST")

    def test_unauthenticated_server_time_later_than_inspection_is_not_accepted(self):
        result = self.run_lab(now=CAPTURE-timedelta(minutes=1))
        self.assertEqual(result["reason"],
                         "SOURCE_OR_CAPTURE_CLOCK_NOT_MATCHING_PRE_EVENT_MANIFEST")

    def test_invalid_or_naive_inspection_time_never_passes(self):
        for wrong in (None, "2026-11-12", OBSERVE.replace(tzinfo=None)):
            with self.subTest(wrong=wrong):
                result = self.run_lab(now=wrong)
                self.assertEqual(result["reason"],
                                 "INVALID_ARCHIVE_ROOT_OR_INSPECTION_CLOCK")

    def test_duplicate_source_id_is_blocked(self):
        self.source_manifest.append(dict(self.source_manifest[1]))
        self.write_manifest()
        self.assertEqual(self.run_lab()["reason"], "DUPLICATED_SOURCE_ID")

    def test_missing_original_manifest_blocks(self):
        (self.root / "OFFICIAL_SCHEDULE_SOURCE_MANIFEST.json").unlink()
        self.assertEqual(self.run_lab()["reason"],
                         "ORIGINAL_SCHEDULE_MANIFEST_MISSING_OR_UNSAFE")

    def test_never_modify_frozen_source_html(self):
        hashes = {p.name: sha256(p.read_bytes()).hexdigest()
                  for p in self.root.glob("*.html")}
        self.run_lab()
        self.assertEqual(hashes, {p.name: sha256(p.read_bytes()).hexdigest()
                                  for p in self.root.glob("*.html")})


if __name__ == "__main__":
    unittest.main()
