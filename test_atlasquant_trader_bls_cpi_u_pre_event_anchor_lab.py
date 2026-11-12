"""Synthetic BLS custody/GitHub witness tests. No HTTP, GitHub post, broker."""
from datetime import datetime, timedelta, timezone
from io import BytesIO
import json
import unittest
from zipfile import ZipFile, ZIP_STORED

from atlasquant_trader_bls_cpi_u_official_bytes_readonly_lab import (
    inspect_bls_cpi_u_v1_bytes_lab,
)
from atlasquant_trader_bls_cpi_u_capture_receipt_lab import (
    prepare_bls_cpi_u_source_receipt_lab,
)
from atlasquant_trader_bls_cpi_u_pre_event_anchor_lab import (
    HEADER, ISSUE, REPO,
    prepare_bls_cpi_u_sha_witness_body_lab as prepare,
    inspect_bls_cpi_u_github_comment_claim_lab as inspect,
)

UTC = timezone.utc
CAPTURE = datetime(2026, 11, 12, 20, 0, 0, 123456, tzinfo=UTC)
PREPARED = datetime(2026, 11, 12, 20, 2, tzinfo=UTC)
CREATED = datetime(2026, 11, 12, 20, 3, tzinfo=UTC)
OBSERVED = datetime(2026, 11, 12, 20, 4, tzinfo=UTC)
CUTOFF = datetime(2026, 11, 15, 22, 0, tzinfo=UTC)


def custody_zip():
    payload = {
        "status": "REQUEST_SUCCEEDED", "message": [],
        "Results": [{
            "series": [{
                "seriesID": "CUUR0000SA0",
                "data": [
                    {"year": "2026", "period": "M09", "periodName": "September",
                     "value": "330.000", "footnotes": []},
                    {"year": "2025", "period": "M09", "periodName": "September",
                     "value": "300.000", "footnotes": []},
                ],
            }],
        }],
    }
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("ascii")
    inspected = inspect_bls_cpi_u_v1_bytes_lab(
        original_bytes=raw, captured_at_utc=CAPTURE,
        server_date_at_utc=CAPTURE)
    assert inspected["state"] == "LAB_BLS_CPI_U_INDEX_BYTES_INSPECTED_UNATTESTED"
    inspected["http_get_completed"] = True
    inspected["http_requests"] = 1
    zipped = prepare_bls_cpi_u_source_receipt_lab(fetched=inspected)
    assert zipped["state"] == "LAB_BLS_CPI_U_SOURCE_ZIP_PREPARED_LOCAL_ONLY"
    return zipped["capture_bundle_zip"]


def params(**kwargs):
    base = dict(
        archive_zip=custody_zip(), reference_period="2026-09",
        prepared_at_utc=PREPARED, forecast_cutoff_at_utc=CUTOFF)
    base.update(kwargs)
    return base


def github_comment(fields):
    cid = 7654321
    return {
        "id": cid,
        "body": fields["anchor_body_unposted"],
        "url": f"https://api.github.com/repos/{REPO}/issues/comments/{cid}",
        "html_url": f"https://github.com/{REPO}/issues/{ISSUE}#issuecomment-{cid}",
        "created_at": CREATED.isoformat().replace("+00:00", "Z"),
        "updated_at": CREATED.isoformat().replace("+00:00", "Z"),
    }


class PreEventShaWitnessTests(unittest.TestCase):
    def safe(self, out):
        self.assertEqual(out["operational_bias"], "AGUARDAR")
        self.assertIsNone(out["calibrated_direction_probability"])
        for field in (
            "github_api_record_independently_authenticated",
            "github_first_observation_independently_attested",
            "bls_original_release_authenticated",
            "bls_historical_vintage_authenticated",
            "cpi_yoy_proven_point_in_time",
            "fx28_forecast_authorized",
            "publishable",
            "live_alert_allowed",
            "trade_authorized", "scheduler_enabled", "worker_enabled",
        ):
            self.assertIs(out[field], False, field)
        self.assertEqual(
            (out["http_requests"], out["file_writes"], out["new_cost_brl"]),
            (0, 0, 0))

    def test_prepare_exact_hashes_and_original_microsecond_timestamp(self):
        args = params()
        out = prepare(**args)
        self.assertEqual(out["state"], "LAB_BLS_CPI_U_SHA_WITNESS_TEXT_PREPARED_NOT_POSTED")
        self.assertTrue(out["anchor_body_unposted"].startswith(HEADER))
        self.assertIn(out["original_source_sha256_local"], out["anchor_body_unposted"])
        self.assertIn(out["manifest_sha256_local"], out["anchor_body_unposted"])
        self.assertIn(out["archive_zip_sha256_local"], out["anchor_body_unposted"])
        self.assertEqual(out["claimed_capture_at_utc"], "2026-11-12T20:00:00.123456Z")
        self.assertIn("point_in_time_authenticated=false", out["anchor_body_unposted"])
        self.assertIsNone(out["comment_id_documentary"])
        self.safe(out)

    def test_matching_pre_event_comment_only_documentary_not_authenticated(self):
        args = params()
        prepared = prepare(**args)
        out = inspect(**args, github_comment=github_comment(prepared),
                      first_observed_at_utc=OBSERVED)
        self.assertEqual(
            out["state"], "LAB_BLS_CPI_U_PRE_EVENT_GITHUB_FIELDS_MATCHED_CLAIM_ONLY")
        self.assertTrue(out["comment_fields_locally_matched_before_cutoff"])
        self.assertEqual(out["comment_id_documentary"], 7654321)
        self.safe(out)

    def test_late_first_observation_never_becomes_pre_event_witness(self):
        args = params()
        out = inspect(**args, github_comment=github_comment(prepare(**args)),
                      first_observed_at_utc=CUTOFF)
        self.assertEqual(out["reason"], "FIRST_OBSERVATION_MISSING_OR_NOT_PRE_EVENT")
        self.assertFalse(out["comment_fields_locally_matched_before_cutoff"])
        self.safe(out)

    def test_edited_comment_not_immutable(self):
        args = params()
        comment = github_comment(prepare(**args))
        comment["updated_at"] = (CREATED + timedelta(seconds=1)).isoformat().replace("+00:00", "Z")
        out = inspect(**args, github_comment=comment, first_observed_at_utc=OBSERVED)
        self.assertEqual(out["reason"], "GITHUB_COMMENT_BODY_URL_OR_PRE_EVENT_CHRONOLOGY_MISMATCH")
        self.safe(out)

    def test_wrong_git_url_or_id_is_rejected(self):
        args = params()
        good = github_comment(prepare(**args))
        for mutation in (
            {"id": True},
            {"html_url": f"https://github.com/{REPO}/issues/1884#issuecomment-7654321"},
            {"url": "https://untrusted.example/api/comments/7654321"},
        ):
            with self.subTest(change=mutation):
                out = inspect(**args, github_comment=dict(good, **mutation),
                              first_observed_at_utc=OBSERVED)
                self.assertEqual(out["state"], "LAB_BLS_CPI_U_PRE_EVENT_SHA_WITNESS_BLOCKED")
                self.safe(out)

    def test_forged_or_wrong_hash_in_comment_is_rejected(self):
        args = params()
        comment = github_comment(prepare(**args))
        comment["body"] = comment["body"].replace(
            "archive_zip_sha256=", "archive_zip_sha256=modified", 1)
        out = inspect(**args, github_comment=comment, first_observed_at_utc=OBSERVED)
        self.assertEqual(out["reason"], "GITHUB_COMMENT_BODY_URL_OR_PRE_EVENT_CHRONOLOGY_MISMATCH")
        self.safe(out)

    def test_comment_created_before_archive_or_prepared_is_rejected(self):
        args = params()
        comment = github_comment(prepare(**args))
        comment["created_at"] = (CAPTURE - timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        comment["updated_at"] = comment["created_at"]
        out = inspect(**args, github_comment=comment, first_observed_at_utc=OBSERVED)
        self.assertEqual(out["reason"], "GITHUB_COMMENT_BODY_URL_OR_PRE_EVENT_CHRONOLOGY_MISMATCH")
        self.safe(out)

    def test_archive_capture_after_cutoff_blocks_preparation(self):
        out = prepare(**params(forecast_cutoff_at_utc=CAPTURE - timedelta(minutes=5)))
        self.assertEqual(out["state"], "LAB_BLS_CPI_U_PRE_EVENT_SHA_WITNESS_BLOCKED")
        self.assertIsNone(out["anchor_body_unposted"])
        self.safe(out)

    def test_repacked_archive_changes_zip_sha_and_blocks_old_comment(self):
        original = params()
        prepared = prepare(**original)
        comment = github_comment(prepared)
        with ZipFile(BytesIO(original["archive_zip"])) as z:
            source = z.read("bls_cpi_u_v1_original_response.json")
            manifest = z.read("capture_manifest.json")
        buf = BytesIO()
        with ZipFile(buf, "w", compression=ZIP_STORED) as z:
            # Same original bytes + manifest but different ZIP-member order:
            z.writestr("capture_manifest.json", manifest)
            z.writestr("bls_cpi_u_v1_original_response.json", source)
        assert buf.getvalue() != original["archive_zip"]
        altered_args = dict(original, archive_zip=buf.getvalue())
        self.assertEqual(
            prepare(**altered_args)["state"],
            "LAB_BLS_CPI_U_SHA_WITNESS_TEXT_PREPARED_NOT_POSTED")
        out = inspect(**altered_args, github_comment=comment,
                      first_observed_at_utc=OBSERVED)
        self.assertEqual(out["state"], "LAB_BLS_CPI_U_PRE_EVENT_SHA_WITNESS_BLOCKED")
        self.safe(out)

    def test_missing_comment_is_not_a_witness(self):
        args = params()
        out = inspect(**args, github_comment=None, first_observed_at_utc=OBSERVED)
        self.assertEqual(out["reason"], "FIRST_OBSERVATION_MISSING_OR_NOT_PRE_EVENT")
        self.safe(out)

    def test_future_month_does_not_qualify_for_anchor(self):
        out = prepare(**params(reference_period="2026-12"))
        self.assertEqual(out["state"], "LAB_BLS_CPI_U_PRE_EVENT_SHA_WITNESS_BLOCKED")
        self.assertIsNone(out["anchor_body_unposted"])
        self.safe(out)


if __name__ == "__main__":
    unittest.main()
