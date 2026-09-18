import json
import os
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

import twelve_cache_v1108 as tc


class _FakeResponse:
    status_code = 200

    def __init__(self, values):
        self._values = values

    def json(self):
        return {"status": "ok", "values": self._values}


class TwelveLocalCacheTests(unittest.TestCase):
    def test_local_mode_fetches_once_then_reuses_cache(self):
        old_series = tc.LOCAL_SERIES_PATH
        old_budget = tc.LOCAL_BUDGET_PATH
        try:
            with tempfile.TemporaryDirectory() as tmp:
                tc.LOCAL_SERIES_PATH = os.path.join(tmp, "series.json")
                tc.LOCAL_BUDGET_PATH = os.path.join(tmp, "budget.json")

                now = pd.Timestamp.now(tz="UTC")
                values = []
                for minutes in (45, 30):
                    dt = now - pd.Timedelta(minutes=minutes)
                    values.append({
                        "datetime": dt.strftime("%Y-%m-%d %H:%M:%S"),
                        "open": "1.1000",
                        "high": "1.1100",
                        "low": "1.0900",
                        "close": "1.1050",
                    })

                settings = {
                    "CHAVE_TWELVE_DATA": "test-key",
                    "GITHUB_TOKEN_HISTORICO": "",
                    "GITHUB_REPO_HISTORICO": "",
                    "GITHUB_BRANCH_HISTORICO": "main",
                }

                def fake_setting(key, default=""):
                    return settings.get(key, default)

                with patch.object(tc, "_setting", side_effect=fake_setting), \
                     patch.object(tc.requests, "get", return_value=_FakeResponse(values)) as get_mock:
                    first, err1 = tc.cached_series("EUR/USD", "15min", 2)
                    second, err2 = tc.cached_series("EUR/USD", "15min", 2)

                self.assertEqual(err1, "")
                self.assertEqual(err2, "")
                self.assertEqual(len(first), 2)
                self.assertEqual(len(second), 2)
                self.assertEqual(get_mock.call_count, 1)
                self.assertFalse(bool(first.attrs.get("cache_only", True)))
                self.assertTrue(bool(second.attrs.get("cache_only", False)))
                self.assertTrue(os.path.exists(tc.LOCAL_SERIES_PATH))

                budget = json.loads(open(tc.LOCAL_BUDGET_PATH, encoding="utf-8").read())
                self.assertEqual(int(budget["used"]), 1)
        finally:
            tc.LOCAL_SERIES_PATH = old_series
            tc.LOCAL_BUDGET_PATH = old_budget

    def test_cloud_mode_remains_read_only(self):
        with patch.object(tc, "_setting", side_effect=lambda key, default="": {
            "GITHUB_TOKEN_HISTORICO": "token",
            "GITHUB_REPO_HISTORICO": "owner/repo",
            "GITHUB_BRANCH_HISTORICO": "runtime",
        }.get(key, default)), \
             patch.object(tc, "_load", return_value=({}, "cloud-cache-error")):
            df, err = tc.cached_series("EUR/USD", "15min", 2)
        self.assertTrue(df.empty)
        self.assertEqual(err, "cloud-cache-error")


if __name__ == "__main__":
    unittest.main()
