"""Explicação auditável dos bloqueios do AtlasQuant Trader (LAB).

O módulo resume SOMENTE evidência de viés W1/D1/H4/M15. Alinhamento
não prova notícia, macro, execução, gatilho ICT/SMC, risco ou retorno.
Nunca autoriza operação e não consulta rede nem serviços externos.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from atlasquant_trader_bias_matrix import TIMEFRAMES, read_bias_matrix

FRAME_NAME = {"W1": "Semanal", "D1": "Diário", "H4": "H4", "M15": "M15"}
CONFLICT_REASONS = {
    "SEM_DIREÇÃO": "Sem direção definida no semanal ou diário.",
    "CONFLITO_W1_D1": "O viés semanal diverge do viés diário.",
    "H4_CONTRÁRIO": "O H4 não confirma a direção semanal e diária.",
    "M15_SEM_CONFIRMAÇÃO": "O M15 não confirmou a direção predominante.",
}
MISSING_CHECKS = (
    "Contexto macroeconômico ainda não confirmado por evidência.",
    "Gatilho técnico e invalidação não certificados pelo Radar.",
    "Gestão de risco e autorização operacional não comprovadas.",
)


def diagnose_trader_bias(payload: Any, *, now: datetime | None = None) -> dict[str, Any]:
    """Fail closed, including when all four directional horizons align."""
    matrix = read_bias_matrix(payload, now=now)
    rows = {}
    counts = {"SEM_DADOS": 0, "SEM_DIREÇÃO": 0,
              "CONFLITO_W1_D1": 0, "H4_CONTRÁRIO": 0,
              "M15_SEM_CONFIRMAÇÃO": 0, "ALINHADO": 0}
    for pair, row in matrix["rows"].items():
        status = row["status"]
        if status == "SEM_DADOS":
            missing = [FRAME_NAME[tf] for tf in TIMEFRAMES if row["timeframes"][tf] is None]
            reason = ("Faltam leituras recentes e válidas: " + ", ".join(missing) + "."
                      if missing else "Os dados não foram confirmados.")
        elif status == "ALINHADO":
            reason = ("Os quatro horizontes estão alinhados, mas isso é apenas "
                      "um filtro de direção; ainda faltam macro, gatilho e risco.")
        else:
            reason = CONFLICT_REASONS[status]
        counts[status] += 1
        rows[pair] = {
            "direction_filter": row["bias"],
            "status": status,
            "why_not": reason,
            "entry_authorized": False,
        }
    coverage = matrix["validated_pairs"]
    return {
        "schema": "ATLASQUANT_TRADER_WHY_NOT_V1",
        "state": matrix["state"],
        "total_pairs": matrix["total_pairs"],
        "complete_pairs": coverage,
        "aligned_pairs": counts["ALINHADO"],
        "blocked_pairs": len(rows),
        "rows": rows, "status_counts": counts,
        "reported_source": matrix["source"],
        "snapshot_utc": matrix["as_of"],
        "provider_authenticated": False,
        "macro_confirmed": False, "technical_trigger_confirmed": False,
        "risk_authorized": False, "entry_authorized": False,
        "checks_outstanding": list(MISSING_CHECKS),
        "summary": ("Nenhum par possui os quatro horizontes completos e recentes."
                    if coverage == 0 else
                    f"{coverage} de {matrix['total_pairs']} pares com quatro horizontes; "
                    f"{counts['ALINHADO']} alinhados apenas para estudo."),
        "notice": "Alinhamento não é taxa de acerto, previsão ou sinal de entrada.",
    }


__all__ = ["diagnose_trader_bias", "FRAME_NAME", "MISSING_CHECKS"]
