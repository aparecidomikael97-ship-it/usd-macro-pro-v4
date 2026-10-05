"""Reference artwork + accessible hit regions, no business logic or provider I/O.

Only trusted, versioned markup enters the component. All identity/content strings
are escaped. Client events are revalidated against the rendered workspace.
"""
from functools import lru_cache
from html import escape
from pathlib import Path
import base64

ASSET_ROOT = Path(__file__).parent / "assets" / "ecosystem_reference"
SURFACES = {"central": ("central.webp", 768, 512),
            "trader": ("trader.jpg", 1280, 720),
            "negocios": ("negocios-body.webp", 768, 434),
            "investimentos": ("investimentos-body.webp", 1048, 665),
            "aion": ("aion-body.webp", 1048, 665)}
TRADER_NAV = (("home", "Início"), ("radar", "Radar"), ("scanner", "Scanner Técnico"),
    ("master", "Painel Mestre"), ("macro", "Macro · EUA"), ("fed", "Fed"), ("micro", "Micro"),
    ("geo", "Geopolítica"), ("market_news", "Notícias"), ("fundamental", "Fundamentalista"),
    ("ict", "ICT / SMC"), ("calendar", "Calendário Econômico"),
    ("news", "Pré-Notícia / Macro Briefing"), ("market_map", "Market Map"),
    ("lab", "Laboratório / Backtests"), ("paper", "Paper Trading"),
    ("guardian", "Guardião de Risco"), ("autopilot", "Autopilot"), ("performance", "Performance / Melhorias"), ("academy", "Academia"),
    ("journal", "Diário"), ("video", "Vídeos / Conteúdo"), ("aion_specialist", "AION Trader"),
    ("profile", "Perfil / Configurações"))
NAV = {
 "trader": TRADER_NAV,
 "negocios": (("home", "Início"), ("overview", "Visão Geral"), ("companies", "Empresas / Clientes"),
    ("b2b", "Automação B2B"), ("leads", "Leads"), ("revenue", "Revenue Ops"), ("crm", "CRM"),
    ("proposals", "Propostas"), ("followup", "Follow-up"), ("saas", "Micro-SaaS"),
    ("international", "Serviços Internacionais"), ("digital", "Produtos Digitais"),
    ("integrations", "Integrações"), ("finops", "Financeiro / FinOps"), ("roi", "ROI"),
    ("success", "Saúde do Cliente"), ("sla", "SLA / Suporte"), ("privacy", "Auditoria / LGPD"),
    ("team", "Equipe & Acessos"), ("sandbox", "Demo / Sandbox"),
    ("aion_specialist", "AION Negócios"), ("profile", "Configurações")),
 "investimentos": (("home", "Visão Geral"), ("radar", "Radar"), ("week", "Análise da Semana"),
    ("indexes", "Índices"), ("commodities", "Commodities"), ("stocks", "Ações Globais"),
    ("fixed", "Renda Fixa"), ("crypto", "Criptomoedas"), ("funds", "Fundos e ETFs"),
    ("portfolio", "Carteira Global"), ("reports", "Relatórios"), ("aion_specialist", "AION Investimentos"),
    ("profile", "Configurações")),
 "aion": (("home", "Núcleo AION"), ("models", "Modelos de IA"), ("processing", "Processamento"),
    ("learning", "Aprendizado"), ("knowledge", "Base de Conhecimento"), ("integrations", "Integrações"),
    ("security", "Segurança"), ("monitoring", "Monitoramento"), ("reports", "Relatórios"),
    ("chat", "Chat do AION"), ("memory", "Memória / Checkpoint"), ("roles", "8 Papéis Internos"),
    ("english", "AION · Inglês"), ("profile", "Configurações")),
}
# Coordinates use pixels in the approved single-workspace reference.
REGIONS = {
 "central": [("area:trader", "Trader", (20,147,173,259)), ("area:negocios", "Negócios", (204,149,173,258)),
   ("area:investimentos", "Investimentos", (385,148,175,257)), ("area:aion", "AION", (569,148,177,260)),
   ("profile", "Perfil", (545,8,118,49)), ("notifications", "Notificações", (669,10,25,42)),
   ("settings", "Configurações", (697,10,30,42)), ("session", "Sessão", (728,10,29,42))],
 "trader": [("week", "Análise da Semana", (180,151,414,177)), ("day", "Análise do Dia", (599,153,182,173)),
   ("close_day", "Fechamento do Dia", (787,151,187,176)), ("close_week", "Fechamento Semanal", (979,151,213,176)),
   ("macro", "Macro", (178,332,112,123)), ("micro", "Micro", (295,331,116,124)), ("geo", "Geopolítica", (415,331,140,124)),
   ("fundamental", "Fundamentalista", (560,332,117,123)), ("ict", "ICT / SMC", (679,332,114,123)),
   ("calendar", "Calendário Econômico", (798,332,112,123)), ("news", "Pré-Notícia", (915,332,111,123)),
   ("master", "Painel Mestre", (1031,332,162,123)), ("geo", "Mapa de Risco Global", (163,465,369,133)),
   ("news", "Notícias em Tempo Real", (163,604,276,111)), ("scanner", "Scanner Técnico", (541,456,252,253)),
   ("radar", "Viés Atual do Mercado", (830,463,173,170)), ("calendar", "Calendário Econômico", (1006,464,257,134)),
   ("geo", "Eventos Geopolíticos", (1006,602,257,108)), ("academy", "Academia", (448,640,105,76)),
   ("lab", "Laboratório", (559,638,117,78)), ("paper", "Paper Trading", (681,639,106,77)),
   ("guardian", "Guardião de Risco", (793,639,111,77)), ("journal", "Diário", (908,639,96,77))],
 "negocios": [],
 "investimentos": [("stocks", "Ações Globais", (173,400,163,112)), ("fixed", "Renda Fixa", (344,400,151,112)),
   ("funds", "Fundos e ETFs", (501,400,165,112)), ("crypto", "Criptomoedas", (672,400,165,112)),
   ("portfolio", "Carteira Global", (844,400,173,112)), ("radar", "Mercados em Destaque", (173,525,282,208)),
   ("portfolio", "Alocação Sugerida pela IA", (470,525,272,208)), ("week", "Oportunidades da Semana", (758,525,259,208))],
 "aion": [("processing", "Processamento de Dados", (188,400,135,111)), ("models", "Modelos de IA", (331,400,136,111)),
   ("learning", "Aprendizado Contínuo", (476,400,134,111)), ("integrations", "Integração Total", (619,400,136,111)),
   ("security", "Segurança e Controle", (764,400,134,111)), ("knowledge", "Núcleo Global", (890,400,144,111)),
   ("monitoring", "Status do Núcleo AION", (188,526,244,207)), ("knowledge", "Núcleo Global", (428,526,305,207)),
   ("reports", "Atividades Recentes", (745,526,289,207))],
}

# The Trader mobile home has an explicit visual contract instead of deriving
# cards from route ids. Several desktop regions intentionally reuse the same
# route (geo/news/calendar) and some source-art labels are legacy text hidden by
# desktop masks. Keeping the mobile card identity by (route, label, crop, kind)
# prevents route collisions and crops icon tiles above rasterized legacy labels.
# Desktop artwork and hit regions remain unchanged.
TRADER_MOBILE_CARDS = (
    ("week", "Análise da Semana", (180,151,414,177), "video"),
    ("day", "Análise do Dia", (599,153,182,173), "video"),
    ("close_day", "Fechamento do Dia", (787,151,187,176), "video"),
    ("close_week", "Fechamento Semanal", (979,151,213,176), "video"),
    ("macro", "Macro", (178,332,112,65), "icon"),
    ("micro", "Micro", (295,331,116,65), "icon"),
    ("geo", "Geopolítica", (415,331,140,65), "icon"),
    ("fundamental", "Fundamentalista", (560,332,117,65), "icon"),
    ("ict", "ICT / SMC", (679,332,114,65), "icon"),
    ("calendar", "Calendário Econômico", (798,332,112,65), "icon"),
    ("news", "Pré-Notícia", (915,332,111,65), "icon"),
    ("master", "Painel Mestre", (1031,332,162,65), "icon"),
    ("geo", "Mapa de Risco Global", (163,465,369,133), "panel"),
    ("news", "Notícias em Tempo Real", (163,604,276,111), "panel"),
    ("radar_master", "Radar Mestre", (541,456,252,253), "panel"),
    ("radar", "Viés Atual do Mercado", (830,463,173,170), "panel"),
    ("calendar", "Calendário Econômico", (1006,464,257,134), "panel"),
    ("geo", "Eventos Geopolíticos", (1006,602,257,108), "panel"),
    ("academy", "Academia", (448,640,105,38), "icon"),
    ("lab", "Laboratório", (559,638,117,40), "icon"),
    ("paper", "Paper Trading", (681,639,106,40), "icon"),
    ("guardian", "Guardião de Risco", (793,639,111,40), "icon"),
    ("journal", "Diário", (908,639,96,38), "icon"),
)

# Remove global market image bands at the asset source, not through CSS hiding.
for _area,_cut in (("negocios",78),("investimentos",83),("aion",83)):
    REGIONS[_area]=[(route,label,(x,y-_cut,w,h)) for route,label,(x,y,w,h) in REGIONS[_area]]
# Original ETF/crypto hit rectangles were 15-18 px left of the artwork border.
REGIONS["investimentos"][:5]=[("stocks","Ações Globais",(173,317,162,113)),
    ("fixed","Renda Fixa",(344,317,163,113)),("funds","Fundos e ETFs",(516,317,163,113)),
    ("crypto","Criptomoedas",(687,317,165,113)),("portfolio","Carteira Global",(862,317,170,113))]
EXTRA = {"trader": (("indexes","Índices"),("commodities","Commodities"),("stocks","Ações"),("week","Análise da Semana"),("day","Análise do Dia"),("close_day","Fechamento do Dia"),("close_week","Fechamento Semanal")),
 "central": (("profile","Perfil"),("notifications","Notificações"),("settings","Configurações"),("session","Sessão"))}
BEGINNER = {"home","radar","scanner","master","macro","news","market_news","academy","aion_specialist","profile","week","day","close_day","close_week"}
CSS = (Path(__file__).parent / "assets" / "ecosystem_reference" / "reference.css")


@lru_cache(maxsize=16)
def asset_uri(filename):
    data = (ASSET_ROOT / filename).read_bytes()
    mime = "image/jpeg" if filename.endswith(".jpg") else "image/webp"
    return f"data:{mime};base64," + base64.b64encode(data).decode()


def dimensions(area):
    if area in {"investimentos", "aion"}:
        return SURFACES[area][1:]
    return SURFACES[area][1:]


def action_labels(area):
    labels = dict(NAV.get(area, ()))
    labels.update(EXTRA.get(area, ()))
    labels.update({"profile":"Perfil / Configurações", "session":"Sessão", "search":"Buscar", "notifications":"Notificações", "settings":"Configurações"})
    labels.update({route: label for route, label, _ in REGIONS[area]})
    if area=='trader':
        labels.update(dict(TRADER_NAV))
        labels['market_news']='Notícias em Tempo Real'
    if area in {"negocios", "investimentos", "aion"}:
        from atlasquant_ecosystem_workspace_ui import workspace_modules
        labels.update({"extended:" + item["id"]: item["title"] for item in workspace_modules(area)})
    return labels


def hotspot(area, route, label, box, *, visible=False):
    w, h = dimensions(area)
    x, y, bw, bh = box
    radius = 16 if area == "central" and route.startswith("area:") else 8
    style = f"left:{x/w*100:.5f}%;top:{y/h*100:.5f}%;width:{bw/w*100:.5f}%;height:{bh/h*100:.5f}%;border-radius:{radius/bw*100:.3f}% / {radius/bh*100:.3f}%"
    if area == "central" and route.startswith("area:"):
        accent={"area:trader":"#21b9ff","area:negocios":"#ff9d1c","area:investimentos":"#28eaa7","area:aion":"#b678ff"}[route]
        style += f";--accent:{accent}"
    return (f'<button class="ref-hit{" ref-mask" if visible else ""}" data-route="{escape(route)}" '
            f'aria-label="{escape(label)}" title="{escape(label)}" style="{style}">'
            f'<span{" class=ref-sr" if not visible else ""}>{escape(label)}</span></button>')


def nav_html(area, mode):
    advanced = str(mode).startswith("Avan")
    rows = NAV.get(area, EXTRA.get(area, ()))
    def row(route, label):
        # Sample the original sidebar's own icon artwork, never substitute emoji.
        index = next((i for i,(key,_) in enumerate(rows) if key == route), 0)
        icon = f'<span class="ref-nav-icon" aria-hidden="true" style="background-size:18px {18*len(rows)}px;background-position:0 -{index*18}px"></span>'
        return f'<button data-route="{escape(route)}" class="ref-nav-item">{icon}{escape(label)}</button>'
    if area == "trader":
        # Experience mode changes guidance, never module discovery or availability.
        return "".join(row(k,v) for k,v in rows)
    essential = [row(k,v) for k,v in rows if area != "trader" or advanced or k in BEGINNER]
    secondary = [row(k,v) for k,v in rows if area == "trader" and not advanced and k not in BEGINNER]
    if area in {"negocios", "investimentos", "aion"}:
        extra = [(k,v) for k,v in action_labels(area).items() if k.startswith("extended:")]
        secondary += [row(k,v) for k,v in extra]
    return "".join(essential) + ('<details><summary>Todas as funções · Avançado</summary>' + "".join(secondary) + "</details>" if secondary else "")


def module_panel(area, selected, *, resident=None):
    title = action_labels(area).get(selected)
    if not title:
        return ""
    # Presentation reads resident context only. No scores, providers or executions.
    from atlasquant_runtime_presentation import module_state
    model=module_state(selected,resident) if area=='trader' else None
    cards = ""
    if area == "trader" and selected in {"radar", "radar_master", "master"}:
        from atlasquant_interface_final import forex_board_html
        cards = forex_board_html(resident)
    if area == "trader" and selected == "scanner":
        cards = '<p>Acompanhamento automático · leitura do estado persistido, sem consulta de provider.</p>'
    if area == "trader" and selected == "master":
        essentials = (("Scanner Técnico", module_state('scanner',resident)['detail'], "scanner"),
                      ("Contexto Macro", module_state('macro',resident)['detail'], "macro"),
                      ("Guardião de Risco", module_state('guardian',resident)['state'], "guardian"),
                      ("AION Trader", "Seu copiloto neste ambiente", "aion_specialist"))
        summary = '<div class="ref-master-summary">' + ''.join(
            f'<button data-route="{route}"><strong>{escape(label)}</strong><span>{escape(text)}</span></button>'
            for label,text,route in essentials) + '</div>'
        cards = summary + cards
    if area == "trader":
        from atlasquant_interface_final import resident_context_html
        cards += resident_context_html(selected, resident)
        from atlasquant_runtime_presentation import module_evidence_html
        cards += module_evidence_html(selected,resident)
        if selected == "indexes":
            cards += '<h2>Criptomoedas · universo separado</h2>' + resident_context_html('crypto', resident)
    if area == "aion" and selected == "roles":
        from atlasquant_interface_final import aion_roles_html
        cards = aion_roles_html()
    if area == "trader" and selected in {"lab", "paper", "journal"}:
        cards += '<div class="ref-preview-grid"><article><strong>Histórico</strong><p>Evolução das leituras; Diário reutiliza o Histórico existente.</p></article><article><strong>Backtest</strong><p>Regras em candles OHLC históricos, CSV TradingView, replay e métricas existentes.</p></article><article><strong>Paper / Forward</strong><p>Simulação prospectiva dentro do Backtest, sem ordem real.</p></article></div><h2>Histórico de Validação AtlasQuant</h2><p>Snapshots, comparação, integridade e backup ZIP no laboratório existente. Filtros de Ano, Mês, Setup, Ativo e Timeframe usam apenas registros disponíveis.</p><p class="ref-state">Armazenamento local: .atlasquant_research/backtest_snapshots. Persistência multiano externa ainda não garantida.</p>'
    if selected == "search":
        cards = '<label>Buscar módulo <input class="ref-search" type="search" placeholder="Radar, Macro, Calendário…" aria-label="Buscar módulo"></label><div class="ref-search-results">' + ''.join(
            f'<button data-route="{route}">{escape(label)}</button>'
            for route,label in NAV.get(area,()) if route != "home") + '</div>'
    if not cards and area in {"negocios", "investimentos", "aion"}:
        preview = {
            "negocios": (
                ("ESCOPO B2B", "Workspace isolado por empresa"),
                ("DADOS", "Somente fontes e integrações autorizadas"),
                ("AÇÃO EXTERNA", "Exige permissão e trilha de auditoria"),
            ),
            "investimentos": (
                ("ESCOPO", "Leitura e comparação de investimentos"),
                ("DADOS", "Sem cotação viva nesta prévia"),
                ("EXECUÇÃO", "Nenhuma ordem financeira automática"),
            ),
            "aion": (
                ("NÚCLEO", "Um único AION Core compartilhado"),
                ("CONHECIMENTO", "Memória e fontes com proveniência"),
                ("AUTORIDADE", "Ações críticas permanecem controladas"),
            ),
        }[area]
        cards = '<div class="ref-preview-grid">' + ''.join(
            f'<article><small>{escape(kicker)}</small><strong>{escape(text)}</strong></article>'
            for kicker, text in preview
        ) + '</div>'
    notice = ("28 pares monitorados. Ranking publicado somente para leituras elegíveis e validadas; destaque não autoriza execução."
              if cards and area == "trader" and selected in {"radar","master","radar_master"} else f"Prévia visual de {title}. Abra a análise existente para usar os recursos conectados.")
    if model:
        notice=model['detail']
    connected = ('<button class="ref-primary" data-route="connected:' + escape(selected) + '">Abrir análise existente</button>'
                 if area == "trader" and selected in {"radar","radar_master","scanner","master","macro","fed","micro","geo","market_news","fundamental","ict","calendar","news","market_map","lab","paper","guardian","autopilot","performance","academy","journal","video","profile"} else "")
    if selected.startswith("why:"):
        notice = "A direção deste par ainda não foi validada. Nenhuma recomendação de compra/venda é apresentada."
    data_state = "VALIDAÇÃO PENDENTE"
    if model:
        data_state=model['state']
    if area == "trader" and selected in {"radar", "master", "radar_master"}:
        from atlasquant_interface_final import eligible_fx_population
        if eligible_fx_population(resident)["ranked"]:
            data_state = "LEITURAS VALIDADAS"
    return (f'<main class="ref-detail" data-module="{escape(selected)}" data-resident-used="{str(bool(model and model["resident_used"])).lower()}">'
        f'<div class="ref-detail-kicker">ATLASQUANT · {escape(area.upper())}</div>'
        '<div class="ref-detail-head">'
        f'<h1>{escape(title)}</h1><button data-route="home">Voltar à visão geral</button></div>'
        f'<p class="ref-state">{escape(model["state"]) if model else "PRÉVIA · sem execução automática"}</p>'
        f'<p class="ref-detail-lede">{notice}</p>'
        '<div class="ref-detail-status">'
        f'<span><small>AMBIENTE</small><strong>{escape(area.upper())}</strong></span>'
        '<span><small>EXECUÇÃO</small><strong>BLOQUEADA</strong></span>'
        f'<span><small>DADOS</small><strong>{data_state}</strong></span>'
        f'</div>{connected}'
        '<div class="ref-tabs" role="tablist"><button data-local-tab="overview" aria-selected="true">Visão geral</button>'
        '<button data-local-tab="context" aria-selected="false">Contexto</button>'
        '<button data-local-tab="status" aria-selected="false">Estado</button></div>'
        f'<section data-tab-panel="overview">{cards or "<p>Nenhum dado validado disponível para exibir.</p>"}</section>'
        f'<section data-tab-panel="context" hidden><p>{escape(model["detail"]) if model else "Conteúdo complementar será exibido nesta aba."}</p></section>'
        f'<section data-tab-panel="status" hidden><p>{escape(model["state"]) if model else "Aguardando dados validados."}</p></section></main>')


def business_reference_home_html(*, mode="Avançado", name="Usuário", show_central=True):
    """Interactive Negócios home using the current B2B operating model.

    The legacy market-research raster remains versioned as provenance, but it is
    not used as the active Business workspace because its labels conflict with
    the current B2B/managed-operations contract.
    """
    from atlasquant_ecosystem_workspace_ui import WORKSPACE_CSS, workspace_modules, workspace_spec

    spec = workspace_spec("negocios")
    module_routes = {
        "b2b": "b2b",
        "revenue": "revenue",
        "saas": "saas",
        "international": "international",
        "digital": "digital",
        "finops": "finops",
        "success": "success",
        "sla": "sla",
        "integrations": "integrations",
        "privacy": "privacy",
        "team": "team",
        "sandbox": "sandbox",
        "aion-business": "aion_specialist",
    }
    nav = "".join(
        f'<button class="ref-nav-item aq-ws-nav-button" data-route="{escape(route)}" '
        f'aria-label="{escape(label)}">{escape(label)}</button>'
        for route, label in NAV["negocios"]
    )
    cards = []
    for item in workspace_modules("negocios"):
        route = module_routes.get(item["id"], item["id"])
        cards.append(
            f'<button class="aq-ws-card aq-ws-card-button" data-route="{escape(route)}" '
            f'aria-label="{escape(item["title"])}" data-module="{escape(item["id"])}" '
            f'data-feature-state="{escape(item["state"])}">'
            f'<small>{escape(item["group"])}</small>'
            f'<h4>{escape(item["title"])}</h4>'
            f'<p>{escape(item["summary"])}</p>'
            f'<span class="aq-ws-state" data-state="{escape(item["state"])}">{escape(item["state"])}</span>'
            '</button>'
        )
    back = (
        '<button data-route="central" class="ref-return aq-ws-back" aria-label="Voltar à Central">← Central</button>'
        if show_central else ""
    )
    mode_label = str(mode or "").strip() or "SESSÃO ATUAL"
    drawer = (
        '<details class="ref-drawer"><summary>Menu · Negócios</summary><nav>'
        + nav_html("negocios", mode)
        + ('<button data-route="central" class="ref-return">← Central</button>' if show_central else '')
        + '</nav></details>'
    )
    return (
        WORKSPACE_CSS
        + '<style>'
        '.aq-ws-nav-button{width:100%;text-align:left;background:transparent;border:1px solid transparent;'
        'border-radius:9px;padding:6px 8px;color:#cfe0f3;font:inherit;cursor:pointer}'
        '.aq-ws-nav-button:hover,.aq-ws-nav-button:focus-visible{border-color:rgba(73,230,178,.34);'
        'background:rgba(73,230,178,.08);outline:none}'
        '.aq-ws-card-button{width:100%;text-align:left;cursor:pointer;color:inherit;font:inherit}'
        '.aq-ws-back{position:static;margin:0 0 8px;display:inline-flex}'
        '.aq-ws-side.ref-sidebar{position:static!important;top:auto!important;left:auto!important;'
        'width:auto!important;height:auto!important;z-index:auto!important;overflow:auto;'
        'border-radius:18px;padding:10px;background:rgba(6,18,39,.78)}'
        '.ref-negocios:has(.aq-ws-business-canvas){max-width:100%!important;margin-inline:0!important}'
        '.aq-ws-business-canvas{position:relative!important;width:100%!important;height:auto!important;'
        'aspect-ratio:auto!important;background:none!important;margin:0!important}'
        '@media(max-width:700px){.ref-negocios .aq-ws-business-canvas{display:block!important}}'
        '</style>'
        '<section class="ref-workspace ref-negocios" data-workspace="negocios" '
        'data-business-contract="managed-operations-v1">'
        + back
        + drawer
        + '<div class="ref-canvas aq-ws-business-canvas" role="group" aria-label="Negócios · cockpit AtlasQuant">'
        + '<section class="aq-ws-shell" data-workspace="negocios">'
        '<div class="aq-ws-top">'
        '<div class="aq-ws-brand"><span class="aq-ws-mark">A</span>'
        '<span>ATLASQUANT · NEGÓCIOS</span></div>'
        '<div class="aq-ws-motto">Poderoso por dentro. Simples por fora.</div></div>'
        '<div class="aq-ws-layout">'
        '<aside class="aq-ws-side ref-sidebar ref-negocios"><div class="aq-ws-side-kicker">NEGÓCIOS</div>'
        f'<div class="aq-ws-nav">{nav}</div></aside>'
        '<main class="aq-ws-main">'
        '<section class="aq-ws-hero"><div>'
        f'<div class="aq-ws-kicker">{escape(spec["kicker"])}</div>'
        f'<h2>{escape(spec["title"])}</h2><p>{escape(spec["hero"])}</p>'
        '<div class="aq-ws-truth">'
        f'<span>MODO {escape(mode_label.upper())}</span>'
        '<span>SEM EXECUÇÃO AUTOMÁTICA</span><span>TENANT ISOLADO</span>'
        '<span>APROVAÇÃO HUMANA PARA AÇÕES CRÍTICAS</span></div></div>'
        '<div class="aq-ws-orb" aria-hidden="true"><b>N</b></div></section>'
        '<div class="aq-ws-section-head"><h3>Operação & gestão</h3>'
        '<span>B2B, receita, cliente, capacidade e governança.</span></div>'
        f'<div class="aq-ws-modules">{"".join(cards)}</div>'
        '<p class="ref-truth">Arte aprovada · dados da imagem ilustrativos; '
        'o workspace ativo usa o contrato B2B atual e não executa ações externas automaticamente.</p>'
        f'<p class="ref-truth">Sessão: {escape(name)}</p>'
        '</main></div></section></div></section>'
    )


def reference_html(area, *, mode="Avançado", selected="", name="Usuário", show_central=True, market_items=None, fx_population=None):
    if area not in SURFACES:
        raise ValueError("unknown reference workspace")
    if area == "trader":
        from atlasquant_compact_cockpit import trader_html
        return trader_html(mode=mode,selected=selected,name=name,show_central=show_central,
            nav_html=nav_html,module_panel=lambda area,selected: module_panel(area,selected,resident=fx_population),uri=asset_uri,market_items=market_items,fx_population=fx_population)
    if area == "aion" and not selected:
        from atlasquant_interface_final import aion_workspace_html
        return aion_workspace_html(mode=mode,name=name,show_central=show_central,nav_html=nav_html,uri=asset_uri)
    if area == "negocios" and not selected:
        return business_reference_home_html(mode=mode, name=name, show_central=show_central)
    filename = SURFACES[area][0]
    uri = asset_uri(filename)
    w,h = dimensions(area)
    bg = "100% 100%"
    position = "right center" if area == "aion" else "left center"
    settings = f"background-image:url({uri});--ref-aspect:{w/h};--ref-ratio:{w}/{h};--ref-size:{bg};--ref-position:{position}"
    if area != "central":
        settings += f";--ref-icon-image:url({asset_uri(area + '_nav.webp')})"
    labels = action_labels(area)
    if selected.startswith("why:") and area == "trader":
        from atlasquant_fx_universe import OFFICIAL_PAIRS
        pair = selected[4:]
        if pair in OFFICIAL_PAIRS:
            labels[selected] = pair + " · Ver por quê"
    if selected not in labels:
        selected = ""
    if selected:
        settings = settings.replace(f"background-image:url({uri})", "background-image:none")
    top = ('<button data-route="central" class="ref-return">← Central</button>' if show_central and area != "central" else "")
    mode_html = ('<button data-route="mode" class="ref-mode">Modo ' + escape(mode) + "</button>" if area != "central" else "")
    drawer = '<details class="ref-drawer"><summary>Menu · ' + escape(area.title()) + '</summary><nav>' + nav_html(area,mode) + top + "</nav></details>"
    detail = module_panel(area,selected) if selected else ""
    if selected.startswith("why:"):
        detail = f'<main class="ref-detail"><h1>{escape(labels[selected])}</h1><p>Direção aguardando ranking validado. Nenhuma compra/venda foi inferida.</p><button data-route="radar">Voltar ao Radar</button></main>'
    hits = ""
    for route, label, box in REGIONS[area]:
        hit = hotspot(area, route, label, box)
        if area == "investimentos" and box[1] > 400:
            hit = hit.replace('class="ref-hit"', 'class="ref-hit ref-neutral-region"')
            start = hit.index('<span'); end = hit.index('</button>')
            hit = hit[:start] + f'<strong>{escape(label)}</strong><b>—</b><small>PRÉVIA · aguardando dados validados</small>' + hit[end:]
        hits += hit
    if area == "trader":
        # Explicit requested corrections cover the source's cross-environment row/card labels.
        hits += hotspot(area,"master","Painel Mestre",(1031,411,162,43),visible=True)
        hits += hotspot(area,"journal","Diário",(908,665,96,48),visible=True)
        # Original top tabs, ticker tiles, search and tools have their own accesses.
        for i,route in enumerate(("home","week","day","close_day","close_week")):
            hits += hotspot(area,route,labels.get(route,"Visão geral"),(216+i*189,108,180,39))
        for i in range(10):
            hits += hotspot(area,"radar","Contexto do ativo",(163+i*110,53,106,47))
        hits += hotspot(area,"search","Buscar",(854,8,151,35))
        hits += hotspot(area,"notifications","Notificações",(1006,8,37,35))
        hits += hotspot(area,"settings","Configurações",(1045,8,34,35))
        hits += hotspot(area,"profile","Perfil / Configurações",(1082,8,156,35))
        hits += hotspot(area,"aion_specialist","AION Trader",(15,586,139,121))
    elif area in {"investimentos","aion"}:
        box=(794,239,190,69) if area=="investimentos" else (848,108,183,112)
        hits+=hotspot(area,"aion_specialist" if area=="investimentos" else "chat","Conversar com o AION",box)
    sidebar = ""
    if area != "central":
        side_width = {"trader":12,"negocios":21.8,"investimentos":16.7,"aion":18.5}[area]
        sidebar = f'<nav class="ref-sidebar ref-{escape(area)}" style="--side-width:{side_width}%">' + nav_html(area,mode) + "</nav>"
    mobile = []
    mobile_rows = (
        TRADER_MOBILE_CARDS
        if area == "trader"
        else tuple((route, label, box, "default") for route, label, box in REGIONS[area])
    )
    for route,label,box,kind in mobile_rows:
        if route in {"profile","notifications","settings","session"}:
            continue
        x,y,bw,bh = box
        scale = 100*w/bw
        posx = 100*x/max(1,w-bw)
        posy = 100*y/max(1,h-bh)
        style = f"aspect-ratio:{bw}/{bh};background-size:{scale}%;background-position:{posx}% {posy}%"
        neutral = area == "investimentos" and y > 400
        if neutral:
            style = "background-image:none"
            kind = "neutral"
        art_content = '<b>—</b><small>PRÉVIA · aguardando dados</small>' if neutral else ''
        mobile.append(
            f'<button class="ref-mobile-card ref-mobile-card-{escape(route)} '
            f'ref-mobile-card-{escape(kind)}" data-route="{escape(route)}" '
            f'data-mobile-kind="{escape(kind)}" data-mobile-crop="{x},{y},{bw},{bh}" '
            f'aria-label="{escape(label)}">'
            f'<span class="ref-mobile-art" style="{style}">{art_content}</span>'
            f'<strong>{escape(label)}</strong></button>'
        )
    # Replace screenshot identity text with the current authenticated identity.
    id_box = {"central":(591,13,75,32),"trader":(1121,8,87,34),"negocios":(682,29,64,30),"investimentos":(876,22,100,35),"aion":(876,22,100,35)}[area]
    ix,iy,iw,ih=id_box
    identity=f'<span class="ref-identity" style="left:{ix/w*100}%;top:{iy/h*100}%;width:{iw/w*100}%;height:{ih/h*100}%">{escape(name)}</span>'
    if area == "central":
        hits += identity
    hx,hy,hw,hh = {"central":(170,60,450,220),"trader":(535,450,268,180),
                   "negocios":(170,1,590,115),"investimentos":(170,0,870,305),
                   "aion":(184,0,856,305)}[area]
    hero_style = f"background-size:{100*w/hw}%;background-position:{100*hx/max(1,w-hw)}% {100*hy/max(1,h-hh)}%"
    truth = "" if area == "central" else '<p class="ref-truth">Arte aprovada · dados da imagem ilustrativos; métricas e execução não validadas</p>'
    from atlasquant_compact_cockpit import header_html
    header=header_html(area,name,mode,top,market_items=market_items) if area != "central" else ""
    shortcuts = ""
    if not detail and area in {"negocios", "investimentos"}:
        from atlasquant_ecosystem_workspace_ui import workspace_modules
        shortcuts = '<section class="final-workspace-shortcuts" aria-label="Capacidades do ambiente">' + ''.join(
            f'<button data-route="extended:{escape(item["id"])}"><strong>{escape(item["title"])}</strong><small>{escape(item["state"])} · {escape(item["summary"])}</small></button>'
            for item in workspace_modules(area)) + '</section>'
    return (f'<section class="ref-workspace ref-{escape(area)}" data-workspace="{escape(area)}" style="{settings}">'
        + header + drawer
        + (f'<div class="ref-detail-layout"><nav class="ref-detail-nav">{nav_html(area,mode)}</nav>{detail}</div>' if detail else
           f'<div class="ref-canvas" role="group" aria-label="{escape(area)} · cockpit AtlasQuant">{sidebar}{hits}</div>'
           f'<div class="ref-mobile-header ref-mobile-header-{escape(area)}" style="{hero_style}"><span class="ref-mobile-kicker">ECOSSISTEMA ATLASQUANT</span><h1>ATLASQUANT · {escape(area.upper())}</h1><p>{escape({"trader":"Mercado, contexto e risco em uma única leitura.","negocios":"Operação B2B, crescimento e automação com controle.","investimentos":"Estratégia hoje. Patrimônio amanhã.","aion":"Inteligência que integra todo o ecossistema.","central":"Poderoso por dentro. Simples por fora."}[area])}</p></div>'
           f'<div class="ref-mobile-grid">{"".join(mobile)}</div>')
        + shortcuts + truth + "</section>")


JS = r"""
export default function(component) {
 const {data, parentElement, setTriggerValue} = component;
 let root=parentElement.querySelector('.ref-component-root');
 if(!root){root=document.createElement('div');root.className='ref-component-root';parentElement.appendChild(root);}
 root.dataset.artReady='false';
 root.innerHTML=data; // Only versioned Python markup, with escaped identity/content.
 // Images inherit a normal CSS property, avoiding the custom-property size
 // limit and repeated parsing of the same data URL for each decorative card.
 const art=root.querySelector('.ref-canvas');
 if(art){
   const value=getComputedStyle(art).backgroundImage;
   const src=value.slice(4,-1).replace(/^['"]|['"]$/g,'');
   const img=new Image();
   img.onload=()=>{root.dataset.artReady='true';};
   img.onerror=()=>{root.dataset.artReady='error';};
   if(value==='none'){Promise.all([...root.querySelectorAll('img')].map(image=>image.decode())).then(()=>root.dataset.artReady='true').catch(()=>root.dataset.artReady='error');}else{img.src=src;}
 }else{root.dataset.artReady='true';}
 root.querySelectorAll('[data-ticker-step]').forEach(b=>{
   b.onclick=()=>root.querySelector('.cq-ticker')?.scrollBy({left:Number(b.dataset.tickerStep)*root.querySelector('.cq-ticker').clientWidth*.75,behavior:'smooth'});
 });
 const ticker=root.querySelector('.cq-ticker');
 if(ticker){ticker.onkeydown=e=>{if(e.key==='ArrowRight'||e.key==='ArrowLeft'){e.preventDefault();ticker.scrollBy({left:e.key==='ArrowRight'?160:-160,behavior:'smooth'});}};}
 const search=root.querySelector('.ref-search');
 if(search){search.oninput=()=>{
   const term=search.value.toLocaleLowerCase();
   root.querySelectorAll('.ref-search-results button').forEach(b=>{b.hidden=!b.textContent.toLocaleLowerCase().includes(term);});
 };}
 root.querySelectorAll('[data-route]').forEach(button=>{
   button.onclick=()=>{button.setAttribute('aria-busy','true');setTriggerValue('navigate',button.dataset.route);};
 });
 root.querySelectorAll('[data-local-tab]').forEach(button=>{
   button.onclick=()=>{
     const selected=button.dataset.localTab;
     root.querySelectorAll('[data-tab-panel]').forEach(panel=>panel.hidden=panel.dataset.tabPanel!==selected);
     root.querySelectorAll('[data-local-tab]').forEach(tab=>tab.setAttribute('aria-selected',tab===button?'true':'false'));
   };
 });
 // The selected workspace always opens at the first fold.
 if(root.querySelector('.ref-detail')) window.scrollTo({top:0,behavior:'instant'});
 return ()=>{root.querySelectorAll('[data-route]').forEach(b=>b.onclick=null);};
}
"""


def _component():
    import streamlit.components.v2 as v2
    return v2.component("atlasquant_reference_cockpit", css=CSS.read_text(encoding="utf-8"), js=JS)


@lru_cache(maxsize=1)
def _chat_component():
    """The existing UI host owns framework wiring; the chat adapter imports no UI runtime."""
    import streamlit.components.v2 as v2
    assets = Path(__file__).parent / "aion_chat" / "web"
    return v2.component("atlasquant_aion_chat_command", css=(assets / "command-chat.css").read_text(encoding="utf-8"), js=(assets / "command-chat.js").read_text(encoding="utf-8"))


def apply_event(session, access, area, event):
    """UI-only state changes. Existing area gate is always authoritative."""
    from atlasquant_central_hub_ui import assert_area_access, request_central_destination
    if not access or access.get("allowed") is not True:
        raise ValueError("authenticated access required")
    if area != "central":
        assert_area_access(access,area)
    elif str(access.get("role","")).upper() != "ADMIN":
        raise ValueError("central area access denied")
    if event.startswith("area:") and area == "central":
        request_central_destination(session,access,event[5:])
        session.pop("aq_reference_module",None)
        session["aq_reference_connected"] = False
    elif event == "central":
        request_central_destination(session,access,"central")
        session.pop("aq_reference_module",None)
        session["aq_reference_connected"] = False
    elif event == "mode":
        target_mode = (
            "Iniciante"
            if str(session.get("atlasquant_experience_mode", "")).startswith("Avan")
            else "Avançado"
        )
        # Streamlit forbids mutating a widget-owned key after that widget has
        # been instantiated in the current run. Persist a separate request that
        # the experience switch consumes before recreating the radio on rerun.
        session["_aq_reference_mode_request"] = target_mode
        try:
            # Plain mappings used by unit tests and callers without a mounted
            # Streamlit radio can update immediately.
            session["atlasquant_experience_mode"] = target_mode
        except Exception:
            pass
    elif event.startswith("connected:") and area == "trader":
        key = event.split(":",1)[1]
        key = "radar" if key == "radar_master" else key
        if key not in dict(TRADER_NAV) or key in {"home","aion_specialist"}:
            raise ValueError("unknown analysis")
        from atlasquant_premium_shell import PREMIUM_MODULES, request_premium_card, consume_premium_navigation
        from atlasquant_ui_v1 import navigation_labels
        pages = list(navigation_labels())
        mode = "Avançado" if key not in {"academy","video","profile"} else str(session.get("atlasquant_experience_mode") or "Iniciante")
        target = request_premium_card(session,key,mode=mode,available_pages=pages)
        if not target:
            raise ValueError("analysis unavailable")
        session["atlasquant_experience_mode"] = mode
        consume_premium_navigation(session,mode=mode,available_pages=pages)
        session["aq_beginner_page"] = target
        session["aq_reference_connected"] = True
    elif event == "home":
        session.pop("aq_reference_module",None)
        session["aq_reference_connected"] = False
        if area == "trader":
            # Keep the legacy selector aligned with the cockpit when returning
            # from a requested analytical page. No authentication state changes.
            session["atlasquant_advanced_area"] = "🎯 Radar"
            session["atlasquant_beginner_area_full"] = "🎯 Radar"
            session["aq_beginner_page"] = "🎯 Radar"
    elif event.startswith("why:") and area == "trader":
        from atlasquant_fx_universe import OFFICIAL_PAIRS
        if event[4:] not in OFFICIAL_PAIRS:
            raise ValueError("unknown pair")
        session["aq_reference_module"] = (area,event)
    elif event in action_labels(area) or event == "search" and area == "trader":
        session["aq_reference_module"] = (area,event)
    else:
        raise ValueError("unknown workspace action")


def render_reference_workspace(
    st,
    access,
    area,
    *,
    mode=None,
    aion_chat_binding=None,
):
    if not access or access.get("allowed") is not True:
        return False
    from atlasquant_central_hub_ui import assert_area_access
    st.markdown(
        '<span id="aq-reference-active" aria-hidden="true"></span>'
        '<style>'
        '[data-testid="stMainBlockContainer"]{max-width:1600px;padding-top:.55rem;padding-left:1rem;padding-right:1rem}'
        '[data-testid="stElementContainer"]:has(#aq-reference-active){height:0!important;min-height:0!important;margin:0!important;padding:0!important}'
        '@media(max-width:700px){'
        '.stApp:has(#aq-reference-active) [data-testid="stHeader"]{display:none!important;height:0!important;min-height:0!important}'
        '.stApp:has(#aq-reference-active) [data-testid="stSidebarCollapsedControl"]{display:none!important}'
        '.stApp:has(#aq-reference-active) [data-testid="stElementContainer"]:has([data-testid="stRadio"]){display:none!important}'
        '.stApp:has(#aq-reference-active) [data-testid="stElementContainer"]:has(.aq-hero),'
        '.stApp:has(#aq-reference-active) [data-testid="stElementContainer"]:has(#aq-account-identity),'
        '.stApp:has(#aq-reference-active) [data-testid="stElementContainer"]:has(.aq-boot-banner),'
        '.stApp:has(#aq-reference-active) [data-testid="stElementContainer"]:has(.aq-voice-dock){display:none!important;height:0!important;min-height:0!important;margin:0!important;padding:0!important}'
        '.stApp:has(#aq-reference-active) [data-testid="stElementContainer"]:has(.aq-voice-dock) + [data-testid="stHorizontalBlock"]{display:none!important}'
        '.stApp:has(#aq-reference-active) .block-container{padding-top:0!important}'
        '.stApp:has(#aq-reference-active) [data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"]{gap:0!important}'
        'html:has(#aq-reference-active) [data-testid="stAppViewContainer"],'
        'html:has(#aq-reference-active) [data-testid="stMain"],'
        'html:has(#aq-reference-active) [data-testid="stMainBlockContainer"],'
        'html:has(#aq-reference-active) .block-container{margin-top:0!important;top:0!important;padding-top:0!important}'
        '.stApp:has(#aq-reference-active) [data-testid="stMainBlockContainer"],'
        '.stApp:has(#aq-reference-active) .block-container{padding-left:.5rem!important;padding-right:.5rem!important}'
        '}'
        '</style>',
        unsafe_allow_html=True,
    )
    if area != "central":
        assert_area_access(access,area)
    elif str(access.get("role") or "").upper() != "ADMIN":
        return False
    selected = st.session_state.get("aq_reference_module")
    selected = selected[1] if isinstance(selected,(list,tuple)) and len(selected)==2 and selected[0]==area else ""
    mode = mode or st.session_state.get("atlasquant_experience_mode") or "Iniciante"
    if area == "aion" and selected in {"", "chat"}:
        from atlasquant_aion_chat_workspace_ui import render_aion_chat_workspace
        product_kwargs = {}
        if aion_chat_binding is not None:
            if not isinstance(aion_chat_binding, dict):
                raise TypeError("aion_chat_binding mapping required")
            required = ("scope", "store", "runtime_context")
            if any(aion_chat_binding.get(key) is None for key in required):
                raise ValueError(
                    "aion_chat_binding requires scope + store + runtime_context"
                )
            product_kwargs = {
                "product_scope": aion_chat_binding["scope"],
                "product_store": aion_chat_binding["store"],
                "runtime_context": aion_chat_binding["runtime_context"],
                "product_conversation_id": aion_chat_binding.get(
                    "conversation_id", ""
                ),
            }
        return render_aion_chat_workspace(
            st,
            access,
            mode=mode,
            selected=selected,
            navigation=NAV["aion"],
            component=_chat_component(),
            **product_kwargs,
        )
    session = access.get("session") or {}
    name = str(access.get("display_name") or session.get("username") or access.get("username") or "Usuário")
    result = _component()(data=reference_html(area,mode=mode,selected=selected,name=name,
        show_central=str(access.get("role") or "").upper()=="ADMIN",market_items=st.session_state.get("atlasquant_validated_market_items"),fx_population=st.session_state.get("atlasquant_reference_fx_population")),key="aq_reference_"+area,on_navigate_change=lambda:None)
    if result.navigate:
        apply_event(st.session_state,access,area,result.navigate)
        st.rerun()
    return True


def render_trader_entry(st, access):
    """Light home/detail shell before any snapshot or live-provider loader."""
    if st.session_state.get("aq_reference_connected"):
        # Existing analytical pages keep their data pipeline, with a lightweight
        # return control above that pipeline. Every event uses the same gate.
        if not access or access.get("allowed") is not True:
            return False
        from atlasquant_central_hub_ui import assert_area_access
        assert_area_access(access, "trader")
        central = ('<button data-route="central">← Central</button>'
                   if str(access.get("role") or "").upper() == "ADMIN" else "")
        markup = '<section class="ref-workspace ref-trader"><div class="ref-toolbar"><button data-route="home">← Cockpit Trader</button>' + central + '</div></section>'
        result = _component()(data=markup,key="aq_reference_connected_nav",on_navigate_change=lambda:None)
        if result.navigate:
            apply_event(st.session_state,access,"trader",result.navigate)
            st.rerun()
        return False
    return render_reference_workspace(st,access,"trader")
