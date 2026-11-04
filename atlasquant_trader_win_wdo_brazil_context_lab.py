"""Documentary Brazil macro facts and WIN/WDO pre-event exposure; LAB only.

Uses official manually transcribed public facts; never reconstructs signed
historical releases, invents Focus expectations, or infers directional odds.
No network, orders, scheduler, Worker, broker, or UI side effects.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Sequence

from atlasquant_trader_macro_joint_dossier_lab import build_macro_joint_dossier_lab
from atlasquant_trader_macro_event_exposure_lab import HORIZONS, WINDOWS

SCHEMA = "ATLASQUANT_TRADER_WIN_WDO_BRAZIL_CONTEXT_LAB_V1"
RESEARCH_ON = date(2026, 11, 3)
INDICES = ("WIN", "WDO")
DOC_FIELDS = frozenset((
    "id", "indicator", "value_pct", "measure", "reference_period",
    "published_on", "conservative_available_from_utc", "source_url", "note",
))
EVENT_FIELDS = frozenset((
    "id", "event_kind", "date", "start_utc", "end_utc", "source_url",
))
DOCS = (
    {"id": "SELIC_TARGET_20260916", "indicator": "SELIC_TARGET",
     "value_pct": "13.75", "measure": "ANNUAL_POLICY_TARGET_RATE",
     "reference_period": "2026-09-17",
     "published_on": "2026-09-16",
     "conservative_available_from_utc": "2026-09-17T00:00:00Z",
     "source_url": "https://www.bcb.gov.br/estabilidadefinanceira/exibenormativo?numero=45963&tipo=Comunicado",
     "note": "Copom target announced September 16, effective September 17; not market-expected path"},
    {"id": "IPCA_202609_MOM", "indicator": "IPCA",
     "value_pct": "0.82", "measure": "UNADJUSTED_MONTH_ON_MONTH",
     "reference_period": "2026-09", "published_on": "2026-10-09",
     "conservative_available_from_utc": "2026-10-10T00:00:00Z",
     "source_url": "https://www.ibge.gov.br/estatisticas/economicas/precos-e-custos/9256-ipca.html",
     "note": "Headline full IPCA, not IPCA-15 or a future result"},
    {"id": "IPCA_202609_YOY", "indicator": "IPCA",
     "value_pct": "4.58", "measure": "UNADJUSTED_YEAR_ON_YEAR",
     "reference_period": "2026-09", "published_on": "2026-10-09",
     "conservative_available_from_utc": "2026-10-10T00:00:00Z",
     "source_url": "https://www.ibge.gov.br/estatisticas/economicas/precos-e-custos/9256-ipca.html",
     "note": "IPCA official twelve-month rolling accumulation; distinguish from monthly change"},
    {"id": "PNAD_202609_ROLLING_UNEMP", "indicator": "UNEMPLOYMENT",
     "value_pct": "5.2", "measure": "ROLLING_THREE_MONTH_UNEMPLOYMENT_RATE",
     "reference_period": "2026-07_TO_2026-09", "published_on": "2026-10-30",
     "conservative_available_from_utc": "2026-10-31T00:00:00Z",
     "source_url": "https://www.ibge.gov.br/estatisticas/sociais/trabalho/2511-np-pnadcontinua/17270-pnad-continua.html",
     "note": "PNAD Continúa monthly dissemination: rolling Jul-Aug-Sep quarter; not single-month unemployment"},
    {"id": "GDP_2026Q2_QOQ", "indicator": "REAL_GDP",
     "value_pct": "0.5", "measure": "SEASONALLY_ADJUSTED_QUARTER_ON_QUARTER",
     "reference_period": "2026-Q2", "published_on": "2026-09-01",
     "conservative_available_from_utc": "2026-09-02T00:00:00Z",
     "source_url": "https://www.ibge.gov.br/estatisticas/economicas/servicos/9300-contas-nacionais-trimestrais.html?lang=pt-BR",
     "note": "Q2 real GDP relative to Q1 with seasonal adjustment; revisions possible"},
    {"id": "GDP_2026Q2_YOY", "indicator": "REAL_GDP",
     "value_pct": "2.0", "measure": "QUARTER_ON_SAME_QUARTER_PRIOR_YEAR",
     "reference_period": "2026-Q2", "published_on": "2026-09-01",
     "conservative_available_from_utc": "2026-09-02T00:00:00Z",
     "source_url": "https://www.ibge.gov.br/estatisticas/economicas/servicos/9300-contas-nacionais-trimestrais.html?lang=pt-BR",
     "note": "Q2 against Q2 2025, NOT four-quarter accumulated growth (1.9%)"},
)
EVENTS = (
    {"id": "COPOM_DECISION_20261104", "event_kind": "BRAZIL_POLICY_DECISION",
     "date": "2026-11-04", "start_utc": "2026-11-04T00:00:00Z",
     "end_utc": "2026-11-04T23:59:59Z",
     "source_url": "https://www.bcb.gov.br/estabilidadefinanceira/exibenormativo?numero=45963&tipo=Comunicado"},
    {"id": "IBGE_IPCA_202610_RELEASE_20261112", "event_kind": "BRAZIL_INFLATION_RELEASE",
     "date": "2026-11-12", "start_utc": "2026-11-12T00:00:00Z",
     "end_utc": "2026-11-12T23:59:59Z",
     "source_url": "https://www.ibge.gov.br/estatisticas/economicas/precos-e-custos/9256-ipca.html"},
    {"id": "BCB_IBC_BR_202609_RELEASE_20261116", "event_kind": "BRAZIL_ACTIVITY_RELEASE",
     "date": "2026-11-16", "start_utc": "2026-11-16T00:00:00Z",
     "end_utc": "2026-11-16T23:59:59Z",
     "source_url": "https://www.bcb.gov.br/estatisticas/calendario_indicadores"},
)
SCENARIO_QUESTIONS = (
    "Copom: como a decisão se compara ao consenso ANTERIOR verificável, ao Focus da data e à curva DI?",
    "IPCA: qual surpresa ante expectativa congelada antes da divulgação e qual efeito na trajetória DI/Selic?",
    "WIN: juros, lucros, atividade, fluxo externo, prêmio fiscal e apetite global a risco concordam?",
    "WDO: diferencial esperado BRL/USD, Fed, fluxo cambial, termos de troca e risco fiscal concordam?",
    "Qual evidência CONTRÁRIA e qual evento invalidariam a tese antes de medir o horizonte?",
)


def _utc(value: Any) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z") or len(value) > 40:
        raise ValueError("Only canonical UTC documentary timestamps allowed")
    try:
        dt = datetime.fromisoformat(value[:-1] + "+00:00")
    except (ValueError, OverflowError) as exc:
        raise ValueError("Invalid documentary UTC instant") from exc
    if dt.utcoffset() != timedelta(0):
        raise ValueError("Non-UTC documentary instant")
    return dt.astimezone(timezone.utc)


def _assert_canonical(
    supplied: Sequence[Mapping[str, Any]] | None,
    canonical: tuple[dict[str, str], ...],
    fields: frozenset[str],
) -> list[dict[str, str]]:
    rows = canonical if supplied is None else supplied
    if not isinstance(rows, (tuple, list)) or len(rows) != len(canonical):
        raise ValueError("Complete canonical documentary set required")
    out = []
    for got, expected in zip(rows, canonical):
        if (not isinstance(got, Mapping) or set(got) != fields
                or dict(got) != expected):
            raise ValueError("Unreviewed or altered Brazil source entry")
        if "value_pct" in got:
            try:
                number = Decimal(got["value_pct"])
            except (InvalidOperation, ValueError) as exc:
                raise ValueError("Invalid economic number") from exc
            if not number.is_finite() or not -100 <= number <= 200:
                raise ValueError("Nonfinite or extreme Brazil number")
        out.append(dict(got))
    return out


def _event_state(event: dict[str, str], now: datetime, horizon: str) -> str | None:
    first, last = _utc(event["start_utc"]), _utc(event["end_utc"])
    deadline = now + WINDOWS[horizon]
    if last <= now or first > deadline:
        return None
    if first <= now < last:
        return "DATE_ONLY_MAY_ALREADY_HAVE_OCCURRED"
    if last <= deadline:
        return "SCHEDULED_WITHIN_WINDOW"
    return "WINDOW_EDGE_TIME_UNCERTAIN"


def build_win_wdo_brazil_context_lab(
    *, at: datetime, documents: Sequence[Mapping[str, Any]] | None = None,
    events: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Expose isolated Brazil facts plus global USD catalyst, no prediction."""
    if not isinstance(at, datetime) or at.tzinfo is None:
        raise ValueError("Explicit timezone-aware research cutoff required")
    now = at.astimezone(timezone.utc)
    if now.date() < RESEARCH_ON:
        raise ValueError("Cannot backdate unarchived Brazil research")
    docs = _assert_canonical(documents, DOCS, DOC_FIELDS)
    upcoming = _assert_canonical(events, EVENTS, EVENT_FIELDS)
    for event in upcoming:
        if _utc(event["end_utc"]) < _utc(event["start_utc"]):
            raise ValueError("Reversed event window")
        if _utc(event["start_utc"]).date().isoformat() != event["date"]:
            raise ValueError("Event date-window mismatch")

    visible = {}
    for row in docs:
        if _utc(row["conservative_available_from_utc"]) > now:
            continue
        state = "LAST_DOCUMENTED_PREVIOUS_READING"
        if row["indicator"] == "SELIC_TARGET" and now.date() >= date(2026, 11, 4):
            state = "COPOM_NEW_DECISION_DAY_REQUIRES_VERIFICATION"
        if row["indicator"] == "IPCA" and now.date() >= date(2026, 11, 12):
            state = "IPCA_NEW_RELEASE_DAY_REQUIRES_VERIFICATION"
        visible[row["id"]] = {**row, "freshness_state": state,
                              "source_bytes_independently_attested": False}

    joint = build_macro_joint_dossier_lab(at=now)
    global_indices = {(r["instrument"], r["horizon"]): r
                      for r in joint["indices_by_horizon"]}
    rows = []
    for horizon in HORIZONS:
        local = [
            {"event_id": event["id"], "event_kind": event["event_kind"],
             "timing_state": status, "source_url": event["source_url"]}
            for event in upcoming
            if (status := _event_state(event, now, horizon)) is not None
        ]
        for instrument in INDICES:
            global_row = global_indices[(instrument, horizon)]
            rows.append({
                "instrument": instrument, "horizon": horizon,
                "brasil_official_facts": visible,
                "brasil_upcoming_events": local,
                "us_upcoming_events": global_row["curated_upcoming_events"],
                "calendar_scope": "PARTIAL_MANUAL_CURATED",
                "pre_event_consensus": None, "focus_vintage_verified": False,
                "forward_di_curve_verified": False,
                "brl_usd_cross_macro_model_verified": False,
                "brazil_fiscal_flow_geo_context_verified": False,
                "directional_bias": "AGUARDAR",
                "probability_calibrated": None,
                "trade_authorized": False,
            })
    if len(rows) != 6 or {r["instrument"] for r in rows} != set(INDICES):
        raise RuntimeError("WIN/WDO horizon matrix not canonical")
    return {
        "schema": SCHEMA, "state": "LAB_BRAZIL_INDEX_CONTEXT_NO_DIRECTION",
        "as_of_utc": now.isoformat(), "official_facts": visible,
        "local_calendar": upcoming, "index_horizons": rows,
        "indicator_count": len(visible), "local_event_count": len(upcoming),
        "index_horizon_count": len(rows),
        "scenario_research_questions": SCENARIO_QUESTIONS,
        "original_source_bytes_archived": False,
        "independent_source_receipts_verified": False,
        "point_in_time_consensus_verified": False,
        "historical_price_independence_proven": False,
        "accuracy_90_proven": False,
        "can_feed_live_radar": False, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "warning": "Brazil official macro values are NOT a directional forecast. "
                   "US calendar exposure alone cannot predict WIN/WDO. "
                   "Absent dated consensus, DI curve, independent prices, fiscal "
                   "and flow evidence, always abstain.",
    }


__all__ = ["SCHEMA", "DOCS", "EVENTS", "build_win_wdo_brazil_context_lab"]
