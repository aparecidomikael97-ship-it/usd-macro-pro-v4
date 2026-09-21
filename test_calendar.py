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
from atlasquant_nowcast_antecedents import (
    build_target_antecedents,
    definitely_future_target,
    normalize_economic_event,
    normalize_economic_events,
    target_catalog,
    upcoming_targets,
)
from atlasquant_live_nowcast import (
    completed_history,
    sync_live_nowcasts,
    summarize_live_nowcasts,
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


class AtlasQuantLiveAntecedentTests(unittest.TestCase):
    def _event(self,name,dt,actual=None,estimate=None,previous=None,comparison=None,period=None):
        return {
            "type":name,
            "date":dt,
            "actual":actual,
            "estimate":estimate,
            "previous":previous,
            "comparison":comparison,
            "period":period,
            "country":"US",
        }

    def test_naive_provider_time_is_marked_unknown_and_same_day_target_is_blocked(self):
        raw=self._event(
            "Nonfarm Payrolls","2026-10-02 12:30:00",
            actual=None,estimate=150,previous=140,
        )
        event=normalize_economic_event(raw)
        self.assertIsNotNone(event)
        self.assertFalse(event.timezone_known)
        same_day=datetime(2026,10,2,8,0,tzinfo=timezone.utc)
        self.assertFalse(definitely_future_target(event,same_day))
        next_day=datetime(2026,10,1,20,0,tzinfo=timezone.utc)
        self.assertTrue(definitely_future_target(event,next_day))

    def test_payroll_antecedents_use_adp_claims_and_ism_with_correct_claims_polarity(self):
        capture=datetime(2026,10,1,18,0,tzinfo=timezone.utc)
        rows=normalize_economic_events([
            self._event("ADP Employment Change","2026-09-30 12:15:00",actual=100,estimate=50,previous=80),
            self._event("Initial Jobless Claims","2026-09-29 12:30:00",actual=250,estimate=230,previous=225),
            self._event("ISM Manufacturing Employment","2026-09-28 14:00:00",actual=52,estimate=50,previous=49),
            self._event("ISM Services Employment","2026-09-27 14:00:00",actual=51,estimate=50,previous=50),
        ])
        out=build_target_antecedents("PAYROLL",rows,captured_at=capture)
        self.assertEqual(out["state"],"READY")
        self.assertEqual(out["signal_count"],4)
        by={x["key"]:x for x in out["provenance"]}
        self.assertGreater(by["ADP"]["direction_score"],0)
        self.assertLess(by["INITIAL_CLAIMS"]["direction_score"],0)
        self.assertGreater(by["ISM_MFG_EMPLOYMENT"]["direction_score"],0)
        self.assertGreater(by["ISM_SERVICES_EMPLOYMENT"]["direction_score"],0)
        self.assertFalse(out["weights_calibrated"])
        self.assertFalse(out["automatic_weight_change"])
        self.assertFalse(out["lookahead_used"])

    def test_pce_does_not_double_count_core_cpi_as_headline_cpi(self):
        capture=datetime(2026,10,20,18,0,tzinfo=timezone.utc)
        rows=normalize_economic_events([
            self._event("Core CPI","2026-10-15 12:30:00",actual=3.3,estimate=3.1,previous=3.2,comparison="yoy"),
            self._event("CPI","2026-10-15 12:30:00",actual=2.8,estimate=2.7,previous=2.7,comparison="yoy"),
            self._event("Core PPI","2026-10-16 12:30:00",actual=3.0,estimate=2.8,previous=2.9,comparison="yoy"),
            self._event("PPI","2026-10-16 12:30:00",actual=2.5,estimate=2.4,previous=2.4,comparison="yoy"),
        ])
        out=build_target_antecedents("PCE",rows,captured_at=capture)
        keys=[x["key"] for x in out["provenance"]]
        self.assertEqual(keys.count("CPI"),1)
        self.assertEqual(keys.count("CORE_CPI"),1)
        self.assertEqual(keys.count("PPI"),1)
        self.assertEqual(keys.count("CORE_PPI"),1)
        ids=[x["event_id"] for x in out["provenance"]]
        self.assertEqual(len(ids),len(set(ids)))

    def test_upcoming_targets_require_consensus_and_no_actual(self):
        capture=datetime(2026,10,1,12,0,tzinfo=timezone.utc)
        events=normalize_economic_events([
            self._event("Nonfarm Payrolls","2026-10-02 12:30:00",actual=None,estimate=150,previous=140),
            self._event("CPI","2026-10-03 12:30:00",actual=None,estimate=None,previous=2.8,comparison="yoy"),
            self._event("PCE Price Index","2026-10-04 12:30:00",actual=2.7,estimate=2.6,previous=2.5,comparison="yoy"),
        ])
        targets=upcoming_targets(events,captured_at=capture,horizon_days=7)
        self.assertEqual(len(targets),1)
        self.assertEqual(targets[0][1].key,"PAYROLL")

    def test_catalog_exposes_payroll_cpi_and_pce_targets(self):
        targets={x["target"] for x in target_catalog()}
        self.assertTrue({"PAYROLL","CPI","CORE_CPI","PCE","CORE_PCE"}.issubset(targets))


class AtlasQuantLiveNowcastLedgerTests(unittest.TestCase):
    def _event(self,name,dt,actual=None,estimate=None,previous=None,comparison=None,period=None):
        return {
            "type":name,"date":dt,"actual":actual,"estimate":estimate,
            "previous":previous,"comparison":comparison,"period":period,"country":"US",
        }

    def _pre_release_events(self,target_actual=None):
        return [
            self._event("ADP Employment Change","2026-09-30 12:15:00",actual=100,estimate=50,previous=80),
            self._event("Initial Jobless Claims","2026-09-29 12:30:00",actual=220,estimate=230,previous=225),
            self._event("ISM Manufacturing Employment","2026-09-28 14:00:00",actual=52,estimate=50,previous=49),
            self._event(
                "Nonfarm Payrolls","2026-10-02 12:30:00",
                actual=target_actual,estimate=150,previous=140,period="Sep",
            ),
        ]

    def test_live_ledger_freezes_one_snapshot_per_event_per_day(self):
        now=datetime(2026,10,1,12,0,tzinfo=timezone.utc)
        ledger,cycle=sync_live_nowcasts(
            self._pre_release_events(),
            now=now,min_history=5,min_analogs=2,
        )
        self.assertEqual(len(ledger),1)
        self.assertEqual(cycle["new_snapshots"],1)
        self.assertEqual(ledger.iloc[0]["indicator"],"PAYROLL")
        self.assertGreater(float(ledger.iloc[0]["signal_count"]),0)
        self.assertEqual(ledger.iloc[0]["nowcast_state"],"INSUFFICIENT_HISTORY")
        self.assertFalse(bool(ledger.iloc[0]["lookahead_used"]))

        repeated,cycle2=sync_live_nowcasts(
            self._pre_release_events(),ledger,now=now+timedelta(hours=4),
            min_history=5,min_analogs=2,
        )
        self.assertEqual(len(repeated),1)
        self.assertEqual(cycle2["new_snapshots"],0)

    def test_next_day_can_freeze_new_snapshot_for_same_release(self):
        first,_=sync_live_nowcasts(
            self._pre_release_events(),
            now=datetime(2026,9,30,10,0,tzinfo=timezone.utc),
            min_history=5,min_analogs=2,
        )
        second,_=sync_live_nowcasts(
            self._pre_release_events(),first,
            now=datetime(2026,10,1,10,0,tzinfo=timezone.utc),
            min_history=5,min_analogs=2,
        )
        self.assertEqual(len(second),2)
        self.assertEqual(second["event_id"].nunique(),1)
        self.assertEqual(second["capture_day"].nunique(),2)

    def test_first_observed_actual_closes_all_snapshots_without_rewriting_forecast(self):
        first,_=sync_live_nowcasts(
            self._pre_release_events(),
            now=datetime(2026,9,30,10,0,tzinfo=timezone.utc),
            min_history=5,min_analogs=2,
        )
        second,_=sync_live_nowcasts(
            self._pre_release_events(),first,
            now=datetime(2026,10,1,10,0,tzinfo=timezone.utc),
            min_history=5,min_analogs=2,
        )
        original_scores=second["signal_score"].tolist()
        closed,cycle=sync_live_nowcasts(
            self._pre_release_events(target_actual=175),second,
            now=datetime(2026,10,3,10,0,tzinfo=timezone.utc),
            min_history=5,min_analogs=2,
        )
        self.assertEqual(cycle["closed_now"],2)
        self.assertTrue(all(bool(x) for x in closed["closed"]))
        self.assertTrue(all(float(x)==175 for x in closed["actual"]))
        self.assertEqual(closed["signal_score"].tolist(),original_scores)
        self.assertTrue(all(x=="ABOVE" for x in closed["surprise_class"]))

        revised,cycle2=sync_live_nowcasts(
            self._pre_release_events(target_actual=180),closed,
            now=datetime(2026,10,4,10,0,tzinfo=timezone.utc),
            min_history=5,min_analogs=2,
        )
        self.assertEqual(cycle2["closed_now"],0)
        self.assertTrue(all(float(x)==175 for x in revised["actual"]))

    def test_completed_history_uses_latest_snapshot_only_once_per_release(self):
        first,_=sync_live_nowcasts(
            self._pre_release_events(),
            now=datetime(2026,9,30,10,0,tzinfo=timezone.utc),
            min_history=5,min_analogs=2,
        )
        second,_=sync_live_nowcasts(
            self._pre_release_events(),first,
            now=datetime(2026,10,1,10,0,tzinfo=timezone.utc),
            min_history=5,min_analogs=2,
        )
        closed,_=sync_live_nowcasts(
            self._pre_release_events(target_actual=160),second,
            now=datetime(2026,10,3,10,0,tzinfo=timezone.utc),
            min_history=5,min_analogs=2,
        )
        history=completed_history(closed)
        self.assertEqual(len(history),1)
        self.assertEqual(history[0].indicator,"PAYROLL")
        self.assertEqual(history[0].captured_at.date(),date(2026,10,1))

    def test_summary_never_claims_price_reaction_or_execution(self):
        ledger,_=sync_live_nowcasts(
            self._pre_release_events(),
            now=datetime(2026,10,1,10,0,tzinfo=timezone.utc),
            min_history=5,min_analogs=2,
        )
        summary=summarize_live_nowcasts(ledger)
        self.assertFalse(summary["lookahead_used"])
        self.assertFalse(summary["market_reaction_scored"])
        self.assertFalse(summary["automatic_execution"])
        self.assertFalse(summary["automatic_weight_change"])


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
