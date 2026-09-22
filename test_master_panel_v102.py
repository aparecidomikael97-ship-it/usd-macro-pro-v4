import unittest
import pandas as pd

# Streamlit is not needed for testing the pure assembly logic in CI; provide a tiny stub
# only if the package is unavailable.
try:
    import streamlit  # noqa: F401
except Exception:
    import sys, types
    st = types.ModuleType('streamlit')
    st.cache_data = lambda *a, **k: (lambda f: f)
    st.secrets = {}
    sys.modules['streamlit'] = st

from master_panel_v102 import (
    build_master_rows,
    _technical_score,
    _integrated_state,
    _scanner_for_pair,
    _technical_temporal_status,
    _execution_display,
)


class MasterPanelTests(unittest.TestCase):
    def matrix(self):
        return pd.DataFrame([
            {'Par':'USD/CHF','Direção':'COMPRA USD/CHF','Score final':93,'Qualidade':84},
            {'Par':'EUR/USD','Direção':'VENDA EUR/USD','Score final':88,'Qualidade':80},
        ])

    def scanner(self, green=True):
        status = '🟢 CONFIRMA' if green else '🔴 CONTRA'
        now = pd.Timestamp.now(tz='UTC').isoformat()
        return {'resultados': {
            'USD/CHF': {'m15_fetched_at': now, 'tecnico': {'disponivel': True, 'h4': {'status': status}, 'h1': {'status': status}, 'm15': {'status': status}}},
            'EUR/USD': {'m15_fetched_at': now, 'tecnico': {'disponivel': True, 'h4': {'status':'🟢 CONFIRMA'}, 'h1': {'status':'🟢 PULLBACK OK'}, 'm15': {'status':'🟡 AGUARDAR GATILHO'}}},
        }}

    def contexts(self):
        return {
            'USD/CHF': {'readiness_score':90,'readiness_grade':'A+','w1_bias':'ALTISTA','d1_bias':'ALTISTA','event_risk':'NORMAL','adr_used_pct':70,'adr_state':'🟡 RANGE MODERADO','bsl_name':'PWH','updated_at':pd.Timestamp.now(tz='UTC').isoformat()},
            'EUR/USD': {'readiness_score':80,'readiness_grade':'A','w1_bias':'BAIXISTA','d1_bias':'BAIXISTA','event_risk':'NORMAL','adr_used_pct':60,'adr_state':'🟡 RANGE MODERADO','ssl_name':'PDL','updated_at':pd.Timestamp.now(tz='UTC').isoformat()},
        }

    def test_green_full_alignment_is_executable(self):
        rows = build_master_rows(self.matrix(), self.contexts(), self.scanner(True))
        usd = next(r for r in rows if r['Par'] == 'USD/CHF')
        self.assertEqual(usd['Estado'], '🟢 EXECUTÁVEL')
        self.assertEqual(usd['Liquidez alvo'], 'PWH')

    def test_waiting_m15_is_quase_pronto(self):
        rows = build_master_rows(self.matrix(), self.contexts(), self.scanner(True))
        eur = next(r for r in rows if r['Par'] == 'EUR/USD')
        self.assertEqual(eur['Estado'], '🟡 QUASE PRONTO')
        self.assertEqual(eur['Liquidez alvo'], 'PDL')

    def test_adr_exhaustion_blocks_execution(self):
        ctx = self.contexts()
        ctx['USD/CHF']['adr_used_pct'] = 125
        rows = build_master_rows(self.matrix(), ctx, self.scanner(True))
        usd = next(r for r in rows if r['Par'] == 'USD/CHF')
        self.assertEqual(usd['Estado'], '🟡 ESTICADO')

    def test_technical_red_is_conflict(self):
        ctx = self.contexts()['USD/CHF']
        tech = {'available': True, 'h4':'🔴 CONTRA', 'h1':'🟢 CONFIRMA', 'm15':'🟢 CONFIRMA'}
        state, _ = _integrated_state('COMPRA USD/CHF', ctx, tech)
        self.assertEqual(state, '🔴 CONFLITO')

    def test_m15_red_is_not_called_quase_pronto(self):
        ctx=self.contexts()["USD/CHF"]
        tech={"available":True,"fresh":True,"age_minutes":5,
              "h4":"🟢 CONFIRMA","h1":"🟢 CONFIRMA","m15":"🔴 CONTRA"}
        state,reason=_integrated_state("COMPRA USD/CHF",ctx,tech)
        self.assertEqual(state,"🔴 GATILHO CONTRA")
        self.assertIn("não tratar como quase pronto",reason)

    def test_m15_unknown_waits_for_proven_trigger(self):
        ctx=self.contexts()["USD/CHF"]
        tech={"available":True,"fresh":True,"age_minutes":5,
              "h4":"🟢 CONFIRMA","h1":"🟢 CONFIRMA","m15":"—"}
        state,reason=_integrated_state("COMPRA USD/CHF",ctx,tech)
        self.assertEqual(state,"⚪ AGUARDAR GATILHO")
        self.assertIn("gatilho comprovado",reason)

    def test_only_yellow_m15_can_be_quase_pronto(self):
        ctx=self.contexts()["USD/CHF"]
        tech={"available":True,"fresh":True,"age_minutes":5,
              "h4":"🟢 CONFIRMA","h1":"🟢 CONFIRMA","m15":"🟡 AGUARDAR GATILHO"}
        state,_=_integrated_state("COMPRA USD/CHF",ctx,tech)
        self.assertEqual(state,"🟡 QUASE PRONTO")

    def test_technical_score_is_bounded(self):
        self.assertEqual(_technical_score({'h4':'🟢 CONFIRMA','h1':'🟢 CONFIRMA','m15':'🟢 CONFIRMA'}), 100.0)
        self.assertGreaterEqual(_technical_score({'h4':'—','h1':'—','m15':'—'}), 0.0)

    def test_scanner_freshness_is_explicit(self):
        now = pd.Timestamp.now(tz='UTC')
        scanner = {'resultados': {
            'USD/CHF': {
                'processado_em': (now - pd.Timedelta(minutes=10)).isoformat(),
                'tecnico': {
                    'disponivel': True,
                    'h4': {'status':'🟢 CONFIRMA'},
                    'h1': {'status':'🟢 PULLBACK OK'},
                    'm15': {'status':'🟡 AGUARDAR GATILHO'},
                }
            }
        }}
        info = _scanner_for_pair(scanner, 'USD/CHF')
        self.assertTrue(info['available'])
        self.assertTrue(info['fresh'])
        self.assertLess(info['age_minutes'], 45)


    def test_current_scanner_has_absolute_reference_and_current_status(self):
        now=pd.Timestamp.now(tz="UTC")
        scanner={"resultados":{"USD/CHF":{
            "m15_fetched_at":(now-pd.Timedelta(minutes=10)).isoformat(),
            "tecnico":{"disponivel":True,"h4":{"status":"🟢 CONFIRMA"},"h1":{"status":"🟢 CONFIRMA"},"m15":{"status":"🟢 CONFIRMA"}},
        }}}
        info=_scanner_for_pair(scanner,"USD/CHF")
        temporal=_technical_temporal_status(info)
        self.assertTrue(info["fresh"])
        self.assertEqual(temporal["code"],"CURRENT")
        self.assertEqual(temporal["label"],"ATUAL")
        self.assertIn("UTC",temporal["reference_display"])
        self.assertIn("UTC",temporal["valid_until_display"])
        self.assertFalse(temporal["requires_revalidation"])

    def test_stale_scanner_is_expired_and_never_authorized(self):
        now=pd.Timestamp.now(tz="UTC")
        scanner={"resultados":{"USD/CHF":{
            "m15_fetched_at":(now-pd.Timedelta(minutes=61)).isoformat(),
            "tecnico":{"disponivel":True,"h4":{"status":"🟢 CONFIRMA"},"h1":{"status":"🟢 CONFIRMA"},"m15":{"status":"🟢 CONFIRMA"}},
        }}}
        info=_scanner_for_pair(scanner,"USD/CHF")
        temporal=_technical_temporal_status(info)
        self.assertFalse(info["fresh"])
        self.assertEqual(temporal["code"],"EXPIRED")
        self.assertIn("EXPIRADA",temporal["label"])
        self.assertEqual(_execution_display("🟢 EXECUTÁVEL",temporal),"⛔ NÃO AUTORIZADA")

    def test_missing_timestamp_is_unverified_fail_closed(self):
        scanner={"resultados":{"USD/CHF":{
            "tecnico":{"disponivel":True,"h4":{"status":"🟢 CONFIRMA"},"h1":{"status":"🟢 CONFIRMA"},"m15":{"status":"🟢 CONFIRMA"}},
        }}}
        info=_scanner_for_pair(scanner,"USD/CHF")
        temporal=_technical_temporal_status(info)
        self.assertFalse(info["fresh"])
        self.assertEqual(temporal["code"],"UNVERIFIED")
        self.assertEqual(temporal["reference_display"],"HORÁRIO NÃO COMPROVADO")
        self.assertTrue(temporal["requires_revalidation"])

    def test_master_rows_separate_macro_bias_from_entry_authorization(self):
        rows=build_master_rows(self.matrix(),self.contexts(),self.scanner(True))
        usd=next(r for r in rows if r["Par"]=="USD/CHF")
        self.assertEqual(usd["Viés macro"],"COMPRA USD/CHF")
        self.assertEqual(usd["Estado"],"🟢 EXECUTÁVEL")
        self.assertEqual(usd["Status temporal"],"ATUAL")
        self.assertIn("UTC",usd["Hora da leitura"])
        self.assertTrue(usd["Autorização"].startswith("✅"))

    def test_master_panel_ui_explicitly_says_macro_bias_is_not_entry(self):
        from pathlib import Path
        src=Path("master_panel_v102.py").read_text(encoding="utf-8")
        self.assertIn("Viés macro não é entrada",src)
        self.assertIn('b2.metric("Viés macro"',src)
        self.assertIn('b3.metric("Estado operacional"',src)
        self.assertIn('"Hora da leitura"',src)
        self.assertIn('"Status temporal"',src)
        self.assertIn('"Autorização"',src)
        self.assertIn("não deve ser interpretado como uma entrada atual",src)

    def test_master_overview_state_is_descriptive_and_fail_closed(self):
        from master_panel_v102 import master_overview_state
        self.assertEqual(master_overview_state(pairs=0,processed=0,scanner_fresh=0)["label"],"AGUARDANDO DADOS")
        self.assertEqual(master_overview_state(pairs=7,processed=7,scanner_fresh=7)["label"],"COBERTURA COMPLETA")
        self.assertEqual(master_overview_state(pairs=7,processed=3,scanner_fresh=2)["label"],"COBERTURA PARCIAL")
        self.assertEqual(master_overview_state(pairs="bad",processed=0,scanner_fresh=0)["label"],"REVISAR")



if __name__ == '__main__':
    unittest.main()
