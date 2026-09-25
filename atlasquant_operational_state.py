"""Shared AtlasQuant operational presentation state.

Pure presentation contract used by Radar / Master Panel / Decision surfaces.
It never changes a score, gate, market-data input, authorization or execution.

Conservative rules:
- bias is descriptive, never an entry authorization;
- unknown freshness never becomes current;
- missing authorization is NOT AUTHORIZED;
- score/quality are descriptive, never probability of profit.
"""
from __future__ import annotations

from html import escape
from typing import Any, Mapping
import math

SCHEMA="ATLASQUANT_OPERATIONAL_PRESENTATION_V1"


def _finite(value:Any, default:float=0.0)->float:
    try:
        out=float(value)
        return out if math.isfinite(out) else float(default)
    except Exception:
        return float(default)


def normalize_bias(value:Any)->str:
    raw=str(value or "").strip().upper()
    if "COMPRA" in raw or "BUY" in raw or "ALTISTA" in raw:
        return "COMPRA"
    if "VENDA" in raw or "SELL" in raw or "BAIXISTA" in raw:
        return "VENDA"
    return "NEUTRO"


def normalize_freshness(
    *,
    temporal_code:Any=None,
    temporal_label:Any=None,
    reference_display:Any=None,
)->dict[str,str|bool]:
    code=str(temporal_code or "").strip().upper()
    label=str(temporal_label or "").strip()
    ref=str(reference_display or "").strip()

    if code=="CURRENT" or label.upper()=="ATUAL":
        return {
            "code":"CURRENT",
            "label":"ATUAL",
            "reference":ref or "horário não informado",
            "requires_revalidation":False,
        }
    if code=="EXPIRED" or "EXPIR" in label.upper():
        return {
            "code":"EXPIRED",
            "label":"EXPIRADA — REVALIDAR",
            "reference":ref or "horário não comprovado",
            "requires_revalidation":True,
        }
    if code in {"UNVERIFIED","NO_DATA"} or "NÃO COMPROVADO" in label.upper() or "NAO COMPROVADO" in label.upper():
        return {
            "code":code or "UNVERIFIED",
            "label":"HORÁRIO NÃO COMPROVADO — REVALIDAR",
            "reference":ref or "horário não comprovado",
            "requires_revalidation":True,
        }
    return {
        "code":"UNKNOWN",
        "label":"FRESCOR NÃO CONFIRMADO",
        "reference":ref or "horário não comprovado",
        "requires_revalidation":True,
    }


def normalize_operational_state(value:Any, *, authorized:bool=False)->dict[str,str|bool]:
    raw=str(value or "").strip()
    upper=raw.upper()

    if authorized:
        state="EXECUTÁVEL"
        tone="good"
        action="AUTORIZADA PELO ESTADO ATUAL"
    elif "EXPIR" in upper or "REVALID" in upper or "DESATUALIZ" in upper:
        state="REVALIDAR"
        tone="warn"
        action="NÃO AUTORIZADA"
    elif any(x in upper for x in ("BLOQUE","NÃO OPERAR","NAO OPERAR","CONFLITO","GATILHO CONTRA")):
        state="BLOQUEADO"
        tone="bad"
        action="NÃO AUTORIZADA"
    elif any(x in upper for x in ("QUASE","AGUARDAR","OBSERV","ESTICADO","SEM VIÉS","SEM VIES","DADOS PARCIAIS","MAPA")):
        state="OBSERVAÇÃO"
        tone="warn"
        action="NÃO AUTORIZADA"
    elif "EXECUTÁVEL" in upper or "EXECUTAVEL" in upper:
        # A green/descriptive state alone is insufficient. Authorization must
        # be passed explicitly by the calling surface.
        state="CONTEXTO ALINHADO"
        tone="info"
        action="NÃO AUTORIZADA"
    else:
        state="SEM CONFIRMAÇÃO"
        tone="neutral"
        action="NÃO AUTORIZADA"
    return {
        "state":state,
        "tone":tone,
        "authorization":action,
        "authorized":bool(authorized),
        "raw_state":raw or "—",
    }


def operational_presentation(
    *,
    pair:Any="—",
    bias:Any="NEUTRO",
    state:Any="",
    quality:Any=None,
    data_score:Any=None,
    temporal_code:Any=None,
    temporal_label:Any=None,
    reference_display:Any=None,
    authorized:bool=False,
    evidence_source:Any="não confirmada",
    next_action:Any="Aguardar confirmação válida.",
)->dict[str,Any]:
    op=normalize_operational_state(state,authorized=authorized)
    freshness=normalize_freshness(
        temporal_code=temporal_code,
        temporal_label=temporal_label,
        reference_display=reference_display,
    )
    q=None if quality is None else max(0.0,min(100.0,_finite(quality,0)))
    data=None if data_score is None else max(0.0,min(100.0,_finite(data_score,0)))

    # Authorization must also have current freshness. This is presentation-only;
    # callers should already enforce the actual engine gate independently.
    final_authorized=bool(op["authorized"]) and freshness["code"]=="CURRENT"
    authorization=(
        "AUTORIZADA PELO ESTADO ATUAL"
        if final_authorized
        else "NÃO AUTORIZADA"
    )
    tone=str(op["tone"])
    state_label=str(op["state"])
    if bool(op["authorized"]) and not final_authorized:
        tone="warn"
        state_label="REVALIDAR"

    return {
        "schema":SCHEMA,
        "pair":str(pair or "—"),
        "bias":normalize_bias(bias),
        "state":state_label,
        "raw_state":op["raw_state"],
        "tone":tone,
        "quality":q,
        "data_score":data,
        "freshness":freshness["label"],
        "freshness_code":freshness["code"],
        "reference":freshness["reference"],
        "requires_revalidation":bool(freshness["requires_revalidation"]),
        "authorization":authorization,
        "authorized":final_authorized,
        "evidence_source":str(evidence_source or "não confirmada"),
        "next_action":str(next_action or "Aguardar confirmação válida."),
        "real_orders_enabled":False,
        "automatic_execution":False,
    }


def operational_strip_html(model:Mapping[str,Any]|None)->str:
    m=dict(model or {})
    tone=str(m.get("tone") or "neutral")
    if tone not in {"good","warn","bad","info","neutral"}:
        tone="neutral"
    quality_text="N/D" if m.get("quality") is None else f"{_finite(m.get('quality'),0):.0f}/100"
    data_text="N/D" if m.get("data_score") is None else f"{_finite(m.get('data_score'),0):.0f}/100"
    return (
        f'<div class="aq-op-spine {tone}">'
        '<div class="aq-op-spine-head">'
        f'<div><small>ESTADO OPERACIONAL · {escape(str(m.get("pair") or "—"))}</small>'
        f'<strong>{escape(str(m.get("bias") or "NEUTRO"))} · {escape(str(m.get("state") or "SEM CONFIRMAÇÃO"))}</strong></div>'
        f'<span>{escape(str(m.get("authorization") or "NÃO AUTORIZADA"))}</span>'
        '</div>'
        '<div class="aq-op-spine-grid">'
        f'<div><small>Frescor</small><strong>{escape(str(m.get("freshness") or "N/D"))}</strong><em>{escape(str(m.get("reference") or ""))}</em></div>'
        f'<div><small>Qualidade</small><strong>{quality_text}</strong><em>score descritivo</em></div>'
        f'<div><small>Dados</small><strong>{data_text}</strong><em>prontidão da evidência</em></div>'
        f'<div><small>Fonte</small><strong>{escape(str(m.get("evidence_source") or "não confirmada"))}</strong><em>camada apresentada</em></div>'
        '</div>'
        f'<div class="aq-op-spine-next"><b>Próximo passo:</b> {escape(str(m.get("next_action") or "Aguardar confirmação válida."))}</div>'
        '</div>'
    )


OPERATIONAL_SPINE_CSS=r"""
<style>
.aq-op-spine{border:1px solid rgba(137,170,210,.22);border-left:4px solid #94a3b8;border-radius:14px;padding:12px 13px;margin:8px 0 13px;background:linear-gradient(145deg,rgba(14,31,52,.92),rgba(8,23,40,.93))}
.aq-op-spine.good{border-left-color:#42d392}.aq-op-spine.warn{border-left-color:#f2c14e}.aq-op-spine.bad{border-left-color:#ff6b7a}.aq-op-spine.info{border-left-color:#4fa3ff}
.aq-op-spine-head{display:flex;justify-content:space-between;align-items:flex-start;gap:10px}
.aq-op-spine-head small{display:block;color:#c9d9ea;font-size:.62rem;font-weight:900;letter-spacing:.08em}
.aq-op-spine-head strong{display:block;color:#fff;font-size:.91rem;margin-top:3px;line-height:1.3}
.aq-op-spine-head>span{border:1px solid rgba(163,190,222,.24);border-radius:999px;padding:4px 8px;color:#f5f8fc;background:rgba(11,29,49,.78);font-size:.62rem;font-weight:900;white-space:nowrap}
.aq-op-spine-grid{display:grid;grid-template-columns:1.2fr .75fr .75fr 1fr;gap:7px;margin-top:10px}
.aq-op-spine-grid>div{border:1px solid rgba(137,170,210,.15);border-radius:10px;padding:7px 8px;background:rgba(9,24,42,.62);min-width:0}
.aq-op-spine-grid small{display:block;color:#d9e5f2;font-size:.59rem;font-weight:900;text-transform:uppercase;letter-spacing:.06em}
.aq-op-spine-grid strong{display:block;color:#fff;font-size:.72rem;margin-top:2px;overflow-wrap:anywhere}
.aq-op-spine-grid em{display:block;color:#cddbeb;font-size:.63rem;font-style:normal;line-height:1.3;margin-top:2px;overflow-wrap:anywhere}
.aq-op-spine-next{border-top:1px solid rgba(137,170,210,.16);margin-top:9px;padding-top:8px;color:#e7f0fa;font-size:.72rem;line-height:1.4}
@media(max-width:760px){.aq-op-spine{padding:10px 10px}.aq-op-spine-grid{grid-template-columns:1fr 1fr}.aq-op-spine-head{gap:7px}.aq-op-spine-head strong{font-size:.82rem}}
@media(max-width:430px){.aq-op-spine-head{display:block}.aq-op-spine-head>span{display:inline-block;margin-top:6px}.aq-op-spine-grid{grid-template-columns:1fr}}
</style>
"""


__all__=[
    "SCHEMA","normalize_bias","normalize_freshness","normalize_operational_state",
    "operational_presentation","operational_strip_html","OPERATIONAL_SPINE_CSS",
]
