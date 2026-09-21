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
