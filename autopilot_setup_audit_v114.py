"""AtlasQuant V11.4 — auditoria prospectiva de setups do Paper Trading.

Esta camada roda DEPOIS do Paper Trading V11.2. Ela não altera checklist,
Gate, pesos, sinais nem execução. O objetivo é congelar, em um sidecar separado,
o estado dos componentes ICT/SMC/institucionais quando um trade Paper aparece
pela primeira vez e, depois, atualizar somente o desfecho desse trade.

Segurança: zero ordens reais, zero conexão com corretora e zero seleção
automática de estratégia com base em performance passada.
"""
from __future__ import annotations

import json
import math
from typing import Any, Mapping

import pandas as pd

import autopilot_paper_v112 as paper_runner
import autopilot_news_nowcast_v1 as news_nowcast_runner
import autopilot_v107 as base

AUDIT_VERSION = "V11.4_SETUP_AUDIT"
PAPER_CSV_PATH = "dados/paper_trades_v112.csv"
AUDIT_CSV_PATH = "dados/paper_setup_audit_v114.csv"
PERFORMANCE_CSV_PATH = "dados/paper_setup_performance_v114.csv"
SUMMARY_JSON_PATH = "dados/paper_setup_summary_v114.json"

COMPONENTS: tuple[tuple[str, str, str], ...] = (
    ("AMD", "ict", "amd"),
    ("FVG", "ict", "fvg"),
    ("CRT", "ict", "crt"),
    ("OTE", "ict", "ote"),
    ("DISPLACEMENT", "institutional", "displacement"),
    ("MSS", "institutional", "mss"),
    ("SMT", "institutional", "smt"),
    ("DEALING_RANGE", "institutional", "dealing_range"),
    ("LIQUIDITY", "institutional", "liquidity"),
    ("SESSION", "institutional", "session"),
    ("PD_ARRAY", "institutional", "pd_array"),
)

BASE_FIELDS = [
    "trade_id", "signal_id", "pair", "side", "setup_id", "setup_attribution",
    "signal_time", "signal_candle_time",
    "score_master", "quality", "rank_index", "h4", "h1", "m15",
    "ict_readiness", "institutional_readiness", "gate", "gate_score",
    "adr_used_pct", "event_risk", "technical_age_min", "map_age_min",
    "data_sufficient", "data_quality_pct", "checklist_passed", "checklist_note", "engine_version",
]
OUTCOME_FIELDS = [
    "status", "result", "entry_time", "entry_price", "stop_price", "target_price",
    "risk_distance", "target_rr", "exit_time", "exit_price", "exit_reason",
    "realized_r", "bars_held", "mfe_r", "mae_r", "ambiguous_touch", "updated_at",
]
AUDIT_META_FIELDS = [
    "audit_capture_at", "audit_capture_delay_min", "audit_capture_mode", "audit_version",
]
VALIDATION_CONTEXT_FIELDS = [
    "d1_regime", "w1_regime", "active_session", "premium_discount_zone",
    "latest_sweep_type",
]
COMPONENT_FIELDS = [
    item
    for name, _, _ in COMPONENTS
    for item in (f"{name.lower()}_status", f"{name.lower()}_score")
]
AUDIT_COLUMNS = BASE_FIELDS + OUTCOME_FIELDS + AUDIT_META_FIELDS + VALIDATION_CONTEXT_FIELDS + COMPONENT_FIELDS
PERFORMANCE_COLUMNS = [
    "component", "state", "trades_closed", "wins", "losses", "breakeven",
    "win_rate_pct", "net_r", "avg_r", "profit_factor_r", "max_drawdown_r",
    "sample_state",
]


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _as_utc(value: Any) -> pd.Timestamp | None:
    if value in (None, ""):
        return None
    try:
        ts = pd.to_datetime(value, utc=True, errors="coerce")
        return None if pd.isna(ts) else pd.Timestamp(ts)
    except Exception:
        return None


def _finite_or_none(value: Any) -> float | None:
    try:
        out = float(value)
        return out if math.isfinite(out) else None
    except Exception:
        return None


def _sample_state(n: int) -> str:
    n = max(0, int(n or 0))
    if n == 0:
        return "AGUARDANDO AMOSTRA"
    if n < 30:
        return "AMOSTRA PEQUENA"
    if n < 100:
        return "AMOSTRA EM FORMAÇÃO"
    return "AMOSTRA MAIS MADURA"


def _normalize_audit(df: pd.DataFrame | None) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame(columns=AUDIT_COLUMNS)
    out = df.copy()
    for col in AUDIT_COLUMNS:
        if col not in out.columns:
            out[col] = None
    return out[AUDIT_COLUMNS].copy()


def _component_value(tecnico: Mapping[str, Any], group: str, key: str) -> tuple[str, float | None]:
    obj = _mapping(_mapping(tecnico).get(group))
    item = _mapping(obj.get(key))
    return str(item.get("status", "") or ""), _finite_or_none(item.get("score"))


def extract_setup_snapshot(
    trade: Mapping[str, Any],
    scanner: Mapping[str, Any],
    *,
    market_map: Mapping[str, Any] | None = None,
    now: pd.Timestamp | None = None,
) -> dict[str, Any]:
    """Congela o contexto observável do scanner para um trade visto pela 1ª vez."""
    now = pd.Timestamp.now(tz="UTC") if now is None else pd.Timestamp(now)
    now = now.tz_localize("UTC") if now.tzinfo is None else now.tz_convert("UTC")

    pair = str(trade.get("pair", "") or "")
    resultados = _mapping(_mapping(scanner).get("resultados"))
    pair_row = _mapping(resultados.get(pair))
    tecnico = _mapping(pair_row.get("tecnico"))

    row: dict[str, Any] = {field: trade.get(field) for field in BASE_FIELDS}
    row.update({field: trade.get(field) for field in OUTCOME_FIELDS})

    created = _as_utc(trade.get("created_at"))
    delay = None if created is None else max(0.0, (now - created).total_seconds() / 60.0)
    row.update({
        "audit_capture_at": now.isoformat(),
        "audit_capture_delay_min": None if delay is None else round(float(delay), 2),
        "audit_capture_mode": "FIRST_SEEN_V114",
        "audit_version": AUDIT_VERSION,
    })

    contexts=_mapping(_mapping(market_map).get("contexts"))
    market_ctx=_mapping(contexts.get(pair))
    d1_structure=_mapping(_mapping(market_ctx.get("d1")).get("structure"))
    w1_structure=_mapping(_mapping(market_ctx.get("w1")).get("structure"))
    killzone=_mapping(market_ctx.get("killzone"))
    active=killzone.get("active")
    if isinstance(active,Mapping):
        active_session=str(active.get("name","") or "")
    else:
        active_session=str(active or "")
    premium=_mapping(market_ctx.get("premium_discount"))
    latest=market_ctx.get("latest_sweep")
    latest_type=str(_mapping(latest).get("type","") or "") if isinstance(latest,Mapping) else str(latest or "")
    row.update({
        "d1_regime":str(trade.get("d1_regime") or d1_structure.get("regime","") or ""),
        "w1_regime":str(trade.get("w1_regime") or w1_structure.get("regime","") or ""),
        "active_session":str(trade.get("active_session") or active_session or ""),
        "premium_discount_zone":str(premium.get("zone","") or ""),
        "latest_sweep_type":latest_type,
    })

    for name, group, key in COMPONENTS:
        status, score = _component_value(tecnico, group, key)
        row[f"{name.lower()}_status"] = status
        row[f"{name.lower()}_score"] = score
    return row


def sync_setup_audit(
    trades: pd.DataFrame | None,
    scanner: Mapping[str, Any] | None,
    existing: pd.DataFrame | None = None,
    *,
    market_map: Mapping[str, Any] | None = None,
    now: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Adiciona novos snapshots e preserva os campos de setup já congelados.

    Para trades já conhecidos, apenas campos de desfecho são atualizados.
    """
    now = pd.Timestamp.now(tz="UTC") if now is None else pd.Timestamp(now)
    now = now.tz_localize("UTC") if now.tzinfo is None else now.tz_convert("UTC")
    audit = _normalize_audit(existing)
    scanner = _mapping(scanner)

    by_id: dict[str, dict[str, Any]] = {}
    if not audit.empty:
        for _, row in audit.iterrows():
            trade_id = str(row.get("trade_id", "") or "").strip()
            if trade_id:
                by_id[trade_id] = row.to_dict()

    if isinstance(trades, pd.DataFrame) and not trades.empty:
        for _, trade_row in trades.iterrows():
            trade = trade_row.to_dict()
            trade_id = str(trade.get("trade_id", "") or "").strip()
            if not trade_id:
                continue
            if trade_id not in by_id:
                by_id[trade_id] = extract_setup_snapshot(trade, scanner, market_map=market_map, now=now)
            else:
                frozen = dict(by_id[trade_id])
                # Campos de contexto/setup permanecem imutáveis. Só o desfecho evolui.
                for field in OUTCOME_FIELDS:
                    if field in trade:
                        frozen[field] = trade.get(field)
                by_id[trade_id] = frozen

    if not by_id:
        return pd.DataFrame(columns=AUDIT_COLUMNS)

    out = pd.DataFrame(list(by_id.values()))
    for col in AUDIT_COLUMNS:
        if col not in out.columns:
            out[col] = None
    out = out[AUDIT_COLUMNS].copy()
    if "signal_time" in out.columns:
        out["_signal_sort"] = pd.to_datetime(out["signal_time"], utc=True, errors="coerce")
        out = out.sort_values(["_signal_sort", "trade_id"], na_position="last").drop(columns=["_signal_sort"])
    return out.reset_index(drop=True)


def _max_drawdown(rs: list[float]) -> float:
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for value in rs:
        equity += float(value)
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    return max_dd


def aggregate_setup_performance(audit: pd.DataFrame | None) -> pd.DataFrame:
    """Resume estados observados por componente, sem criar ranking ou vencedor."""
    d = _normalize_audit(audit)
    if d.empty:
        return pd.DataFrame(columns=PERFORMANCE_COLUMNS)
    closed = d[d["status"].astype(str).str.upper().eq("CLOSED")].copy()
    if closed.empty:
        return pd.DataFrame(columns=PERFORMANCE_COLUMNS)
    closed["_r"] = pd.to_numeric(closed["realized_r"], errors="coerce")
    closed = closed[closed["_r"].map(lambda x: bool(pd.notna(x) and math.isfinite(float(x))))].copy()
    if closed.empty:
        return pd.DataFrame(columns=PERFORMANCE_COLUMNS)
    closed["_exit"] = pd.to_datetime(closed["exit_time"], utc=True, errors="coerce")

    rows: list[dict[str, Any]] = []
    for name, _, _ in COMPONENTS:
        col = f"{name.lower()}_status"
        if col not in closed.columns:
            continue
        work = closed.copy()
        work[col] = work[col].fillna("").astype(str).str.strip().replace("", "(SEM ESTADO)")
        for state, group in work.groupby(col, dropna=False):
            g = group.sort_values(["_exit", "trade_id"], na_position="last")
            rs = [float(x) for x in g["_r"].tolist()]
            n = len(rs)
            wins = sum(1 for x in rs if x > 0)
            losses = sum(1 for x in rs if x < 0)
            breakeven = sum(1 for x in rs if x == 0)
            gross_profit = sum(x for x in rs if x > 0)
            gross_loss = abs(sum(x for x in rs if x < 0))
            pf = None if gross_loss <= 0 else gross_profit / gross_loss
            rows.append({
                "component": name,
                "state": str(state),
                "trades_closed": int(n),
                "wins": int(wins),
                "losses": int(losses),
                "breakeven": int(breakeven),
                "win_rate_pct": round((wins / n) * 100.0, 2) if n else None,
                "net_r": round(sum(rs), 4),
                "avg_r": round(sum(rs) / n, 4) if n else None,
                "profit_factor_r": None if pf is None else round(float(pf), 4),
                "max_drawdown_r": round(_max_drawdown(rs), 4),
                "sample_state": _sample_state(n),
            })

    if not rows:
        return pd.DataFrame(columns=PERFORMANCE_COLUMNS)
    return (
        pd.DataFrame(rows, columns=PERFORMANCE_COLUMNS)
        .sort_values(["component", "state"], kind="stable")
        .reset_index(drop=True)
    )


def _paper_blocker_summary(status: Mapping[str, Any] | None) -> dict[str, Any]:
    paper=_mapping(_mapping(status).get("paper_trading_v112"))
    cycle=_mapping(paper.get("last_cycle"))
    checklists=_mapping(cycle.get("checklists"))
    hard: dict[str,int]={}
    soft: dict[str,int]={}
    states: dict[str,int]={}
    passed=0
    for item in checklists.values():
        row=_mapping(item)
        state=str(row.get("state","") or "").strip()
        if state:
            states[state]=states.get(state,0)+1
        if bool(row.get("passed",False)):
            passed+=1
        for reason in list(row.get("hard_blocks",[]) or []):
            key=str(reason or "").strip()
            if key: hard[key]=hard.get(key,0)+1
        for reason in list(row.get("soft_blocks",[]) or []):
            key=str(reason or "").strip()
            if key: soft[key]=soft.get(key,0)+1
    return {
        "pairs_evaluated":len(checklists),
        "checklists_passed":passed,
        "hard_block_counts":dict(sorted(hard.items(),key=lambda kv:(-kv[1],kv[0]))),
        "soft_block_counts":dict(sorted(soft.items(),key=lambda kv:(-kv[1],kv[0]))),
        "state_counts":dict(sorted(states.items(),key=lambda kv:(-kv[1],kv[0]))),
        "diagnostic_only":True,
        "thresholds_changed":False,
    }


def build_summary(audit: pd.DataFrame, performance: pd.DataFrame, *, now: pd.Timestamp | None = None, status: Mapping[str, Any] | None = None) -> dict[str, Any]:
    now = pd.Timestamp.now(tz="UTC") if now is None else pd.Timestamp(now)
    now = now.tz_localize("UTC") if now.tzinfo is None else now.tz_convert("UTC")
    d = _normalize_audit(audit)
    closed = d[d["status"].astype(str).str.upper().eq("CLOSED")].copy() if not d.empty else d
    r = pd.to_numeric(closed.get("realized_r"), errors="coerce").dropna() if not closed.empty else pd.Series(dtype=float)
    r = r[r.map(lambda x: math.isfinite(float(x)))] if len(r) else r
    trusted={"EXPLICIT_INPUT","MANUAL_TAG","SOURCE_MODEL_EXPLICIT"}
    if "setup_id" in d.columns and "setup_attribution" in d.columns:
        explicit_setups=(
            d["setup_id"].fillna("").astype(str).str.strip().ne("")
            & d["setup_attribution"].fillna("").astype(str).str.upper().isin(trusted)
        )
    else:
        explicit_setups=pd.Series(False,index=d.index)
    if isinstance(closed,pd.DataFrame) and "setup_id" in closed.columns and "setup_attribution" in closed.columns:
        explicit_setup_closed=(
            closed["setup_id"].fillna("").astype(str).str.strip().ne("")
            & closed["setup_attribution"].fillna("").astype(str).str.upper().isin(trusted)
        )
    else:
        explicit_setup_closed=pd.Series(False,index=closed.index)
    return {
        "version": AUDIT_VERSION,
        "generated_at": now.isoformat(),
        "audited_trades": int(len(d)),
        "closed_trades": int(len(r)),
        "explicit_setup_trades": int(explicit_setups.sum()) if len(d) else 0,
        "explicit_setup_closed_trades": int(explicit_setup_closed.sum()) if len(closed) else 0,
        "setup_attribution_inferred": False,
        "component_state_rows": int(len(performance)) if isinstance(performance, pd.DataFrame) else 0,
        "paper_blockers": _paper_blocker_summary(status),
        "sample_state": _sample_state(int(len(r))),
        "net_r": round(float(r.sum()), 4) if len(r) else 0.0,
        "safety": {
            "real_orders": False,
            "broker_connection": False,
            "auto_strategy_selection": False,
            "auto_gate_change": False,
            "purpose": "auditoria prospectiva descritiva por componente/setup",
        },
        "files": {
            "audit": AUDIT_CSV_PATH,
            "performance": PERFORMANCE_CSV_PATH,
        },
    }


def _audit_cycle() -> tuple[bool, dict[str, Any], list[str]]:
    errors: list[str] = []
    trades, err = base.gh_get_csv(PAPER_CSV_PATH)
    if err:
        if "404" not in str(err):
            errors.append("Paper trades: " + str(err))
        trades = pd.DataFrame()

    scanner, err = base.gh_get_json(base.SCANNER_PATH, {})
    if err:
        errors.append("Scanner: " + str(err))
    scanner = scanner if isinstance(scanner, Mapping) else {}

    master, err = base.gh_get_json(base.MASTER_PATH, {})
    if err:
        errors.append("Market Map: " + str(err))
    master = master if isinstance(master, Mapping) else {}

    existing, err = base.gh_get_csv(AUDIT_CSV_PATH)
    if err:
        if "404" not in str(err):
            errors.append("Setup audit: " + str(err))
        existing = pd.DataFrame()

    now = base.utcnow()
    audit = sync_setup_audit(trades, scanner, existing, market_map=master, now=now)
    performance = aggregate_setup_performance(audit)
    status_before, _ = base.gh_get_json(base.STATUS_PATH, {})
    status_before = status_before if isinstance(status_before, dict) else {}
    summary = build_summary(audit, performance, now=now, status=status_before)

    ok1, err1 = base.gh_put_csv(
        AUDIT_CSV_PATH,
        audit,
        "V11.4 Setup Audit: atualiza snapshots prospectivos",
    )
    if not ok1:
        errors.append("Salvar setup audit: " + str(err1))

    ok2, err2 = base.gh_put_csv(
        PERFORMANCE_CSV_PATH,
        performance,
        "V11.4 Setup Audit: atualiza desempenho por componente",
    )
    if not ok2:
        errors.append("Salvar performance setup: " + str(err2))

    ok3, err3 = base.gh_put_json(
        SUMMARY_JSON_PATH,
        summary,
        "V11.4 Setup Audit: atualiza resumo",
    )
    if not ok3:
        errors.append("Salvar resumo setup: " + str(err3))

    status = status_before
    status["setup_audit_v114"] = {
        "enabled": True,
        "audited_trades": summary.get("audited_trades", 0),
        "closed_trades": summary.get("closed_trades", 0),
        "component_state_rows": summary.get("component_state_rows", 0),
        "sample_state": summary.get("sample_state"),
        "real_orders": False,
        "broker_connection": False,
        "errors": errors[:10],
    }
    existing_errors = list(status.get("errors", []) or [])
    status["errors"] = (existing_errors + errors)[:20]
    ok4, err4 = base.gh_put_json(
        base.STATUS_PATH,
        status,
        "V11.4 Autopilot: status com Setup Audit",
    )
    if not ok4:
        errors.append("Salvar status setup audit: " + str(err4))
        # The status sink itself failed, so make the failure observable in CI logs.
        print("[setup-audit][status-write-failed] " + str(err4))

    if errors:
        print("[setup-audit][errors] " + " | ".join(str(x) for x in errors[:10]))

    return bool(ok1 and ok2 and ok3 and ok4), summary, errors


def main() -> int:
    rc = paper_runner.main()
    audit_ok, summary, errors = _audit_cycle()
    news_ok, news_summary, news_errors = news_nowcast_runner._news_nowcast_cycle()
    print(json.dumps({
        "setup_audit_v114": summary,
        "setup_audit_ok": audit_ok,
        "setup_audit_errors": errors,
        "news_nowcast_v1": news_summary,
        "news_nowcast_ok": news_ok,
        "news_nowcast_errors": news_errors,
    }, ensure_ascii=False, indent=2, default=str))
    # Mantém o retorno estrutural do Autopilot/Paper. Setup Audit e News Nowcast
    # são sidecars observáveis; não mascaram a coleta principal nem habilitam trade.
    return int(rc)


if __name__ == "__main__":
    raise SystemExit(main())
