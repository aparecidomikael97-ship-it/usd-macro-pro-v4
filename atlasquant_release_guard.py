"""AtlasQuant update/release guardrails.

The module evaluates evidence for staging/promotion and supports automatic
rollback decisions. Core model changes remain manual-promotion by design.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReleaseEvidence:
    tests_total: int
    tests_failed: int
    critical_regressions: int
    compile_ok: bool
    health_check_ok: bool
    shadow_samples: int = 0
    shadow_critical_mismatches: int = 0
    data_migrations_ok: bool = True


def assess_release(ev: ReleaseEvidence, *, min_tests: int = 1,
                   min_shadow_samples_for_core: int = 100,
                   core_model_change: bool = False) -> dict[str, object]:
    hard: list[str] = []
    pending: list[str] = []
    if ev.tests_total < min_tests:
        hard.append("Cobertura de testes insuficiente")
    if ev.tests_failed:
        hard.append(f"{ev.tests_failed} teste(s) falharam")
    if ev.critical_regressions:
        hard.append(f"{ev.critical_regressions} regressão(ões) crítica(s)")
    if not ev.compile_ok:
        hard.append("Compilação/sintaxe falhou")
    if not ev.health_check_ok:
        hard.append("Health check falhou")
    if not ev.data_migrations_ok:
        hard.append("Migração/compatibilidade de dados falhou")
    if ev.shadow_critical_mismatches:
        hard.append("Shadow mode detectou divergência crítica")
    if core_model_change and ev.shadow_samples < min_shadow_samples_for_core:
        pending.append(f"Shadow Mode precisa de pelo menos {min_shadow_samples_for_core} amostras")

    staging_ok = not hard
    promotion_ready = staging_ok and not pending
    return {
        "staging_ok": staging_ok,
        "eligible_for_manual_promotion": promotion_ready,
        "automatic_core_promotion": False,
        "hard_blocks": hard,
        "pending": pending,
    }


def should_rollback(*, app_boot_ok: bool, health_check_ok: bool,
                    critical_engine_error: bool = False,
                    data_integrity_breach: bool = False,
                    error_rate_pct: float = 0.0, max_error_rate_pct: float = 5.0) -> dict[str, object]:
    reasons = []
    if not app_boot_ok:
        reasons.append("Aplicação não inicializou")
    if not health_check_ok:
        reasons.append("Health check pós-deploy falhou")
    if critical_engine_error:
        reasons.append("Erro crítico no motor")
    if data_integrity_breach:
        reasons.append("Violação de integridade dos dados")
    if float(error_rate_pct) > float(max_error_rate_pct):
        reasons.append("Taxa de erros acima do limite")
    return {"rollback": bool(reasons), "reasons": reasons}
