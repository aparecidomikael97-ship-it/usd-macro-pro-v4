"""Trader Radar compacto: apresentação pura, sem ordens ou acesso a provedores.

Dados do dia só aparecem quando entregues por um contrato diário validado.
O módulo não transforma ranking técnico em valorização de preço.
"""
from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from math import isfinite
from typing import Any, Mapping

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS

SCHEMA = "ATLASQUANT_TRADER_RADAR_COMPACT_V1"
PAGES = (("home", "Início"), ("radar", "Radar"), ("scanner", "Scanner Técnico"),
         ("master", "Painel Mestre"))
INDEX_GROUPS = (
    ("Estados Unidos", (("SPX500", "S&P 500"), ("NAS100", "Nasdaq 100"),
                        ("US30", "Dow Jones"), ("RUS2000", "Russell 2000"))),
    ("Brasil", (("WIN", "WIN · mini-índice"), ("WDO", "WDO · minidólar"))),
    ("Europa", (("DAX40", "DAX 40"), ("CAC40", "CAC 40"),
                ("FTSE100", "FTSE 100"), ("STOXX50", "Euro Stoxx 50"))),
    ("Ásia", (("NIKKEI225", "Nikkei 225"), ("TOPIX", "TOPIX"),
               ("HANGSENG", "Hang Seng"), ("CSI300", "CSI 300"),
               ("KOSPI200", "KOSPI 200"))),
)
EVENT_GUIDES = (
    ("Inflação · CPI / PCE / IPCA", "Inflação acima do consenso pode elevar a expectativa de juros e favorecer a moeda local; a reação depende do que já estava precificado."),
    ("Emprego · NFP / desemprego", "Emprego mais forte pode alterar a expectativa de juros e o dólar. Bolsas podem reagir em qualquer direção."),
    ("Atividade · PMI / ISM / PIB", "Atividade surpreendendo para cima pode apoiar a moeda e setores cíclicos, mas aumentar preocupações com inflação."),
    ("Bancos centrais · Fed / Copom / BCE", "Decisões, comunicado e tom das autoridades podem alterar juros, câmbio e índices. O consenso importa tanto quanto a decisão."),
    ("Vendas e consumo", "Consumo acima do esperado pode apoiar o crescimento, mas também mudar a trajetória projetada de juros."),
)

_CSS = r"""
<style>
.aqr-shell{--aqr-cyan:#5be5ec;--aqr-ink:#e7f0fb;--aqr-muted:#91a6be;--aqr-outline:#2b465c;--aqr-panel:#0d1c2c;color:var(--aqr-ink);background:#080e1b!important;border:0!important;border-radius:0!important;padding:0!important;box-shadow:none!important;font-family:Inter,Segoe UI,Arial,sans-serif;width:100%;min-height:850px;overflow:visible!important}
.aqr-shell *{box-sizing:border-box}.aqr-shell button{font:inherit;cursor:pointer}.aqr-app{display:grid;grid-template-columns:220px minmax(0,1fr);min-height:860px}
.aqr-aside{border-right:1px solid #263448;background:#0b1626;min-width:0}.aqr-aside-inner{position:sticky;top:0;min-height:850px;height:100dvh;padding:25px 13px 24px;display:flex;flex-direction:column;gap:25px}
.aqr-brand{display:flex;gap:10px;align-items:center;padding:0 9px}.aqr-logo{display:grid;place-items:center;background:linear-gradient(135deg,#154052,#0e2b43);border:1px solid #51dce8;color:#71ecf1;font-size:22px;font-weight:950;width:36px;height:36px;border-radius:11px}
.aqr-brand strong{font-size:15px;letter-spacing:.04em;line-height:1.2;display:block;color:#eff7ff}.aqr-brand small{font-size:9px;letter-spacing:.2em;font-weight:850;color:var(--aqr-cyan);display:block;margin-top:3px}
.aqr-side-label{color:#7791b0;letter-spacing:.23em;font-weight:850;font-size:9px;margin:9px 10px 10px}.aqr-nav{display:grid;gap:6px}
.aqr-nav button{display:flex;gap:13px;text-align:left;align-items:center;color:#adbed1;background:transparent;border:1px solid transparent;border-radius:11px;padding:14px 15px;font-size:12px;font-weight:700;min-height:46px;width:100%}
.aqr-nav button:hover{background:#122b3d;border-color:#2f8397}.aqr-nav button[aria-current=page]{color:#e7faff;background:#123647;border-color:#42bbd0;box-shadow:inset 3px 0 0 #53dfdf;font-weight:800}.aqr-nav-icon{width:15px;color:var(--aqr-cyan);font-size:13px;text-align:center}
.aqr-aside-note{margin-top:auto;background:linear-gradient(145deg,#0f3045,#102339);border:1px solid #36536b;border-radius:13px;padding:14px 12px}.aqr-aside-note strong{display:block;color:#6af4ed;font-size:10px;letter-spacing:.12em}.aqr-aside-note p{font-size:11px;color:#a6b8cc;line-height:1.55;margin:7px 0 12px}.aqr-aside-note small{display:block;padding-top:11px;border-top:1px solid #2c455a;font-size:10px;color:#96acc4}
.aqr-main{min-width:0;padding:28px clamp(16px,2.8vw,46px) 26px;background:radial-gradient(ellipse at 83% 0,rgba(20,78,110,.28),transparent 32%),linear-gradient(#0c1827,#090f1c 55%)}
.aqr-topline{display:flex;align-items:center;justify-content:space-between;gap:15px;flex-wrap:wrap;margin:0 0 29px}.aqr-crumb{color:#9caec6;font-size:11px;letter-spacing:.03em}.aqr-crumb strong{color:#e6f5ff}.aqr-controls{display:flex;gap:9px;align-items:center;flex-wrap:wrap}
.aqr-chip{border:1px solid #3b5369;color:#b8cce0;background:rgba(16,34,52,.8);border-radius:999px;padding:8px 11px;font-size:10px;font-weight:850;white-space:nowrap}.aqr-chip-warn{background:#31291f;border-color:#805a37;color:#f3c99f}.aqr-avatar{display:grid;place-items:center;width:30px;height:30px;border-radius:50%;color:#83edf2;background:#163244;border:1px solid #426478;font-size:11px;font-weight:850}
.aqr-hero{position:relative;overflow:hidden;border-radius:17px;background:linear-gradient(110deg,#10273a 0%,#122e42 66%,#173a50 100%);border:1px solid #2e5d75;min-height:212px;padding:30px 32px 24px;margin-bottom:20px}.aqr-hero:after{content:"";position:absolute;width:280px;height:280px;border:28px solid rgba(58,162,191,.10);border-radius:50%;right:25px;top:-75px;box-shadow:0 0 0 42px rgba(62,158,193,.04)}
.aqr-hero:before{content:"";position:absolute;width:84px;height:84px;border:1.5px solid #3a9bba;border-radius:20px;right:9%;top:61px;transform:rotate(45deg);z-index:1}.aqr-hero>*{position:relative;z-index:2}.aqr-kicker{font-size:10px;letter-spacing:.13em;font-weight:950;color:#82f0f4}.aqr-hero h1{font-size:clamp(24px,3vw,38px);line-height:1.12;letter-spacing:-.045em;margin:12px 0 6px;font-weight:850;color:#eaf4ff}.aqr-hero p{font-size:13px;color:#b4cbdd;max-width:620px;line-height:1.65;margin:0 0 16px}.aqr-badges{display:flex;gap:7px;flex-wrap:wrap}.aqr-badges span{font-size:10px;border:1px solid #42687c;background:#112b3b;border-radius:5px;padding:7px 10px;color:#c7e2ed}
.aqr-warning{border:1px solid #745a36;background:linear-gradient(95deg,#242323,#1c2128);color:#dec5a4;padding:14px 16px;border-radius:11px;margin:19px 0 29px;font-size:11px;line-height:1.6}.aqr-warning strong{color:#f8d8a4}.aqr-warning-icon{margin-right:8px}
.aqr-section{margin:27px 0 30px}.aqr-heading{display:flex;justify-content:space-between;align-items:end;flex-wrap:wrap;gap:12px;margin-bottom:14px}.aqr-heading h2{font-size:18px;letter-spacing:-.025em;font-weight:800;margin:0;color:#e5effb}.aqr-heading p{font-size:11px;color:#95aabe;margin:6px 0 0}.aqr-status{display:inline-block;border-radius:6px;font-size:10px;font-weight:800;padding:5px 8px;border:1px solid #6b543e;background:#35271b;color:#e2b482}.aqr-status-cool{color:#b8a6de;border-color:#66527a;background:#251d38}
.aqr-grid{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:13px}.aqr-card{min-width:0;grid-column:span 6;border:1px solid #2a4359;background:linear-gradient(160deg,#102236,#0d1b2b);border-radius:14px;padding:17px}.aqr-card.aqr-fourth{grid-column:span 3}.aqr-card.aqr-third{grid-column:span 4}.aqr-card.aqr-wide{grid-column:1/-1}.aqr-card h3{font-size:14px;margin:0 0 9px;color:#eaf6ff}.aqr-card p{margin:5px 0;font-size:11px;line-height:1.55;color:#9fb4c8}.aqr-card small{font-size:10px;color:#90a9c1}.aqr-stat-label{font-size:11px;color:#a8c0d5}.aqr-stat-label span{color:var(--aqr-cyan);margin-right:7px;font-weight:900}.aqr-value{font-size:24px;color:#aec7d9;font-weight:900;margin:22px 0 8px}.aqr-foot{font-size:10px;color:#718aa5;padding:19px 0;border-top:1px solid #26344c;margin-top:22px}
.aqr-flow h3{font-size:12px;margin:11px 0 4px}.aqr-flow p{min-height:32px}.aqr-flow a,.aqr-link{display:inline-block;border:1px solid #315f70;border-radius:5px;background:#112e3d;color:#bcf4f6;padding:5px 7px;font-size:10px;font-weight:800;margin-top:6px;text-decoration:none}.aqr-flow button{border:1px solid #315f70;border-radius:5px;background:#112e3d;color:#bcf4f6;padding:5px 7px;font-size:10px;font-weight:800;margin-top:6px}.aqr-flow .aqr-icon{color:var(--aqr-cyan);font-size:16px}
.aqr-tablewrap{overflow-x:auto;border:1px solid #2b4054;border-radius:13px;background:#0d1b2c}.aqr-table{width:100%;border-collapse:collapse;min-width:520px;font-size:11px}.aqr-table thead{background:#12273a}.aqr-table th{text-align:left;color:#8ba8c1;font-size:10px;letter-spacing:.06em;padding:12px 13px}.aqr-table td{padding:12px 13px;border-top:1px solid #24374a;color:#b7cada}.aqr-table td:first-child{color:#e9f5ff;font-weight:800}.aqr-table .aqr-tag{margin:0}.aqr-empty-area{text-align:center;border:1px solid #284158;border-radius:11px;padding:27px 14px;color:#8ea8c2;background:linear-gradient(160deg,#0f2032,#0c1928);font-size:11px}.aqr-empty-area strong{display:block;font-size:13px;color:#b9d5e6;margin-bottom:5px}.aqr-muted{color:#8aa2bb}.aqr-tag{display:inline-block;border:1px solid #796040;background:#33271d;color:#eac086;padding:4px 7px;border-radius:5px;font-size:10px;font-weight:750}.aqr-tag.up{color:#68e9b6;background:#153d38;border-color:#2d796b}.aqr-tag.down{color:#ffa5ab;background:#3b2633;border-color:#74475c}.aqr-tag.flat{color:#e7c994}.aqr-table .aqr-tag{font-size:10px}
.aqr-currency{grid-column:span 3;min-width:0;background:linear-gradient(140deg,#112438,#0b1b2d);border:1px solid #28465b;border-radius:10px;padding:16px 12px}.aqr-currency strong{font-size:14px;color:#dfedf7}.aqr-currency small{display:block;font-size:10px;color:#94adbf;margin-top:5px}.aqr-currency-value{margin:16px 0 8px;font-weight:800;color:#b0c2d5;font-size:17px}
.aqr-tabs{display:flex;gap:6px;flex-wrap:wrap}.aqr-tabs button{border:1px solid #344c65;background:#0c1b30;color:#b2c6db;border-radius:6px;padding:8px 11px;font-size:10px;font-weight:800}.aqr-tabs button[aria-selected=true]{background:#133d4a;color:#b6faff;border-color:#50ced7}.aqr-region{margin-top:16px}.aqr-region h3{margin:0 0 10px;color:#e2f3fc;font-size:13px}.aqr-indices{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:13px}.aqr-market-card{border:1px solid #2a4359;border-radius:12px;background:#102133;padding:15px;min-height:145px}.aqr-market-card h4{font-size:12px;margin:0 0 17px;color:#dceeff}.aqr-market-card p{font-size:10px;color:#92acc2;margin:9px 0}.aqr-market-card .aqr-value{font-size:18px;margin:0 0 8px}.aqr-market-card .aqr-tag{margin-top:8px}
.aqr-strategy{border:1px solid #3e6e75;background:linear-gradient(120deg,#112a37,#0b1a2c);border-radius:14px;padding:19px;margin:17px 0}.aqr-strategy h3{font-size:16px;color:#eaf7ff;margin:0 0 6px}.aqr-strategy p{font-size:11px;color:#a9bcd0;line-height:1.7;margin:8px 0}.aqr-strategy-result{margin-top:15px;border-top:1px solid #284659;padding-top:12px}.aqr-strategy-caution{border-left:3px solid #dfae69;background:#322a1e;border-radius:5px;padding:9px 12px;margin-top:13px;color:#e8ca9e;font-size:11px;line-height:1.6}
.aqr-guide{background:#102c3b;border-left:3px solid #4cdbdd;border-radius:8px;padding:13px;margin:12px 0;color:#c6e1ec;font-size:11px;line-height:1.6}.aqr-guide strong{display:block;margin-bottom:4px;color:#e4f7f9}.aqr-detail{border:1px solid #2d445b;background:#0f1d2c;border-radius:12px;padding:16px}.aqr-detail h3{margin:0 0 8px;font-size:13px}.aqr-detail p{font-size:11px;color:#b3c6d6;line-height:1.65}
.aqr-event{padding:12px 4px;border-bottom:1px solid #23394b}.aqr-event:last-child{border:0}.aqr-event strong{font-size:12px;color:#d9edf8;display:block}.aqr-event p{font-size:11px;line-height:1.6;color:#a5b9ca}
.aqr-entry{margin:14px auto 7px;max-width:700px;display:block;width:calc(100% - 26px);text-align:left;padding:16px 20px;border:1px solid rgba(80,209,246,.65);border-radius:18px;color:#f0fbff;background:linear-gradient(115deg,rgba(0,88,138,.96),rgba(7,21,59,.98));box-shadow:0 0 27px rgba(24,154,226,.17);cursor:pointer}.aqr-entry strong{font-size:1rem;display:block}.aqr-entry small{display:block;margin-top:4px;color:#b7d9eb;font-size:.75rem}.aqr-entry:hover{border-color:#a6f5ff}
.aqr-shell button:focus-visible,.aqr-entry:focus-visible{outline:3px solid #8cefff;outline-offset:2px}.aqr-shell [hidden]{display:none!important}
@media(min-width:1300px){.aqr-main{padding-left:46px;padding-right:46px}}
@media(max-width:1050px){.aqr-app{grid-template-columns:195px minmax(0,1fr)}.aqr-main{padding:22px 20px}.aqr-card.aqr-fourth{grid-column:span 6}.aqr-indices{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:700px){.aqr-app{display:block}.aqr-aside-inner{position:static;min-height:0;height:auto;padding:12px;gap:9px}.aqr-aside-note{display:none}.aqr-side-label{margin:2px 4px}.aqr-nav{grid-template-columns:repeat(2,minmax(0,1fr));gap:5px}.aqr-nav button{min-height:40px;padding:8px;font-size:11px}.aqr-main{padding:14px}.aqr-topline{margin-bottom:14px}.aqr-hero{padding:22px 18px;min-height:190px}.aqr-hero h1{font-size:26px}.aqr-hero:before{right:-14px;opacity:.28}.aqr-hero:after{opacity:.4}.aqr-warning{margin-bottom:17px}.aqr-card,.aqr-card.aqr-fourth,.aqr-card.aqr-third{grid-column:1/-1}.aqr-currency{grid-column:span 6}.aqr-indices{grid-template-columns:1fr}.aqr-controls{gap:5px}.aqr-chip{font-size:9px;padding:6px}.aqr-crumb{font-size:10px}}
@media(prefers-reduced-motion:reduce){.aqr-shell *{scroll-behavior:auto!important;animation:none!important;transition:none!important}}
</style>
"""
def _num(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) and abs(number) <= 100 else None


def _daily(data: Any) -> dict[str, Any]:
    """Only a named, timestamped daily contract may publish percentages."""
    blank = {"source": "", "stamp": "", "pairs": {}, "currencies": {}, "indices": {}}
    if not isinstance(data, Mapping) or data.get("state") != "VALIDATED_DAILY":
        return blank
    source = str(data.get("source") or "").strip()
    raw_stamp = str(data.get("as_of") or "")
    if not source or not raw_stamp:
        return blank
    try:
        stamp = datetime.fromisoformat(raw_stamp.replace("Z", "+00:00"))
        if stamp.tzinfo is None or (stamp - datetime.now(timezone.utc)).total_seconds() > 300:
            return blank
    except (TypeError, ValueError):
        return blank
    result = {"source": source, "stamp": stamp.strftime("%d/%m/%Y %H:%M UTC"),
              "pairs": {}, "currencies": {}, "indices": {}}
    for market in ("pairs", "currencies", "indices"):
        items = data.get(market)
        if not isinstance(items, Mapping):
            continue
        allowed = (set(OFFICIAL_PAIRS) if market == "pairs" else
                   set(CURRENCIES) if market == "currencies" else
                   {key for _, group in INDEX_GROUPS for key, _ in group})
        for symbol, item in items.items():
            if symbol not in allowed or not isinstance(item, Mapping):
                continue
            change = _num(item.get("change_pct"))
            bias = str(item.get("bias") or "").upper()
            if change is None or (market != "currencies" and bias not in {"ALTA", "BAIXA", "NEUTRO"}):
                continue
            result[market][symbol] = {"change_pct": change, "bias": bias}
    return result


def _tag(bias: str) -> str:
    kind = {"ALTA": "up", "BAIXA": "down", "NEUTRO": "flat"}.get(bias, "")
    return f'<span class="aqr-tag {kind}">{escape(bias or "AGUARDANDO")}</span>'


def _pct(row: Mapping[str, Any] | None) -> str:
    if row is None:
        return '<span class="aqr-muted">—</span>'
    value = row["change_pct"]
    kind = "up" if value > 0 else ("down" if value < 0 else "flat")
    number = f"{value:+.2f}%".replace(".", ",")
    return f'<span class="aqr-tag {kind}">{number}</span>'


def _currency_panel(data: Mapping[str, Any]) -> str:
    rows = data["currencies"]
    ranked = sorted(rows.items(), key=lambda item: item[1]["change_pct"], reverse=True) if len(rows) == 8 else []
    body = "".join(
        f'<div class="aqr-row"><strong>{i}. {escape(code)}</strong>{_pct(value)}<span class="aqr-muted">relativo</span></div>'
        for i, (code, value) in enumerate(ranked, 1))
    if not body:
        body = "".join(f'<div class="aqr-row"><strong>{escape(code)}</strong><span class="aqr-muted">—</span>{_tag("")}</div>' for code in CURRENCIES)
    return '<article class="aqr-card"><h3>Força das 8 moedas<small>Comparação relativa do dia · não é preço nominal</small></h3><div class="aqr-list">' + body + "</div></article>"


def _top_panel(data: Mapping[str, Any]) -> str:
    rows = data["pairs"]
    # A partial universe must not be advertised as the daily Top 10.
    ranked = sorted(rows.items(), key=lambda item: item[1]["change_pct"], reverse=True)[:10] if len(rows) == 28 else []
    body = "".join(f'<div class="aqr-row"><strong>#{i} {escape(pair)}</strong>{_pct(value)}{_tag(value["bias"])}</div>' for i, (pair, value) in enumerate(ranked, 1))
    if not body:
        body = '<p class="aqr-empty">Top 10 aguardando as 28 variações diárias verificadas. O ranking técnico atual não é usado como valorização.</p>'
    return '<article class="aqr-card"><h3>Top 10 · valorização Forex<small>Variação diária em ordem decrescente · universo completo</small></h3><div class="aqr-list">' + body + "</div></article>"


def _indices_panel(data: Mapping[str, Any], *, wide: bool = False) -> str:
    parts = []
    for region, instruments in INDEX_GROUPS:
        items = "".join(
            f'<div class="aqr-row"><strong>{escape(name)}</strong>{_pct(data["indices"].get(symbol))}'
            f'{_tag(data["indices"].get(symbol, {}).get("bias", ""))}</div>'
            for symbol, name in instruments)
        parts.append(f'<article class="aqr-card"><h3>{escape(region)}</h3><div class="aqr-list">{items}</div></article>')
    if wide:
        return "".join(parts)
    return '<article class="aqr-card"><h3>Índices e futuros<small>EUA · Brasil · Europa · Ásia</small></h3><div class="aqr-list">' + "".join(
        f'<div class="aqr-row"><strong>{escape(region)}</strong><span class="aqr-muted">{len(instruments)} ativos</span>{_tag("")}</div>'
        for region, instruments in INDEX_GROUPS) + "</div></article>"



def _heading(title: str, sub: str, badge: str = "") -> str:
    status = f'<span class="aqr-status">{escape(badge)}</span>' if badge else ""
    return (f'<div class="aqr-heading"><div><h2>{escape(title)}</h2>'
            f'<p>{escape(sub)}</p></div>{status}</div>')


def _placeholder_card(label: str, description: str, icon: str = "◈") -> str:
    return (f'<article class="aqr-card aqr-fourth"><div class="aqr-stat-label">'
            f'<span>{escape(icon)}</span>{escape(label)}</div>'
            f'<div class="aqr-value">—</div><small>{escape(description)}</small></article>')


def _hero(page: str) -> str:
    heading = {
        "home": ("Seu mercado. Uma visão clara.",
                 "Um centro de análise objetivo: força das moedas, direção dos pares, leitura técnica e contexto econômico, cada coisa no seu lugar."),
        "radar": ("Onde o mercado está se movendo.",
                  "Moedas, pares de Forex e índices globais organizados para uma leitura diária clara."),
        "scanner": ("Do contexto à oportunidade.",
                    "Estrutura, tendência e zonas técnicas em vários tempos gráficos, com critérios explícitos."),
        "master": ("Entenda o porquê do movimento.",
                   "Macroeconomia, micro, geopolítica, notícias e calendário econômico explicados sem confundir informação com previsão."),
    }[page]
    return ('<section class="aqr-hero"><div class="aqr-kicker">INTELIGÊNCIA DE MERCADO · PRÉVIA</div>'
            f'<h1>{escape(heading[0])}</h1><p>{escape(heading[1])}</p>'
            '<div class="aqr-badges"><span>28 PARES FOREX</span><span>8 MOEDAS</span>'
            '<span>ÍNDICES + WIN / WDO</span><span>D1 · H4 · M15</span></div></section>')


def _disclaimer() -> str:
    return ('<aside class="aqr-warning" role="note"><span class="aqr-warning-icon">⚠</span>'
            '<strong>Esta é uma prévia da interface.</strong> Nenhuma cotação, ranking, viés ou calendário '
            'está conectado ao mercado, salvo quando os dados estiverem explicitamente validados e identificados. '
            'Onde aparece “—” ou “Aguardando dados”, não existe leitura real. '
            'Não usar para decisões de investimento.</aside>')


def _home(data: Mapping[str, Any]) -> str:
    summary = (_placeholder_card("Moeda mais forte", "Força relativa entre 8 moedas")
               + _placeholder_card("Melhor par do dia", "Variação % diária entre 28 pares", "↗")
               + _placeholder_card("Viés de índices / futuros", "Inclui WIN e WDO · D1 + H4", "▥")
               + _placeholder_card("Próximo evento", "Calendário econômico do dia", "◷"))
    flow = (
        ("◎", "01 / Radar",
         "Qual moeda está mais forte? Quais pares lideram a valorização? Qual o viés?",
         "Abrir Radar →", "radar"),
        ("⌁", "02 / Scanner Técnico",
         "Onde existem tendência, zonas válidas, estrutura e possíveis reversões?",
         "Abrir Scanner →", "scanner"),
        ("▦", "03 / Painel Mestre",
         "O que explica o movimento? Quais indicadores e eventos podem impactá-lo?",
         "Abrir Painel →", "master"),
    )
    cards = "".join(
        f'<article class="aqr-card aqr-third aqr-flow"><div class="aqr-icon">{escape(icon)}</div>'
        f'<h3>{escape(title)}</h3><p>{escape(desc)}</p>'
        f'<button data-route="{route}">{escape(button)}</button></article>'
        for icon, title, desc, button, route in flow)
    return (
        '<section class="aqr-section">' +
        _heading("Panorama do mercado", "Os quatro blocos principais do dia, sem excesso de informação.",
                 "Aguardando integração") +
        '<div class="aqr-grid">' + summary + '</div></section>'
        '<section class="aqr-section">' +
        _heading("Fluxo de análise", "Uma pergunta por área, para você navegar com rapidez.") +
        '<div class="aqr-grid">' + cards + '</div></section>'
        '<section class="aqr-section">' +
        _heading("Avisos econômicos", "Depois da integração, aparecerão aqui apenas os eventos realmente relevantes.") +
        '<div class="aqr-empty-area"><strong>Calendário econômico ainda não conectado</strong>'
        'Somente eventos verificados, com horário e fonte, poderão aparecer aqui.</div></section>')


def _currencies_approved(data: Mapping[str, Any]) -> str:
    rows = data["currencies"]
    ordered = (sorted(rows.items(), key=lambda x: x[1]["change_pct"], reverse=True)
               if len(rows) == len(CURRENCIES) else [(c, None) for c in CURRENCIES])
    return '<div class="aqr-grid">' + "".join(
        '<article class="aqr-currency"><strong>' + escape(code) +
        '</strong><small>Força relativa</small><div class="aqr-currency-value">' +
        (_pct(value) if value else '—') + '</div><span class="aqr-tag">Aguardando validação</span></article>'
        for code, value in ordered) + '</div>'


def _top_approved(data: Mapping[str, Any]) -> str:
    rows = data["pairs"]
    complete = len(rows) == len(OFFICIAL_PAIRS)
    if not complete:
        return ('<div class="aqr-empty-area"><strong>Top 10 aguardando</strong>'
                'Variações diárias dos 28 pares ainda não verificadas. '
                'Um ranking técnico não equivale à valorização diária.</div>')
    ranked = sorted(rows.items(), key=lambda item: item[1]["change_pct"], reverse=True)[:10]
    return '<div class="aqr-grid">' + "".join(
        '<article class="aqr-card aqr-fourth"><h3>#' + str(i) + ' ' + escape(pair) +
        '</h3><div class="aqr-value">' + _pct(value) + '</div>' + _tag(value["bias"]) +
        '</article>' for i, (pair, value) in enumerate(ranked, 1)) + '</div>'


def _forex_table(data: Mapping[str, Any]) -> str:
    rows = "".join(
        f'<tr><td>{escape(pair)}</td><td>{_pct(data["pairs"].get(pair))}</td>'
        f'<td>{_tag(data["pairs"].get(pair, {}).get("bias", ""))}</td>'
        '<td><span class="aqr-muted">Aguardando D1 + H4</span></td></tr>'
        for pair in OFFICIAL_PAIRS)
    return (
        '<div class="aqr-tablewrap"><table class="aqr-table">'
        '<thead><tr><th>Par</th><th>Variação diária</th><th>Viés diário</th>'
        '<th>Confirmação</th></tr></thead><tbody>' + rows + '</tbody></table></div>')


def _opening_score(raw: Any) -> dict[str, Any] | None:
    """Viés experimental de pré-abertura: exige contrato, fonte e carimbo temporal.

    Não representa edge testado; jamais emite ordem ou sinal de entrada.
    """
    from zoneinfo import ZoneInfo
    if not isinstance(raw, Mapping) or raw.get("state") != "VALIDATED_OPENING":
        return None
    source = str(raw.get("source") or "").strip()
    timestamp = str(raw.get("as_of") or "").strip()
    if not source or not timestamp:
        return None
    try:
        stamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        if stamp.tzinfo is None:
            return None
        delta = (now - stamp.astimezone(timezone.utc)).total_seconds()
        local = stamp.astimezone(ZoneInfo("America/Sao_Paulo"))
        # A coleta para abertura do WIN foi combinada entre 8h50 e 9h BRT.
        if not (-300 <= delta <= 6 * 3600) or not (local.hour == 8 and local.minute >= 50 or
                                                   local.hour == 9 and local.minute == 0):
            return None
    except (ValueError, TypeError, OverflowError):
        return None
    values = [_num(raw.get(key)) for key in ("vix_pct", "iron_pct", "oil_pct")]
    if any(value is None for value in values):
        return None
    vix, iron, oil = values
    score = round(iron + oil - vix, 4)
    magnitude = abs(score)
    level = ("Indefinido" if magnitude < 1.5 else "Fraco" if magnitude < 2.5
             else "Moderado" if magnitude <= 4.5 else "Forte")
    side = "Comprador" if score > 0 else "Vendedor" if score < 0 else "Neutro"
    return {"vix": vix, "iron": iron, "oil": oil, "score": score,
            "level": level, "side": side, "source": source,
            "stamp": local.strftime("%d/%m/%Y %H:%M BRT")}


def _opening_strategy(raw: Any) -> str:
    """Abaixo dos contratos WIN/WDO: três fatores exatos, WDO independente."""
    opening = raw.get("opening") if isinstance(raw, Mapping) else None
    read = _opening_score(opening)
    factors = (("VIX", "Índice de Volatilidade S&P 500", "vix"),
               ("Minério", "SGX IODEX Iron Ore Futures", "iron"),
               ("Petróleo", "Futuros de petróleo leve bruto", "oil"))
    blocks = "".join(
        '<article class="aqr-market-card"><h4>' + escape(title) + '</h4>'
        '<p>' + escape(label) + '</p><div class="aqr-value">' +
        (_pct({"change_pct": read[key]}) if read else '—') +
        '</div><span class="aqr-tag">' + ("Validado" if read else "Aguardando cotação") +
        '</span></article>'
        for title, label, key in factors)
    if read:
        result = (
            f'<strong>WIN: cenário exploratório {read["side"].lower()} ({read["level"].lower()})</strong>'
            f'<p>Score: {read["score"]:+.2f} pontos percentuais · '
            f'Fonte: {escape(read["source"])} · {escape(read["stamp"])}. '
            'Somente uma inclinação preliminar, sem entrada automática.</p>'
        )
    else:
        result = ('<strong>WIN: aguardando dados válidos para a abertura</strong>'
                  '<p>Score exploratório = variação % do minério + variação % do petróleo '
                  '− variação % do VIX. Coleta prevista entre 8h50 e 9h (Brasília). '
                  'Sem fonte, horário e três variações verificadas, não há viés calculado.</p>')
    return (
        '<section class="aqr-strategy" aria-label="Estratégia de Abertura">'
        '<div class="aqr-heading"><div><h3>Estratégia de Abertura · Brasil</h3>'
        '<p>WIN · três fatores de contexto pré-abertura; WDO · leitura própria.</p></div>'
        '<span class="aqr-status">Pesquisa / sem ordens</span></div>'
        '<div class="aqr-indices">' + blocks + '</div>'
        '<div class="aqr-strategy-result">' + result + '</div>'
        '<div class="aqr-strategy-caution"><strong>Confirmação obrigatória:</strong> '
        'O score isolado não é gatilho. Conferir VWAP, preço, estrutura, liquidez, '
        'zonas e risco antes de considerar um cenário. Intensidades propostas ainda sem backtest.</div>'
        '<p><strong>WDO:</strong> modelo independente em preparação, com contexto de DXY, juros '
        'e confirmação do gráfico. Não copiar o viés calculado do WIN.</p></section>')


def _region_html(region: str, instruments: Any, data: Mapping[str, Any],
                 raw_daily: Any) -> str:
    items = "".join(
        '<article class="aqr-market-card"><h4>' + escape(name) +
        '</h4><div class="aqr-value">' + _pct(data["indices"].get(symbol)) +
        '</div><p>Confirmação H4: —</p><p>Direção D1: ' +
        escape(data["indices"].get(symbol, {}).get("bias", "Aguardando dados")) +
        '</p>' + _tag(data["indices"].get(symbol, {}).get("bias", "")) +
        '</article>' for symbol, name in instruments)
    strategy = _opening_strategy(raw_daily) if region == "Brasil" else ""
    return ('<section class="aqr-region"><h3>' + escape(region) + '</h3>'
            '<div class="aqr-indices">' + items + '</div>' + strategy + '</section>')


def _radar(data: Mapping[str, Any], raw_daily: Any = None) -> str:
    filters = (("all", "Todos"), ("us", "EUA"), ("br", "Brasil"),
               ("eu", "Europa"), ("asia", "Ásia"))
    keys = ("us", "br", "eu", "asia")
    buttons = "".join(
        '<button data-local-tab="' + key + '" aria-selected="' +
        ("true" if key == "all" else "false") + '">' + label + '</button>'
        for key, label in filters)
    panels = ('<section data-tab-panel="all">' +
              "".join(_region_html(region, assets, data, raw_daily)
                      for region, assets in INDEX_GROUPS) + '</section>')
    panels += "".join(
        '<section data-tab-panel="' + key + '" hidden>' +
        _region_html(region, assets, data, raw_daily) + '</section>'
        for key, (region, assets) in zip(keys, INDEX_GROUPS))
    return (
        '<section class="aqr-section">' +
        _heading("Força relativa das 8 moedas",
                 "Comparação relativa para orientar a leitura; não é cotação nominal.") +
        _currencies_approved(data) + '</section>'
        '<section class="aqr-section">' +
        _heading("Top 10 do dia",
                 "Pares ordenados por variação diária quando o universo completo for validado.") +
        _top_approved(data) + '</section>'
        '<section class="aqr-section">' +
        _heading("Os 28 pares Forex",
                 "Variação diária, viés e confirmação técnica por par.") +
        _forex_table(data) + '</section>'
        '<section class="aqr-section">' +
        _heading("Índices e Futuros",
                 "EUA, Brasil, Europa e Ásia · WIN e WDO sem confundir com Ibovespa.") +
        '<nav class="aqr-tabs" aria-label="Região de índices e futuros">' + buttons +
        '</nav>' + panels + '</section>')


def _scanner() -> str:
    items = (
        ("D1 · Direção", "Viés principal do ativo e contexto de tendência."),
        ("H4 · Confirmação", "Estrutura intermediária, liquidez e alinhamento."),
        ("M15 · Gatilho", "Região válida e confirmação antes de qualquer decisão."),
        ("Reversões", "Alertas de mudança de caráter, invalidação e contra-tendência."),
    )
    cards = "".join(
        '<article class="aqr-card aqr-fourth"><h3>' + escape(title) +
        '</h3><div class="aqr-value">—</div><p>' + escape(description) +
        '</p><span class="aqr-tag">Aguardando leitura</span></article>'
        for title, description in items)
    return (
        '<section class="aqr-section">' +
        _heading("Scanner Técnico", "Observe a estrutura do preço sem confundir hipótese com sinal.",
                 "Dados não conectados") +
        '<div class="aqr-grid">' + cards + '</div></section>'
        '<section class="aqr-section">' +
        _heading("Matriz de leitura", "D1 · H4 · M15 · M30 · H1 · M5") +
        '<div class="aqr-grid">'
        '<article class="aqr-card"><h3>Observe a estrutura</h3><p>Em análise: tendência, '
        'BOS/CHoCH, OB, FVG, liquidez e regiões de interesse.</p>'
        '<div class="aqr-guide"><strong>Filtro</strong>OB e FVG só devem aparecer no seu '
        'próprio timeframe, com validação explícita e sem misturar regiões.</div></article>'
        '<article class="aqr-card"><h3>O que fica no radar</h3>'
        '<div class="aqr-guide"><strong>Direção</strong>Tendência dominante identificada.</div>'
        '<div class="aqr-guide"><strong>Força relativa</strong>Moedas fortes versus fracas, '
        'sem forçar entradas.</div><div class="aqr-guide"><strong>Reversão</strong> '
        'Zona contrária com confirmação de estrutura.</div>'
        '<div class="aqr-guide"><strong>Invalidação</strong>Critério objetivo de saída da zona.</div>'
        '</article></div></section>'
        '<section class="aqr-section">' +
        _heading("Possíveis oportunidades", "Exibir somente setups comprovadamente validados.") +
        '<div class="aqr-empty-area"><strong>Nenhuma oportunidade validada disponível</strong>'
        'O scanner não inventa entrada nem aciona ordens.</div></section>')


def _master() -> str:
    highlights = (
        _placeholder_card("Cenário macro", "Sem avaliação atual", "")
        + _placeholder_card("Bancos centrais", "Fed, BCE, BoE, BoJ e outros", "")
        + _placeholder_card("Risco geopolítico", "Sem monitoramento ativo", "")
        + _placeholder_card("Notícias relevantes", "Sem feed conectado", "")
    )
    dimensions = (
        ("MACRO", "Economia global",
         "Inflação, juros, atividade, emprego, decisões de bancos centrais, DXY e apetite por risco.",
         "Exemplo condicional: uma inflação acima das expectativas pode alterar apostas de juros e aumentar a volatilidade do dólar; a reação não é automática."),
        ("MICRO", "Setores e empresas",
         "Balanços, atividade setorial, resultados corporativos e fatores específicos que afetam determinados índices.",
         "Um índice pode subir mesmo quando algumas empresas caem. A composição importa."),
        ("GEOPOLÍTICA", "Riscos globais",
         "Conflitos, sanções, energia, comércio e cadeias de suprimentos com efeitos distintos por região.",
         "Notícia de risco não implica uma única direção; confirme a reação do mercado."),
        ("NOTÍCIAS", "Fatos e desdobramentos",
         "Eventos com fonte, horário, contexto e efeito potencial, separados de opinião e projeção.",
         "A notícia e a reação do preço são duas informações diferentes."),
    )
    panels = "".join(
        '<article class="aqr-card"><span class="aqr-tag up">' + escape(kicker) +
        '</span><h3 style="margin-top:15px">' + escape(title) +
        '</h3><p>' + escape(desc) + '</p><div class="aqr-guide">' +
        escape(note) + '</div></article>' for kicker, title, desc, note in dimensions)
    guides = "".join(
        '<div class="aqr-event"><strong>' + escape(title) +
        '</strong><p>' + escape(impact) + '</p></div>' for title, impact in EVENT_GUIDES)
    return (
        '<section class="aqr-section">' +
        _heading("Painel Mestre", "O contexto por trás do movimento do mercado, separado da leitura de preços.",
                 "Contexto e risco") +
        '<div class="aqr-grid">' + highlights + '</div></section>'
        '<section class="aqr-section">' +
        _heading("Quatro dimensões", "As informações poderão ser combinadas, mas suas fontes ficarão identificadas.") +
        '<div class="aqr-grid">' + panels + '</div></section>'
        '<section class="aqr-section">' +
        _heading("Calendário econômico",
                 "Valor divulgado, consenso, anterior, horário e fonte com impacto condicional.",
                 "Aguardando integração") +
        '<div class="aqr-empty-area"><strong>Calendário econômico ainda não conectado</strong>'
        'Eventos reais dependerão de fonte identificada e horário validado.</div></section>'
        '<section class="aqr-section">' +
        _heading("Guia de impacto dos indicadores", "Exemplos educativos, não previsões.") +
        '<div class="aqr-grid"><article class="aqr-card aqr-wide">' +
        guides + '</article></div></section>')


def trader_radar_html(*, selected: str = "", name: str = "Usuário",
                      show_central: bool = True, daily_data: Any = None) -> str:
    data = _daily(daily_data)
    page = selected if selected in {key for key, _ in PAGES} else "home"
    title = dict(PAGES)[page]
    icons = {"home": "⌂", "radar": "◉", "scanner": "⌁", "master": "▦"}
    nav = "".join(
        '<button data-route="' + key + '" aria-current="' +
        ("page" if key == page else "false") +
        '"><span class="aqr-nav-icon" aria-hidden="true">' + icons[key] +
        '</span>' + escape(label) + '</button>' for key, label in PAGES)
    content = {"home": lambda: _home(data),
               "radar": lambda: _radar(data, daily_data),
               "scanner": _scanner, "master": _master}[page]()
    back = ('<button class="aqr-chip" data-route="central">← Central AtlasQuant</button>'
            if show_central else "")
    status = ('DADOS VALIDADOS · ' + escape(data["stamp"])
              if data["stamp"] else "● DADOS NÃO CONECTADOS")
    return (
        _CSS +
        '<section class="ref-workspace aqr-shell" data-workspace="trader_radar" '
        'data-visual-reference="approved-20261102-v1">'
        '<div class="aqr-app"><aside class="aqr-aside"><div class="aqr-aside-inner">'
        '<div class="aqr-brand"><span class="aqr-logo">A</span><span><strong>ATLASQUANT'
        '</strong><small>TRADER RADAR</small></span></div>'
        '<div><div class="aqr-side-label">PAINEL DE CONTROLE</div>'
        '<nav class="aqr-nav" aria-label="Navegação AtlasQuant Trader">' + nav +
        '</nav></div><div class="aqr-aside-note"><strong>◦ PRÉVIA PRIVADA</strong>'
        '<p>Interface para aprovação visual.<br>Não conectada a preços, notícias '
        'ou operações.</p><small>Versão conceitual • v0.1</small></div></div></aside>'
        '<main class="aqr-main"><header class="aqr-topline">'
        '<div class="aqr-crumb">ATLASQUANT / TRADER RADAR / <strong>' +
        escape(title.upper()) + '</strong></div>'
        '<div class="aqr-controls"><span class="aqr-chip aqr-chip-warn">' + status +
        '</span><span class="aqr-chip">VISUALIZAÇÃO</span>' + back +
        '<span class="aqr-avatar" aria-label="Sessão do usuário">' +
        escape((name.strip()[:1] or "U").upper()) + '</span></div></header>' +
        _hero(page) + _disclaimer() + content +
        '<footer class="aqr-foot">ATLASQUANT / TRADER RADAR · Poderoso por dentro. '
        'Simples por fora. · Sem ordens reais, sem dados fictícios.</footer></main></div></section>'
    )


def central_entry_html() -> str:
    return (_CSS + '<button type="button" class="aqr-entry" data-route="area:trader_radar" '
            'aria-label="Abrir AtlasQuant Trader · Forex e Índices">'
            '<strong>✦ AtlasQuant Trader · Forex & Índices <span class="aqr-tag up">NOVO</span></strong>'
            '<small>28 pares · Top 10 diário · 8 moedas · WIN/WDO · índices globais · Macro</small></button>')


__all__ = ["SCHEMA", "PAGES", "INDEX_GROUPS", "_daily",
           "trader_radar_html", "central_entry_html"]