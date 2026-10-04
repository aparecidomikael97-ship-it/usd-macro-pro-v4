"""Evidence classification and compact serialization, never provider collection."""
from datetime import datetime, timezone
import math
from collections.abc import Mapping


def snapshot_presentation(snapshot, *, now=None):
    from atlasquant_fast_startup import validate_home_snapshot
    from atlasquant_fx_universe import OFFICIAL_PAIRS
    try:
        check=validate_home_snapshot(snapshot,now=now)
        packs=check['snapshot'].get('packs')
        if not isinstance(packs,list) or any(not isinstance(p,Mapping) or p.get('pair') not in OFFICIAL_PAIRS for p in packs):
            return {'state':'INVALID','snapshot':{},'age_minutes':None}
        if len({p['pair'] for p in packs})!=len(packs):
            return {'state':'INVALID','snapshot':{},'age_minutes':None}
        errors=set(check['errors'])
        state='VALIDATED_CURRENT' if not errors else 'STALE_HISTORY' if errors=={'stale'} else 'INVALID'
        return {'state':state,'snapshot':check['snapshot'] if state!='INVALID' else {},'age_minutes':check['age_minutes']}
    except (ValueError,TypeError,KeyError,AttributeError):
        return {'state':'INVALID','snapshot':{},'age_minutes':None}


def finite_positive(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and value>0


def stamp_age(value, *, now=None):
    try:
        stamp=datetime.fromisoformat(str(value).replace('Z','+00:00'))
        age=((now or datetime.now(timezone.utc))-stamp).total_seconds()/60
        return age if age>=0 else None
    except (ValueError,TypeError):
        return None


def compact_market_strip(scanner, *, now=None):
    """Extract at most 30 existing closed M15 candles per official pair. Zero I/O."""
    from atlasquant_fx_universe import OFFICIAL_PAIRS
    from twelve_cache_v1108 import valid_records
    results=(scanner or {}).get('resultados') or {}
    if not isinstance(results,Mapping): return []
    out=[]
    for pair,raw in results.items():
        if pair not in OFFICIAL_PAIRS or not isinstance(raw,Mapping): continue
        technical=raw.get('tecnico') or {}
        cache=technical.get('cache_v110') or {} if isinstance(technical,Mapping) else {}
        records=cache.get('m15') or [] if isinstance(cache,Mapping) else []
        try: frame=valid_records(records,'15min',now=now).tail(30)
        except (ValueError,TypeError,KeyError,AttributeError): continue
        if frame.empty: continue
        times=[value.isoformat() for value in frame['datetime']]
        age=stamp_age(times[-1],now=now)
        out.append({'asset':pair,'last_price':float(frame.iloc[-1]['close']),
            'last_price_at':times[-1],'closes':[float(value) for value in frame['close']],
            'series_timestamps':times,'series_as_of':times[-1],'series_timeframe':'M15',
            'series_state':'CURRENT' if age is not None and age<70 else 'HISTORICAL_STALE',
            'source':'scanner/cache_v110/m15','closed_candles':True})
    return out


def module_state(route, resident=None):
    """One state contract for every Trader route, based on module evidence."""
    from atlasquant_interface_final import eligible_fx_population, temporal_signal_status
    resident=resident if isinstance(resident,dict) else {}
    history=resident.get('history') or []
    runtime=resident.get('runtime_status') or {}
    snapshot_state=resident.get('snapshot_state','INVALID')
    historical=snapshot_state=='STALE_HISTORY'
    current=eligible_fx_population(resident)['ranked']
    codes=[temporal_signal_status(row.get('signal')) for row in history]
    counts=f"{len(history)} leituras persistidas · {codes.count('EXPIRED')} expiradas · {codes.count('NO_SIGNAL')} sem sinal"
    label='SEM DADOS'; detail='Nenhuma evidência residente disponível para este módulo.'; used=False
    if route in {'home','radar','scanner','master','ict','guardian'} and history:
        label='ATUAL' if current and not historical else 'ÚLTIMA LEITURA · REVALIDAR'
        detail=counts+' · Cobertura técnica atual: '+str(len(current))+'/'+str(len(history))
        used=True
    elif route=='market_map' and resident.get('market_map'):
        rows=resident['market_map']; fresh=0 if historical else sum(row.get('map_current') is True for row in rows)
        label='ATUAL' if fresh else 'ÚLTIMA LEITURA · REVALIDAR'
        detail=f"Market Map atual: {fresh}/{len(rows)} · Última leitura persistida: {len(rows)}/{len(rows)}"
        used=True
    elif route in {'macro','fed','fundamental'}:
        value=(resident.get('macro_context') or {}).get('fed' if route=='fed' else 'macro_eua')
        if value:
            age=stamp_age(resident.get('macro_as_of'))
            label='ATUAL' if age is not None and age<=90 else 'ÚLTIMA LEITURA · REVALIDAR'
            detail='Macro disponível · '+str(resident.get('macro_as_of','—'))+' · frescor independente do técnico'
            used=True
    elif route=='autopilot':
        stamp=runtime.get('last_run') or (resident.get('freshness') or {}).get('generated_at')
        if stamp:
            label='ÚLTIMA LEITURA · REVALIDAR' if stamp_age(stamp) is None or stamp_age(stamp)>90 else 'ATUAL'
            detail='AUTOMÁTICO · cron 7,37 · quota 480/dia · última execução '+str(stamp)+' · '+str(runtime.get('operational_readiness') or ('MARKET_CLOSED' if (resident.get('runtime') or {}).get('market_open') is False else 'estado do mercado indisponível'))
            used=True
    elif route=='market_news' and runtime.get('news_unique_stories') is not None:
        label='ÚLTIMA LEITURA · REVALIDAR' if stamp_age(runtime.get('news_updated_at')) is None or stamp_age(runtime.get('news_updated_at'))>90 else 'ATUAL'
        detail=str(runtime['news_unique_stories'])+' histórias persistidas · '+str(runtime.get('news_updated_at','—'))
        used=True
    elif route=='news':
        nowcast=runtime.get('news_nowcast_v1') or {}
        if nowcast.get('runtime_state') in {'AUTH_ERROR','AUTH_COOLDOWN'}:
            label='BLOQUEADO POR DEPENDÊNCIA EXTERNA'; detail='Nowcast EODHD · AUTH_ERROR / HTTP 401 · sem previsão inventada'; used=True
        elif nowcast:
            label='ÚLTIMA LEITURA · REVALIDAR';detail='Nowcast persistido · '+str(nowcast.get('runtime_state','SEM DADOS'));used=True
    elif route in {'paper','performance'}:
        paper=runtime.get('paper_trading_v112') or {}
        model=runtime.get('model_paper_v1') or {}
        if paper or model:
            label='ÚLTIMA LEITURA · REVALIDAR' if historical else 'ATUAL'
            detail=f"Paper: {paper.get('trades_total','—')} trades · Model Paper: {model.get('candidates_total','—')} candidatos · sem ordem real";used=True
        elif route=='paper': label='DISPONÍVEL LOCALMENTE';detail='Motor Paper existente; sem estado de runtime carregado. Nenhuma ordem real.'
    elif route in {'lab','journal','profile'}:
        label='DISPONÍVEL LOCALMENTE';detail={'lab':'Motor Backtest, importação CSV, replay e histórico local disponíveis.','journal':'Histórico local de snapshots disponível; abrir o laboratório para consultar registros existentes.','profile':'Preferências do ambiente disponíveis.'}[route]
    elif route in {'indexes','crypto'}:
        label='SEM FONTE LIVE';detail='SEM FONTE LIVE CONFIGURADA · universo implementado; produtor live específico não encontrado.'
    return {'state':label,'detail':detail,'resident_used':used,'snapshot_state':snapshot_state,'scanner_summary':counts}


def normalize_market_items(items, assets, *, now=None):
    accepted=[]
    for item in items if isinstance(items,(list,tuple)) else []:
        if not isinstance(item,dict) or item.get('validated') is not True or not item.get('source') or item.get('asset') not in assets: continue
        age=stamp_age(item.get('as_of'),now=now)
        if age is None: continue
        historical=item.get('presentation_state')=='HISTORICAL_STALE' or 'last_bias' in item or 'macro_score' in item
        if age>60 and not historical: continue
        row={key:item[key] for key in ('asset','source','as_of')}
        row['presentation_state']='HISTORICAL_STALE' if item.get('presentation_state')=='HISTORICAL_STALE' or age>60 else 'CURRENT'
        if age<=60 and item.get('presentation_state')!='HISTORICAL_STALE':
            for key in ('score','change_pct'):
                value=item.get(key)
                if isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value): row[key]=value
            if item.get('bias') in ('Compra','Venda','Neutro'): row['bias']=item['bias']
        quote_age=stamp_age(item.get('quote_as_of') or item.get('as_of'),now=now)
        if quote_age is not None and quote_age<=60 and item.get('presentation_state')!='HISTORICAL_STALE' and finite_positive(item.get('price')):
            row['price']=item['price'];row['quote_current']=True
        if item.get('last_bias') in ('COMPRA','VENDA','NEUTRO','AGUARDAR'):
            row.update(last_bias=item['last_bias'],temporal_state=str(item.get('temporal_state') or 'UNVERIFIED'))
        if finite_positive(item.get('last_price')) and stamp_age(item.get('last_price_at'),now=now) is not None:
            row.update(last_price=item['last_price'],last_price_at=item['last_price_at'])
        macro=item.get('macro_score')
        if isinstance(macro,(int,float)) and not isinstance(macro,bool) and math.isfinite(macro): row['macro_score']=macro
        for key in ('series','historical_series'):
            series=item.get(key)
            if not isinstance(series,(list,tuple)) or len(series)<2 or not all(finite_positive(v) for v in series): continue
            series_age=stamp_age(item.get('series_as_of') or item.get('quote_as_of') or item['as_of'],now=now)
            times=item.get('series_timestamps')
            if times is not None:
                ages=[stamp_age(value,now=now) for value in times]
                if len(times)!=len(series) or any(a is None or a<15 for a in ages) or any(ages[i]<=ages[i+1] for i in range(len(ages)-1)): continue
                if not item.get('series_source'): continue
            if series_age is None: continue
            target='series' if key=='series' and series_age<=70 and row['presentation_state']=='CURRENT' else 'historical_series'
            if target=='historical_series' and not item.get('series_source'): continue
            row[target]=list(series)[-30:]
            row['series_as_of']=item.get('series_as_of') or item.get('quote_as_of') or item['as_of']
        accepted.append(row)
    return accepted


def market_ticker_html(area, items, assets, symbols):
    from html import escape
    records={row['asset']:row for row in normalize_market_items(items,assets)}
    ordered=list(dict.fromkeys(list(records)+list(assets)))
    tiles=[]
    for asset in ordered:
        row=records.get(asset,{})
        state='SEM FONTE LIVE CONFIGURADA' if '/' not in asset else 'SEM DADOS'
        price_label='Preço'; price='—'; change='—'
        if row:
            state='DADOS ATUAIS VALIDADOS' if row.get('presentation_state')=='CURRENT' and not row.get('last_bias') else 'ÚLTIMA LEITURA · REVALIDAR'
            if row.get('quote_current'): price=f"{row['price']:.4f}".replace('.',',')
            elif 'last_price' in row: price_label='Último preço';price=f"{row['last_price']:.5f}"
            if 'change_pct' in row: change=f"{row['change_pct']:+.2f}%".replace('.',',')
            if row.get('bias'): state+=' · '+row['bias']
            if row.get('last_bias'):
                code=row.get('temporal_state','UNVERIFIED')
                temporal='EXPIRADO · REVALIDAR · EXPIRED' if code=='EXPIRED' else 'SEM SINAL / AGUARDAR · NO_SIGNAL' if code=='NO_SIGNAL' else code+' · REVALIDAR'
                state+=' · Último viés: '+row['last_bias']+' · '+temporal
            if asset=='DXY':
                score=row.get('macro_score',row.get('score'))
                state=('Força USD macro: '+str(score)+' · Fonte: runtime macro · ' if score is not None else '')+'DXY spot: sem fonte live configurada'
        spark=''; series=row.get('series') or row.get('historical_series')
        if series:
            lo,hi=min(series),max(series)
            points=' '.join(f'{i*50/(len(series)-1):.1f},{18-(v-lo)/(hi-lo)*16 if hi>lo else 10:.1f}' for i,v in enumerate(series))
            label='Série atual M15 validada' if row.get('series') else 'HISTÓRICO M15 · REVALIDAR'
            spark=f'<span><svg class="cq-real-spark" viewBox="0 0 50 20" aria-label="{label}"><polyline points="{points}" fill="none" stroke="currentColor" stroke-width="1.3"/></svg><small style="white-space:normal;max-width:90px">{label}</small></span>'
        stamp=row.get('last_price_at') or row.get('as_of')
        updated=f'<small>Atualizado: {escape(str(stamp))}</small>' if stamp else ''
        tiles.append(f'<button class="cq-tick" data-route="radar" data-asset="{escape(asset)}" aria-label="{escape(asset+" · "+state)}"><span class="cq-symbols">{symbols(asset)}</span><span><strong>{escape(asset)}</strong><small>{price_label}: {price}</small><small>Variação: {change}</small>{updated}<em>{escape(state)}</em></span>{spark}</button>')
    historical=any(row.get('presentation_state')=='HISTORICAL_STALE' or row.get('last_bias') for row in records.values())
    global_state='ÚLTIMA LEITURA · REVALIDAR' if historical else 'DADOS ATUAIS VALIDADOS' if records else 'SEM DADOS · SEM FONTE LIVE CONFIGURADA onde não houver produtor'
    return _ticker_wrapper(tiles,global_state,bool(records))


def _ticker_wrapper(tiles,state,available):
    order='Ordem residente do motor' if available else 'Ordem de referência'
    return '<section class="cq-market" aria-label="Faixa de ativos"><button class="cq-scroll" data-ticker-step="-1" aria-label="Ativos anteriores">‹</button><div class="cq-ticker" tabindex="0" role="region" aria-label="Ativos · rolagem horizontal">'+''.join(tiles)+'</div><button class="cq-scroll" data-ticker-step="1" aria-label="Mais ativos">›</button></section><div class="cq-market-state">'+state+' <label>Organização <select aria-label="Organização dos ativos"><option>'+order+'</option><option disabled>Melhor viés · requer lista validada</option></select></label></div>'


def module_evidence_html(route, resident=None):
    from html import escape
    resident=resident if isinstance(resident,dict) else {}
    runtime=resident.get('runtime_status') or {}
    values=[]
    if route in {'scanner','autopilot','master'}:
        values=[('Atualização','AUTOMÁTICA · cron 7,37; nenhum clique de provider necessário'),
            ('Última execução',runtime.get('last_run') or (resident.get('freshness') or {}).get('generated_at','SEM DADOS')),
            ('Cota','480/dia · 28/hora · 6/62s'),
            ('Consumo observado',(runtime.get('twelve_budget') or {}).get('used','SEM DADOS')),
            ('Scanner fresco',runtime.get('scanner_fresh','SEM DADOS'))]
    elif route=='market_news':
        values=[('News Global',runtime.get('news_unique_stories','SEM DADOS')),
            ('Atualizado',runtime.get('news_updated_at','—'))]
    elif route=='news':
        state=runtime.get('news_nowcast_v1') or {}
        values=[('Pré-Notícia / Macro Briefing','Eventos e contexto macro; separado de News Global'),
            ('Nowcast EODHD',state.get('runtime_state','SEM DADOS')),
            ('Dependência','HTTP 401 · autenticação externa' if state.get('runtime_state') in {'AUTH_ERROR','AUTH_COOLDOWN'} else 'Sem previsão validada'),
            ('Retry (min)',state.get('provider_retry_after_min','—'))]
    elif route in {'paper','performance','guardian'}:
        keys=('paper_trading_v112','model_paper_v1','setup_audit_v114','quota_shadow') if route=='performance' else ('paper_trading_v112','model_paper_v1') if route=='paper' else ('quota_shadow',)
        for key in keys:
            data=runtime.get(key) or {}
            values.extend((key+' · '+field,data[field]) for field in ('trades_total','candidates_total','blocked_context','blocked_timeframe','open_positions','closed_trades','sample_state','quota_shadow_validated','provider_block_rate_pct') if field in data)
    elif route=='ict':
        for row in resident.get('ict_history') or []:
            values.extend([(row.get('pair','—')+' · ICT',row.get('ict_label') or row.get('ict_read') or 'SEM DADOS'),
                ('Referência técnica',row.get('technical_timestamp','—')),
                ('Estado','ÚLTIMA LEITURA · REVALIDAR' if resident.get('snapshot_state')=='STALE_HISTORY' or row.get('ict_fresh') is not True else 'ATUAL')])
    if not values: return ''
    return '<section class="ref-panel" aria-label="Estado residente do módulo">'+''.join('<p><strong>'+escape(str(key))+':</strong> '+escape(str(value))+'</p>' for key,value in values)+'</section>'
