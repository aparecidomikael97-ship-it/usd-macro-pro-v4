"""Resident integration tests: fixtures are synthetic and never production data."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
import pytest
from test_atlasquant_fast_startup import snapshot
from atlasquant_trader_resident import resident_trader_state, hydrate_trader_resident_state
from atlasquant_compact_cockpit import ticker_html
from atlasquant_reference_ui import reference_html, TRADER_NAV, module_panel


def fresh_snapshot():
    now = datetime.now(timezone.utc)
    value = snapshot(generated_at=now.isoformat())
    value["packs"] = [dict(pair=pair, direction=direction, priority=85-i,
        data_ready={"sufficient":True,"score":90}, quality=90,
        gate="PASS", state="LEITURA", evidence_source="TEST FIXTURE",
        signal_lifecycle={"status_code":"CONFIRMED", "side":"BUY" if direction=="COMPRA" else "SELL", "valid_until":(now+timedelta(minutes=30)).isoformat()})
        for i,(pair,direction) in enumerate((("EUR/USD","COMPRA"),("GBP/USD","VENDA")))]
    return value, now


def test_existing_pipeline_freshness_ticker_and_scanner_are_connected_without_io():
    value, now = fresh_snapshot(); original = deepcopy(value)
    with patch("requests.get",side_effect=AssertionError("provider forbidden")), patch("requests.post",side_effect=AssertionError("execution forbidden")):
        state = resident_trader_state(value, now=now, series_state={})
    population = state["atlasquant_reference_fx_population"]
    assert population["freshness"] == {"state":"VALIDATED_SNAPSHOT","generated_at":value["generated_at"],"source":"runtime snapshot"}
    assert len(population["rows"]) == 28
    items = {r["asset"]:r for r in state["atlasquant_validated_market_items"]}
    assert items["EUR/USD"]["bias"] == "Compra"
    assert items["GBP/USD"]["bias"] == "Venda"
    assert items["EUR/USD"]["source"] == "TEST FIXTURE"
    assert items["DXY"]["score"] == 60
    assert "price" not in items["DXY"] and "bias" not in items["DXY"]
    assert value == original
    html = ticker_html("trader",list(items.values()))
    status = html.split('class="cq-market-state"')[1]
    assert "DADOS ATUAIS VALIDADOS" in status and "PRÉVIA" not in status
    home = reference_html("trader",market_items=list(items.values()),fx_population=population)
    assert 'class="cq-engine-bias">COMPRA' in home
    assert 'class="cq-engine-bias">VENDA' in home
    assert "Top 10 · ranking validado" in home


def test_seven_runtime_pairs_show_only_existing_technical_fields_without_provider():
    from atlasquant_fast_startup import EXPECTED_FX_PAIRS
    value, now=fresh_snapshot()
    value["packs"]=[dict(value["packs"][0],pair=pair,h4="CONFIRMA",h1="ALINHADO",m15="AGUARDANDO") for pair in EXPECTED_FX_PAIRS]
    with patch("requests.get",side_effect=AssertionError("network forbidden")), patch("requests.post",side_effect=AssertionError("network forbidden")):
        state=resident_trader_state(value,now=now,series_state={})
        for selected in ('','scanner','radar','fed','market_map','macro','indexes'):
            html=reference_html('trader',selected=selected,market_items=state['atlasquant_validated_market_items'],fx_population=state['atlasquant_reference_fx_population'])
            assert html
        home=reference_html('trader',fx_population=state['atlasquant_reference_fx_population'])
    assert home.count('class="cq-engine-bias"') == 7
    assert home.count('H4: CONFIRMA · H1: ALINHADO · M15: AGUARDANDO') == 7
    assert 'Prioridade 85.0 · Qualidade 90.0' in home
    assert 'Gate: PASS' in home and 'Snapshot: '+value['generated_at'] in home
    from atlasquant_interface_final import eligible_fx_population
    ranked=eligible_fx_population(state['atlasquant_reference_fx_population'],now=now)['ranked']
    assert {r['pair'] for r in ranked} == set(EXPECTED_FX_PAIRS)


def candle_cache(now):
    return {'series':{'EUR/USD|15min':{'fetched_at':now.isoformat(),'records':[
        {'datetime':(now-timedelta(minutes=45-i*15)).isoformat(),
         'open':1.1,'high':1.2,'low':1.0,'close':1.1+i*.01}
        for i in range(3)]}}}


def test_ticker_series_are_exact_existing_closed_validated_cache_records():
    value, now=fresh_snapshot(); cache=candle_cache(now); original=deepcopy(cache)
    # This live candle must never become the displayed price or sparkline.
    cache['series']['EUR/USD|15min']['records'].append(dict(original['series']['EUR/USD|15min']['records'][0],datetime=now.isoformat(),close=1.15))
    with patch('requests.get',side_effect=AssertionError('provider forbidden')), patch('twelve_cache_v1108.cached_series',side_effect=AssertionError('cache fetch forbidden')):
        state=resident_trader_state(value,now=now,series_state=cache)
    eur=next(r for r in state['atlasquant_validated_market_items'] if r['asset']=='EUR/USD')
    assert eur['series'] == [1.1,1.11,1.12]
    assert eur['price'] == 1.12 and 'closed M15' in eur['quote_source']
    assert ticker_html('trader',state['atlasquant_validated_market_items']).count('class="cq-real-spark"') == 1
    dxy=next(r for r in state['atlasquant_validated_market_items'] if r['asset']=='DXY')
    assert 'series' not in dxy and 'price' not in dxy and 'bias' not in dxy


@pytest.mark.parametrize('invalid',['stale','malformed','unclosed'])
def test_invalid_cache_never_supplies_price_or_sparkline(invalid):
    value, now=fresh_snapshot(); cache=candle_cache(now)
    raw=cache['series']['EUR/USD|15min']
    if invalid=='stale': raw['fetched_at']=(now-timedelta(hours=2)).isoformat()
    elif invalid=='malformed': raw['records']=[{'datetime':now.isoformat(),'close':1.1}]
    else:
        for row in raw['records']: row['datetime']=now.isoformat()
    state=resident_trader_state(value,now=now,series_state=cache)
    assert all('series' not in r and 'price' not in r for r in state['atlasquant_validated_market_items'])
    assert 'cq-real-spark' not in ticker_html('trader',state['atlasquant_validated_market_items'])


def test_budget_cron_and_quota_saver_contracts_remain_intact():
    import ast
    def constants(path):
        out={}
        for node in ast.parse(Path(path).read_text(encoding='utf-8')).body:
            if isinstance(node,ast.Assign):
                for target in node.targets:
                    if isinstance(target,ast.Name) and isinstance(node.value,ast.Constant): out[target.id]=node.value.value
        return out
    budget=constants('twelve_budget_v1108.py'); autopilot=constants('autopilot_v107.py')
    assert budget['DAILY_LIMIT']==480 and budget['HOURLY_LIMIT']==28
    assert autopilot['AUTOPILOT_DAILY_CALL_BUDGET']==480
    assert [autopilot[k] for k in ('M15_EVERY_MIN','H1_EVERY_MIN','H4_EVERY_MIN','PRIORITY_M15_EVERY_MIN','PRIORITY_H1_EVERY_MIN')]==[55,115,235,25,55]
    assert 'cron: "7,37 * * * *"' in Path('.github/workflows/autopilot-v107.yml').read_text(encoding='utf-8')


@pytest.mark.parametrize("invalid",["stale","unsafe","missing","malformed"])
def test_failed_validation_clears_previous_state_and_never_publishes_rank(invalid):
    value, now = fresh_snapshot()
    if invalid == "stale": value["generated_at"]=(now-timedelta(hours=2)).isoformat()
    elif invalid == "unsafe": value["safety"]["real_orders"]=True
    elif invalid == "missing": value["inputs"]["fast_boot"].pop("ranking")
    else: value["inputs"]=[]
    state={"atlasquant_reference_fx_population":{"old":True},"atlasquant_validated_market_items":[{"old":True}]}
    hydrate_trader_resident_state(state,value)
    if invalid=='stale':
        from atlasquant_interface_final import eligible_fx_population
        population=state['atlasquant_reference_fx_population']
        assert population['snapshot_state']=='STALE_HISTORY'
        assert len(population['history'])==2
        assert eligible_fx_population(population)['ranked']==[]
        assert 'ÚLTIMA LEITURA · REVALIDAR' in ticker_html('trader',state['atlasquant_validated_market_items'])
        return
    assert state == {"atlasquant_reference_fx_population":{},"atlasquant_validated_market_items":[]}
    home=reference_html("trader",fx_population=state["atlasquant_reference_fx_population"])
    assert "Ranking aguardando dados validados" in home
    assert "cq-engine-bias" not in home
    assert "SEM DADOS · SEM FONTE LIVE CONFIGURADA" in ticker_html("trader",state["atlasquant_validated_market_items"])


def test_macro_only_snapshot_cannot_fabricate_fx_ranking_or_directions():
    value, now = fresh_snapshot()
    value["packs"]=[{"pair":"EUR/USD","direction":"COMPRA"}]
    state=resident_trader_state(value,now=now)
    items=state["atlasquant_validated_market_items"]
    assert [r["asset"] for r in items] == ["DXY"]
    assert "bias" not in items[0] and "price" not in items[0]
    assert "Top 10 · ranking validado" not in reference_html("trader",fx_population=state["atlasquant_reference_fx_population"])


def test_blocked_engine_action_is_neutral_not_original_buy():
    value, now=fresh_snapshot(); value["packs"][0]["gate"]="BLOCKED"
    state=resident_trader_state(value,now=now)
    eur=next(x for x in state["atlasquant_validated_market_items"] if x["asset"]=="EUR/USD")
    assert eur["bias"] == "Neutro"
    home=reference_html("trader",fx_population=state["atlasquant_reference_fx_population"])
    assert 'class="cq-engine-bias">NÃO OPERAR' in home


@pytest.mark.parametrize("score",[None,True,float("nan"),float("inf"),"invalid"])
def test_invalid_usd_score_is_not_published(score):
    value, now=fresh_snapshot(); value["inputs"]["fast_boot"]["ranking"][0]["Pontuação_Final"]=score
    assert all(x["asset"]!="DXY" for x in resident_trader_state(value,now=now)["atlasquant_validated_market_items"])


def test_routes_and_sidebar_contract_preserved():
    assert len(TRADER_NAV)==24 and len(set(k for k,_ in TRADER_NAV))==24
    css=Path("assets/ecosystem_reference/reference.css").read_text(encoding="utf-8")
    rule=css.split('.cq-nav .ref-nav-item{')[1].split('}')[0]
    assert "overflow-wrap:normal" in rule and "overflow-wrap:anywhere" not in rule
    for route in ("fed","macro","micro","geo","market_news","fundamental","ict","calendar","news","market_map"):
        assert 'data-route="connected:'+route+'"' in module_panel("trader",route)


@pytest.mark.parametrize('code', ['EXPIRED','BLOCKED','NO_SIGNAL','POSSIBLE','UNVERIFIED'])
def test_new_snapshot_never_renews_old_or_unconfirmed_technical_signal(code):
    from atlasquant_interface_final import eligible_fx_population
    value, now = fresh_snapshot()
    for pack in value['packs']:
        pack['signal_lifecycle'].update(status_code=code,
            reference_at=(now-timedelta(days=1)).isoformat(),
            valid_until=(now-timedelta(hours=23) if code=='EXPIRED' else now+timedelta(minutes=30)).isoformat())
    with patch('requests.get',side_effect=AssertionError('network forbidden')), patch('requests.post',side_effect=AssertionError('network forbidden')):
        state=resident_trader_state(value,now=now,series_state={})
        population=state['atlasquant_reference_fx_population']
        assert eligible_fx_population(population,now=now)['ranked'] == []
        for route in ('','scanner','radar','market_map','why:EUR/USD'):
            html=reference_html('trader',selected=route,fx_population=population,
                market_items=state['atlasquant_validated_market_items'])
            assert code in html and 'REVALIDAR' in html
            assert 'Top 10 · ranking validado' not in html
    eur=next(item for item in state['atlasquant_validated_market_items'] if item['asset']=='EUR/USD')
    assert eur['last_bias']=='COMPRA' and 'bias' not in eur


def test_confirmed_signal_with_elapsed_expiry_is_not_ranked():
    from atlasquant_interface_final import eligible_fx_population
    value, now=fresh_snapshot()
    for pack in value['packs']:
        pack['signal_lifecycle']['valid_until']=(now-timedelta(seconds=1)).isoformat()
    state=resident_trader_state(value,now=now,series_state={})
    assert eligible_fx_population(state['atlasquant_reference_fx_population'],now=now)['ranked']==[]
    assert all(item['temporal_state']=='EXPIRED' for item in state['atlasquant_validated_market_items'] if item['asset']!='DXY')


def test_indices_and_crypto_universes_stay_separate_without_fabricated_live_data():
    from atlasquant_interface_final import resident_context_html
    from atlasquant_radar_board import INDEX_UNIVERSE, CRYPTO_UNIVERSE
    assert [symbol for symbol,_ in INDEX_UNIVERSE]==['DXY','US30','NAS100','SPX500','IBOV','WIN','WDO']
    assert [symbol for symbol,_ in CRYPTO_UNIVERSE]==['BTC/USD','ETH/USD','SOL/USD']
    for selected,universe in (('indexes',INDEX_UNIVERSE),('crypto',CRYPTO_UNIVERSE)):
        html=resident_context_html(selected)
        assert all(symbol in html for symbol,_ in universe)
        assert html.count('SEM LEITURA AO VIVO')==len(universe)
        assert 'coleta live específica não encontrada' in html
