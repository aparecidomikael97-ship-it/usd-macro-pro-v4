"""Presentation contracts; synthetic fixtures never enter application state."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import pytest
from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_interface_final import (
    eligible_fx_population, forex_board_html, direction_label,
    filter_snapshot_history, snapshot_filter_fields, AION_PRESENTATION_ROLES,
)


def resident_fixture():
    now = datetime.now(timezone.utc)
    rows = [dict(pair=pair, priority=90-i, data_score=90, data_ready=True,
                 provenance_state='CONFIRMADA', evidence_source='TEST FIXTURE',
                 pipeline={'ranking':'ELEGÍVEL PARA ESTUDO'}, session_match='MATCH',
                 action='NÃO OPERAR', reason='Synthetic test evidence')
            for i,pair in enumerate(OFFICIAL_PAIRS)]
    return {'rows':rows,'freshness':{'state':'VALIDATED_SNAPSHOT',
            'generated_at':now.isoformat(),'source':'TEST FIXTURE'}}, now


def test_ranking_is_engine_order_and_eleventh_is_promoted():
    from atlasquant_radar_board import rank_fx_population
    resident, now = resident_fixture()
    original = deepcopy(resident)
    ranked = eligible_fx_population(resident, now=now)['ranked']
    assert ranked == rank_fx_population(resident['rows'])
    eleventh = ranked[10]['pair']
    resident['rows'][0]['data_ready'] = False
    promoted = eligible_fx_population(resident, now=now)['ranked']
    assert promoted[9]['pair'] == eleventh
    assert resident['rows'][1:] == original['rows'][1:]
    html = forex_board_html(resident)
    assert html.count('final-featured"') == 10
    assert html.count('class="final-ring"') == 10
    assert html.count('data-pair=') == 28
    assert html.count('data-ranked="true"') == 27
    assert 'TOP 10 · POSIÇÃO A VALIDAR' not in html


@pytest.mark.parametrize('invalid', ['missing','stale','future','naive','state'])
def test_unvalidated_freshness_never_publishes_positions(invalid):
    resident, now = resident_fixture()
    if invalid == 'missing': resident.pop('freshness')
    elif invalid == 'state': resident['freshness']['state'] = 'UNCONFIRMED'
    else:
        stamp = now - timedelta(minutes=91) if invalid == 'stale' else now + timedelta(minutes=5)
        if invalid == 'naive': stamp = now.replace(tzinfo=None)
        resident['freshness']['generated_at'] = stamp.isoformat()
    assert eligible_fx_population(resident, now=now)['ranked'] == []
    html = forex_board_html(resident)
    assert 'Ranking aguardando dados validados' in html
    assert html.count('data-ranked="false"') == 28
    assert 'final-position' not in html


@pytest.mark.parametrize('field,value', [('priority',float('nan')),('priority',True),
    ('priority',101),('data_ready',False),('evidence_source',''),
    ('provenance_state','SEM DADOS'),('pipeline',{'ranking':'BLOQUEADO PARA ESTUDO'})])
def test_ineligible_rows_cannot_keep_a_position(field,value):
    resident, now = resident_fixture()
    resident['rows'][0][field] = value
    assert len(eligible_fx_population(resident,now=now)['ranked']) == 27


def test_duplicates_and_unknown_pairs_never_expand_universe():
    resident, now = resident_fixture()
    resident['rows'] += [resident['rows'][0],dict(resident['rows'][0],pair='FAKE/USD')]
    assert len(eligible_fx_population(resident,now=now)['ranked']) == 28


def test_direction_requires_confirmed_unexpired_engine_signal():
    now = datetime.now(timezone.utc)
    row = {'signal':{'status_code':'CONFIRMED','side':'BUY','valid_until':(now+timedelta(minutes=1)).isoformat()}}
    assert direction_label(row,now=now) == 'Direção: Compra confirmada'
    row['signal']['valid_until'] = (now-timedelta(seconds=1)).isoformat()
    assert direction_label(row,now=now) == 'Direção: sinal expirado'
    row['signal']['status_code'] = 'BLOCKED'
    assert 'Compra' not in direction_label(row,now=now)


def test_filters_only_use_existing_metadata_without_mutation():
    snap = {'created_at':'2026-10-03T00:00:00Z','settings':{'values':{'strategy':'BOS','execution_timeframe':'M15'}},'evidence':{'bundle':{'pair':'EUR/USD'}}}
    other = deepcopy(snap); other['created_at'] = '2025-09-01T00:00:00Z'
    records = [snap,other]; original = deepcopy(records)
    assert snapshot_filter_fields(snap) == {'Ano':'2026','Mês':'10','Setup':'BOS','Ativo':'EUR/USD','Timeframe':'M15'}
    assert filter_snapshot_history(records,{'Ano':'2026','Mês':'10','Setup':'BOS','Ativo':'EUR/USD','Timeframe':'M15'}) == [snap]
    assert filter_snapshot_history(records,{'Ano':'Todos'}) == records
    assert records == original
    assert snapshot_filter_fields({})['Setup'] == 'Não informado'


def test_eight_product_roles_share_one_core_and_do_not_replace_registry():
    assert len(AION_PRESENTATION_ROLES) == 8
    assert [label.split(' / ')[0] for label,_ in AION_PRESENTATION_ROLES] == [
        'Orquestrador','Arquiteto','Guardião','Prime','Shadow','Sentinel','Comercial','Educador']


def test_multi_strategy_snapshots_are_filterable_without_invented_setup():
    from atlasquant_interface_final import snapshot_filter_values
    snap = {'evidence':{'bundle':{'evidence_summary':[{'strategy':'BOS'},{'strategy':'FVG'}]}}}
    before = deepcopy(snap)
    assert snapshot_filter_values(snap)['Setup'] == ['BOS','FVG']
    assert filter_snapshot_history([snap],{'Setup':'FVG'}) == [snap]
    assert filter_snapshot_history([snap],{'Setup':'FAKE'}) == []
    assert snap == before


def test_master_data_status_matches_resident_evidence():
    from atlasquant_reference_ui import reference_html
    resident,_ = resident_fixture()
    assert 'LEITURAS VALIDADAS' in reference_html('trader',selected='master',fx_population=resident)
    assert 'VALIDAÇÃO PENDENTE' in reference_html('trader',selected='master')


def test_investment_reference_numbers_are_covered_by_neutral_native_states():
    from atlasquant_reference_ui import reference_html
    html = reference_html('investimentos')
    assert html.count('class="ref-hit ref-neutral-region"') == 3
    assert html.count('ref-mobile-card-neutral"') == 3
    assert html.count('PRÉVIA · aguardando dados validados') == 3
