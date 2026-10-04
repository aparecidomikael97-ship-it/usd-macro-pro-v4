"""Read-only presentation of resident engine output; no loaders or financial rules."""
from datetime import datetime, timezone
from html import escape
import math


def eligible_fx_population(resident=None, *, now=None):
    """Reuse the existing Radar ordering, publishing only confirmed resident rows.

    This does not calculate a score, signal or technical coverage. Freshness and
    provenance must already be supplied by the existing analytical page.
    """
    from atlasquant_fx_universe import OFFICIAL_PAIRS
    empty = {'ranked': [], 'universe': list(OFFICIAL_PAIRS), 'source': ''}
    if not isinstance(resident, dict): return empty
    freshness = resident.get('freshness')
    if not isinstance(freshness, dict): return empty
    if freshness.get('state') not in {'LIVE_REFRESH', 'CACHED_SNAPSHOT', 'VALIDATED_SNAPSHOT'}: return empty
    raw_stamp = freshness.get('runtime_generated_at') or freshness.get('generated_at')
    try:
        stamp = datetime.fromisoformat(str(raw_stamp).replace('Z', '+00:00'))
        age = ((now or datetime.now(timezone.utc)) - stamp).total_seconds()
        from atlasquant_fast_startup import DEFAULT_MAX_RUNTIME_AGE_MIN
        if age < -60 or age > DEFAULT_MAX_RUNTIME_AGE_MIN * 60: return empty
    except (ValueError, TypeError): return empty
    rows = resident.get('rows')
    if not isinstance(rows, (list, tuple)): return empty
    eligible = []; seen = set()
    for row in rows:
        if not isinstance(row, dict): continue
        pair = row.get('pair')
        pipeline = row.get('pipeline') or {}
        score = row.get('priority')
        if pair not in OFFICIAL_PAIRS or pair in seen: continue
        if row.get('data_ready') is not True or row.get('provenance_state') != 'CONFIRMADA': continue
        if not isinstance(pipeline, dict) or pipeline.get('ranking') != 'ELEGÍVEL PARA ESTUDO': continue
        if isinstance(score, bool) or not isinstance(score, (float, int)) or not math.isfinite(score): continue
        if not 0 <= score <= 100: continue
        if not row.get('evidence_source'): continue
        signal = row.get('signal') or {}
        if not isinstance(signal, dict) or signal.get('status_code') != 'CONFIRMED': continue
        try:
            expiry = datetime.fromisoformat(str(signal.get('valid_until')).replace('Z', '+00:00'))
            if expiry <= (now or datetime.now(timezone.utc)): continue
        except (ValueError, TypeError): continue
        seen.add(pair); eligible.append(dict(row))
    from atlasquant_radar_board import rank_fx_population
    ranked = rank_fx_population(eligible)
    return {'ranked': ranked, 'universe': list(OFFICIAL_PAIRS), 'source': str(freshness.get('source') or 'Radar existente')}


def direction_label(row, *, now=None):
    """Display direction only when the engine's temporal signal is confirmed."""
    signal = row.get('signal') or {}
    if not isinstance(signal, dict) or signal.get('status_code') != 'CONFIRMED': return 'Direção: aguardando confirmação'
    try:
        expires = datetime.fromisoformat(str(signal.get('valid_until')).replace('Z', '+00:00'))
        if expires <= (now or datetime.now(timezone.utc)): return 'Direção: sinal expirado'
    except (ValueError, TypeError): return 'Direção: aguardando confirmação'
    side = signal.get('side')
    return 'Direção: ' + ({'BUY': 'Compra confirmada', 'SELL': 'Venda confirmada'}.get(side) or 'aguardando confirmação')


def forex_board_html(resident=None, *, compact=False):
    model = eligible_fx_population(resident)
    ranked = model['ranked']; published = {row['pair'] for row in ranked}
    def card(pair, row=None, position=None, featured=False):
        row = row or {}
        number = (f'<b class="final-position">#{position}</b>' + ('<i class="final-ring" aria-hidden="true"></i>' if featured else '')) if position else '<small>MONITORADO · SEM POSIÇÃO PUBLICADA</small>'
        details = ('<span>' + escape(direction_label(row)) + '</span><small>Força: ' + escape(f"{row['priority']:.1f}") + '</small>') if position else '<span>Sem leitura elegível para ranking</span>'
        context = f'<p>{escape(str(row.get("reason") or "Contexto não informado"))}</p>' if featured else ''
        return f'<article class="ref-pair final-fx-card {"final-featured" if featured else "final-secondary"}" data-pair="{escape(pair)}" data-ranked="{str(bool(position)).lower()}">{number}<strong>{escape(pair)}</strong>{details}{context}<button data-route="why:{escape(pair)}">Ver por quê</button></article>'
    if ranked:
        top = ranked[:10]
        featured = '<section class="final-top"><h2>Top 10 · ranking validado</h2><p class="cq-note">' + escape(model['source']) + ' · ' + str(len(ranked)) + ' pares elegíveis · destaque não autoriza entrada</p><div class="final-top-grid">' + ''.join(card(row['pair'], row, i+1, True) for i,row in enumerate(top)) + '</div></section>'
        remaining = ''.join(card(row['pair'], row, i+11) for i,row in enumerate(ranked[10:]))
    else:
        featured = '<section class="final-top final-empty"><h2>Ranking aguardando dados validados</h2><p>28 pares monitorados. Nenhum Top 10 publicado sem leitura elegível e proveniência confirmada.</p><button data-route="connected:radar">Abrir Radar existente</button></section>'
        remaining = ''
    remaining += ''.join(card(pair) for pair in model['universe'] if pair not in published)
    return f'<div class="final-fx-board {"final-compact" if compact else ""}" data-eligible-count="{len(ranked)}">{featured}<aside class="final-rest"><h2>{"Demais posições / monitorados" if ranked else "Universo monitorado · 28 pares"}</h2><div class="final-rest-grid">{remaining}</div></aside></div>'


def pair_reason_html(pair, resident=None):
    model = eligible_fx_population(resident)
    row = next((row for row in model['ranked'] if row['pair'] == pair), None)
    if row is None:
        history = (resident or {}).get('history') or []
        old = next((value for value in history if value.get('pair') == pair), None)
        if old:
            return resident_context_html('scanner', {'history': [old]})
        return '<p>Par monitorado; ranking e direção aguardando dados validados.</p>'
    reasons = '<p>' + escape(str(row.get('reason') or 'Motivo não informado pelo motor.')) + '</p>'
    reasons += '<p>' + escape(direction_label(row)) + '</p>'
    reasons += '<p>Estado: ' + escape(str(row.get('state') or 'não informado')) + ' · Gate: ' + escape(str(row.get('gate') or 'não informado')) + '</p>'
    for key, label in [('blockers','Bloqueios'), ('positives','Evidências')]:
        items = row.get(key)
        if isinstance(items, (list, tuple)) and items:
            reasons += '<h3>' + label + '</h3><ul>' + ''.join('<li>' + escape(str(value)) + '</li>' for value in items) + '</ul>'
    return reasons + '<p>Leitura de estudo; nenhuma autorização de execução.</p>'


def temporal_signal_status(signal, *, now=None):
    signal = signal if isinstance(signal,dict) else {}
    code = str(signal.get('status_code') or 'UNVERIFIED')
    if code in {'CONFIRMED','POSSIBLE'}:
        try:
            expiry=datetime.fromisoformat(str(signal.get('valid_until')).replace('Z','+00:00'))
            if expiry <= (now or datetime.now(timezone.utc)): return 'EXPIRED'
        except (ValueError,TypeError): return 'UNVERIFIED'
    return code


def resident_context_html(selected, resident=None):
    """Bounded presentation of persisted evidence; no provider or scoring calls."""
    resident = resident if isinstance(resident, dict) else {}
    def fields(values):
        return '<article class="ref-panel">' + ''.join(
            '<p><strong>'+escape(str(key))+':</strong> '+escape(str(value))+'</p>'
            for key,value in values) + '</article>'
    if selected == 'market_map' and resident.get('market_map'):
        return '<p>Projeção do Market Map persistido nos packs · sem nova coleta. Frescor técnico independente do snapshot.</p>'+''.join(fields([
            ('Par',row.get('pair','—')),('W1',row.get('w1','—')),('D1',row.get('d1','—')),
            ('Zona',row.get('pd_zone','—')),('Risco de evento',row.get('event','—')),
            ('Referência técnica',row.get('technical_timestamp','—')),
            ('Frescor','CURRENT' if row.get('map_current') is True else 'EXPIRED / REVALIDAR'),
        ]+[(name,level) for name,level in (row.get('levels') or {}).items()]) for row in resident['market_map'] if isinstance(row,dict))
    if selected in {'scanner','radar','radar_master','master','market_map'}:
        history = resident.get('history') or []
        return '<section aria-label="Leituras técnicas persistidas">' + ''.join(fields([
            ('Par',row.get('pair','—')), ('Último viés',row.get('bias','—')),
            ('Status temporal',temporal_signal_status(row.get('signal'))+(' / REVALIDAR' if temporal_signal_status(row.get('signal'))!='CONFIRMED' else ' · validade técnica independente do snapshot')),
            ('Referência',(row.get('signal') or {}).get('reference_at','—')),
            ('Validade técnica',(row.get('signal') or {}).get('valid_until','—')),
            ('H4',row.get('h4','—')), ('H1',row.get('h1','—')), ('M15',row.get('m15','—')),
            ('Gate',row.get('gate','—')), ('Prioridade',row.get('priority','—')),
            ('Qualidade',row.get('data_score','—')),
        ]) for row in history if isinstance(row,dict)) + '</section>' if history else ''
    if selected in {'macro','fed'}:
        context = resident.get('macro_context') or {}
        value = context.get('fed' if selected == 'fed' else 'macro_eua') or {}
        if not isinstance(value,dict): return ''
        rows = [('Snapshot macro',resident.get('macro_as_of','—'))]
        if selected == 'fed':
            rows += [(key,value[key]) for key in ('tom','forca') if key in value]
            rows += [('Manchete persistida',title) for title in (value.get('titulos') or [])[:5]]
        else:
            rows += [('Índice amplo USD (FRED)' if key=='Índice amplo do dólar' else key,item) for key,item in value.items() if not key.startswith('_') and isinstance(item,(int,float,str))]
            rows += [('Auditoria FRED',str(item.get('Indicador'))+' · '+str(item.get('Última observação'))+' · '+str(item.get('Fonte'))+' · '+str(item.get('Status'))) for item in (value.get('_auditoria') or []) if isinstance(item,dict)]
            rows += [('DXY','Índice amplo FRED não é cotação spot DXY')]
        return fields(rows) if value else ''
    if selected in {'indexes','crypto'}:
        from atlasquant_radar_board import INDEX_UNIVERSE, CRYPTO_UNIVERSE
        universe = INDEX_UNIVERSE if selected == 'indexes' else CRYPTO_UNIVERSE
        return '<p>Universo implementado; coleta live específica não encontrada.</p>'+fields([(symbol,label+' · — · SEM LEITURA AO VIVO') for symbol,label in universe])
    return ''


AION_PRESENTATION_ROLES = (
    ('Orquestrador / Núcleo', 'Coordena contexto e prioridades.'),
    ('Arquiteto / Estrategista', 'Planeja arquitetura e evolução.'),
    ('Guardião / Auditor', 'Revisa evidências, políticas e bloqueios.'),
    ('Prime / Execução', 'Ações somente com gates e aprovação.'),
    ('Shadow / Pesquisa e Triagem', 'Pesquisa e organiza evidências.'),
    ('Sentinel / Monitoramento', 'Observa saúde e estados do ecossistema.'),
    ('Comercial / Leads e CRM', 'Apoia relacionamento e oportunidades.'),
    ('Educador / Treinamento', 'Explica e organiza aprendizado.'),
)


def aion_roles_html():
    return '<section class="final-aion-roles"><div class="final-core"><span aria-hidden="true">◉</span><h2>Um único AION Core</h2><p>8 papéis internos · Não são oito IAs independentes; responsabilidades compartilhadas, sem autonomia crítica independente</p></div><div class="final-role-grid">' + ''.join(f'<article data-internal-role="{i}"><small>PAPEL {i}</small><strong>{escape(label)}</strong><p>{escape(purpose)}</p></article>' for i,(label,purpose) in enumerate(AION_PRESENTATION_ROLES,1)) + '</div></section>'


def snapshot_filter_fields(snapshot):
    settings = (snapshot.get('settings') or {}).get('values') or {}
    bundle = (snapshot.get('evidence') or {}).get('bundle') or {}
    stamp = str(snapshot.get('created_at') or '')
    return {'Ano': stamp[:4], 'Mês': stamp[5:7], 'Setup': str(settings.get('strategy') or settings.get('setup') or bundle.get('setup') or 'Não informado'), 'Ativo': str(bundle.get('pair') or settings.get('pair') or 'Não informado'), 'Timeframe': str(settings.get('execution_timeframe') or settings.get('timeframe') or bundle.get('timeframe') or 'Não informado')}


def snapshot_filter_values(snapshot):
    fields = snapshot_filter_fields(snapshot)
    values = {key: [value] for key, value in fields.items()}
    bundle = (snapshot.get('evidence') or {}).get('bundle') or {}
    if fields['Setup'] == 'Não informado':
        strategies = sorted({str(row['strategy']) for row in bundle.get('evidence_summary', [])
                             if isinstance(row, dict) and row.get('strategy')})
        if strategies: values['Setup'] = strategies
    return values


def filter_snapshot_history(snapshots, filters):
    return [snapshot for snapshot in snapshots if all(value == 'Todos' or value in snapshot_filter_values(snapshot).get(key, []) for key,value in filters.items())]


def aion_workspace_html(*, mode, name, show_central, nav_html, uri):
    from atlasquant_compact_cockpit import header_html
    top = '<button data-route="central">← Central</button>' if show_central else ''
    header = header_html('aion', name, mode, top)
    drawer = '<details class="ref-drawer"><summary>Funções do AION · Ver todas</summary><nav>' + nav_html('aion', mode) + '</nav></details>'
    cards = ''.join(f'<button class="cq-panel ref-mobile-card" data-route="{route}"><strong>{label}</strong><small>{description}</small></button>' for route,label,description in (
        ('processing','Processamento de Dados','Estados e fontes do ecossistema'),
        ('models','Modelos de IA','Modelos e cenários'),
        ('learning','Aprendizado Contínuo','Conhecimento com proveniência'),
        ('integrations','Integrações','Ambientes conectados'),
        ('security','Segurança e Controle','Ações críticas controladas'),
        ('knowledge','Núcleo Global','Base de conhecimento compartilhada'),
        ('monitoring','Monitoramento','Saúde e estados do sistema'),
        ('roles','8 Papéis Internos','Um único AION Core')))
    hero = f'<div class="final-aion-banner"><div><h1>AION</h1><p>Núcleo de inteligência do AtlasQuant</p><p>Poderoso por dentro. <strong>Simples por fora.</strong></p></div><img src="{uri("aion-body.webp")}" alt="Ilustração do núcleo AION"/></div>'
    return f'<section class="ref-workspace ref-aion cq-workspace final-aion-workspace" data-workspace="aion" style="--accent:#7596ff;--ref-icon-image:url({uri("aion_nav.webp")})">{header}{drawer}<div class="ref-canvas cq-canvas"><div class="cq-layout"><nav class="cq-nav ref-sidebar ref-aion" aria-label="Funções do AION">{nav_html("aion",mode)}</nav><main class="cq-main">{hero}{aion_roles_html()}<div class="final-aion-tools">{cards}</div></main></div></div><p class="ref-truth">Arte aprovada · dados da imagem ilustrativos. Papéis de apresentação de um único núcleo. Nenhuma IA independente ou autonomia crítica nova. Dados e estados não informados permanecem indisponíveis.</p></section>'
