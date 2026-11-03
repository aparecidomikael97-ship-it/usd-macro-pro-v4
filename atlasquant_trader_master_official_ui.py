"""Approved-shell official macro snapshot; observation period != release time."""
from __future__ import annotations

from datetime import date
from html import escape
from math import isfinite
from typing import Any, Mapping

from atlasquant_trader_master_official_series import SPECS

STYLE = """
<style>
.aqr-official-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));
 gap:12px;margin:14px 0}
.aqr-official-item{border:1px solid #2b4c64;background:#0b1d30;
 border-radius:12px;padding:14px 15px;min-width:0}
.aqr-official-item h3{font-weight:700;font-size:12px;color:#d8eafa;margin:0}
.aqr-official-item .aqr-official-number{font-size:21px;color:#e4f8fa;font-weight:800;
 margin:14px 0 7px}
.aqr-official-item small{font-size:10px;color:#a2bbca;display:block;
 line-height:1.6}
.aqr-official-tag{display:inline-block;border:1px solid #3b6680;
 padding:4px 7px;border-radius:6px;font-size:9px;color:#80dce5;margin-top:10px}
.aqr-official-tag.await{color:#d8b789;border-color:#766145}
@media(max-width:1000px){.aqr-official-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:640px){.aqr-official-grid{grid-template-columns:1fr}}
</style>
"""


def _fmt(raw: Any) -> str:
    if raw is None or isinstance(raw, bool):
        return "—"
    try:
        n = float(raw)
    except (TypeError, ValueError, OverflowError):
        return "—"
    if not isfinite(n) or abs(n) > 100000:
        return "—"
    return f"{n:,.2f}".replace(",", " ").replace(".", ",")


def official_macro_html(raw: Any) -> str:
    data = raw if isinstance(raw, Mapping) else {}
    state = str(data.get("state") or "DESATIVADO")
    lookup = {}
    values = data.get("rows")
    if isinstance(values, list):
        lookup = {row.get("id"): row for row in values
                  if isinstance(row, Mapping) and row.get("id") in SPECS}
    cards = []
    for key, (name, source, series, frequency, units, _, transform) in SPECS.items():
        row = lookup.get(key) or {}
        valid = (
            state in ("VALIDADO", "PARCIAL")
            and row.get("state") == "VALIDADO"
            and row.get("source") == source
            and row.get("series") == series
            and row.get("frequency") == frequency
            and row.get("unit") == units
        )
        try:
            stamp = date.fromisoformat(str(row.get("observation_date") or ""))
            as_of = stamp.strftime("%d/%m/%Y")
        except ValueError:
            valid = False
            as_of = "—"
        display = _fmt(row.get("value")) if valid else "—"
        if display == "—":
            valid = False
        cards.append(
            '<article class="aqr-official-item">'
            '<h3>' + escape(name) + '</h3>'
            '<div class="aqr-official-number">' + display +
            ((' <span style="font-size:11px">' + escape(units) + '</span>')
             if valid else '') + '</div>'
            '<small>Fonte: ' + escape(source) + ' · Série ' +
            escape(series) + '</small>'
            '<small>Frequência: ' + escape(frequency) +
            ' · Período: ' + escape(as_of) + '</small>'
            '<small>Transformação: ' + escape(transform or "original") +
            '</small><span class="aqr-official-tag' +
            ("" if valid else " await") + '">' +
            ("SÉRIE CONSULTADA" if valid else "AGUARDANDO DADOS") +
            '</span></article>'
        )
    status = (
        "Observações de fontes oficiais; o período de referência não é o horário da divulgação."
        if state in ("VALIDADO", "PARCIAL") else
        "Coleta ainda desativada ou aguardando fontes. Nenhuma observação foi simulada."
    )
    return (
        STYLE + '<section class="aqr-section" aria-label="Indicadores oficiais">'
        '<div class="aqr-heading"><div><h2>Indicadores oficiais · Brasil e EUA</h2>'
        '<p>BCB/SGS e FRED · atualização de consulta separada da frequência da série.</p>'
        '</div><span class="aqr-status">' +
        escape(state[:40]) + '</span></div>'
        '<div class="aqr-guide"><strong>Como interpretar</strong>' +
        escape(status) +
        ' Valores observados NÃO são consenso, surpresa de calendário nem '
        'uma recomendação para negociar.</div>'
        '<div class="aqr-official-grid">' + "".join(cards) + '</div></section>'
    )


__all__ = ["official_macro_html"]
