"""AtlasQuant update/release guardrails.

The module evaluates evidence for staging/promotion and supports automatic
rollback decisions. Core model changes remain manual-promotion by design.
"""
from __future__ import annotations

from dataclasses import dataclass
import math


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
    private_access_required: bool = False
    access_config_ok: bool = True


def _valid_bool(value: object) -> bool:
    return isinstance(value,bool)


def _valid_count(value: object) -> bool:
    if isinstance(value,bool):
        return False
    try:
        x=float(value)
        return math.isfinite(x) and x >= 0 and x.is_integer()
    except Exception:
        return False


def assess_release(ev: ReleaseEvidence, *, min_tests: int = 1,
                   min_shadow_samples_for_core: int = 100,
                   core_model_change: bool = False) -> dict[str, object]:
    hard: list[str] = []
    pending: list[str] = []
    count_fields=(("tests_total",ev.tests_total),("tests_failed",ev.tests_failed),("critical_regressions",ev.critical_regressions),("shadow_samples",ev.shadow_samples),("shadow_critical_mismatches",ev.shadow_critical_mismatches))
    invalid_counts=[name for name,value in count_fields if not _valid_count(value)]
    if invalid_counts:
        hard.append("Contagens de release inválidas: "+", ".join(invalid_counts))
    if not _valid_count(min_tests) or int(min_tests)<1:
        hard.append("Limite mínimo de testes inválido")
    if not _valid_count(min_shadow_samples_for_core) or int(min_shadow_samples_for_core)<1:
        hard.append("Limite mínimo de Shadow inválido")
    bool_fields=(
        ("compile_ok",ev.compile_ok),
        ("health_check_ok",ev.health_check_ok),
        ("data_migrations_ok",ev.data_migrations_ok),
        ("private_access_required",ev.private_access_required),
        ("access_config_ok",ev.access_config_ok),
    )
    invalid_bools=[name for name,value in bool_fields if not _valid_bool(value)]
    if invalid_bools:
        hard.append("Flags de release inválidas: "+", ".join(invalid_bools))
    if _valid_count(ev.tests_total) and _valid_count(min_tests) and ev.tests_total < min_tests:
        hard.append("Cobertura de testes insuficiente")
    if _valid_count(ev.tests_failed) and ev.tests_failed:
        hard.append(f"{ev.tests_failed} teste(s) falharam")
    if _valid_count(ev.critical_regressions) and ev.critical_regressions:
        hard.append(f"{ev.critical_regressions} regressão(ões) crítica(s)")
    if _valid_bool(ev.compile_ok) and not ev.compile_ok:
        hard.append("Compilação/sintaxe falhou")
    if _valid_bool(ev.health_check_ok) and not ev.health_check_ok:
        hard.append("Health check falhou")
    if _valid_bool(ev.data_migrations_ok) and not ev.data_migrations_ok:
        hard.append("Migração/compatibilidade de dados falhou")
    if _valid_bool(ev.private_access_required) and ev.private_access_required:
        if not _valid_bool(ev.access_config_ok) or not ev.access_config_ok:
            hard.append("Acesso privado obrigatório sem configuração válida")
    if _valid_count(ev.shadow_critical_mismatches) and ev.shadow_critical_mismatches:
        hard.append("Shadow mode detectou divergência crítica")
    if core_model_change and _valid_count(ev.shadow_samples) and _valid_count(min_shadow_samples_for_core) and ev.shadow_samples < min_shadow_samples_for_core:
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
    bool_inputs=(
        ("app_boot_ok",app_boot_ok),
        ("health_check_ok",health_check_ok),
        ("critical_engine_error",critical_engine_error),
        ("data_integrity_breach",data_integrity_breach),
    )
    invalid=[name for name,value in bool_inputs if not isinstance(value,bool)]
    if invalid:
        reasons.append("Flags de rollback inválidas: "+", ".join(invalid))
    try:
        rate=float(error_rate_pct); limit=float(max_error_rate_pct)
        rates_valid=math.isfinite(rate) and math.isfinite(limit) and rate>=0 and limit>=0
    except Exception:
        rates_valid=False
        rate=limit=0.0
    if not rates_valid:
        reasons.append("Taxa/limite de erros inválido")
    if not app_boot_ok:
        reasons.append("Aplicação não inicializou")
    if not health_check_ok:
        reasons.append("Health check pós-deploy falhou")
    if critical_engine_error:
        reasons.append("Erro crítico no motor")
    if data_integrity_breach:
        reasons.append("Violação de integridade dos dados")
    if rates_valid and rate > limit:
        reasons.append("Taxa de erros acima do limite")
    return {"rollback": bool(reasons), "reasons": reasons}
