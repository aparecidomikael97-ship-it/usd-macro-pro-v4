"""Compact presentation only: no provider, price calculation or authorization changes."""
from html import escape

TRADER_ASSETS = ("DXY", "EUR/USD", "GBP/USD", "AUD/USD", "USD/JPY", "USD/CHF", "USD/CAD", "NZD/USD", "NASDAQ", "S&P 500", "IBOV", "OURO", "PETR4", "VALE3", "BTC", "ETH")
INVESTMENT_ASSETS = ("IBOV", "S&P 500", "NASDAQ", "PETR4", "VALE3", "ETF", "TESOURO", "OURO", "BTC", "ETH")
CURRENCIES = {"USD":"US", "EUR":"EU", "GBP":"GB", "AUD":"AU", "JPY":"JP", "CHF":"CH", "CAD":"CA", "NZD":"NZ"}


def flag(code):
    """Local SVG country/currency symbols: stable identification, never inferred from price."""
    star = '<path d="M0 -3L.9 -.9 3 -.9 1.5 .6 1.9 2.7 0 1.4 -1.9 2.7 -1.5 .6 -3 -.9 -.9 -.9Z" fill="#ffe46b"/>'
    if code == "US":
        art = '<rect width="30" height="20" fill="white"/>' + ''.join(f'<rect y="{i*20/13}" width="30" height="{20/13}" fill="#c92e43"/>' for i in range(0,13,2)) + '<rect width="13" height="11" fill="#15356f"/>' + ''.join(f'<circle cx="{1+i*2+(j%2)}" cy="{1+j*1.1}" r=".35" fill="white"/>' for j in range(9) for i in range(6 if j%2==0 else 5))
    elif code == "EU":
        import math
        art = '<rect width="30" height="20" fill="#1242a8"/>' + ''.join(f'<g transform="translate({15+6*math.sin(i*math.pi/6)} {10-6*math.cos(i*math.pi/6)}) scale(.4)">{star}</g>' for i in range(12))
    elif code in {"GB","AU","NZ"}:
        union = '<rect width="30" height="20" fill="#15356f"/><path d="M0 0L30 20M30 0L0 20" stroke="white" stroke-width="4"/><path d="M0 0L30 20M30 0L0 20" stroke="#c92e43" stroke-width="1.6"/><path d="M15 0V20M0 10H30" stroke="white" stroke-width="7"/><path d="M15 0V20M0 10H30" stroke="#c92e43" stroke-width="4"/>'
        art = union if code == "GB" else '<rect width="30" height="20" fill="#15356f"/><g transform="scale(.5)">'+union+'</g>' + ''.join(f'<g transform="translate({x} {y}) scale(.5)">'+star.replace('#ffe46b', '#ffffff' if code=='AU' else '#fa5061')+'</g>' for x,y in [(23,6),(20,12),(27,12),(23,17)] + ([(8,15),(25,14)] if code=='AU' else []))
    elif code == "JP":
        art = '<rect width="30" height="20" fill="white"/><circle cx="15" cy="10" r="6" fill="#c92e43"/>'
    elif code == "CH":
        art = '<rect width="30" height="20" fill="#ce233e"/><path d="M15 4V16M9 10H21" stroke="white" stroke-width="4"/>'
    elif code == "CA":
        art = '<rect width="30" height="20" fill="white"/><path d="M0 0H7V20H0ZM23 0H30V20H23Z" fill="#ce233e"/><path d="M15 3L17 7 20 6 19 10 22 11 17 14 17 16 15 15 15 18 14 18 14 15 12 16 12 14 8 11 11 10 10 6 13 7Z" fill="#ce233e"/>'
    elif code == "BR":
        art = '<rect width="30" height="20" fill="#15934e"/><path d="M15 2L28 10 15 18 2 10Z" fill="#ffe46b"/><circle cx="15" cy="10" r="5" fill="#134bb0"/><path d="M10 8Q15 7 20 11" stroke="white" fill="none"/>'
    else:
        raise ValueError("unknown country symbol")
    names={"US":"Estados Unidos","EU":"Eurozona","GB":"Reino Unido","AU":"Austrália","JP":"Japão","CH":"Suíça","CA":"Canadá","NZ":"Nova Zelândia","BR":"Brasil"}
    return f'<svg class="cq-flag" role="img" data-country="{code}" aria-label="{names[code]}" viewBox="0 0 30 20"><title>{names[code]}</title>{art}</svg>' 


def asset_symbol(asset):
    if "/" in asset:
        a,b=asset.split("/")
        return flag(CURRENCIES[a])+flag(CURRENCIES[b])
    if asset=="DXY": return flag("US")
    if asset in {"PETR4","VALE3"}: return flag("BR")
    icon = "₿" if asset=="BTC" else "Ξ" if asset=="ETH" else "Au" if asset=="OURO" else "RF" if asset=="TESOURO" else "ETF" if asset=="ETF" else "▥"
    return f'<span class="cq-class-icon" aria-label="Classe do ativo {escape(asset)}">{icon}</span>'


def normalized_market_items(items):
    from atlasquant_runtime_presentation import normalize_market_items
    return normalize_market_items(items,set(TRADER_ASSETS+INVESTMENT_ASSETS))


def ticker_html(area,items=None):
    if area not in {'trader','investimentos'}: return ''
    from atlasquant_runtime_presentation import market_ticker_html
    return market_ticker_html(area,items,TRADER_ASSETS if area=='trader' else INVESTMENT_ASSETS,asset_symbol)


def header_html(area,name,mode,top,market_items=None):
    title={"trader":"Trader","negocios":"Negócios","investimentos":"Investimentos","aion":"AION"}[area]
    from atlasquant_reference_ui import asset_uri
    return f'<header class="cq-header"><div class="ref-toolbar" style="background-image:linear-gradient(90deg,#020b20ee,#020b2077,#020b20ee),url({asset_uri("trader-city.webp")});background-size:cover"><button class="cq-brand" data-route="home"><img class="cq-mark" src="{asset_uri("trader-mark.webp")}" alt=""/><span>ATLASQUANT<small>ECOSSISTEMA · {title}</small></span></button><div class="cq-header-actions">{top}<button data-route="mode" class="ref-mode">Modo {escape(mode)}</button><button data-route="notifications" aria-label="Notificações"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><path d="M6 16H18L16 13V9A4 4 0 006 9V13ZM10 19H14M12 3V5"/></svg></button><button data-route="profile">{escape(name)}</button></div></div>{ticker_html(area,market_items)}</header>'


def trader_html(*,mode,selected,name,show_central,nav_html,module_panel,uri,market_items=None,fx_population=None):
    top='<button data-route="central" class="ref-return">← Central</button>' if show_central else ''
    header=header_html('trader',name,mode,top,market_items)
    guidance = 'Iniciante: orientação simplificada; todas as funções, inclusive avançadas, continuam disponíveis.' if str(mode).startswith('Inic') else 'Avançado: acesso direto a todas as funções.'
    drawer=f'<details class="ref-drawer cq-functions"><summary><strong>Funções do Trader · 24</strong><span>Ver todas as funções · inclui avançadas</span></summary><p class="cq-functions-note">{guidance}</p><nav aria-label="24 funções do Trader">{nav_html("trader",mode)}</nav></details>'
    nav=f'<nav class="cq-nav ref-sidebar ref-trader" aria-label="24 funções do Trader"><strong class="cq-nav-title">Funções · 24</strong>{nav_html("trader",mode)}</nav>'
    detail=module_panel('trader',selected) if selected else ''
    if selected.startswith('why:'):
        from atlasquant_interface_final import pair_reason_html
        detail=f'<main class="ref-detail"><div class="ref-detail-head"><h1>{escape(selected[4:])} · Ver por quê</h1><button data-route="home">Voltar à visão geral</button></div>{pair_reason_html(selected[4:],fx_population)}<button data-route="radar">Voltar ao Radar</button></main>'
    if detail:
        content=f'<div class="ref-detail-layout"><nav class="ref-detail-nav" aria-label="24 funções do Trader"><strong class="cq-nav-title">Funções · 24</strong>{nav_html("trader",mode)}</nav>{detail}</div>'
    else:
        cards=[]
        for route,label,desc,image,icon in [('indexes','Índices','S&P 500 · Nasdaq','trader-indices.webp',''),('commodities','Commodities','Ouro · Petróleo','trader-commodities.webp',''),('stocks','Ações','Principais bolsas','trader-stocks.webp',''),('day','Manhã','Panorama do dia','','☀'),('close_day','Fechamento do Dia','Resumo e movimentos','','↗'),('close_week','Fechamento da Semana','Desempenho e contexto','','▦'),('week','Análise da Semana','Tendências e oportunidades','','▥')]:
            art=f'<img src="{uri(image)}" alt=""/>' if image else f'<span class="cq-card-icon" aria-hidden="true">{icon}</span>'
            cards.append(f'<button class="cq-card ref-mobile-card" data-route="{route}" aria-label="{label}">{art}<strong>{label}</strong><small>{desc}</small></button>')
        from atlasquant_fx_universe import OFFICIAL_PAIRS
        from atlasquant_interface_final import eligible_fx_population, temporal_signal_status
        population=eligible_fx_population(fx_population)
        history=(fx_population or {}).get('history') or []
        pairs=[row['pair'] for row in population['ranked'][:10]] or [row['pair'] for row in history] or list(OFFICIAL_PAIRS)[:10]
        ranking_label='Top 10 · ranking validado' if population['ranked'] else 'Ranking aguardando dados validados'
        resident_rows={row['pair']:row for row in history}
        resident_rows.update({row['pair']:row for row in population['ranked']})
        published={row['pair'] for row in population['ranked']}
        rows=[]
        for i,pair in enumerate(pairs):
            row=resident_rows.get(pair,{})
            bias=row.get('action') if row.get('action') in {'COMPRA','VENDA','NEUTRO','NÃO OPERAR','NAO OPERAR'} else ''
            if row and pair not in published:
                bias='Último viés: '+str(row.get('bias') or 'AGUARDAR')
            bias_html=f'<small class="cq-engine-bias">{escape(bias)}</small>' if bias else ''
            facts=[]
            if row:
                facts.append(str(row.get('state') or 'Estado indisponível'))
                signal=row.get('signal') or {}
                facts.append('Status temporal: '+temporal_signal_status(signal)+(' / REVALIDAR' if pair not in published else ''))
                facts.append('Validade técnica: '+str(signal.get('valid_until') or '—'))
                facts.append(f"Prioridade {row['priority']:.1f} · Qualidade {row['data_score']:.1f}")
                technical=' · '.join(f'{key.upper()}: {row[key]}' for key in ('h4','h1','m15') if row.get(key) not in (None,'','—','N/D'))
                if technical: facts.append(technical)
                facts.append('Gate: '+str(row.get('gate') or '—'))
                facts.append('Snapshot: '+str((fx_population.get('freshness') or {}).get('generated_at') or '—'))
            context_html=''.join(f'<small class="cq-engine-context">{escape(fact)}</small>' for fact in facts)
            position='#'+str(i+1) if population['ranked'] else '—'
            rows.append(f'<div class="cq-pair"><span class="cq-symbols">{asset_symbol(pair)}</span><strong>{escape(pair)}{bias_html}{context_html}</strong><span class="cq-pending">{position}</span><button data-route="why:{pair}">Ver por quê</button></div>')
        rows=''.join(rows)
        radar=f'<section class="cq-panel cq-bias"><button class="cq-panel-head" data-route="radar">Viés Atual do Mercado <span>↗</span></button><p class="cq-pending">{ranking_label}</p><div class="cq-neutral-bar" aria-hidden="true"></div><button class="cq-panel-head" data-route="scanner">Scanner Técnico · universo Forex</button><p class="cq-note">28 pares monitorados; cobertura técnica conforme o motor.</p><div class="cq-pairs" data-universe="forex">{rows}</div></section>'
        globe=f'<button class="cq-globe" data-route="master" aria-label="Painel Mestre"><img src="{uri("trader-globe.webp")}" alt="Globo do cockpit Trader"/><span>Painel Mestre · 28 pares</span></button>'
        aion=f'<button class="cq-panel cq-aion" data-route="aion_specialist"><img src="{uri("trader-aion.webp")}" alt=""/><span><strong>AION Trader</strong><small>Inteligência neste ambiente</small></span><b>›</b></button>'
        side=aion+''.join(f'<button class="cq-panel cq-info ref-mobile-card" data-route="{route}"><span aria-hidden="true">{icon}</span><span><strong>{label}</strong><small>{desc}</small></span><b>›</b></button>' for route,label,desc,icon in [('market_news','Notícias em Tempo Real','Principais eventos e impacto','▤'),('calendar','Calendário Econômico','Próximos eventos e indicadores','▦'),('geo','Eventos Geopolíticos','Mapa de Risco Global','◎'),('guardian','Alertas e Risco','Aguardando sinais validados','♧')])
        footer=''.join(f'<button class="cq-panel ref-mobile-card" data-route="{route}"><strong>{label}</strong><small>{desc}</small></button>' for route,label,desc in [('journal','Diário','Registro e acompanhamento'),('macro','Macro · EUA','Contexto dos EUA e USD'),('fed','Fed','Política monetária e narrativa'),('news','Pré-Notícia / Macro Briefing','Eventos e briefing antes da divulgação'),('market_map','Market Map','Contexto intermercado'),('autopilot','Autopilot','Monitoramento e auditoria'),('performance','Performance / Melhorias','Métricas, estabilidade e validação'),('micro','Microeconomia','Setores e economia real'),('fundamental','Fundamentalista','Análise de ativos'),('ict','ICT / Smart Money','Estruturas de mercado'),('paper','Paper Trading','Simulação'),('lab','Laboratório / Backtests','Testes e estatísticas'),('academy','Academia','Cursos e aprendizado'),('video','Vídeos / Análises','Conteúdo'),('profile','Perfil / Configurações','Preferências')])
        hero=f'<div class="cq-hero" style="background-image:url({uri("trader-banner.webp")})"><div><h1>Trader</h1><p>Análises · Estratégias · Operações</p></div><p>Poderoso por dentro. <strong>Simples por fora.</strong></p></div>'
        content=f'<div class="ref-canvas cq-canvas"><div class="cq-layout">{nav}<main class="cq-main">{hero}<div class="cq-cards">{"".join(cards)}</div><div class="cq-overview">{radar}{globe}<section class="cq-side">{side}</section></div><div class="cq-tools">{footer}</div></main></div></div>'
    return f'<section class="ref-workspace ref-trader cq-workspace" data-workspace="trader" style="--ref-icon-image:url({uri("trader_nav.webp")})">{header}{drawer}{content}<p class="ref-truth">Elementos gráficos da referência · dados da imagem ilustrativos substituídos por campos sem cotação; métricas sem evidência ficam indisponíveis; ranking depende de validação do motor</p></section>'
