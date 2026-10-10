"""Synthetic transport only: actual readers and writers, no external endpoints."""
import base64
import hashlib
import json
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import requests
import atlasquant_flight_recorder_store as flight
import atlasquant_research_evidence_store as research
import atlasquant_shadow_store as shadow
from twelve_budget_v1108 import Budget, BudgetUnavailable, GitHubStore

CASES = (
    (flight, "persist_records", "serialize_records", [{"decision_id": "fixture", "value": 1}]),
    (research, "persist_research_evidence", "serialize_evidence_records", [{"record_id": "fixture", "value": 1}]),
    (shadow, "persist_shadow_samples", "serialize_samples", [{"sample_id": "fixture", "value": 1}]),
)
ARGS = dict(repo="example/repository", branch="atlasquant-runtime", token="SYNTHETIC_NON_REAL")
NOW = datetime(2026, 10, 9, 12, tzinfo=timezone.utc)


def blob(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()


def response(status, payload):
    return SimpleNamespace(status_code=status, json=lambda: payload, raise_for_status=lambda: None)


def contents(raw, claimed_sha=None):
    return response(200, {"encoding": "base64", "content": base64.b64encode(raw).decode("ascii"),
                          "sha": claimed_sha or blob(raw)})


class ClosureAuditRegressions(unittest.TestCase):
    def setUp(self):
        self.network = patch("requests.sessions.Session.request",
                             side_effect=AssertionError("UNMOCKED_NETWORK_FORBIDDEN"))
        self.network.start()
        self.addCleanup(self.network.stop)

    def test_real_readers_accept_exact_bytes_with_one_write(self):
        for module, writer, serializer, data in CASES:
            with self.subTest(store=module.__name__):
                raw = getattr(module, serializer)(data).encode("utf-8")
                with patch.object(requests, "get", side_effect=[response(404, {}), contents(raw)]) as get, \
                     patch.object(requests, "put", return_value=response(201, {"content": {"sha": blob(raw)}})) as put:
                    result = getattr(module, writer)(data, **ARGS)
                self.assertEqual(result["reason"], "SAVED")
                self.assertTrue(result["verified"])
                self.assertEqual((get.call_count, put.call_count), (2, 1))

    def test_readback_duplicate_json_key_cannot_hide_different_bytes(self):
        for module, writer, serializer, data in CASES:
            with self.subTest(store=module.__name__):
                raw = getattr(module, serializer)(data).encode("utf-8")
                changed = raw.replace(b'"value":1', b'"value":999,"value":1')
                self.assertNotEqual(raw, changed)
                self.assertEqual(json.loads(raw), json.loads(changed))
                with patch.object(requests, "get", side_effect=[response(404, {}), contents(changed, blob(raw))]), \
                     patch.object(requests, "put", return_value=response(201, {"content": {"sha": blob(raw)}})) as put:
                    result = getattr(module, writer)(data, **ARGS)
                self.assertEqual(result["reason"], "UNKNOWN_OUTCOME", result)
                self.assertFalse(result["safe_to_retry"])
                self.assertEqual(put.call_count, 1)

    def test_missing_or_unavailable_get_content_cannot_overwrite_existing_blob(self):
        for module, writer, serializer, data in CASES:
            for payload in ({"sha": "a"*40}, {"sha": "a"*40, "encoding": "none", "content": ""}):
                with self.subTest(store=module.__name__, payload=payload):
                    with patch.object(requests, "get", return_value=response(200, payload)), \
                         patch.object(requests, "put", side_effect=AssertionError("WRITE_FORBIDDEN")) as put:
                        result = getattr(module, writer)(data, **ARGS)
                    put.assert_not_called()
                    self.assertFalse(result["ok"])

    def test_preflight_incorrect_blob_sha_cannot_write(self):
        for module, writer, serializer, data in CASES:
            with self.subTest(store=module.__name__):
                raw = getattr(module, serializer)(data).encode("utf-8")
                with patch.object(requests, "get", return_value=contents(raw, "a"*40)), \
                     patch.object(requests, "put", side_effect=AssertionError("WRITE_FORBIDDEN")) as put:
                    result = getattr(module, writer)([dict(data[0], value=2)], **ARGS)
                self.assertFalse(result["ok"], result)
                put.assert_not_called()

    def test_invalid_base64_is_not_silently_ignored(self):
        for module, writer, serializer, data in CASES:
            with self.subTest(store=module.__name__):
                raw = getattr(module, serializer)(data).encode("utf-8")
                payload = contents(raw).json()
                payload["content"] = "!!!" + payload["content"]
                with patch.object(requests, "get", return_value=response(200, payload)), \
                     patch.object(requests, "put") as put:
                    result = getattr(module, writer)(data, **ARGS)
                self.assertFalse(result["ok"], result)
                put.assert_not_called()

    def test_line_wrapped_base64_and_existing_records_remain_supported(self):
        for module, writer, serializer, data in CASES:
            with self.subTest(store=module.__name__):
                raw = getattr(module, serializer)(data).encode("utf-8")
                payload = contents(raw).json()
                encoded = payload["content"]
                payload["content"] = "\n".join(encoded[i:i+8] for i in range(0, len(encoded), 8)) + "\n"
                with patch.object(requests, "get", return_value=response(200, payload)), patch.object(requests, "put") as put:
                    result = getattr(module, writer)(data, **ARGS)
                self.assertEqual(result["reason"], "ALREADY_PRESENT")
                put.assert_not_called()

    def test_budget_reported_conflict_never_replays_at_higher_layer(self):
        for status in (409, 422):
            with self.subTest(status=status):
                store = GitHubStore("SYNTHETIC_NON_REAL", "example/repository", "atlasquant-runtime")
                with patch.object(store, "load", return_value=({}, None)) as get, \
                     patch.object(requests, "put", return_value=response(status, {})) as put:
                    with self.assertRaises(BudgetUnavailable):
                        Budget(store).reserve(NOW)
                self.assertEqual(put.call_count, 1)
                self.assertEqual(get.call_count, 1)

    def test_budget_timeout_never_replays(self):
        store = GitHubStore("SYNTHETIC_NON_REAL", "example/repository", "atlasquant-runtime")
        with patch.object(store, "load", return_value=({}, None)), \
             patch.object(requests, "put", side_effect=requests.Timeout("synthetic")) as put:
            with self.assertRaises(BudgetUnavailable):
                Budget(store).reserve(NOW)
        self.assertEqual(put.call_count, 1)


if __name__ == "__main__":
    unittest.main()
