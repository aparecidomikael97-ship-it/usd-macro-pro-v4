import unittest

from atlasquant_geopolitical_engine import build_geopolitical_context


class GeopoliticalEngineTests(unittest.TestCase):
    def test_non_geopolitical_macro_headlines_do_not_create_signal(self):
        state={"currencies":{
            "EUR":{"articles":[{"title":"Euro area CPI inflation slows","weighted_impact":-0.2}]},
            "USD":{"articles":[{"title":"US payroll growth beats expectations","weighted_impact":0.3}]},
        }}
        out=build_geopolitical_context("EUR/USD",state)
        self.assertFalse(out["available"])
        self.assertEqual(out["direction"],"INDISPONÍVEL")
        self.assertEqual(out["event_count"],0)
        self.assertGreaterEqual(out["dropped_non_geo"],2)

    def test_same_global_story_is_deduplicated_across_pair_currencies(self):
        base={
            "story_id":"S001",
            "title":"Geopolitical tensions escalate after military attack and new sanctions",
            "source":"Reuters",
            "recency_factor":1.0,
            "source_factor":1.15,
            "independence_factor":0.8,
        }
        state={"currencies":{
            "EUR":{"articles":[{**base,"weighted_impact":-0.35}]},
            "USD":{"articles":[{**base,"weighted_impact":0.20}]},
        }}
        out=build_geopolitical_context("EUR/USD",state)
        self.assertTrue(out["available"])
        self.assertEqual(out["event_count"],1)
        self.assertEqual(out["independent_stories"],1)
        event=out["events"][0]
        self.assertIn("EUR",event["currency_impacts"])
        self.assertIn("USD",event["currency_impacts"])
        self.assertLess(event["direct_pair_balance"],0)

    def test_structured_event_uses_explicit_currency_impacts_severity_and_duration(self):
        state={"geopolitical_events":[{
            "event_id":"G1",
            "title":"Shipping route disruption after maritime attack",
            "category":"shipping",
            "source":"Verified wire",
            "quality":92,
            "severity":"high",
            "duration":"medium",
            "channels":["shipping","energy"],
            "currency_impacts":{"EUR":-55,"USD":20},
            "fresh":True,
        }]}
        out=build_geopolitical_context("EUR/USD",state)
        self.assertTrue(out["available"])
        self.assertEqual(out["direction"],"VENDA")
        self.assertEqual(out["severity"],"ALTO")
        self.assertIn("shipping",out["channels"])
        self.assertEqual(out["events"][0]["duration_label"],"MÉDIO")
        self.assertLess(out["events"][0]["direct_pair_balance"],0)

    def test_explicit_pair_impact_and_geography_take_priority_without_inference(self):
        state={"geopolitical_events":[{
            "event_id":"PAIR-1",
            "title":"Trade restrictions expand across shipping corridor",
            "category":"trade",
            "source":"Verified wire",
            "quality":94,
            "severity":"high",
            "duration":"long",
            "risk_regime":"neutral",
            "pair_impacts":{"EUR/USD":-70},
            "regions":["Europe"],
            "countries":["Country A","Country B"],
            "commodities":["natural gas"],
        }]}
        out=build_geopolitical_context("EUR/USD",state)
        self.assertTrue(out["available"])
        event=out["events"][0]
        self.assertTrue(event["pair_impact_explicit"])
        self.assertEqual(event["direct_pair_balance"],-70.0)
        self.assertIn("Europe",out["regions"])
        self.assertIn("natural gas",out["commodities"])
        self.assertEqual(out["risk_regime"],"MISTO/NEUTRO")

    def test_one_story_is_available_but_low_confidence_risk_is_visible(self):
        state={"geopolitical_events":[{
            "event_id":"G2",
            "title":"New sanctions announced after geopolitical conflict",
            "category":"sanctions",
            "source":"Wire",
            "quality":80,
            "severity":"medium",
            "duration":"short",
            "currency_impacts":{"GBP":-30,"USD":10},
        }]}
        out=build_geopolitical_context("GBP/USD",state)
        self.assertTrue(out["available"])
        self.assertEqual(out["event_count"],1)
        self.assertTrue(any("única história" in x for x in out["risks"]))
        self.assertLess(out["quality"],80)

    def test_deescalation_changes_regime_without_claiming_political_outcome(self):
        state={"geopolitical_events":[{
            "event_id":"G3",
            "title":"Ceasefire and diplomatic agreement announced",
            "category":"diplomacy",
            "source":"Wire A",
            "quality":88,
            "severity":"medium",
            "duration":"short",
        },{
            "event_id":"G4",
            "title":"Peace talks continue under truce",
            "category":"deescalation",
            "source":"Wire B",
            "quality":85,
            "severity":"medium",
            "duration":"short",
        }]}
        out=build_geopolitical_context("AUD/JPY",state)
        self.assertTrue(out["available"])
        self.assertEqual(out["risk_regime"],"DESCOMPRESSÃO")
        self.assertFalse(out["probability"])
        self.assertFalse(out["decision_effect"])

    def test_opposing_explicit_events_are_flagged_as_conflict(self):
        state={"geopolitical_events":[{
            "event_id":"A",
            "title":"Trade restrictions announced",
            "category":"trade",
            "source":"Source A",
            "quality":90,
            "severity":"high",
            "duration":"medium",
            "currency_impacts":{"AUD":60,"USD":-10},
        },{
            "event_id":"B",
            "title":"New sanctions announced",
            "category":"sanctions",
            "source":"Source B",
            "quality":90,
            "severity":"high",
            "duration":"medium",
            "currency_impacts":{"AUD":-60,"USD":10},
        }]}
        out=build_geopolitical_context("AUD/USD",state)
        self.assertTrue(out["geo_conflict"])
        self.assertTrue(any("impactos opostos" in x for x in out["risks"]))
        self.assertLess(out["quality"],90)

    def test_commodity_or_channel_context_does_not_invent_direct_fx_impact(self):
        state={"geopolitical_events":[{
            "event_id":"E1",
            "title":"Energy supply disruption after pipeline attack",
            "category":"energy",
            "source":"Wire",
            "quality":90,
            "severity":"high",
            "duration":"medium",
            "channels":["oil"],
        }]}
        out=build_geopolitical_context("CAD/USD",state)
        self.assertTrue(out["available"])
        event=out["events"][0]
        self.assertEqual(event["currency_impacts"],{})
        self.assertEqual(event["direct_pair_balance"],0.0)
        self.assertTrue(any("sem impacto cambial explícito" in x for x in out["risks"]))

    def test_stale_event_is_excluded(self):
        state={"geopolitical_events":[{
            "event_id":"OLD",
            "title":"Military attack escalates conflict",
            "category":"conflict",
            "source":"Wire",
            "quality":90,
            "severity":"high",
            "duration":"medium",
            "fresh":False,
            "currency_impacts":{"EUR":-50,"USD":20},
        }]}
        out=build_geopolitical_context("EUR/USD",state)
        self.assertFalse(out["available"])

    def test_critical_uncorroborated_event_creates_advisory_blocker(self):
        state={"geopolitical_events":[{
            "event_id":"CRIT-1",
            "title":"Major escalation after invasion",
            "category":"conflict",
            "source":"Single source",
            "quality":90,
            "severity":"critical",
            "duration":"long",
            "currency_impacts":{"EUR":-70,"USD":25},
        }]}
        out=build_geopolitical_context("EUR/USD",state)
        self.assertTrue(out["available"])
        self.assertEqual(out["severity"],"CRÍTICO")
        self.assertTrue(out["research_blockers"])
        self.assertTrue(any("CORROBORAÇÃO" in x for x in out["research_blockers"]))
        self.assertFalse(out["changes_gate"])

    def test_never_changes_operational_controls(self):
        state={"geopolitical_events":[{
            "event_id":"SAFE",
            "title":"Blockade raises geopolitical tensions",
            "category":"shipping",
            "source":"Wire",
            "quality":90,
            "severity":"high",
            "duration":"medium",
            "currency_impacts":{"EUR":-50,"USD":20},
        }]}
        out=build_geopolitical_context("EUR/USD",state)
        self.assertFalse(out["probability"])
        self.assertFalse(out["decision_effect"])
        self.assertFalse(out["changes_gate"])
        self.assertFalse(out["changes_score_mestre"])
        self.assertFalse(out["changes_weights"])
        self.assertFalse(out["real_orders_enabled"])
        self.assertFalse(out["automatic_execution"])


if __name__=="__main__":
    unittest.main()