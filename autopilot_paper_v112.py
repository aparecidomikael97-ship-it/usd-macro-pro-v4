"""AtlasQuant V11.2 — Autopilot + Paper Trading.

Executa o Autopilot V11.1 (quota saver) e, sem consumir chamadas adicionais
da Twelve Data, reutiliza o cache M15 persistido para simular entradas somente
quando o checklist operacional completo estiver liberado.
"""
from __future__ import annotations

import json

import pandas as pd

import autopilot_v107 as base
import autopilot_quota_guard_v111 as quota
from paper_trading_v112 import run_paper_cycle, summarize_paper_trades

PAPER_CSV_PATH = "dados/paper_trades_v112.csv"
PAPER_SUMMARY_PATH = "dados/paper_trading_summary_v112.json"


def _paper_cycle() -> tuple[bool, dict, list[str]]:
    errors: list[str] = []

    inputs, err = base.gh_get_json(base.INPUT_PATH, {})
    if err:
        errors.append("Paper inputs: " + err)
    scanner, err = base.gh_get_json(base.SCANNER_PATH, {})
    if err:
        errors.append("Paper scanner: " + err)
    master, err = base.gh_get_json(base.MASTER_PATH, {})
    if err:
        errors.append("Paper Market Map: " + err)
    trades, err = base.gh_get_csv(PAPER_CSV_PATH)
    if err:
        # Arquivo inexistente no primeiro ciclo é normal; só sinaliza erro real.
        if "404" not in str(err):
            errors.append("Paper diário: " + err)
        trades = pd.DataFrame()

    try:
        updated, cycle = run_paper_cycle(
            inputs if isinstance(inputs, dict) else {},
            scanner if isinstance(scanner, dict) else {},
            master if isinstance(master, dict) else {},
            trades,
            now=base.utcnow(),
        )
    except Exception as exc:
        return False, {}, errors + [f"Paper engine: {type(exc).__name__}: {exc}"]

    ok, err = base.gh_put_csv(
        PAPER_CSV_PATH,
        updated,
        "V11.2 Paper Trading: atualiza diário simulado",
    )
    if not ok:
        errors.append("Salvar Paper diário: " + err)

    summary = summarize_paper_trades(updated)
    summary["last_cycle"] = cycle
    summary["safety"] = {
        "real_orders": False,
        "broker_connection": False,
        "entry_rule": "Decision Integrity executável + zero hard/soft blocks",
        "entry_timing": "OPEN do primeiro M15 posterior ao sinal",
        "stop_model": "1.0 ATR M15 pré-entrada",
        "target_model": "2R",
        "same_candle_stop_and_target": "LOSS conservador",
        "max_hold": "96 candles M15 / 24h",
    }

    ok2, err2 = base.gh_put_json(
        PAPER_SUMMARY_PATH,
        summary,
        "V11.2 Paper Trading: resumo de desempenho",
    )
    if not ok2:
        errors.append("Salvar Paper resumo: " + err2)

    status, _ = base.gh_get_json(base.STATUS_PATH, {})
    if not isinstance(status, dict):
        status = {}
    status["paper_trading_v112"] = {
        "enabled": True,
        "real_orders": False,
        "trades_total": summary.get("trades_total", 0),
        "pending_entries": summary.get("pending_entries", 0),
        "open_positions": summary.get("open_positions", 0),
        "closed_trades": summary.get("closed_trades", 0),
        "wins": summary.get("wins", 0),
        "losses": summary.get("losses", 0),
        "breakeven": summary.get("breakeven", 0),
        "win_rate_pct": summary.get("win_rate_pct", 0.0),
        "net_r": summary.get("net_r", 0.0),
        "avg_r": summary.get("avg_r", 0.0),
        "profit_factor_r": summary.get("profit_factor_r"),
        "last_cycle": cycle,
        "errors": errors[:10],
    }
    existing_errors = list(status.get("errors", []) or [])
    status["errors"] = (existing_errors + errors)[:20]
    ok3, err3 = base.gh_put_json(
        base.STATUS_PATH,
        status,
        "V11.2 Autopilot: status com Paper Trading",
    )
    if not ok3:
        errors.append("Salvar status Paper: " + err3)

    return bool(ok and ok2 and ok3), summary, errors


def main() -> int:
    # Instala economia de API da V11.1 e roda o motor principal.
    quota.install_quota_guard()
    rc = base.main()

    paper_ok, summary, paper_errors = _paper_cycle()
    print(json.dumps({
        "paper_trading_v112": summary,
        "paper_ok": paper_ok,
        "paper_errors": paper_errors,
    }, ensure_ascii=False, indent=2, default=str))

    # Mantém os códigos estruturais do Autopilot base. Erros de dados Paper ficam
    # visíveis no status, mas não derrubam o pipeline inteiro.
    return int(rc)


if __name__ == "__main__":
    raise SystemExit(main())
