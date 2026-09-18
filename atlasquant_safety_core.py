"""AtlasQuant Safety Core.

Independent, fail-closed veto layer. It never manufactures a market direction
and never increases a model score. It can only permit, warn, wait or block.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math


@dataclass(frozen=True)
class SafetyInput:
    data_quality: float | None
    data_fresh: bool | None
    essential_sources_ok: bool | None
    source_conflict: bool = False
    major_event_minutes: float | None = None
    update_health_ok: bool | None = True
    regime_supported: bool | None = True
    model_conflict: bool = False
    technical_ready: bool | None = None
    lookahead_risk: bool = False
    extra_hard_blocks: tuple[str, ...] = field(default_factory=tuple)


def _finite(v) -> bool:
    try:
        return math.isfinite(float(v))
    except Exception:
        return False


def evaluate_safety(inp: SafetyInput, *, min_data_quality: float = 75.0,
                    major_event_buffer_min: float = 15.0) -> dict[str, object]:
    hard: list[str] = []
    warnings: list[str] = []

    if inp.data_quality is None or not _finite(inp.data_quality):
        hard.append("Qualidade dos dados indisponível")
    elif float(inp.data_quality) < float(min_data_quality):
        hard.append(f"Qualidade dos dados abaixo do mínimo ({float(inp.data_quality):.1f})")
    if inp.data_fresh is not True:
        hard.append("Dados essenciais antigos ou sem confirmação de frescor")
    if inp.essential_sources_ok is not True:
        hard.append("Fonte essencial indisponível ou sem confirmação")
    if inp.source_conflict:
        hard.append("Fontes críticas discordam entre si")
    if inp.update_health_ok is not True:
        hard.append("Versão/health check do sistema não está saudável")
    if inp.lookahead_risk:
        hard.append("Risco de look-ahead / informação futura detectado")
    if inp.major_event_minutes is not None:
        if not _finite(inp.major_event_minutes):
            hard.append("Janela de evento de alto impacto inválida")
        else:
            minutes = float(inp.major_event_minutes)
            if minutes < 0:
                hard.append("Janela de evento de alto impacto inválida")
            elif minutes <= float(major_event_buffer_min):
                hard.append(f"Evento de alto impacto em {minutes:.0f} min")
    if inp.regime_supported is False:
        warnings.append("Regime atual fora/na borda da amostra validada")
    if inp.model_conflict:
        warnings.append("Conflito material entre módulos independentes")
    if inp.technical_ready is False:
        warnings.append("Direção pode existir, mas o timing técnico ainda não confirmou")
    hard.extend(str(x) for x in inp.extra_hard_blocks if str(x).strip())

    blocked = bool(hard)
    if blocked:
        light = "RED"
        state = "NO_TRADE"
        action = "NÃO OPERAR"
    elif warnings:
        light = "YELLOW"
        state = "WAIT_CONFIRMATION"
        action = "AGUARDAR CONFIRMAÇÃO"
    else:
        light = "GREEN"
        state = "SEARCH_ENTRY"
        action = "PROCURAR ENTRADA"
    return {
        "blocked": blocked,
        "traffic_light": light,
        "state": state,
        "action": action,
        "hard_blocks": hard,
        "warnings": warnings,
    }
