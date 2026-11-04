"""Official page identity is never equivalent to verified macro/event data."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import unittest

from atlasquant_trader_g8_country_macro_catalog_lab import (
    build_g8_country_macro_candidate_catalog_lab,
)
from atlasquant_trader_macro_pit_documentation_link_lab import (
    SCHEMA, inspect_macro_pit_documentation_link_lab,
)

ISSUED_PRE = datetime(2026, 11, 4, 12, tzinfo=timezone.utc)
AT_PRE = datetime(2026, 11, 4, 14, tzinfo=timezone.utc)
ISSUED_POST = datetime(2026, 11, 5, 13, 40, tzinfo=timezone.utc)
AT_POST = datetime(2026, 11, 5, 14, tzinfo=timezone.utc)


def url(currency: str, group: str) -> str:
    return next(x["source_info_url"] for x in
                build_g8_country_macro_candidate_catalog_lab()["candidates"]
                if x["currency"] == currency and x["group"] == group)


def pre() -> dict:
    return {
        "state": "LAB_SYNTHETIC_MACRO_PRE", "event_id": "USD-CPI-LAB-001",
        "currency": "USD", "indicator_id": "CPI", "unit": "PERCENT",
        "source": "BLS labelled synthetic", "previous": 2.5, "consensus": 2.7,
        "previous_captured_at_utc": "2026-11-03T11:00:00+00:00",
        "consensus_captured_at_utc": "2026-11-04T10:00:00+00:00",
        "scheduled_release_at_utc": "2026-11-05T13:30:00+00:00",
        "deadband_predeclared": 0.1,
    }


def post() -> dict:
    return {
        "state": "LAB_SYNTHETIC_MACRO_ACTUAL",
        "event_id": "USD-CPI-LAB-001", "source": "BLS labelled synthetic",
        "actual": 3.0, "released_at_utc": "2026-11-05T13:30:00+00:00",
        "captured_at_utc": "2026-11-05T13:32:00+00:00",
    }


class PITOfficialDocumentationLinkLabTests(unittest.TestCase):
    def link(self, p=None, a=None, *, landing=None,
             issued=ISSUED_PRE, evaluated=AT_PRE):
        return inspect_macro_pit_documentation_link_lab(
            pre() if p is None else p, a,
            documentation_url=url("USD", "INFLATION") if landing is None else landing,
            forecast_issued_at=issued, evaluated_at=evaluated,
        )

    def test_pre_release_documentation_match_is_still_not_real_bias(self) -> None:
        p = pre(); before = deepcopy(p)
        out = self.link(p)
        self.assertEqual(p, before)
        self.assertEqual(out["schema"], SCHEMA)
        self.assertEqual(out["state"], "LAB_DOCUMENTATION_LINKED_UNATTESTED")
        self.assertTrue(out["official_landing_page_identified"])
        self.assertEqual(out["currency"], "USD")
        self.assertEqual(out["fundamental_group"], "INFLATION")
        self.assertEqual(out["event"]["kind"], "MACRO_SCHEDULE_ONLY")
        self.assertIsNone(out["event"]["actual_synthetic"])
        self.assertIsNone(out["event"]["surprise_synthetic"])
        self.assertEqual(out["operational_bias"],
                         {"D1": "AGUARDAR", "W1": "AGUARDAR", "MN1": "AGUARDAR"})
        for field in ("source_content_authenticated",
                      "release_and_consensus_vintages_attested",
                      "provider_license_verified", "can_feed_live_radar",
                      "trade_authorized", "publishable"):
            self.assertFalse(out[field])

    def test_post_release_surprise_is_numeric_not_currency_direction(self) -> None:
        out = self.link(a=post(), issued=ISSUED_POST, evaluated=AT_POST)
        self.assertEqual(out["state"], "LAB_DOCUMENTATION_LINKED_UNATTESTED")
        self.assertEqual(out["event"]["kind"], "MACRO_ACTUAL_RELEASED")
        self.assertAlmostEqual(out["event"]["surprise_synthetic"], 0.3)
        self.assertEqual(out["event"]["surprise_relation_synthetic"], "ABOVE_CONSENSUS")
        self.assertEqual(out["macro_direction"], "UNDETERMINED")
        self.assertFalse(out["can_feed_live_radar"])

    def test_future_actual_cannot_leak_into_pre_release_forecast(self) -> None:
        out = self.link(a=post())
        self.assertEqual(out["state"], "LAB_BLOCKED")
        self.assertTrue(out["reason"].startswith("PIT_REFUSED:"))
        self.assertFalse(out["official_landing_page_identified"])

    def test_official_page_of_wrong_currency_or_group_is_not_evidence(self) -> None:
        for wrong in (url("EUR", "INFLATION"), url("USD", "EMPLOYMENT"),
                      "https://www.bls.gov/other/", "http://www.bls.gov/"):
            with self.subTest(wrong=wrong):
                out = self.link(landing=wrong)
                self.assertEqual(out["reason"],
                                 "DOCUMENTATION_PAGE_DOES_NOT_MATCH_CURRENCY_AND_GROUP")
                self.assertFalse(out["trade_authorized"])

    def test_indicator_must_be_preselected_for_country_and_group(self) -> None:
        p = pre(); p["indicator_id"] = "CORE_CPI"
        self.assertEqual(self.link(p)["reason"], "UNSELECTED_INDICATOR_OR_UNIT")
        p = pre(); p["unit"] = "INDEX"
        self.assertEqual(self.link(p)["reason"], "UNSELECTED_INDICATOR_OR_UNIT")

    def test_schema_cannot_carry_extra_claims_or_unsigned_fields(self) -> None:
        p = pre(); p["source_authenticated"] = True
        out = self.link(p)
        self.assertTrue(out["reason"].startswith("PIT_REFUSED:"))
        self.assertEqual(out["state"], "LAB_BLOCKED")

    def test_released_event_wrong_id_is_blocked(self) -> None:
        a = post(); a["event_id"] = "FAKE-CPI-REPORT"
        self.assertEqual(self.link(a=a, issued=ISSUED_POST,
                                   evaluated=AT_POST)["state"], "LAB_BLOCKED")

    def test_timezone_required(self) -> None:
        with self.assertRaises(ValueError):
            self.link(issued=ISSUED_PRE.replace(tzinfo=None))

    def test_all_32_catalog_pages_are_research_leads_only(self) -> None:
        cat = build_g8_country_macro_candidate_catalog_lab()
        self.assertEqual(len(cat["candidates"]), 32)
        for row in cat["candidates"]:
            self.assertTrue(row["source_info_url"].startswith("https://"))
            self.assertFalse(row["source_page_is_live_feed"])
            self.assertFalse(row["allowed_for_live_bias"])


if __name__ == "__main__":
    unittest.main()
