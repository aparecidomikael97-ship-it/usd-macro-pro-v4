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
    consensus_at = _utc(value.get("consensus_captured_at_utc"))
    surprise = value.get("actual_minus_consensus")
    actual = value.get("actual_synthetic")
    consensus = value.get("consensus_synthetic")
    previous = value.get("previous_synthetic")
    cls = value.get("surprise_class")
    # Never accept a post-release "consensus" as if it were an ex-ante
    # benchmark. Independently recompute the numerical surprise instead
    # of trusting a label or delta copied from a separate PR/dossier.
    if (timestamp is None or timestamp > now
            or consensus_at is None or consensus_at >= timestamp
            or value.get("currency") not in currencies
            or not isinstance(value.get("event_id"), str)
            or not 3 <= len(value["event_id"]) <= 90
            or cls not in SURPRISE_CLASSES
            or value.get("release_verified") is not False
            or value.get("strength_direction") != "AGUARDAR"
            or any(isinstance(x, bool) or not isinstance(x, (int, float))
                   or not isfinite(x) for x in (surprise, actual, consensus))
            or (previous is not None and
                (isinstance(previous, bool) or not isinstance(previous, (int, float))
                 or not isfinite(previous)))
            or abs((actual - consensus) - surprise) > 1e-8 * max(1.0, abs(surprise))
            or (cls == "ABOVE_CONSENSUS" and surprise <= 0)
            or (cls == "BELOW_CONSENSUS" and surprise >= 0)):
        return None
    # IN_LINE_WITH_CONSENSUS may legitimately have a nonzero delta:
    # the parent dossier's predeclared deadband is not in this contract.
    return {
        "timestamp": timestamp, "consensus_at": consensus_at,
        "currency": value["currency"], "event_id": value["event_id"],
        "surprise_class": cls,
        # A single macro event can appear in up to seven FX pairs and in
        # overlapping D1/W1/MN1 windows. It must have the SAME documentary
        # values everywhere; repetition is not independent corroboration.
        "documentary_fingerprint": (
            value["currency"], timestamp, consensus_at,
            value.get("indicator"), value.get("unit"), previous,
            consensus, actual, surprise, cls,
        ),
    }


def _documentary_coverage(base: str, quote: str, per_currency: dict) -> dict[str, Any]:
    """Describe only the supplied claims, never all real economic events."""
    a = sorted(per_currency[base])
    b = sorted(per_currency[quote])
    if a and b:
        state = "ALEGACOES_DOCUMENTAIS_DAS_DUAS_MOEDAS_NAO_AUTENTICADAS"
    elif a or b:
        state = "ALEGACOES_DOCUMENTAIS_APENAS_DE_UMA_MOEDA"
    else:
        state = "SEM_ALEGACOES_DOCUMENTAIS_NO_DOSSIE"
    return {
        "state": state,
        "base_currency": base, "quote_currency": quote,
        "base_unattested_event_ids": a, "quote_unattested_event_ids": b,
        "base_unattested_event_count": len(a),
        "quote_unattested_event_count": len(b),
        "two_currencies_with_claims": bool(a and b),
        "absence_of_claims_does_not_mean_no_real_release": True,
        "macro_fundamentals_authenticated": False,
        "counterevidence_verified": False,
        "basis_for_operational_bias": False,
    }


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
    event_ledger: dict[str, tuple[Any, ...]] = {}
    # Collect only claims present in the supplied dossier, not a supposed
    # exhaustive economic calendar. Each event is counted once per currency,
    # per horizon, even if repeated in seven FX pairs.
    universe_claims = {
        h: {currency: set() for currency in CURRENCIES} for h in HORIZONS
    }
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
                    "macro_documentary_coverage": _documentary_coverage(
                        base, quote, {base: set(), quote: set()}),
                }
                continue
            start, end = date.fromisoformat(start_raw), date.fromisoformat(end_raw)
            alignments, event_ids = [], set()
            per_currency = {base: set(), quote: set()}
            for claim in f["macro_surprise_claims"]:
                c = _claim(claim, currencies={base, quote}, now=now)
                if c is None or c["event_id"] in event_ids:
                    return _refuse("CLAIM_MACRO_INVALIDA_DUPLICADA_OU_FUTURA")
                event_ids.add(c["event_id"])
                identity = c["event_id"]
                fingerprint = c["documentary_fingerprint"]
                if (identity in event_ledger and
                        event_ledger[identity] != fingerprint):
                    return _refuse("EVENTO_MACRO_CONTRADITORIO_ENTRE_PARES_OU_HORIZONTES")
                event_ledger[identity] = fingerprint
                per_currency[c["currency"]].add(identity)
                universe_claims[horizon][c["currency"]].add(identity)
                alignments.append({
                    "currency": c["currency"], "event_id": c["event_id"],
                    "surprise_class_unattested": c["surprise_class"],
                    "consensus_snapshot_declared_at_utc": c["consensus_at"].isoformat(),
                    "consensus_snapshot_origin_authenticated": False,
                    "calendar_relation": _calendar_classification(
                        c["timestamp"], start, end),
                    "can_explain_ecb_move": False,
                })
            frames[horizon] = {
                "relation": observed["relacao_passada"],
                "reference_from_date": start_raw,
                "reference_to_date": end_raw,
                "calendar_alignments": alignments,
                "macro_documentary_coverage": _documentary_coverage(
                    base, quote, per_currency),
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

    # A release about USD supplied for EUR/USD should not silently disappear
    # from GBP/USD's *same-horizon* dossier. This is a documentary propagation
    # warning only: missing records do NOT establish zero actual releases.
    pair_frames_with_gaps = 0
    for row in compared:
        for horizon in HORIZONS:
            coverage = row["horizons"][horizon]["macro_documentary_coverage"]
            gaps = {}
            for currency in (row["base"], row["quote"]):
                seen_here = set(coverage[
                    "base_unattested_event_ids" if currency == row["base"]
                    else "quote_unattested_event_ids"])
                missing = sorted(universe_claims[horizon][currency] - seen_here)
                gaps[currency] = {
                    "missing_count_from_other_pairs_same_horizon": len(missing),
                    "first_missing_event_ids": missing[:8],
                    "truncated_example_list": len(missing) > 8,
                }
            has_gap = any(x["missing_count_from_other_pairs_same_horizon"] > 0
                          for x in gaps.values())
            if has_gap:
                pair_frames_with_gaps += 1
            coverage["documentary_visibility_gaps"] = gaps
            coverage["not_same_as_real_event_calendar_completeness"] = True
            coverage["incomplete_relative_to_supplied_pair_dossier"] = has_gap

    out = _refuse("REFERENCIAS_BCE_E_SURPRESAS_SINTETICAS_NAO_PROVAM_CAUSA")
    out.update({
        "state": "LAB_TEMPORAL_CONTEXT_ONLY", "pair_count": len(compared),
        "rows": compared, "as_of_utc": now.isoformat(),
        "ecb_reference_date": ecb["reference_date"],
        "ecb_reference_outdated": ecb["reference_outdated_over_four_days"],
        "same_day_release_order_is_unverified": True,
        "macro_window_is_as_of_clock_not_exact_ecb_fix_window": True,
        "context_is_caller_supplied_unattested": True,
        "cross_pair_macro_event_consistency_checked": True,
        "distinct_unattested_macro_events": len(event_ledger),
        "repeated_claims_are_not_independent_evidence": True,
        "supplied_macro_events_by_currency_and_horizon": {
            h: {c: len(universe_claims[h][c]) for c in CURRENCIES}
            for h in HORIZONS
        },
        "pair_horizons_with_relative_documentary_visibility_gaps":
            pair_frames_with_gaps,
        "full_economic_calendar_coverage_verified": False,
        "two_sided_economic_explanation_proven": False,
        "explanation": ("Coincidência temporal entre resultado econômico e mudança "
                        "de referência não comprova causa. Publicação após a "
                        "referência não pode explicar o movimento anterior."),
    })
    return out


__all__ = ["SCHEMA", "build_ecb_macro_timing_bridge_lab"]
