"""Presentation of existing currency-news headlines, not independently proven facts."""
from __future__ import annotations

from html import escape
from typing import Any, Mapping

from atlasquant_trader_master_legacy_news import build_legacy_news_read_model

STYLE = """
<style>
.aqr-news-list{display:grid;gap:10px;margin-top:12px}
.aqr-news-item{background:#102536;border:1px solid #315166;border-radius:10px;
 padding:12px 15px;color:#c2d7e8}
.aqr-news-item summary{cursor:pointer;display:flex;justify-content:space-between;
 gap:12px;align-items:center;line-height:1.5;list-style:none}
.aqr-news-item summary:focus-visible{outline:2px solid #68e6ed;outline-offset:4px}
.aqr-news-item summary strong{font-size:12px;color:#edf8ff}
.aqr-news-item small{display:block;color:#98b7c8;font-size:10px;margin-top:6px}
.aqr-news-item p{color:#b0cede;font-size:11px;line-height:1.6}
.aqr-news-item a{color:#88e9f2;font-size:11px;text-decoration:underline}
.aqr-news-tag{font-size:9px;border:1px solid #6a5d43;color:#e3cb9d;
 background:#2b2a22;border-radius:6px;padding:5px 7px;white-space:nowrap}
@media(max-width:700px){.aqr-news-item summary{display:block}
.aqr-news-tag{display:inline-block;margin-top:7px}}
</style>
"""


def master_news_html(data: Any) -> str:
    """Accept only the normalized adapter snapshot; no fetch is done here."""
    status = data if isinstance(data, Mapping) else {}
    base = (
        STYLE + '<section class="aqr-section" aria-label="Notícias e geopolítica">'
        '<div class="aqr-heading"><div><h2>Notícias e geopolítica</h2>'
        '<p>Observação das oito moedas · manchete não significa fato comprovado.</p>'
        '</div></div>'
    )
    if status.get("state") != "OBSERVACIONAL":
        reason = escape(str(status.get("reason") or
                            "Nenhum snapshot reutilizável de notícias nesta sessão."))
        return (
            base + '<div class="aqr-empty-area"><strong>Aguardando manchetes verificáveis</strong>'
            '<p>' + reason + '</p>'
            'O Painel Mestre não aciona uma nova coleta de notícias, nem cria '
            'notícias ou vieses para preencher a interface.</div></section>'
        )
    rows = status.get("articles")
    if not isinstance(rows, list) or not rows:
        return base + '<div class="aqr-empty-area">Sem manchetes recentes.</div></section>'
    card_list = []
    for item in rows[:12]:
        if not isinstance(item, Mapping):
            continue
        title = escape(str(item.get("title") or ""))
        if not title:
            continue
        source = escape(str(item.get("publisher") or "Fonte ausente"))
        clock = escape(str(item.get("time_brt") or "—"))
        currencies = escape(", ".join(item.get("currencies") or [])[:75])
        theme = escape(str(item.get("type") or "MANCHETE"))
        url = escape(str(item.get("url") or ""), quote=True)
        follow = (
            '<p><a href="' + url +
            '" target="_blank" rel="noopener noreferrer nofollow">Consultar publicação original</a></p>'
        ) if url.startswith("https://") else ""
        card_list.append(
            '<details class="aqr-news-item">'
            '<summary><span><strong>' + title + '</strong>'
            '<small>' + clock + ' BRT · ' + source + ' · ' + currencies +
            '</small></span><span class="aqr-news-tag">' + theme + '</span></summary>'
            '<p>Fonte editorial: ' + source + '. O título foi publicado, '
            'mas seu conteúdo não foi verificado independentemente pelo AtlasQuant.'
            ' O antigo score heurístico de notícias NÃO aprova operações.</p>' +
            follow + '</details>'
        )
    incomplete = max(0, int(status.get("total") or 0) - len(card_list))
    omitted = (
        '<p class="aqr-cal-caption">Mais ' + str(incomplete) +
        ' manchetes não exibidas nesta visualização compacta.</p>'
    ) if incomplete else ""
    coverage = ", ".join(status.get("covered_currencies") or [])
    stamp = escape(str(status.get("snapshot_at") or "—"))
    return (
        base + '<div class="aqr-guide"><strong>Camada observacional · NÃO É SINAL</strong>'
        + str(int(status.get("total") or 0)) + ' manchetes distintas recuperadas'
        ' do módulo existente; ' +
        str(int(status.get("geo_count") or 0)) +
        ' com palavras-chave geopolíticas, sem validação do fato. Moedas com '
        'cobertura no snapshot: ' + escape(coverage) +
        '. Última coleta da camada existente: ' + stamp +
        ' UTC. Nenhuma consulta adicional foi efetuada nesta aba.</div>'
        '<div class="aqr-news-list">' + "".join(card_list) + '</div>'
        + omitted + '</section>'
    )


__all__ = ["master_news_html"]
