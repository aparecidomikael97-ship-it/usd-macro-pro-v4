import unittest

from atlasquant_macro_engine import build_structured_macro, ranking_rows_to_currency_context, economic_rows_to_indicators


def comp(score, quality=90, **extra):
    out={"score":score,"quality":quality,"fresh":True}
    out.update(extra)
    return out


class StructuredMacroEngineTests(unittest.TestCase):
    def test_structured_pair_uses_independent_core_groups(self):
        ctx={"currencies":{
            "EUR":{
                "rates":comp(42),"inflation":comp(45),"growth":comp(40),
            },
            "USD":{
                "rates":comp(75),"inflation":comp(68),"growth":comp(60),
            },
        }}
        out=build_structured_macro("EUR/USD",ctx,legacy_balance=-10,legacy_quality=80)
        self.assertTrue(out["available"])
        self.assertEqual(out["mode"],"structured")
        self.assertEqual(out["direction"],"VENDA")
        self.assertLess(out["balance"],-12)
        self.assertGreaterEqual(out["coverage"],50)
        self.assertEqual({x["group"] for x in out["groups"]},{"rates","inflation","growth"})

    def test_missing_quote_component_is_not_fake_neutral_evidence(self):
        ctx={"currencies":{
            "EUR":{"rates":comp(70),"inflation":comp(65),"growth":comp(60)},
            "USD":{"rates":comp(40),"growth":comp(50)},
        }}
        out=build_structured_macro("EUR/USD",ctx,legacy_balance=15,legacy_quality=80)
        names={x["group"] for x in out["groups"]}
        self.assertNotIn("inflation",names)
        self.assertIn("rates",names)

    def test_stale_component_is_excluded(self):
        ctx={"currencies":{
            "EUR":{"rates":comp(70),"inflation":comp(60),"growth":comp(60)},
            "USD":{"rates":comp(40),"inflation":comp(50,fresh=False),"growth":comp(50)},
        }}
        out=build_structured_macro("EUR/USD",ctx)
        self.assertNotIn("inflation",{x["group"] for x in out["groups"]})

    def test_actual_vs_consensus_builds_surprise_group(self):
        ctx={
            "currencies":{
                "EUR":{"rates":comp(50),"growth":comp(50)},
                "USD":{"rates":comp(50),"growth":comp(50)},
            },
            "indicators":[{
                "currency":"USD","name":"Core PCE","actual":3.0,"consensus":2.8,
                "previous":2.9,"higher_supports_currency":True,"scale":0.2,
                "quality":90,"fresh":True,
            }],
        }
        out=build_structured_macro("EUR/USD",ctx)
        row=next(x for x in out["groups"] if x["group"]=="expectations")
        self.assertLess(row["balance"],0)
        self.assertTrue(any("Core PCE" in x for x in out["reasons"]))
        self.assertTrue(any("apenas um lado" in x for x in out["risks"]))

    def test_consensus_vs_previous_builds_pre_release_expectation(self):
        ctx={
            "currencies":{
                "GBP":{"rates":comp(50),"growth":comp(50)},
                "USD":{"rates":comp(50),"growth":comp(50)},
            },
            "indicators":[{
                "currency":"USD","name":"NFP","actual":None,"consensus":200,
                "previous":150,"higher_supports_currency":True,"scale":50,
                "quality":80,
            }],
        }
        out=build_structured_macro("GBP/USD",ctx)
        self.assertTrue(any("expectativa" in x for x in out["reasons"]))

    def test_unemployment_rule_can_invert_higher_print(self):
        ctx={
            "currencies":{
                "EUR":{"rates":comp(50),"growth":comp(50)},
                "USD":{"rates":comp(50),"growth":comp(50)},
            },
            "indicators":[{
                "currency":"USD","name":"Unemployment","actual":4.5,"consensus":4.2,
                "higher_supports_currency":False,"scale":0.1,"quality":90,
            }],
        }
        out=build_structured_macro("EUR/USD",ctx)
        row=next(x for x in out["groups"] if x["group"]=="expectations")
        self.assertGreater(row["balance"],0)

    def test_indicator_without_explicit_direction_rule_is_ignored(self):
        ctx={
            "currencies":{
                "EUR":{"rates":comp(50),"growth":comp(50)},
                "USD":{"rates":comp(50),"growth":comp(50)},
            },
            "indicators":[{
                "currency":"USD","name":"Ambiguous release","actual":10,"consensus":8,
                "scale":1,"quality":90,
            }],
        }
        out=build_structured_macro("EUR/USD",ctx)
        self.assertNotIn("expectations",{x["group"] for x in out["groups"]})

    def test_existing_fed_payload_is_compatible(self):
        ctx={
            "currencies":{
                "EUR":{"rates":comp(50),"growth":comp(50)},
                "USD":{"rates":comp(50),"growth":comp(50)},
            },
            "fed":{"tom":"Restritivo","forca":0.8},
        }
        out=build_structured_macro("EUR/USD",ctx)
        row=next(x for x in out["groups"] if x["group"]=="central_bank")
        self.assertLess(row["balance"],0)
        self.assertTrue(any("apenas um lado" in x for x in out["risks"]))

    def test_upcoming_event_is_risk_not_direction(self):
        base_ctx={"currencies":{
            "EUR":{"rates":comp(50),"inflation":comp(50)},
            "USD":{"rates":comp(50),"inflation":comp(50)},
        }}
        out1=build_structured_macro("EUR/USD",base_ctx)
        ctx2=dict(base_ctx)
        ctx2["event"]={"disponivel":True,"evento":"FOMC","impacto":"ALTO"}
        out2=build_structured_macro("EUR/USD",ctx2)
        self.assertEqual(out1["balance"],out2["balance"])
        self.assertTrue(any("FOMC" in x for x in out2["risks"]))

    def test_legacy_fallback_preserves_existing_macro_when_structured_coverage_is_low(self):
        ctx={"currencies":{"EUR":{"rates":comp(60)},"USD":{"rates":comp(50)}}}
        out=build_structured_macro("EUR/USD",ctx,legacy_balance=28,legacy_quality=82)
        self.assertEqual(out["mode"],"legacy_fallback")
        self.assertEqual(out["balance"],28.0)
        self.assertEqual(out["direction"],"COMPRA")

    def test_no_inputs_and_no_legacy_is_unavailable(self):
        out=build_structured_macro("EUR/USD",None)
        self.assertFalse(out["available"])
        self.assertEqual(out["direction"],"INDISPONÍVEL")
        self.assertEqual(out["mode"],"insufficient")

    def test_internal_macro_conflict_is_flagged_and_quality_discounted(self):
        ctx={"currencies":{
            "EUR":{"rates":comp(75),"inflation":comp(70),"growth":comp(25),"activity":comp(30),"labour":comp(30)},
            "USD":{"rates":comp(35),"inflation":comp(40),"growth":comp(70),"activity":comp(68),"labour":comp(65)},
        }}
        out=build_structured_macro("EUR/USD",ctx)
        self.assertTrue(out["macro_conflict"])
        self.assertTrue(any("Divergência interna" in x for x in out["risks"]))
        self.assertTrue(any("Juros/política" in x for x in out["risks"]))
        self.assertLess(out["quality"],90)

    def test_research_engine_never_changes_operational_controls(self):
        ctx={"currencies":{
            "EUR":{"rates":comp(70),"inflation":comp(70),"growth":comp(70)},
            "USD":{"rates":comp(30),"inflation":comp(30),"growth":comp(30)},
        }}
        out=build_structured_macro("EUR/USD",ctx)
        self.assertFalse(out["probability"])
        self.assertFalse(out["decision_effect"])
        self.assertFalse(out["changes_gate"])
        self.assertFalse(out["changes_score_mestre"])
        self.assertFalse(out["changes_weights"])
        self.assertFalse(out["real_orders_enabled"])
        self.assertFalse(out["automatic_execution"])


    def test_ranking_adapter_maps_real_pair_components(self):
        rows=[
            {"Código":"EUR","n_juros":40,"n_inflacao":45,"n_pib":55,"n_emprego":50,"n_atividade":50,"fonte":"FRED + transformação anual"},
            {"Código":"USD","n_juros":75,"n_inflacao":65,"n_pib":60,"n_emprego":70,"n_atividade":62,"fonte":"FRED + transformação anual"},
        ]
        out=ranking_rows_to_currency_context(rows,usd_quality=92)
        self.assertIn("rates",out["EUR"])
        self.assertNotIn("labour",out["EUR"])
        self.assertNotIn("activity",out["EUR"])
        self.assertIn("labour",out["USD"])
        self.assertIn("activity",out["USD"])
        self.assertEqual(out["USD"]["rates"]["quality"],92)

    def test_ranking_adapter_does_not_promote_fallback_as_fresh(self):
        rows=[{"Código":"AUD","n_juros":50,"n_inflacao":50,"n_pib":50,"fonte":"FRED + fallback parcial"}]
        out=ranking_rows_to_currency_context(rows)
        self.assertFalse(out["AUD"]["rates"]["fresh"])
        self.assertEqual(out["AUD"]["rates"]["quality"],35.0)


    def test_economic_adapter_maps_known_release_rules(self):
        rows={
            "PCE Núcleo anual":{"consenso":2.8,"anterior":2.7,"real":3.0,"source":"EODHD"},
            "Desemprego":{"consenso":4.2,"anterior":4.1,"real":4.4,"source":"EODHD"},
            "Unknown thing":{"consenso":10,"anterior":9,"real":11,"source":"EODHD"},
        }
        out=economic_rows_to_indicators(rows)
        self.assertEqual(len(out),2)
        pce=next(x for x in out if "PCE" in x["name"])
        unemp=next(x for x in out if "Desemprego" in x["name"])
        self.assertTrue(pce["higher_supports_currency"])
        self.assertFalse(unemp["higher_supports_currency"])
        self.assertEqual(pce["scale"],0.2)

    def test_economic_adapter_skips_unknown_or_empty_release(self):
        rows={
            "Mystery release":{"consenso":1,"anterior":0},
            "Payroll":{"consenso":None,"real":None,"anterior":150},
        }
        self.assertEqual(economic_rows_to_indicators(rows),[])


if __name__=="__main__":
    unittest.main()