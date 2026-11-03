"""Official macro evidence: period/unit provenance, no fake release or orders."""
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from atlasquant_trader_master_official_series import (
    FEATURE_FLAG, SPECS, normalize_series, enabled,
    _http_one, read_official_series,
)
from atlasquant_trader_master_official_ui import official_macro_html
from atlasquant_trader_radar_compact_ui import trader_radar_html

NOW = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)


def _bcb(date="30/10/2026", value="12,25"):
    return [{"data": date, "valor": value}]


def _fred(date="2026-10-01", value="3.1"):
    return {"observations": [{"date": date, "value": value}]}


class OfficialSeriesTests(unittest.TestCase):
    def test_opt_in_disabled_even_with_existing_fred_key(self):
        self.assertFalse(enabled({}))
        self.assertTrue(enabled({FEATURE_FLAG: "1"}))
        self.assertFalse(enabled({FEATURE_FLAG: "unknown"}))
        fake = SimpleNamespace(secrets={})
        with patch.dict("os.environ", {FEATURE_FLAG: "0", "CHAVE_FRED": "DEMO"}, clear=False):
            with patch("atlasquant_trader_master_official_series._one_day") as get:
                out = read_official_series(fake, at=NOW)
                self.assertEqual(out["state"], "DESATIVADO")
                self.assertEqual(len(out["rows"]), len(SPECS))
                self.assertTrue(all(row["value"] is None for row in out["rows"]))
                get.assert_not_called()

    def test_bcb_selic_rate_period_and_unit(self):
        row = normalize_series("BR_SELIC_META", _bcb(), at=NOW)
        self.assertEqual(row["state"], "VALIDADO")
        self.assertEqual(row["value"], 12.25)
        self.assertEqual(row["unit"], "% ao ano")
        self.assertEqual(row["source"], "BCB-SGS")
        self.assertEqual(row["observation_date"], "2026-10-30")
        self.assertFalse(row["trade_authorized"])
        self.assertIn("não horário de divulgação", row["reason"])

    def test_bcb_ipca_monthly_and_annual_not_mixed(self):
        monthly = normalize_series(
            "BR_IPCA_MENSAL", _bcb(date="01/09/2026", value="-0,32"), at=NOW)
        annual = normalize_series(
            "BR_IPCA_12M", _bcb(date="01/09/2026", value="4,58"), at=NOW)
        self.assertEqual(monthly["value"], -0.32)
        self.assertEqual(annual["value"], 4.58)
        self.assertNotEqual(monthly["unit"], annual["unit"])
        self.assertEqual(monthly["frequency"], "MENSAL")
        self.assertEqual(annual["frequency"], "MENSAL")

    def test_fred_yoy_transform_and_observation_date(self):
        cpi = normalize_series("US_CPI_YOY", _fred(), at=NOW)
        self.assertEqual(cpi["transformation"], "pc1")
        self.assertEqual(cpi["value"], 3.1)
        self.assertEqual(cpi["unit"], "% em 12 meses")
        self.assertNotIn("consensus", cpi)
        self.assertFalse(cpi["trade_authorized"])

    def test_future_stale_or_invalid_number_fail_closed(self):
        cases = (
            ("BR_SELIC_META", _bcb(date="31/12/2026", value="12,25")),
            ("BR_SELIC_META", _bcb(date="01/10/2026", value="12,25")),
            ("BR_IPCA_12M", _bcb(date="01/01/2026", value="4,58")),
            ("US_CPI_YOY", _fred(date="2026-10-01", value=".")),
            ("US_UNEMPLOYMENT", _fred(date="2026-10-01", value="nan")),
            ("US_TREASURY_2Y", _fred(date="2026-10-01", value="3.2")),
        )
        for key, raw in cases:
            with self.subTest(key=key, raw=raw):
                out = normalize_series(key, raw, at=NOW)
                self.assertNotEqual(out["state"], "VALIDADO")
                self.assertIsNone(out["value"])

    def test_latest_valid_observation_not_first_item(self):
        data = {"observations": [
            {"date": "2026-09-01", "value": "2.5"},
            {"date": "2026-10-01", "value": "3.3"},
            {"date": "2026-08-01", "value": "3.7"},
        ]}
        out = normalize_series("US_CPI_YOY", data, at=NOW)
        self.assertEqual(out["value"], 3.3)
        self.assertEqual(out["observation_date"], "2026-10-01")

    def test_fred_no_key_does_not_fetch(self):
        calls = []
        def fake(*args, **kwargs):
            calls.append((args, kwargs))
            return SimpleNamespace(status_code=200, json=lambda: _fred())
        self.assertIsNone(_http_one("US_CPI_YOY", "", request_get=fake))
        self.assertEqual(calls, [])

    def test_fred_and_bcb_requests_scoped_with_timeouts(self):
        calls = []
        def fake(url, *, params, timeout):
            calls.append((url, params, timeout))
            data = _fred() if "stlouisfed" in url else _bcb()
            return SimpleNamespace(status_code=200, json=lambda: data)
        self.assertIsInstance(_http_one("BR_SELIC_META", "", request_get=fake), list)
        self.assertIsInstance(_http_one("US_CPI_YOY", "LABKEY", request_get=fake), dict)
        self.assertEqual(calls[0][2], 7)
        self.assertEqual(calls[1][1]["units"], "pc1")
        self.assertEqual(calls[1][1]["series_id"], "CPIAUCSL")
        self.assertEqual(calls[0][1]["formato"], "json")

    def test_enabled_source_uses_only_existing_key_and_read_model(self):
        raw = {
            "BR_SELIC_META": _bcb(), "BR_IPCA_MENSAL": _bcb(value="0,32"),
            "BR_IPCA_12M": _bcb(value="4,58"),
            "US_CPI_YOY": _fred(), "US_UNEMPLOYMENT": _fred(value="4.0"),
            "US_TREASURY_2Y": _fred(date="2026-10-30", value="3.9"),
        }
        with patch.dict("os.environ", {FEATURE_FLAG: "1", "CHAVE_FRED": "LAB_EXISTING"}, clear=False):
            with patch("atlasquant_trader_master_official_series._one_day", return_value=raw) as fetch:
                model = read_official_series(SimpleNamespace(secrets={}), at=NOW)
        self.assertEqual(model["state"], "VALIDADO")
        self.assertFalse(model["trade_authorized"])
        self.assertEqual(len(model["rows"]), 6)
        self.assertTrue(all(r["state"] == "VALIDADO" for r in model["rows"]))
        fetch.assert_called_once_with("2026-11-02", "LAB_EXISTING")
        html = official_macro_html(model)
        self.assertIn("BR_IPCA", str(model["rows"][1]["id"]))
        self.assertIn("CPI EUA", html)
        self.assertIn("30/10/2026", html)
        self.assertIn("Período", html)
        self.assertNotIn("previsão de compra", html)

    def test_template_no_data_never_claims_current_values(self):
        html = official_macro_html(None)
        self.assertIn("DESATIVADO", html)
        self.assertIn("—", html)
        self.assertIn("Nenhuma observação foi simulada", html)
        markup = trader_radar_html(selected="master")
        self.assertIn("Indicadores oficiais · Brasil e EUA", markup)
        self.assertIn("Meta Selic", markup)
        self.assertIn('data-visual-reference="approved-20261102-v1"', markup)

    def test_malformed_future_or_nan_response_no_fake_values(self):
        out = normalize_series(
            "BR_IPCA_12M",
            [{"data": "31/12/2026", "valor": "4,30"},
             {"data": "01/09/2026", "valor": "NaN"}], at=NOW)
        self.assertIsNone(out["value"])
        self.assertNotEqual(out["state"], "VALIDADO")


if __name__ == "__main__":
    unittest.main()
