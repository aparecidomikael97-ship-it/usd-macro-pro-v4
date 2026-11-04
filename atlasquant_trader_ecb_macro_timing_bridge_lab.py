"""Documentary timing bridge: ECB ex-post vs *unattested* macro claims.

Designed for a future connection with the separate PR #1803 macro dossier.
No import dependency on that PR, no network, no claims that a release moved FX.
ECB fixes have calendar dates, not verified intraday execution timestamps.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from math import isfinite
from typing import Any, Mapping

from atlasquant_ecb_g8_reference_lab import ECB_PUBLICATION_ZONE
from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair
from atlasquant_trader_ecb_horizon_context_lab import build_ecb_horizon_context_lab

SCHEMA = "ATLASQUANT_TRADER_ECB_MACRO_TIMING_BRIDGE_LAB_V1"
MACRO_DOSSIER_SCHEMA = "ATLASQUANT_TRADER_MACRO_CAUSAL_DOSSIER_LAB_V1"
HORIZONS = ("D1", "W1", "MN1")
MAX_CLAIMS_PER_FRAME = 64
SURPRISE_CLASSES = frozenset((
    "ABOVE_CONSENSUS", "BELOW_CONSENSUS", "IN_LINE_WITH_CONSENSUS",
))


def _refuse(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "rows": [], "pair_count": 0, "cause_verified": False,
        "macro_original_sources_authenticated": False,
        "ecb_reference_origin_authenticated": False,
        "intraday_reference_fix_time_verified": False,
        "calendar_realtime_verified": False,
        "spot_price_independently_verified": False,
        "operational_bias": "AGUARDAR", "trade_authorized": False,
        "can_feed_live_radar": False, "publishable": False,
        "scheduler_enabled": False, "worker_enabled": False,
        "external_http_requests": 0, "new_cost_brl": 0,
    }


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not 20 <= len(value) <= 45:
        return None
    try:
        x = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, OverflowError):
        return None
    if x.tzinfo is None or x.utcoffset() is None:
        return None
    return x.astimezone(timezone.utc)


def _claim(value: Any, *, currencies: set[str], now: datetime) -> dict | None:
    if not isinstance(value, Mapping):
        return None
    timestamp = _utc(value.get("released_at_utc"))
    surprise = value.get("actual_minus_consensus")
    if (timestamp is None or timestamp > now
            or value.get("currency") not in currencies
            or not isinstance(value.get("event_id"), str)
            or not 3 <= len(value["event_id"]) <= 90
            or value.get("surprise_class") not in SURPRISE_CLASSES
            or value.get("release_verified") is not False
            or value.get("strength_direction") != "AGUARDAR"
            or isinstance(surprise, bool)
            or not isinstance(surprise, (int, float))
            or not isfinite(surprise)):
        return None
    return {"timestamp": timestamp, "currency": value["currency"],
            "event_id": value["event_id"], "surprise_class": value["surprise_class"]}


def _calendar_classification(timestamp: datetime, start: date, end: date) -> str:
    # The ECB fixing is labeled by a European calendar date. A late UTC
    # release can already belong to the NEXT European business date.
    day = timestamp.astimezone(ECB_PUBLICATION_ZONE).date()
    if day < start:
        return "DIVULGADO_ANTES_DA_JANELA_BCE"
    if day > end:
        return "DIVULGADO_DEPOIS_DA_REFERENCIA_BCE"
    if day == start or day == end:
        return "MESMO_DIA_DA_FIXACAO_ORDEM_INTRADIA_DESCONHECIDA"
    return "DENTRO_DAS_DATAS_BCE_SEM_PROVA_DE_CAUSALIDADE"


def build_ecb_macro_timing_bridge_lab(
    xml_data: Any, macro_dossier: Any, *, at: datetime,
) -> dict[str, Any]:
    """Calendar-aligned review of 28×3 claims; all biases remain AGUARDAR."""
    # Context is rederived from XML bytes, not from a user-editable price matrix.
    ecb = build_ecb_horizon_context_lab(xml_data, at=at)
    if ecb["state"] != "LAB_CONTEXT_EXPOST_ONLY":
        return _refuse("REFERENCIA_BCE_INDISPONIVEL")
    now = at.astimezone(timezone.utc)
    if not isinstance(macro_dossier, Mapping):
        return _refuse("DOSSIE_MACRO_AUSENTE")
    if (macro_dossier.get("schema") != MACRO_DOSSIER_SCHEMA
            or macro_dossier.get("state") != "LAB_CAUSAL_EVIDENCE_GAPS_ONLY"
            or macro_dossier.get("pair_count") != 28
            or macro_dossier.get("currency_count") != 8
            or _utc(macro_dossier.get("as_of_utc")) != now
            or any(macro_dossier.get(flag) is not False for flag in (
                "published_macro_receipts_attested", "official_news_source_authenticated",
                "calendar_realtime_verified", "strength_causation_proven",
                "can_feed_live_radar", "trade_authorized", "publishable",
                "scheduler_enabled", "worker_enabled"))):
        return _refuse("DOSSIE_MACRO_SEM_CONTRATO_SEGURO")
    rows = macro_dossier.get("rows")
    if not isinstance(rows, list) or len(rows) != 28:
        return _refuse("COBERTURA_28_PARES_INCOMPLETA")
    mr = {}
    for row in rows:
        if not isinstance(row, Mapping):
            return _refuse("LINHA_MACRO_INVALIDA")
        pair = row.get("pair")
        if not isinstance(pair, str) or pair not in OFFICIAL_PAIRS or pair in mr:
            return _refuse("PAR_MACRO_DUPLICADO_OU_DESCONHECIDO")
        base, quote = split_pair(pair)
        frames = row.get("horizons")
        if (row.get("base") != base or row.get("quote") != quote
                or row.get("trade_authorized") is not False
                or not isinstance(frames, Mapping)
                or set(frames) != set(HORIZONS)):
            return _refuse("LINHA_MACRO_COM_AUTORIDADE_OU_JANELA_INVALIDA")
        mr[pair] = row

    if set(mr) != set(OFFICIAL_PAIRS):
        return _refuse("COBERTURA_28_PARES_INCOMPLETA")
    compared = []
    for row in ecb["pair_explanations"]:
        pair, base, quote = row["pair"], row["base"], row["quote"]
        macro = mr[pair]
        frames = {}
        for horizon in HORIZONS:
            f = macro["horizons"][horizon]
            if (not isinstance(f, Mapping)
                    or f.get("operational_bias") != "AGUARDAR"
                    or f.get("base_currency_strength_cause") != "NAO_COMPROVADA"
                    or f.get("quote_currency_strength_cause") != "NAO_COMPROVADA"
                    or f.get("actual_values_source_attested") is not False
                    or not isinstance(f.get("macro_surprise_claims"), list)
                    or len(f["macro_surprise_claims"]) > MAX_CLAIMS_PER_FRAME):
                return _refuse("MACRO_HORIZONTE_INSEGURO")
            observed = row["historico"][horizon]
            start_raw, end_raw = observed["de"], observed["ate"]
            if start_raw is None or end_raw is None:
                if f["macro_surprise_claims"]:
                    # Missing market history cannot be reconciled by a news claim.
                    return _refuse("NOTICIAS_NAO_REPARAM_HISTORICO_BCE_AUSENTE")
                frames[horizon] = {
                    "relation": "HISTORICO_INSUFICIENTE",
                    "calendar_alignments": [], "conclusion": "AGUARDAR",
                    "matched_as_market_cause": False,
                }
                continue
            start, end = date.fromisoformat(start_raw), date.fromisoformat(end_raw)
            alignments, event_ids = [], set()
            for claim in f["macro_surprise_claims"]:
                c = _claim(claim, currencies={base, quote}, now=now)
                if c is None or c["event_id"] in event_ids:
                    return _refuse("CLAIM_MACRO_INVALIDA_DUPLICADA_OU_FUTURA")
                event_ids.add(c["event_id"])
                alignments.append({
                    "currency": c["currency"], "event_id": c["event_id"],
                    "surprise_class_unattested": c["surprise_class"],
                    "calendar_relation": _calendar_classification(
                        c["timestamp"], start, end),
                    "can_explain_ecb_move": False,
                })
            frames[horizon] = {
                "relation": observed["relacao_passada"],
                "reference_from_date": start_raw,
                "reference_to_date": end_raw,
                "calendar_alignments": alignments,
                "news_documentary_count_not_attested": f.get("news_documentary_count"),
                "calendar_risk_status_not_live": f.get("calendar_risk_status_documentary"),
                "conclusion": "AGUARDAR", "matched_as_market_cause": False,
            }
        compared.append({
            "pair": pair, "base": base, "quote": quote,
            "D1_W1_MN1_historical_relationship": row["comparacao_d1_w1_mn1"],
            "horizons": frames, "strength_cause": "NAO_VERIFICADA",
            "operational_bias": "AGUARDAR", "trade_authorized": False,
        })

    out = _refuse("REFERENCIAS_BCE_E_SURPRESAS_SINTETICAS_NAO_PROVAM_CAUSA")
    out.update({
        "state": "LAB_TEMPORAL_CONTEXT_ONLY", "pair_count": len(compared),
        "rows": compared, "as_of_utc": now.isoformat(),
        "ecb_reference_date": ecb["reference_date"],
        "ecb_reference_outdated": ecb["reference_outdated_over_four_days"],
        "same_day_release_order_is_unverified": True,
        "macro_window_is_as_of_clock_not_exact_ecb_fix_window": True,
        "context_is_caller_supplied_unattested": True,
        "explanation": ("Coincidência temporal entre resultado econômico e mudança "
                        "de referência não comprova causa. Publicação após a "
                        "referência não pode explicar o movimento anterior."),
    })
    return out


__all__ = ["SCHEMA", "build_ecb_macro_timing_bridge_lab"]
