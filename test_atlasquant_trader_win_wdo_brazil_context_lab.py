"""Brazil macro documentary WIN/WDO contract and anti-lookahead tests."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_trader_win_wdo_brazil_context_lab import (
    SCHEMA, DOCS, EVENTS, build_win_wdo_brazil_context_lab,
)

AT = datetime(2026, 11, 3, 12, tzinfo=timezone.utc)


def build(at=AT, documents=None, events=None):
    return build_win_wdo_brazil_context_lab(
        at=at, documents=documents, events=events,
    )


def row(instrument, horizon="W1", at=AT):
    return next(x for x in build(at)["index_horizons"]
                if x["instrument"] == instrument and x["horizon"] == horizon)


class BrazilContextTests(unittest.TestCase):
    def test_brazil_contract_lab_only(self):
        r = build()
        self.assertEqual(r["schema"], SCHEMA)
        self.assertEqual(r["state"], "LAB_BRAZIL_INDEX_CONTEXT_NO_DIRECTION")

    def test_six_official_readings_and_three_events(self):
        r = build()
        self.assertEqual(r["indicator_count"], 6)
        self.assertEqual(r["local_event_count"], 3)
        self.assertEqual(len(DOCS), 6)
        self.assertEqual(len(EVENTS), 3)

    def test_brazil_selic_is_september_prior_decision(self):
        x = build()["official_facts"]["SELIC_TARGET_20260916"]
        self.assertEqual(x["value_pct"], "13.75")
        self.assertEqual(x["published_on"], "2026-09-16")
        self.assertEqual(x["reference_period"], "2026-09-17")

    def test_ipca_september_monthly_and_yoy_distinct(self):
        facts = build()["official_facts"]
        self.assertEqual(facts["IPCA_202609_MOM"]["value_pct"], "0.82")
        self.assertEqual(facts["IPCA_202609_YOY"]["value_pct"], "4.58")
        self.assertNotEqual(facts["IPCA_202609_MOM"]["measure"],
                            facts["IPCA_202609_YOY"]["measure"])

    def test_ipca_full_is_not_ipca_15(self):
        facts = build()["official_facts"]
        self.assertEqual(facts["IPCA_202609_MOM"]["indicator"], "IPCA")
        self.assertNotIn("IPCA_15", facts)

    def test_pnad_is_three_month_rolling_not_one_month(self):
        x = build()["official_facts"]["PNAD_202609_ROLLING_UNEMP"]
        self.assertEqual(x["value_pct"], "5.2")
        self.assertEqual(x["reference_period"], "2026-07_TO_2026-09")
        self.assertEqual(x["measure"], "ROLLING_THREE_MONTH_UNEMPLOYMENT_RATE")

    def test_gdp_qoq_and_yoy_not_mixed(self):
        facts = build()["official_facts"]
        self.assertEqual(facts["GDP_2026Q2_QOQ"]["value_pct"], "0.5")
        self.assertEqual(facts["GDP_2026Q2_YOY"]["value_pct"], "2.0")
        self.assertEqual(facts["GDP_2026Q2_QOQ"]["measure"],
                         "SEASONALLY_ADJUSTED_QUARTER_ON_QUARTER")
        self.assertNotEqual(facts["GDP_2026Q2_YOY"]["measure"],
                            facts["GDP_2026Q2_QOQ"]["measure"])

    def test_all_sources_official_bcb_or_ibge(self):
        for item in DOCS:
            self.assertTrue(item["source_url"].startswith(
                ("https://www.bcb.gov.br/", "https://www.ibge.gov.br/")
            ))

    def test_no_independent_retrieval_claim(self):
        for item in build()["official_facts"].values():
            self.assertFalse(item["source_bytes_independently_attested"])

    def test_copom_research_before_nov4_does_not_see_decision(self):
        x = build()["official_facts"]["SELIC_TARGET_20260916"]
        self.assertEqual(x["freshness_state"],
                         "LAST_DOCUMENTED_PREVIOUS_READING")

    def test_copom_nov4_requires_new_decision_review(self):
        at = datetime(2026, 11, 4, 0, tzinfo=timezone.utc)
        x = build(at)["official_facts"]["SELIC_TARGET_20260916"]
        self.assertEqual(x["value_pct"], "13.75")
        self.assertEqual(x["freshness_state"],
                         "COPOM_NEW_DECISION_DAY_REQUIRES_VERIFICATION")

    def test_ipca_nov12_prior_reading_requires_refresh(self):
        at = datetime(2026, 11, 12, 0, tzinfo=timezone.utc)
        x = build(at)["official_facts"]["IPCA_202609_YOY"]
        self.assertEqual(x["value_pct"], "4.58")
        self.assertEqual(x["freshness_state"],
                         "IPCA_NEW_RELEASE_DAY_REQUIRES_VERIFICATION")

    def test_win_wdo_six_distinct_horizon_rows(self):
        rows = build()["index_horizons"]
        self.assertEqual(len(rows), 6)
        self.assertEqual({x["instrument"] for x in rows}, {"WIN", "WDO"})
        self.assertEqual({x["horizon"] for x in rows}, {"D1", "W1", "MN1"})
        self.assertEqual(len({(x["instrument"], x["horizon"])
                              for x in rows}), 6)

    def test_copom_tomorrow_edge_uncertain_with_date_only(self):
        event = row("WIN", "D1")["brasil_upcoming_events"]
        self.assertEqual([x["event_id"] for x in event],
                         ["COPOM_DECISION_20261104"])
        self.assertEqual(event[0]["timing_state"], "WINDOW_EDGE_TIME_UNCERTAIN")

    def test_copom_in_weekly_window(self):
        event = row("WDO", "W1")["brasil_upcoming_events"]
        self.assertEqual([x["event_id"] for x in event],
                         ["COPOM_DECISION_20261104"])
        self.assertEqual(event[0]["timing_state"], "SCHEDULED_WITHIN_WINDOW")

    def test_three_macro_events_inside_monthly(self):
        ids = [x["event_id"] for x in row("WIN", "MN1")["brasil_upcoming_events"]]
        self.assertEqual(ids, [x["id"] for x in EVENTS])

    def test_nov4_intra_day_does_not_falsely_say_copom_future(self):
        at = datetime(2026, 11, 4, 12, tzinfo=timezone.utc)
        events = row("WIN", "D1", at)["brasil_upcoming_events"]
        state = next(x["timing_state"] for x in events
                     if x["event_id"] == "COPOM_DECISION_20261104")
        self.assertEqual(state, "DATE_ONLY_MAY_ALREADY_HAVE_OCCURRED")

    def test_nov5_copom_no_longer_future(self):
        at = datetime(2026, 11, 5, 0, tzinfo=timezone.utc)
        events = row("WIN", "W1", at)["brasil_upcoming_events"]
        self.assertFalse(any(x["event_id"] == "COPOM_DECISION_20261104"
                             for x in events))

    def test_us_calendar_risk_kept_distinct_from_brazil(self):
        r = row("WDO", "W1")
        ids = {x["event_id"] for x in r["us_upcoming_events"]}
        self.assertIn("BLS_US_EMPLOYMENT_20261106", ids)
        self.assertNotIn("COPOM_DECISION_20261104", ids)

    def test_win_and_wdo_do_not_inherit_forex_direction(self):
        for r in build()["index_horizons"]:
            self.assertEqual(r["directional_bias"], "AGUARDAR")
            self.assertIsNone(r["probability_calibrated"])
            self.assertIsNone(r["pre_event_consensus"])
            self.assertFalse(r["trade_authorized"])

    def test_missing_focus_di_flow_fiscal_explicit(self):
        for r in build()["index_horizons"]:
            self.assertFalse(r["focus_vintage_verified"])
            self.assertFalse(r["forward_di_curve_verified"])
            self.assertFalse(r["brazil_fiscal_flow_geo_context_verified"])

    def test_scenario_questions_are_questions_not_facts(self):
        items = build()["scenario_research_questions"]
        self.assertGreaterEqual(len(items), 4)
        self.assertTrue(all(x.endswith("?") for x in items))

    def test_no_promoted_operational_statuses(self):
        r = build()
        for key in (
            "original_source_bytes_archived",
            "independent_source_receipts_verified",
            "point_in_time_consensus_verified",
            "historical_price_independence_proven",
            "accuracy_90_proven", "can_feed_live_radar",
            "trade_authorized", "worker_enabled", "scheduler_enabled",
        ):
            self.assertFalse(r[key], key)

    def test_reject_cpi_numeric_change(self):
        docs = deepcopy(list(DOCS))
        docs[1]["value_pct"] = "99.99"
        with self.assertRaises(ValueError):
            build(documents=docs)

    def test_reject_selic_relocated_before_meeting(self):
        docs = deepcopy(list(DOCS))
        docs[0]["conservative_available_from_utc"] = "2026-09-01T00:00:00Z"
        with self.assertRaises(ValueError):
            build(documents=docs)

    def test_reject_source_hostname_substitution(self):
        docs = deepcopy(list(DOCS))
        docs[2]["source_url"] = "https://www.ibge.gov.br.attacker.invalid"
        with self.assertRaises(ValueError):
            build(documents=docs)

    def test_reject_missing_documents(self):
        with self.assertRaises(ValueError):
            build(documents=list(DOCS)[:-1])

    def test_reject_extra_documents(self):
        with self.assertRaises(ValueError):
            build(documents=list(DOCS) + [deepcopy(DOCS[0])])

    def test_reject_copom_fake_market_consensus_in_calendar(self):
        events = deepcopy(list(EVENTS))
        events[0]["consensus_pct"] = "13.50"
        with self.assertRaises(ValueError):
            build(events=events)

    def test_reject_copom_forged_date(self):
        events = deepcopy(list(EVENTS))
        events[0]["date"] = "2026-11-03"
        with self.assertRaises(ValueError):
            build(events=events)

    def test_reject_missing_date_or_extra_event(self):
        with self.assertRaises(ValueError):
            build(events=list(EVENTS)[:-1])
        with self.assertRaises(ValueError):
            build(events=list(EVENTS) + [deepcopy(EVENTS[0])])

    def test_research_before_nov3_is_forbidden(self):
        with self.assertRaises(ValueError):
            build(at=datetime(2026, 11, 2, 23, 59, tzinfo=timezone.utc))

    def test_naive_clock_rejected(self):
        with self.assertRaises(ValueError):
            build(at=datetime(2026, 11, 3, 12))

    def test_offset_clock_normalized(self):
        at = datetime(2026, 11, 3, 8, tzinfo=timezone(timedelta(hours=-4)))
        self.assertEqual(build(at)["as_of_utc"], AT.isoformat())

    def test_no_network_runtime_code_in_module(self):
        import atlasquant_trader_win_wdo_brazil_context_lab as module
        for name in ("requests", "subprocess", "schedule", "run_worker"):
            self.assertFalse(hasattr(module, name))
