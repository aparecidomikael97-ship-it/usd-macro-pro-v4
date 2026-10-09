"""Adversarial offline contract tests for the existing AION provider adapter."""
import unittest
from unittest.mock import patch

import atlasquant_aion_provider as provider


class FakeResponse:
    status_code = 200

    def json(self):
        return {"id": "offline-fixture", "output_text": "resposta de teste"}


class FakeSession:
    def __init__(self):
        self.calls = []

    def post(self, url, headers=None, json=None, timeout=None):
        self.calls.append({
            "url": url, "headers": dict(headers or {}),
            "json": dict(json or {}), "timeout": timeout,
        })
        return FakeResponse()


class FullRequestBindingTests(unittest.TestCase):
    def env(self):
        return {
            "AION_MODEL_PROVIDER": "openai",
            "OPENAI_API_KEY": "synthetic-noncredential-for-tests",
            "AION_OPENAI_FAST_MODEL": "fast-model",
            "AION_OPENAI_REASONING_MODEL": "reasoning-model",
            "AION_OPENAI_INPUT_USD_PER_MTOK": "1",
            "AION_OPENAI_OUTPUT_USD_PER_MTOK": "2",
            "AION_OPENAI_MAX_OUTPUT_TOKENS": "500",
            "AION_OPENAI_TIMEOUT_SECONDS": "45",
        }

    def execute(self, prompt, lane, env, digest):
        session = FakeSession()
        result = provider.execute_openai_answer(
            prompt, lane=lane,
            budget={"allow_paid": True, "monthly_limit_usd": 10},
            external_feature_enabled=True, request_approved=True,
            values=env, session=session, expected_request_sha256=digest,
        )
        return result, session.calls

    def test_preflight_has_no_permission_and_matches_fake_transport(self):
        prompt = "AION: análise 😀 e acentuação\nsegunda linha"
        values = self.env()
        preview = provider.preview_openai_request_binding(
            prompt, lane="EXTERNAL_FAST", values=values,
        )
        self.assertEqual(preview["state"], "BOUND_REQUEST_PREVIEW_UNTRUSTED")
        self.assertEqual(len(preview["request_sha256"]), 64)
        self.assertFalse(preview["signed_request_verified"])
        self.assertFalse(preview["human_owner_identity_verified"])
        self.assertFalse(preview["model_invocation_authorized"])
        self.assertNotIn(values["OPENAI_API_KEY"], repr(preview))
        self.assertNotIn(prompt, repr(preview))
        result, calls = self.execute(
            prompt, "EXTERNAL_FAST", values, preview["request_sha256"],
        )
        self.assertTrue(result["called"])
        self.assertEqual(result["truth_state"], "MODEL_OUTPUT_UNVERIFIED")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["url"], preview["endpoint"])
        self.assertEqual(calls[0]["timeout"], preview["timeout_seconds"])
        self.assertEqual(calls[0]["json"], {
            "model": preview["resolved_model"],
            "input": prompt,
            "max_output_tokens": preview["max_output_tokens"],
        })

    def test_missing_malformed_or_client_invented_hash_never_calls_http(self):
        values = self.env()
        prompt = "Texto neutro"
        correct = provider.preview_openai_request_binding(
            prompt, lane="EXTERNAL_FAST", values=values,
        )["request_sha256"]
        for bad in (None, False, 0, "", "1"*64, correct.upper(), "z"*64):
            with self.subTest(hash=repr(bad)):
                result, calls = self.execute(
                    prompt, "EXTERNAL_FAST", values, bad,
                )
                self.assertEqual(result["state"], "BLOCKED_REQUEST_BINDING")
                self.assertFalse(result["called"])
                self.assertEqual(calls, [])

    def test_changes_to_resolved_request_block_before_http(self):
        values = self.env()
        prompt = "Mensagem original"
        correct = provider.preview_openai_request_binding(
            prompt, lane="EXTERNAL_FAST", values=values,
        )["request_sha256"]
        changed_model = dict(values)
        changed_model["AION_OPENAI_FAST_MODEL"] = "different-model"
        changed_cap = dict(values)
        changed_cap["AION_OPENAI_MAX_OUTPUT_TOKENS"] = "501"
        changed_timeout = dict(values)
        changed_timeout["AION_OPENAI_TIMEOUT_SECONDS"] = "8.5"
        cases = [
            (prompt, "EXTERNAL_FAST", changed_model),
            (prompt, "EXTERNAL_FAST", changed_cap),
            (prompt, "EXTERNAL_FAST", changed_timeout),
            (prompt + "!", "EXTERNAL_FAST", values),
            (prompt, "EXTERNAL_REASONING", values),
        ]
        for message, lane, opts in cases:
            with self.subTest(message=message, lane=lane, options=opts):
                result, calls = self.execute(message, lane, opts, correct)
                self.assertEqual(result["state"], "BLOCKED_REQUEST_BINDING")
                self.assertEqual(calls, [])
        with patch.object(provider, "OPENAI_RESPONSES_URL",
                          "https://changed.example.invalid/v1/responses"):
            result, calls = self.execute(
                prompt, "EXTERNAL_FAST", values, correct,
            )
            self.assertEqual(result["state"], "BLOCKED_REQUEST_BINDING")
            self.assertEqual(calls, [])

    def test_deterministic_preview_and_invalid_inputs(self):
        values = self.env()
        reversed_order = dict(reversed(list(values.items())))
        for lane in ("EXTERNAL_FAST", "EXTERNAL_REASONING"):
            first = provider.preview_openai_request_binding(
                "Olá 😀", lane=lane, values=values,
            )
            second = provider.preview_openai_request_binding(
                "Olá 😀", lane=lane, values=reversed_order,
            )
            self.assertEqual(first["request_sha256"], second["request_sha256"])
        for prompt, lane in (
            (" pergunta", "EXTERNAL_FAST"),
            ("senha pessoal", "EXTERNAL_FAST"),
            ("ok", "LOCAL_DETERMINISTIC"),
            ({"input":"ok"}, "EXTERNAL_FAST"),
        ):
            result = provider.preview_openai_request_binding(
                prompt, lane=lane, values=values,
            )
            self.assertEqual(result["state"], "BLOCKED_REQUEST_SHAPE")
            self.assertFalse(result["model_invocation_authorized"])


if __name__ == "__main__":
    unittest.main()
