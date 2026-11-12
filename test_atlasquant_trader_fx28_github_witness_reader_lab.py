"""Fake GitHub comment pages. No live API or market directions in tests."""
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
import json
import unittest
from unittest.mock import patch

from atlasquant_trader_fx28_ny17_prospective_campaign_lab import (
    CAMPAIGN_ID, _nominal_windows,
)
from atlasquant_trader_fx28_github_witness_reader_lab import (
    HEADER, API, inspect_github_campaign_comment_pages_lab as inspect,
    fetch_github_campaign_receipts_readonly_lab as fetch,
)

UTC = timezone.utc
T0 = datetime(2026, 11, 12, 20, tzinfo=UTC)
START, END = _nominal_windows("D1")[0]
NEXT = START + timedelta(minutes=1)
CREATED = START - timedelta(hours=2)
REPO = "aparecidomikael97-ship-it/usd-macro-pro-v4"


def comment(*, horizon="D1", index=0, cid=12345,
            created=None, updated=None, body=None):
    start, end = _nominal_windows(horizon)[index]
    born = start - timedelta(hours=2) if created is None else created
    changed = born if updated is None else updated
    text = "\n".join((
        HEADER,
        f"campaign_id={CAMPAIGN_ID}",
        f"horizon={horizon}",
        f"start_utc={start.isoformat().replace('+00:00', 'Z')}",
        f"end_utc={end.isoformat().replace('+00:00', 'Z')}",
        "pairs=28",
        "roster_sha256=" + "a" * 64,
        "research_only=true",
        "trade_authorized=false",
    ))
    return {
        "id": cid,
        "body": text if body is None else body,
        "url": f"https://api.github.com/repos/{REPO}/issues/comments/{cid}",
        "html_url": f"https://github.com/{REPO}/issues/1884#issuecomment-{cid}",
        "created_at": born.isoformat().replace("+00:00", "Z"),
        "updated_at": changed.isoformat().replace("+00:00", "Z"),
    }


def audit(items, *, at=T0):
    raw = json.dumps(items, ensure_ascii=True, separators=(",", ":")).encode()
    return inspect(pages=[raw], observed_at_utc=at)


class FakeResponse:
    def __init__(self, raw, *, date=None, content_type="application/json"):
        self.raw = raw
        self.headers = {
            "Date": date or format_datetime(datetime.now(UTC)),
            "Content-Type": content_type,
        }

    def getcode(self):
        return 200

    def read(self, size):
        return self.raw[:size]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class GithubReadonlyWitnessTests(unittest.TestCase):
    def safe(self, r):
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        self.assertIsNone(r["validated_directional_accuracy"])
        self.assertIsNone(r["calibrated_direction_probability"])
        self.assertEqual(r["expected_pair_horizon_slots"], 672)
        for key in (
            "external_comment_witness_independently_verified",
            "full_forecast_payload_digest_verified",
            "original_macro_sources_authenticated",
            "pepperstone_price_source_authenticated",
            "publishable", "live_alert_allowed", "trade_authorized",
            "worker_enabled", "scheduler_enabled",
        ):
            self.assertFalse(r[key], key)
        self.assertEqual((r["file_writes"], r["new_cost_brl"]), (0, 0))
        self.assertTrue(r["research_only"])

    def test_zero_actual_comments_is_not_a_forecast(self):
        r = audit([])
        self.assertEqual(r["state"], "LAB_GITHUB_WITNESS_RECEIPTS_DOCUMENTARY_ONLY_NO_GO")
        self.assertEqual(r["received_comment_count"], 0)
        self.assertEqual(r["accepted_pre_event_comment_claims"], 0)
        self.assertEqual(r["future_pair_slots"], 672)
        self.assertEqual(r["due_missing_witness_pair_slots"], 0)
        self.assertFalse(r["local_comment_fields_checked"])
        self.safe(r)

    def test_no_forecasts_when_first_ny17_session_becomes_due(self):
        r = audit([], at=NEXT)
        self.assertEqual(r["due_missing_witness_pair_slots"], 56)
        self.assertEqual(r["due_pre_event_comment_claim_pair_slots"], 0)
        self.assertEqual(r["future_pair_slots"], 616)
        self.safe(r)

    def test_one_claimed_valid_comment_before_session_is_still_not_proof(self):
        r = audit([comment()], at=CREATED + timedelta(minutes=1))
        self.assertEqual(r["accepted_pre_event_comment_claims"], 1)
        self.assertEqual(r["future_pre_event_comment_claim_pair_slots"], 28)
        self.assertEqual(r["future_pair_slots"], 672)
        self.assertTrue(r["local_comment_fields_checked"])
        self.assertFalse(r["external_comment_witness_independently_verified"])
        self.safe(r)

    def test_past_comment_first_observed_after_start_is_not_witness(self):
        r = audit([comment()], at=NEXT)
        self.assertEqual(r["accepted_pre_event_comment_claims"], 0)
        self.assertEqual(r["rejected_late_or_edited_comment_claims"], 1)
        self.assertEqual(r["due_missing_witness_pair_slots"], 56)
        self.safe(r)

    def test_edited_comment_cannot_be_considered_immutable(self):
        r = audit([comment(updated=CREATED + timedelta(minutes=1))],
                  at=CREATED + timedelta(minutes=2))
        self.assertEqual(r["rejected_late_or_edited_comment_claims"], 1)
        self.assertEqual(r["accepted_pre_event_comment_claims"], 0)
        self.safe(r)

    def test_duplicate_same_window_anchors_block_everything(self):
        r = audit([comment(cid=101), comment(cid=102)],
                  at=CREATED + timedelta(minutes=1))
        self.assertEqual(r["reason"], "DUPLICATE_OR_UNKNOWN_WINDOW_WITNESS")
        self.assertEqual(r["state"], "LAB_GITHUB_RECEIPT_READER_BLOCKED")
        self.safe(r)

    def test_different_horizons_start_same_time_but_are_distinct(self):
        r = audit([comment(cid=101), comment(horizon="W1", cid=102)],
                  at=CREATED + timedelta(minutes=1))
        self.assertEqual(r["accepted_pre_event_comment_claims"], 2)
        self.assertEqual(r["future_pre_event_comment_claim_pair_slots"], 56)
        self.safe(r)

    def test_wrong_github_issue_link_is_fail_closed(self):
        c = comment()
        c["html_url"] = f"https://github.com/{REPO}/issues/99999#issuecomment-12345"
        r = audit([c], at=CREATED + timedelta(minutes=1))
        self.assertEqual(r["reason"], "INVALID_GITHUB_COMMENT_ID_URL_OR_TIMESTAMP")
        self.safe(r)

    def test_missing_or_wrong_hash_never_becomes_pre_event_witness(self):
        c = comment()
        c["body"] = c["body"].replace("a" * 64, "not-a-hash")
        r = audit([c], at=CREATED + timedelta(minutes=1))
        self.assertEqual(r["reason"], "MALFORMED_OR_NONCANONICAL_FORECAST_ANCHOR")
        self.safe(r)

    def test_wrong_window_or_schema_is_rejected(self):
        c = comment()
        c["body"] = c["body"].replace("pairs=28", "pairs=27")
        r = audit([c], at=CREATED + timedelta(minutes=1))
        self.assertEqual(r["reason"], "MALFORMED_OR_NONCANONICAL_FORECAST_ANCHOR")
        self.safe(r)

    def test_source_date_in_future_must_block(self):
        c = comment(created=START + timedelta(days=1))
        r = audit([c], at=CREATED + timedelta(minutes=1))
        self.assertEqual(r["reason"], "INVALID_GITHUB_COMMENT_ID_URL_OR_TIMESTAMP")
        self.safe(r)

    def test_unrelated_comment_not_mistaken_for_prediction(self):
        r = audit([{"id": 100, "body": "General discussion; no forecast."}])
        self.assertEqual(r["unrelated_comments"], 1)
        self.assertEqual(r["accepted_pre_event_comment_claims"], 0)
        self.safe(r)

    def test_json_and_pagination_malformed_or_truncated_fail(self):
        for pages, why in (
            ([b"{}"], "INVALID_GITHUB_COMMENT_PAGE_SHAPE"),
            ([b"not-json"], "INVALID_GITHUB_JSON_RESPONSE"),
            ([b"[]", b"[]"], "EARLY_PAGE_END_CANNOT_HAVE_FOLLOWING_PAGE"),
            ([b"[" + b"{}," * 100 + b"{}]"], "INVALID_GITHUB_COMMENT_PAGE_SHAPE"),
            ([b"x" * 520000], "INVALID_OR_OVERSIZED_GITHUB_RESPONSE_PAGE"),
        ):
            with self.subTest(why=why):
                r = inspect(pages=pages, observed_at_utc=T0)
                self.assertEqual(r["reason"], why)
                self.safe(r)

    def test_unauthenticated_no_token_must_not_access_network(self):
        with patch("atlasquant_trader_fx28_github_witness_reader_lab.urlopen") as client:
            r = fetch(token=None)
            client.assert_not_called()
        self.assertEqual(r["reason"], "MISSING_OR_INVALID_GITHUB_READ_TOKEN_NO_HTTP")
        self.safe(r)

    def test_bounded_get_with_fake_http_still_not_forecast_authentication(self):
        raw = b"[]"
        response = FakeResponse(raw)
        with patch("atlasquant_trader_fx28_github_witness_reader_lab.urlopen",
                   return_value=response) as client:
            r = fetch(token="synthetic-test-token")
            client.assert_called_once()
            request = client.call_args.args[0]
            self.assertEqual(request.get_method(), "GET")
            self.assertTrue(request.full_url.startswith(API))
        self.assertEqual(r["state"], "LAB_GITHUB_WITNESS_RECEIPTS_DOCUMENTARY_ONLY_NO_GO")
        self.assertTrue(r["actual_https_get_completed"])  # mocked and not attested
        self.assertEqual(r["http_requests"], 1)
        self.assertEqual(r["received_comment_count"], 0)
        self.assertFalse(r["external_comment_witness_independently_verified"])
        self.safe(r)

    def test_live_get_non_json_is_blocked_no_fallback(self):
        response = FakeResponse(b"<html>error</html>", content_type="text/html")
        with patch("atlasquant_trader_fx28_github_witness_reader_lab.urlopen",
                   return_value=response):
            r = fetch(token="synthetic-test-token")
        self.assertEqual(r["reason"], "GITHUB_API_NOT_JSON")
        self.assertFalse(r["actual_https_get_completed"])
        self.safe(r)


if __name__ == "__main__":
    unittest.main()
