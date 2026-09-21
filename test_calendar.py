from datetime import date, datetime, timedelta, timezone
import unittest

from calendar_core import eod_row, parse_fomc, upcoming, value_text
from atlasquant_news_nowcast import (
    HistoricalRelease,
    LeadingSignal,
    build_empirical_nowcast,
    build_empirical_nowcast_from_score,
    classify_surprise,
    combine_leading_signals,
)
from atlasquant_news_backtest import (
    monthly_news_scores,
    multiclass_brier,
    simple_month_score,
    walk_forward_news_backtest,
)
from atlasquant_news_research_panel import (
    build_news_research_report,
    news_history_template_csv,
    normalize_news_history_csv,
)
from atlasquant_indicator_scenarios import (
    FIELD_GUIDE,
    indicator_catalog,
    indicator_scenario_guide,
    indicator_spec,
)


class CalendarTests(unittest.TestCase):
    def test_fed_dates_and_year_sections(self):
        html = "<h4>2026 FOMC Meetings</h4><b>September</b><div>15-16*</div><h4>2025 FOMC Meetings</h4>September 16-17*"
        rows = parse_fomc(html)
        self.assertEqual({r["date"] for r in rows}, {"2026-09-16", "2025-09-17"})
        self.assertTrue(all("projeções" in r["details"] for r in rows))

    def test_fed_cross_month_and_scripts(self):
        rows = parse_fomc("<script>2026 FOMC Meetings December 1-2</script><h4>2026 FOMC Meetings</h4>Apr/May 30-1")
        self.assertEqual([r["date"] for r in rows], ["2026-05-01"])

    def test_alternative_cross_month_text(self):
        rows = parse_fomc("<h4>2026 FOMC Meetings</h4>April 30-May 1*")
        self.assertEqual(rows[0]["date"], "2026-05-01")
        self.assertIn("projeções", rows[0]["details"])

    def test_unknown_structure_not_invented(self):
        self.assertEqual(parse_fomc("<html>Access denied</html>"), [])
        self.assertEqual(parse_fomc(""), [])

    def test_dedup_meeting_dates(self):
        rows = parse_fomc("<h4>2026 FOMC Meetings</h4>September 15-16* September 15-16*")
        self.assertEqual(len(rows), 1)

    def test_filter_sort_dedup_and_today(self):
        def row(dt):
            return {"Data": dt, "Evento": "FOMC", "Fonte": "Fed"}
        rows = upcoming(
            [row("2026-09-16"), row("2026-09-13"), row("2026-09-12"), row("2026-10-01"), row("2026-09-16")],
            date(2026, 9, 13),
            7,
        )
        self.assertEqual([r["Em dias"] for r in rows], [0, 3])

    def test_negative_window_empty(self):
        self.assertEqual(upcoming([], date(2026, 9, 13), -1), [])

    def test_timezone_not_guessed_and_zero_preserved(self):
        row = eod_row({"date": "2026-09-16 14:00:00", "type": "GDP", "estimate": 0}, "America/Cuiaba")
        self.assertEqual(row["Consenso"], "0")
        self.assertIn("fuso não informado", row["Horário"])
        self.assertEqual(row["Realizado"], "—")

    def test_explicit_timezone_converts_day(self):
        row = eod_row({"date": "2026-09-16T02:00:00Z", "type": "Event"}, "America/Cuiaba")
        self.assertEqual(row["Data"], date(2026, 9, 15))
        self.assertEqual(row["Horário"], "22:00")

    def test_invalid_date_or_timezone_ignored(self):
        self.assertIsNone(eod_row({"date": "invalid"}, "UTC"))
        self.assertIsNone(eod_row({"date": "2026-09-16T02:00:00Z"}, "Bad/Zone"))

    def test_value_text_preserves_zero(self):
        self.assertEqual(value_text(0), "0")
        self.assertEqual(value_text("0.0"), "0.0")
        self.assertEqual(value_text(None), "—")
        self.assertEqual(value_text("nan"), "—")




class AtlasQuantIndicatorScenarioTests(unittest.TestCase):
    def test_previous_consensus_actual_are_explicitly_explained(self):
        self.assertIn("Anterior",FIELD_GUIDE)
        self.assertIn("Consenso",FIELD_GUIDE)
        self.assertIn("Atual",FIELD_GUIDE)
        self.assertIn("expectativa",FIELD_GUIDE["Consenso"].lower())

    def test_payroll_scenarios_are_specific_and_contextual(self):
        guide=indicator_scenario_guide("US Non Farm Payrolls")
        self.assertTrue(guide["recognized"])
        self.assertEqual(guide["indicator_id"],"nfp")
        self.assertIn("salários",guide["caveat"].lower())
        self.assertFalse(guide["price_reaction_guaranteed"])
        self.assertFalse(guide["automatic_execution"])
        self.assertIn("consenso",guide["scenarios"]["ABOVE"]["label"].lower())

    def test_unemployment_and_claims_do_not_use_wrong_higher_is_better_rule(self):
        unemployment=indicator_scenario_guide("Unemployment Rate")
        claims=indicator_scenario_guide("Initial Jobless Claims")
        self.assertIn("mais fraco",unemployment["scenarios"]["ABOVE"]["macro_context"].lower())
        self.assertIn("fragilidade",claims["scenarios"]["ABOVE"]["macro_context"].lower())

    def test_adp_warns_it_is_not_infallible_nfp_forecast(self):
        guide=indicator_scenario_guide("ADP Employment Change")
        self.assertTrue(guide["recognized"])
        self.assertIn("não é uma previsão direta",guide["caveat"].lower())

    def test_unknown_event_fails_closed_without_generic_direction(self):
        guide=indicator_scenario_guide("Mystery Index")
        self.assertFalse(guide["recognized"])
        self.assertEqual(guide["scenarios"],{})
        self.assertIn("não aplica",guide["interpretation"].lower())

    def test_catalog_has_core_indicator_families(self):
        ids={x["id"] for x in indicator_catalog()}
        self.assertTrue({"cpi","pce","nfp","unemployment","jobless-claims","adp","ppi","pmi-ism","gdp"}.issubset(ids))


class AtlasQuantNewsNowcastTests(unittest.TestCase):
    def _history(self,n=60,indicator="PAYROLL"):
        start=datetime(2025,1,1,13,30,tzinfo=timezone.utc)
        rows=[]
        pattern=[(-0.8,-1.0),(0.0,0.0),(0.8,1.0)]
        for i in range(n):
            score,surprise=pattern[i%3]
            scheduled=start+timedelta(days=i*3)
            rows.append(HistoricalRelease(
                indicator=indicator,
                scheduled_at=scheduled,
                captured_at=scheduled-timedelta(hours=12),
                consensus=100.0,
                actual=100.0+surprise,
                signal_score=score,
                tolerance=0.1,
                unit="k",
            ))
        return rows

    def test_surprise_classification_uses_explicit_tolerance(self):
        self.assertEqual(classify_surprise(101,100,0.1),"ABOVE")
        self.assertEqual(classify_surprise(99,100,0.1),"BELOW")
        self.assertEqual(classify_surprise(100.05,100,0.1),"INLINE")

    def test_leading_signals_are_point_in_time_and_weighted(self):
        capture=datetime(2026,9,20,12,0,tzinfo=timezone.utc)
        out=combine_leading_signals([
            LeadingSignal("ADP",capture-timedelta(hours=2),0.8,2.0),
            LeadingSignal("Claims",capture-timedelta(hours=1),-0.2,1.0),
        ],captured_at=capture)
        self.assertEqual(out["state"],"READY")
        self.assertAlmostEqual(out["signal_score"],(0.8*2-0.2)/3,places=6)
        self.assertFalse(out["lookahead_used"])

        with self.assertRaises(ValueError):
            combine_leading_signals([
                LeadingSignal("future",capture+timedelta(minutes=1),1.0,1.0),
            ],captured_at=capture)

    def test_nowcast_refuses_percentages_when_history_is_insufficient(self):
        history=self._history(8)
        capture=history[-1].scheduled_at+timedelta(days=10)
        out=build_empirical_nowcast_from_score(
            indicator="PAYROLL",consensus=100,captured_at=capture,
            signal_score=0.8,history=history,min_history=20,min_analogs=5,
        )
        self.assertEqual(out["state"],"INSUFFICIENT_HISTORY")
        self.assertIsNone(out["probabilities"])
        self.assertIsNone(out["estimate"])
        self.assertFalse(out["automatic_execution"])

    def test_empirical_nowcast_uses_same_indicator_historical_analogs(self):
        history=self._history(60)
        capture=history[-1].scheduled_at+timedelta(days=10)
        out=build_empirical_nowcast_from_score(
            indicator="PAYROLL",consensus=100,captured_at=capture,
            signal_score=0.8,history=history,min_history=30,min_analogs=10,
            bandwidth=0.05,alpha=1,
        )
        self.assertEqual(out["state"],"RESEARCH_ESTIMATE")
        self.assertEqual(out["top_class"],"ABOVE")
        self.assertGreater(out["probabilities"]["ABOVE"],0.8)
        self.assertAlmostEqual(sum(out["probabilities"].values()),1.0,places=5)
        self.assertFalse(out["calibrated"])
        self.assertIsNone(out["profit_probability"])
        self.assertFalse(out["market_reaction_predicted"])
        self.assertFalse(out["lookahead_used"])

    def test_full_nowcast_combines_pre_release_signals_without_market_claim(self):
        history=self._history(60)
        capture=history[-1].scheduled_at+timedelta(days=10)
        out=build_empirical_nowcast(
            indicator="PAYROLL",consensus=100,captured_at=capture,
            signals=[
                LeadingSignal("ADP",capture-timedelta(days=1),0.9,2),
                LeadingSignal("ISM employment",capture-timedelta(hours=8),0.6,1),
            ],
            history=history,min_history=30,min_analogs=10,bandwidth=0.3,
        )
        self.assertEqual(out["state"],"RESEARCH_ESTIMATE")
        self.assertEqual(out["leading_signals"]["state"],"READY")
        self.assertFalse(out["market_reaction_predicted"])


class AtlasQuantNewsResearchPanelTests(unittest.TestCase):
    def test_template_contains_point_in_time_fields(self):
        template=news_history_template_csv()
        for field in (
            "indicator","scheduled_at","captured_at","consensus",
            "actual","signal_score","tolerance",
        ):
            self.assertIn(field,template)

    def test_normalizer_accepts_aliases_and_rejects_post_release_capture(self):
        import pandas as pd
        frame=pd.DataFrame([
            {
                "evento":"PAYROLL",
                "event_time":"2026-09-04T12:30:00Z",
                "snapshot_time":"2026-09-03T18:00:00Z",
                "consenso":155,
                "atual":165,
                "leading_score":0.5,
                "tolerancia":5,
            },
            {
                "evento":"PAYROLL",
                "event_time":"2026-10-02T12:30:00Z",
                "snapshot_time":"2026-10-02T13:00:00Z",
                "consenso":150,
                "atual":149,
                "leading_score":-0.1,
                "tolerancia":5,
            },
        ])
        out=normalize_news_history_csv(frame)
        self.assertEqual(out["accepted"],1)
        self.assertEqual(out["rejected"],1)
        self.assertIn("captured_at histórico deve ser anterior",out["errors"][0])

    def test_report_keeps_news_accuracy_separate_from_market_reaction(self):
        start=datetime(2025,1,1,13,30,tzinfo=timezone.utc)
        records=[]
        for i in range(30):
            score=(-0.8,0.0,0.8)[i%3]
            surprise=(-1.0,0.0,1.0)[i%3]
            scheduled=start+timedelta(days=i*3)
            records.append(HistoricalRelease(
                indicator="PAYROLL",
                scheduled_at=scheduled,
                captured_at=scheduled-timedelta(hours=12),
                consensus=100,
                actual=100+surprise,
                signal_score=score,
                tolerance=0.1,
            ))
        report=build_news_research_report(
            records,min_history=9,min_analogs=3,bandwidth=0.05
        )
        self.assertGreater(report["backtest"]["forecast_samples"],10)
        self.assertFalse(report["market_reaction_scored"])
        self.assertFalse(report["real_orders_enabled"])
        self.assertFalse(report["trading_news_enabled"])
        self.assertFalse(report["automatic_weight_change"])


class AtlasQuantNewsBacktestTests(unittest.TestCase):
    def _history(self,n=60):
        start=datetime(2025,1,1,13,30,tzinfo=timezone.utc)
        rows=[]
        pattern=[(-0.8,-1.0),(0.0,0.0),(0.8,1.0)]
        for i in range(n):
            score,surprise=pattern[i%3]
            scheduled=start+timedelta(days=i*3)
            rows.append(HistoricalRelease(
                indicator="PAYROLL",
                scheduled_at=scheduled,
                captured_at=scheduled-timedelta(hours=12),
                consensus=100.0,
                actual=100.0+surprise,
                signal_score=score,
                tolerance=0.1,
            ))
        return rows

    def test_multiclass_brier_is_zero_for_perfect_forecast(self):
        self.assertAlmostEqual(
            multiclass_brier({"BELOW":0,"INLINE":0,"ABOVE":1},"ABOVE"),
            0.0,
            places=9,
        )

    def test_walk_forward_uses_only_prior_releases_and_separates_data_from_market(self):
        bt=walk_forward_news_backtest(
            self._history(),
            min_history=9,
            min_analogs=3,
            bandwidth=0.05,
            alpha=0.2,
        )
        self.assertGreater(bt["forecast_samples"],30)
        self.assertEqual(bt["overall"]["class_accuracy_pct"],100.0)
        self.assertFalse(bt["lookahead_used"])
        self.assertFalse(bt["market_reaction_scored"])
        self.assertIsNone(bt["profit_probability"])
        self.assertFalse(bt["automatic_execution"])
        for row in bt["forecasts"]:
            self.assertFalse(row["lookahead_used"])
            self.assertLess(row["captured_at"],row["scheduled_at"])

    def test_monthly_scorecards_expose_hits_without_calling_them_trades(self):
        bt=walk_forward_news_backtest(
            self._history(30),
            min_history=9,min_analogs=3,bandwidth=0.05,alpha=0.2,
        )
        rows=monthly_news_scores(bt)
        self.assertTrue(rows)
        self.assertEqual(sum(x["samples"] for x in rows),bt["forecast_samples"])
        self.assertTrue(all(" de " in x["score_text"] for x in rows))
        self.assertTrue(all("não é taxa de gain" in x["interpretation"].lower() for x in rows))

    def test_month_score_is_classification_not_gain_rate(self):
        bt=walk_forward_news_backtest(
            self._history(30),
            min_history=9,min_analogs=3,bandwidth=0.05,alpha=0.2,
        )
        score=simple_month_score(bt)
        self.assertEqual(score["hits"],score["samples"])
        self.assertIn("de",score["text"])
        self.assertIn("não é taxa de gain",score["interpretation"].lower())

if __name__ == "__main__":
    unittest.main()
