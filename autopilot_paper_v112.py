"""AtlasQuant V11.2 — Autopilot + Paper Trading.

Executa o Autopilot V11.1 (quota saver) e, sem consumir chamadas adicionais
da Twelve Data, reutiliza o cache M15 persistido para simular entradas somente
quando o checklist operacional completo estiver liberado.

V11.6 acrescenta uma camada analítica de custos conservadores ao diário Paper.
Ela não altera sinal, entrada, stop, alvo, resultado bruto ou classificação
WIN/LOSS; apenas registra spread/slippage e calcula o R líquido auditável.
"""
from __future__ import annotations

import json

import pandas as pd

import autopilot_v107 as base
import autopilot_quota_guard_v111 as quota
import autopilot_model_paper_v1 as model_paper
from paper_friction_v116 import apply_paper_friction, summarize_net
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

    # V11.6: reaplica a fricção a cada ciclo. O motor V11.2 normaliza apenas suas
    # colunas-base, então esta etapa garante que os campos de custo permaneçam
    # reproduzíveis sem contaminar a lógica de execução simulada.
    costed = apply_paper_friction(updated)

    ok, err = base.gh_put_csv(
        PAPER_CSV_PATH,
        costed,
        "V11.6 Paper Trading: atualiza diário simulado com custos",
    )
    if not ok:
        errors.append("Salvar Paper diário: " + err)

    summary = summarize_paper_trades(updated)
    friction = summarize_net(costed)
    summary["last_cycle"] = cycle
    summary["friction_v116"] = friction
    summary["gross_r_before_friction"] = friction.get("gross_r", 0.0)
    summary["friction_r"] = friction.get("friction_r", 0.0)
    summary["net_r_after_friction"] = friction.get("net_r", 0.0)
    summary["safety"] = {
        "real_orders": False,
        "broker_connection": False,
        "entry_rule": "Decision Integrity executável + zero hard/soft blocks",
        "entry_timing": "OPEN do primeiro M15 posterior ao sinal",
        "stop_model": "1.0 ATR M15 pré-entrada",
        "target_model": "2R",
        "same_candle_stop_and_target": "LOSS conservador",
        "max_hold": "96 candles M15 / 24h",
        "friction_model": "V11.6 fixed conservative research friction",
        "friction_changes_signal": False,
        "friction_changes_result_classification": False,
    }

    ok2, err2 = base.gh_put_json(
        PAPER_SUMMARY_PATH,
        summary,
        "V11.6 Paper Trading: resumo bruto e líquido após custos",
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
        # Mantém o campo legado por compatibilidade e expõe explicitamente o
        # líquido após fricção para painéis/validação novos.
        "net_r": summary.get("net_r", 0.0),
        "gross_r_before_friction": friction.get("gross_r", 0.0),
        "friction_r": friction.get("friction_r", 0.0),
        "net_r_after_friction": friction.get("net_r", 0.0),
        "friction_version": friction.get("version"),
        "avg_r": summary.get("avg_r", 0.0),
        "profit_factor_r": summary.get("profit_factor_r"),
        "profit_factor_net_r": friction.get("profit_factor_net_r"),
        "last_cycle": cycle,
        "errors": errors[:10],
    }
    existing_errors = list(status.get("errors", []) or [])
    status["errors"] = (existing_errors + errors)[:20]
    ok3, err3 = base.gh_put_json(
        base.STATUS_PATH,
        status,
        "V11.6 Autopilot: status com custos do Paper Trading",
    )
    if not ok3:
        errors.append("Salvar status Paper: " + err3)

    return bool(ok and ok2 and ok3), summary, errors


def main() -> int:
    # Instala economia de API da V11.1 e roda o motor principal.
    quota.install_quota_guard()
    rc = base.main()

    paper_ok, summary, paper_errors = _paper_cycle()
    model_ok, model_summary, model_errors = model_paper._model_paper_cycle()
    print(json.dumps({
        "paper_trading_v112": summary,
        "paper_ok": paper_ok,
        "paper_errors": paper_errors,
        "model_paper_v1": model_summary,
        "model_paper_ok": model_ok,
        "model_paper_errors": model_errors,
    }, ensure_ascii=False, indent=2, default=str))

    # Mantém os códigos estruturais do Autopilot base. Erros de dados Paper ficam
    # visíveis no status, mas não derrubam o pipeline inteiro.
    return int(rc)


if __name__ == "__main__":
    raise SystemExit(main())
