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
    ("Brasil", (("IBOV", "Ibovespa"), ("WIN", "Mini índice B3"))),
    ("Europa", (("DAX40", "DAX 40"), ("CAC40", "CAC 40"),
                ("FTSE100", "FTSE 100"), ("STOXX50", "Euro Stoxx 50"))),
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
.aqr-shell{--a:#46d8ff;--fg:#f0f8ff;--mut:#90a8c4;--line:rgba(93,176,243,.22);color:var(--fg);background:radial-gradient(circle at 75% 4%,rgba(20,138,211,.22),transparent 31%),linear-gradient(155deg,#071a31,#030b1c 55%,#061323);border:1px solid rgba(75,173,234,.35);border-radius:23px;padding:22px;box-shadow:0 22px 60px rgba(0,0,0,.38);font-family:Inter,system-ui,sans-serif}
.aqr-shell *{box-sizing:border-box}.aqr-top{display:flex;align-items:center;justify-content:space-between;gap:18px;flex-wrap:wrap}.aqr-brand{display:flex;gap:12px;align-items:center}.aqr-logo{display:grid;place-items:center;width:42px;height:42px;border-radius:13px;background:linear-gradient(135deg,#2be1ed,#3465ea);box-shadow:0 0 25px rgba(36,184,240,.37);font-weight:950;color:#02162c}
.aqr-brand h1{margin:0;font-size:1.25rem;letter-spacing:.07em;color:#fff}.aqr-brand p{margin:2px 0 0;color:var(--mut);font-size:.68rem;letter-spacing:.11em;text-transform:uppercase}
.aqr-back,.aqr-nav button,.aqr-tabs button{background:#0c233d;color:#d4eeff;border:1px solid var(--line);border-radius:10px;padding:9px 13px;font:inherit;cursor:pointer}.aqr-back:hover,.aqr-nav button:hover,.aqr-tabs button:hover{border-color:var(--a);color:#fff}
.aqr-sub{display:flex;gap:12px;align-items:center;justify-content:space-between;flex-wrap:wrap;margin:18px 0 15px}.aqr-sub h2{font-size:1.5rem;margin:0}.aqr-meta{display:inline-flex;gap:8px;align-items:center;border:1px solid #365574;color:#bee0fc;background:#082139;border-radius:999px;padding:7px 11px;font-size:.73rem}
.aqr-dot{width:7px;height:7px;border-radius:50%;background:#ffc26a;display:inline-block}.aqr-nav{display:flex;gap:7px;flex-wrap:wrap;padding-bottom:17px;border-bottom:1px solid var(--line)}.aqr-nav button[aria-current=page]{color:#041525;background:linear-gradient(110deg,#36d9ff,#65abff);border-color:transparent;font-weight:800}
.aqr-grid{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:13px;margin-top:16px}.aqr-card{grid-column:span 6;min-width:0;border:1px solid var(--line);border-radius:16px;padding:15px;background:linear-gradient(160deg,rgba(19,51,80,.81),rgba(6,20,41,.90));box-shadow:inset 0 1px 0 rgba(190,229,255,.05)}
.aqr-card.aqr-wide{grid-column:1/-1}.aqr-card.aqr-third{grid-column:span 4}.aqr-card h3{font-size:.96rem;color:#e8f6ff;margin:0 0 10px}.aqr-card h3 small{font-size:.67rem;display:block;color:var(--mut);font-weight:500;margin-top:5px}.aqr-card p{color:#abc2dd;font-size:.78rem;line-height:1.55;margin:8px 0}
.aqr-list{display:grid;gap:7px}.aqr-row{display:grid;grid-template-columns:1fr auto auto;gap:12px;align-items:center;border-bottom:1px solid rgba(104,163,219,.10);padding:8px 3px;font-size:.77rem}.aqr-row:last-child{border:0}.aqr-row strong{color:#f3fbff}.aqr-muted{color:var(--mut)}.aqr-tag{display:inline-block;border:1px solid rgba(135,161,193,.30);background:rgba(125,154,191,.09);color:#adc3d9;padding:3px 8px;border-radius:999px;font-size:.66rem;font-weight:750;white-space:nowrap}
.aqr-tag.up{color:#6af5bb;border-color:rgba(67,226,155,.33);background:rgba(30,166,113,.12)}.aqr-tag.down{color:#ff9caa;border-color:rgba(239,96,119,.32);background:rgba(210,61,86,.10)}.aqr-tag.flat{color:#e7d19a;border-color:rgba(213,178,95,.27)}
.aqr-intro{background:linear-gradient(100deg,rgba(15,72,114,.82),rgba(5,29,58,.55));border:1px solid var(--line);border-radius:15px;padding:17px;margin-top:17px}
.aqr-intro b{color:#85e7ff}.aqr-intro p{margin:5px 0 0;color:#bfd5ee;font-size:.82rem}.aqr-tablewrap{overflow-x:auto}.aqr-table{width:100%;border-collapse:collapse;min-width:540px;font-size:.75rem}.aqr-table th{color:#8cadcf;font-weight:700;text-align:left;font-size:.65rem;text-transform:uppercase;letter-spacing:.08em;padding:10px 9px;border-bottom:1px solid var(--line)}.aqr-table td{padding:10px 9px;border-bottom:1px solid rgba(130,180,238,.12)}.aqr-table td:first-child{font-weight:800;color:#f0f9ff}.aqr-table tbody tr:hover{background:rgba(45,141,220,.08)}
.aqr-callout{border-left:3px solid #ffc36c;background:rgba(255,181,74,.07);padding:10px 14px;border-radius:0 12px 12px 0;color:#d8e7f8;font-size:.76rem;line-height:1.5}.aqr-tabs{display:flex;flex-wrap:wrap;gap:6px;margin:12px 0}.aqr-tabs button[aria-selected=true]{border-color:#46d8ff;color:#75e6ff;background:rgba(38,129,184,.24)}[data-tab-panel][hidden]{display:none!important}
.aqr-foot{color:#7492b2;font-size:.67rem;margin:16px 2px 0}.aqr-empty{color:#98aecb;font-size:.77rem;line-height:1.5;padding:10px 0}
.aqr-entry{margin:14px auto 7px;max-width:700px;display:block;width:calc(100% - 26px);text-align:left;padding:16px 20px;border:1px solid rgba(80,209,246,.65);border-radius:18px;color:#f0fbff;background:linear-gradient(115deg,rgba(0,88,138,.96),rgba(7,21,59,.98));box-shadow:0 0 27px rgba(24,154,226,.17);cursor:pointer}.aqr-entry strong{font-size:1rem;display:block}.aqr-entry small{display:block;margin-top:4px;color:#b7d9eb;font-size:.75rem}.aqr-entry:hover{border-color:#a6f5ff;box-shadow:0 0 32px rgba(60,192,243,.3)}
.aqr-entry:focus-visible,.aqr-shell button:focus-visible{outline:2px solid #b9f5ff;outline-offset:2px}
@media(max-width:780px){.aqr-shell{padding:13px;border-radius:16px}.aqr-card,.aqr-card.aqr-third{grid-column:1/-1}.aqr-sub h2{font-size:1.2rem}.aqr-row{gap:6px}.aqr-brand h1{font-size:1rem}.aqr-meta{font-size:.67rem}}
@media(prefers-reduced-motion:reduce){.aqr-shell *, .aqr-entry{scroll-behavior:auto;animation:none!important;transition:none!important}}
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
        parts.append(f'<article class="aqr-card {"aqr-third" if wide else ""}"><h3>{escape(region)}</h3><div class="aqr-list">{items}</div></article>')
    if wide:
        return "".join(parts)
    return '<article class="aqr-card"><h3>Índices globais<small>EUA · Brasil · Europa</small></h3><div class="aqr-list">' + "".join(
        f'<div class="aqr-row"><strong>{escape(region)}</strong><span class="aqr-muted">{len(instruments)} índices</span>{_tag("")}</div>'
        for region, instruments in INDEX_GROUPS) + "</div></article>"


def _home(data: Mapping[str, Any]) -> str:
    return ('<div class="aqr-intro"><b>Leitura do dia, em um só lugar.</b>'
            '<p>Moedas mais fortes, pares com maior valorização, vieses de Forex e índices. '
            'Sem horários de sessão como filtro do ranking; fora do pregão, vale o último fechamento disponível e identificado.</p></div>'
            '<div class="aqr-grid">' + _currency_panel(data) + _top_panel(data) +
            '<article class="aqr-card aqr-wide"><h3>Radar de índices</h3><div class="aqr-grid">' +
            _indices_panel(data, wide=True) + '</div></article>' +
            '<article class="aqr-card aqr-wide"><h3>Painel de contexto</h3>'
            '<p>Macro · Micro · Geopolítica · Notícias. Indicadores com valor divulgado, consenso, anterior e impacto possível quando o calendário estiver conectado.</p>'
            '<button class="aqr-back" data-route="master">Abrir Painel Mestre</button></article></div>')


def _radar(data: Mapping[str, Any]) -> str:
    fx = "".join(
        f'<tr><td>{escape(pair)}</td><td>{_pct(data["pairs"].get(pair))}</td>'
        f'<td>{_tag(data["pairs"].get(pair, {}).get("bias", ""))}</td></tr>'
        for pair in OFFICIAL_PAIRS)
    return ('<div class="aqr-grid">' + _top_panel(data) + _currency_panel(data) +
            '<article class="aqr-card aqr-wide"><h3>28 pares de Forex · visão diária</h3>'
            '<div class="aqr-tablewrap"><table class="aqr-table"><thead><tr><th>Par</th><th>Variação do dia</th><th>Viés D1</th></tr></thead><tbody>' +
            fx + '</tbody></table></div></article>' + _indices_panel(data, wide=True) + '</div>')


def _scanner() -> str:
    return ('<div class="aqr-intro"><b>Scanner técnico · módulo preservado</b>'
            '<p>Após conectar as leituras, exibiremos D1 (viés), H4 (confirmação) e M15 (gatilho), '
            'com tendência, OB, FVG e alerta de reversão. Nenhum sinal é inferido nesta prévia.</p></div>'
            '<div class="aqr-grid"><article class="aqr-card aqr-wide"><h3>Estado do scanner</h3>'
            '<div class="aqr-callout">Aguardando leitura técnica validada. '
            'O radar diário não é uma recomendação de entrada nem executa ordens.</div></article></div>')


def _master() -> str:
    tabs = (("macro", "Macro"), ("micro", "Micro"), ("geo", "Geopolítica"), ("news", "Notícias"))
    buttons = "".join(f'<button data-local-tab="{key}" aria-selected="{str(i==0).lower()}">{label}</button>' for i, (key, label) in enumerate(tabs))
    guides = "".join(f'<div class="aqr-row"><strong>{escape(title)}</strong><span class="aqr-muted">—</span>{_tag("")}</div><p>{escape(impact)}</p>' for title, impact in EVENT_GUIDES)
    panels = (
        '<section data-tab-panel="macro"><article class="aqr-card aqr-wide"><h3>Calendário econômico e impacto provável</h3>'
        '<div class="aqr-callout">Eventos em tempo real ainda sem fornecedor conectado. '
        'Valor divulgado, consenso, anterior, horário e fonte só aparecerão com dados verificados.</div>'
        '<div class="aqr-list">' + guides + '</div></article></section>'
        '<section data-tab-panel="micro" hidden><article class="aqr-card aqr-wide"><h3>Microeconomia</h3>'
        '<p>Setores, margens, consumo, lucros empresariais e crédito. Leituras e fontes aguardando integração.</p></article></section>'
        '<section data-tab-panel="geo" hidden><article class="aqr-card aqr-wide"><h3>Geopolítica</h3>'
        '<p>Conflitos, energia, cadeias de suprimento, sanções e aversão ao risco. Eventos aguardando fonte validada.</p></article></section>'
        '<section data-tab-panel="news" hidden><article class="aqr-card aqr-wide"><h3>Notícias de mercado</h3>'
        '<p>Manchetes, horário, origem e ativos afetados aparecerão aqui depois da conexão de notícias verificadas.</p></article></section>'
    )
    return '<div class="aqr-intro"><b>Painel Mestre · o que move o mercado</b><p>Contexto, surpresa econômica, reação do preço e risco. Macro abrange o mundo todo.</p></div><nav class="aqr-tabs" aria-label="Contexto de mercado">' + buttons + '</nav><div class="aqr-grid">' + panels + '</div>'


def trader_radar_html(*, selected: str = "", name: str = "Usuário",
                      show_central: bool = True, daily_data: Any = None) -> str:
    data = _daily(daily_data)
    page = selected if selected in {key for key, _ in PAGES} else "home"
    title = dict(PAGES)[page]
    nav = "".join(
        f'<button data-route="{key}" aria-current="{"page" if key == page else "false"}">{escape(label)}</button>'
        for key, label in PAGES)
    back = '<button class="aqr-back" data-route="central">← Central</button>' if show_central else ""
    status = ('Última atualização: ' + data["stamp"] + ' · ' + data["source"]
              if data["stamp"] else "Dados diários ainda não conectados")
    content = {"home": lambda: _home(data), "radar": lambda: _radar(data),
               "scanner": _scanner, "master": _master}[page]()
    return (_CSS + '<section class="ref-workspace aqr-shell" data-workspace="trader_radar">'
            '<div class="aqr-top"><div class="aqr-brand"><span class="aqr-logo">AQ</span>'
            '<div><h1>ATLASQUANT · TRADER RADAR</h1>'
            '<p>Forex · Índices · inteligência de mercado</p></div></div>' + back + '</div>'
            '<div class="aqr-sub"><h2>' + escape(title) + '</h2><span class="aqr-meta">'
            '<i class="aqr-dot"></i>' + escape(status) + '</span></div>'
            '<nav class="aqr-nav" aria-label="Navegação Trader Radar">' + nav + '</nav>' + content +
            '<p class="aqr-foot">Radar informativo · sem ordens reais · não inventa cotações, vieses ou eventos. '
            'Viés diário e variação percentual são medidas diferentes.</p></section>')


def central_entry_html() -> str:
    return (_CSS + '<button type="button" class="aqr-entry" data-route="area:trader_radar" '
            'aria-label="Abrir Trader Radar · Forex e Índices">'
            '<strong>✦ Trader Radar · Forex & Índices <span class="aqr-tag up">NOVO</span></strong>'
            '<small>28 pares · Top 10 diário · 8 moedas · índices · Macro e notícias</small></button>')


__all__ = ["SCHEMA", "PAGES", "INDEX_GROUPS", "_daily",
           "trader_radar_html", "central_entry_html"]
