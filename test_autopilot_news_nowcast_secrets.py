import unittest
from unittest.mock import Mock, patch

import autopilot_news_nowcast_v1 as n


class NewsNowcastSecretRedactionTests(unittest.TestCase):
    def test_safe_diagnostic_redacts_query_and_raw_secret(self):
        secret="SENSITIVE_PROVIDER_TOKEN_123"
        raw=f"401 for https://example.test/events?api_token={secret}&from=2026-01-01 token={secret}"
        clean=n._safe_diagnostic(raw,secret)
        self.assertNotIn(secret,clean)
        self.assertIn("api_token=[REDACTED]",clean)
        self.assertIn("token=[REDACTED]",clean)

    def test_401_and_403_are_classified_as_auth_error(self):
        secret="SENSITIVE_PROVIDER_TOKEN_AUTH"
        for code in (401,403):
            response=Mock()
            response.status_code=code
            response.raise_for_status.side_effect=n.requests.HTTPError(
                f"{code} Client Error for url: https://eodhd.com/api/economic-events?api_token={secret}"
            )
            with self.subTest(code=code), patch.object(n.requests,"get",return_value=response):
                rows,status=n.fetch_eodhd_events(
                    secret,start_date="2026-09-01",end_date="2026-09-30"
                )
            self.assertEqual(rows,[])
            self.assertEqual(status["reason"],"AUTH_ERROR")
            self.assertEqual(status["http_status"],code)
            self.assertNotIn(secret,status["error"])

    def test_429_is_classified_as_rate_limited(self):
        response=Mock()
        response.status_code=429
        response.raise_for_status.side_effect=n.requests.HTTPError("429 Too Many Requests")
        with patch.object(n.requests,"get",return_value=response):
            rows,status=n.fetch_eodhd_events(
                "TOKEN",start_date="2026-09-01",end_date="2026-09-30"
            )
        self.assertEqual(rows,[])
        self.assertEqual(status["reason"],"RATE_LIMITED")

    def test_recent_auth_error_enters_cooldown_without_fetch_permission(self):
        now=n.pd.Timestamp("2026-09-22T19:00:00Z")
        state={
            "last_attempt_at":(now-n.pd.Timedelta(minutes=15)).isoformat(),
            "last_provider_status":{"reason":"AUTH_ERROR","http_status":401},
        }
        policy=n.provider_fetch_policy(state,now=now)
        self.assertFalse(policy["fetch"])
        self.assertEqual(policy["runtime_state"],"AUTH_COOLDOWN")
        self.assertEqual(policy["reason"],"AUTH_ERROR")
        self.assertGreater(policy["retry_after_min"],0)
        self.assertFalse(n.should_fetch_provider(state,now=now))

    def test_legacy_provider_error_with_401_is_normalized_without_refetch(self):
        now=n.pd.Timestamp("2026-09-22T19:30:00Z")
        state={
            "last_attempt_at":(now-n.pd.Timedelta(minutes=20)).isoformat(),
            "last_provider_status":{
                "reason":"PROVIDER_ERROR",
                "http_status":401,
                "requests":1,
            },
        }
        policy=n.provider_fetch_policy(state,now=now)
        self.assertFalse(policy["fetch"])
        self.assertEqual(policy["runtime_state"],"AUTH_COOLDOWN")
        self.assertEqual(policy["reason"],"AUTH_ERROR")
        self.assertGreater(policy["retry_after_min"],300)

    def test_legacy_provider_error_with_429_is_normalized_to_rate_limit(self):
        now=n.pd.Timestamp("2026-09-22T19:30:00Z")
        state={
            "last_attempt_at":(now-n.pd.Timedelta(minutes=10)).isoformat(),
            "last_provider_status":{"reason":"PROVIDER_ERROR","http_status":429},
        }
        policy=n.provider_fetch_policy(state,now=now)
        self.assertFalse(policy["fetch"])
        self.assertEqual(policy["runtime_state"],"RATE_LIMIT_COOLDOWN")
        self.assertEqual(policy["reason"],"RATE_LIMITED")

    def test_auth_error_retries_after_cooldown(self):
        now=n.pd.Timestamp("2026-09-22T19:00:00Z")
        state={
            "last_attempt_at":(
                now-n.pd.Timedelta(minutes=n.DEFAULT_AUTH_RETRY_MIN+1)
            ).isoformat(),
            "last_provider_status":{"reason":"AUTH_ERROR","http_status":401},
        }
        policy=n.provider_fetch_policy(state,now=now)
        self.assertTrue(policy["fetch"])
        self.assertEqual(policy["runtime_state"],"FETCH_ALLOWED")

    def test_rate_limit_has_shorter_cooldown_than_auth_error(self):
        now=n.pd.Timestamp("2026-09-22T19:00:00Z")
        state={
            "last_attempt_at":(now-n.pd.Timedelta(minutes=10)).isoformat(),
            "last_provider_status":{"reason":"RATE_LIMITED","http_status":429},
        }
        policy=n.provider_fetch_policy(state,now=now)
        self.assertFalse(policy["fetch"])
        self.assertEqual(policy["runtime_state"],"RATE_LIMIT_COOLDOWN")
        self.assertLess(n.DEFAULT_RATE_LIMIT_RETRY_MIN,n.DEFAULT_AUTH_RETRY_MIN)

    def test_provider_http_error_never_returns_token(self):
        secret="SENSITIVE_PROVIDER_TOKEN_456"
        response=Mock()
        response.status_code=401
        response.raise_for_status.side_effect=RuntimeError(
            f"401 for https://eodhd.com/api/economic-events?api_token={secret}&country=US"
        )
        with patch.object(n.requests,"get",return_value=response):
            rows,status=n.fetch_eodhd_events(
                secret,start_date="2026-09-01",end_date="2026-09-30"
            )
        self.assertEqual(rows,[])
        self.assertFalse(status["ok"])
        self.assertNotIn(secret,status["error"])
        self.assertIn("[REDACTED]",status["error"])


if __name__=="__main__":
    unittest.main()
