"""Synthetic evidence fixtures: current and historical are separate contracts."""
import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from pathlib import Path
from test_atlasquant_reference_resident import fresh_snapshot
from atlasquant_trader_resident import resident_trader_state
from atlasquant_runtime_presentation import snapshot_presentation, compact_market_strip, module_state
from atlasquant_compact_cockpit import ticker_html, normalized_market_items
from atlasquant_interface_final import eligible_fx_population
from atlasquant_reference_ui import reference_html, TRADER_NAV


def historical_fixture():
    value,now=fresh_snapshot()
    stamp=(now-timedelta(minutes=107)).isoformat()
    value['generated_at']=stamp;value['runtime_generated_at']=stamp
    value['inputs']['generated_at']=stamp
    technical=(now-timedelta(days=1)).isoformat()
    pairs=[('EUR/USD','VENDA',1.12519),('GBP/USD','VENDA',1.32401),('AUD/USD','AGUARDAR',.69561),('NZD/USD','VENDA',.56152),('USD/JPY','COMPRA',157.86313),('USD/CHF','COMPRA',.82882),('USD/CAD','COMPRA',1.42503)]
    value['packs']=[dict(pair=pair,direction=bias,price=price,technical_timestamp=technical,
        h4='CONFIRMA',h1='PULLBACK OK',m15='AGUARDAR GATILHO',priority=75,quality=35,
        data_ready={'sufficient':False,'score':35},gate='WAIT',state='BLOCKED',map_current=False,
        evidence_source='SYNTHETIC TEST FIXTURE',ict_label='Leitura ICT persistida de teste',ict_fresh=False,
        signal_lifecycle={'status_code':'NO_SIGNAL' if bias=='AGUARDAR' else 'EXPIRED','reference_at':technical,'valid_until':(now-timedelta(hours=23)).isoformat()}) for pair,bias,price in pairs]
    value['runtime']={'market_open':False,'scanner_pairs':7,'market_map_pairs':7}
    status={'last_run':stamp,'operational_readiness':'MARKET_CLOSED','scanner_fresh':0,'news_updated_at':stamp,'news_unique_stories':219,
        'twelve_budget':{'used':0,'limit':480},'news_nowcast_v1':{'runtime_state':'AUTH_ERROR','provider_retry_after_min':360},
        'paper_trading_v112':{'trades_total':0},'model_paper_v1':{'candidates_total':387,'blocked_context':381,'blocked_timeframe':6},
        'setup_audit_v114':{'sample_state':'AGUARDANDO AMOSTRA'}}
    return value,status,now


def scanner_fixture(now, count=45):
    records=[{'datetime':(now-timedelta(minutes=15*(count-i+1))).isoformat(),
        'open':1.1,'high':1.3,'low':1.0,'close':1.1+i/1000} for i in range(count)]
    records += [{'datetime':now.isoformat(),'open':1.1,'high':1.3,'low':1.0,'close':1.2}]
    return {'resultados':{'EUR/USD':{'tecnico':{'cache_v110':{'m15':records}}}}}


class RuntimeConsistencyTests(unittest.TestCase):
    def test_stale_107_minutes_preserves_seven_history_rows_prices_and_no_ranking(self):
        value,status,now=historical_fixture(); original=deepcopy(value)
        with patch('requests.get',side_effect=AssertionError('IO forbidden')),patch('requests.post',side_effect=AssertionError('provider forbidden')):
            state=resident_trader_state(value,now=now,series_state={},runtime_status=status)
            population=state['atlasquant_reference_fx_population']
            self.assertEqual(population['snapshot_state'],'STALE_HISTORY')
            self.assertEqual(len(population['history']),7)
            self.assertEqual(eligible_fx_population(population,now=now)['ranked'],[])
            rows=normalized_market_items(state['atlasquant_validated_market_items'])
            pairs=[row for row in rows if '/' in row['asset']]
            self.assertEqual(len(pairs),7)
            self.assertEqual(sum(row['temporal_state']=='EXPIRED' for row in pairs),6)
            self.assertEqual(sum(row['temporal_state']=='NO_SIGNAL' for row in pairs),1)
            self.assertTrue(all('price' not in row and 'bias' not in row for row in pairs))
            html=ticker_html('trader',state['atlasquant_validated_market_items'])
            for pack in value['packs']: self.assertIn(f"Último preço: {pack['price']:.5f}",html)
            self.assertIn('ÚLTIMA LEITURA · REVALIDAR',html)
            self.assertNotIn('DADOS ATUAIS VALIDADOS',html)
            self.assertNotIn('PRÉVIA',html)
        self.assertEqual(value,original)

    def test_structural_or_safety_errors_never_become_historical_evidence(self):
        value,_,now=historical_fixture()
        for mutate in (lambda s:s['safety'].update(real_orders=True),lambda s:s['inputs'].update(fast_boot={}),lambda s:s['packs'].append(None),lambda s:s.update(runtime_generated_at=(now+timedelta(minutes=1)).isoformat())):
            item=deepcopy(value);mutate(item)
            with self.subTest(item=item.get('runtime_generated_at')):
                self.assertEqual(snapshot_presentation(item,now=now)['state'],'INVALID')
                self.assertEqual(resident_trader_state(item,now=now,series_state={})['atlasquant_reference_fx_population'],{})

    def test_current_confirmed_population_uses_same_contract_in_both_panels(self):
        from atlasquant_master_market import build_executive_market_snapshot
        value,now=fresh_snapshot()
        resident=resident_trader_state(value,now=now,series_state={})['atlasquant_reference_fx_population']
        expected=eligible_fx_population(resident,now=now)['ranked']
        self.assertEqual(len(expected),2)
        self.assertEqual(build_executive_market_snapshot(fx_resident=resident)['forex']['top'],expected)
        resident['snapshot_state']='STALE_HISTORY';resident['freshness']['state']='STALE_HISTORY'
        self.assertEqual(build_executive_market_snapshot(fx_resident=resident)['forex']['top'],[])

    def test_macro_attention_never_becomes_operational_top_ten(self):
        from atlasquant_master_market import build_executive_market_snapshot
        ranking=[{'Código':code,'Pontuação_Final':90-i*9} for i,code in enumerate(('USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'))]
        result=build_executive_market_snapshot(ranking=ranking)
        self.assertEqual(result['forex']['monitored'],28)
        self.assertEqual(result['forex']['top'],[])
        self.assertTrue(result['forex']['macro_attention'])
        self.assertTrue(all(row['action']=='NÃO OPERAR' for row in result['forex']['macro_attention']))

    def test_market_strip_serializes_only_thirty_existing_closed_candles_without_io(self):
        import autopilot_v107 as autopilot
        value,status,now=historical_fixture();scanner=scanner_fixture(now)
        original=deepcopy(scanner)
        with patch('requests.get',side_effect=AssertionError('provider forbidden')),patch.object(autopilot,'td_fetch',side_effect=AssertionError('Twelve forbidden')):
            result=autopilot.build_home_snapshot_payload(value['inputs'],value['packs'],scanner,{}, {},now=now)
        strip=result['market_strip'][0]
        self.assertEqual(len(strip['closes']),30)
        self.assertEqual(strip['closes'],[record['close'] for record in original['resultados']['EUR/USD']['tecnico']['cache_v110']['m15'][:-1]][-30:])
        self.assertEqual(len(strip['series_timestamps']),30)
        self.assertTrue(strip['closed_candles'])
        self.assertNotIn('cache_v110',strip)
        self.assertNotIn('records',strip)
        self.assertNotIn('open',strip)
        self.assertEqual(scanner,original)

    def test_historical_real_series_is_explicitly_not_live(self):
        value,status,now=historical_fixture()
        value['market_strip']=compact_market_strip(scanner_fixture(now-timedelta(days=1)),now=now)
        state=resident_trader_state(value,now=now,series_state={},runtime_status=status)
        eur=next(row for row in state['atlasquant_validated_market_items'] if row['asset']=='EUR/USD')
        self.assertIn('historical_series',eur);self.assertNotIn('series',eur)
        html=ticker_html('trader',state['atlasquant_validated_market_items'])
        self.assertIn('HISTÓRICO M15 · REVALIDAR',html)
        self.assertIn('cq-real-spark',html)
        self.assertNotIn('Série atual M15',html)

    def test_malformed_or_unclosed_series_does_not_render(self):
        value,_,now=historical_fixture();value['market_strip']=compact_market_strip(scanner_fixture(now),now=now)
        for change in ({'source':'unknown'},{'closed_candles':False},{'series_timestamps':[now.isoformat()]*30},{'closes':[float('nan')]*30}):
            item=deepcopy(value);item['market_strip'][0].update(change)
            state=resident_trader_state(item,now=now,series_state={})
            self.assertNotIn('cq-real-spark',ticker_html('trader',state['atlasquant_validated_market_items']))

    def test_all_24_routes_have_systemic_states_and_no_generic_preview(self):
        value,status,now=historical_fixture()
        state=resident_trader_state(value,now=now,series_state={},runtime_status=status)
        resident=state['atlasquant_reference_fx_population']
        for route,title in TRADER_NAV:
            with self.subTest(route=route):
                with patch('requests.get',side_effect=AssertionError('provider forbidden')):
                    html=reference_html('trader',selected='' if route=='home' else route,fx_population=resident,market_items=state['atlasquant_validated_market_items'])
                self.assertNotIn('PRÉVIA · sem execução automática',html)
                self.assertNotIn('VALIDAÇÃO PENDENTE',html)
                if module_state(route,resident)['resident_used']:
                    self.assertIn(module_state(route,resident)['state'],html)
        self.assertIn('219 histórias',module_state('market_news',resident)['detail'])
        self.assertIn('HTTP 401',module_state('news',resident)['detail'])
        self.assertEqual(module_state('lab',resident)['state'],'DISPONÍVEL LOCALMENTE')
        self.assertEqual(module_state('macro',resident)['state'],'ÚLTIMA LEITURA · REVALIDAR')
        self.assertIn('Market Map atual: 0/7',module_state('market_map',resident)['detail'])

    def test_indices_crypto_and_investment_ticker_are_explicit_about_missing_sources(self):
        html=ticker_html('trader');investment=ticker_html('investimentos')
        for asset in ('NASDAQ','BTC','ETH'):
            self.assertIn('aria-label="'+asset+' · SEM FONTE LIVE CONFIGURADA"',html)
        self.assertNotIn('PRÉVIA',html+investment)
        self.assertNotIn('<small>Preço: 0.00',html+investment)
        self.assertEqual((html+investment).count('<small>Preço: —'),26)

    def test_manual_refresh_requires_both_flag_and_existing_admin_session(self):
        import master_panel_v102 as panel
        for flag,role,expected in (('','ADMIN',False),('1','USER',False),('1','ADMIN',True)):
            with patch.dict('os.environ',{'ATLASQUANT_MANUAL_MARKET_REFRESH':flag}),patch.object(panel.st,'session_state',{'atlasquant_access_session':{'role':role}}):
                self.assertEqual(panel.manual_market_refresh_allowed(),expected)
        src=Path('master_panel_v102.py').read_text(encoding='utf-8')
        self.assertEqual(src.count('if manual_market_refresh_allowed() and st.button('),2)


if __name__=='__main__': unittest.main()
