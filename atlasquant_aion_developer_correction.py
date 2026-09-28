"""Evidence-linked correction planning for AION Developer.

Builds a bounded correction proposal from a Developer Intelligence snapshot,
an evidence-grounded diagnostic and an existing human-gated developer package.

The proposal is planning metadata only. It never edits code, generates a patch,
executes tests, calls a process or network, persists state, commits, merges,
deploys or promotes a release. Diagnostic hypotheses remain UNKNOWN until
separate evidence confirms a root cause.
"""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Mapping

from atlasquant_aion_developer_diagnostics import SCHEMA as DIAGNOSTIC_SCHEMA
from atlasquant_aion_developer_engine import ADVERSARIAL_CHECKS
from atlasquant_aion_developer_intelligence import (
    SCHEMA as INTELLIGENCE_SCHEMA,
    validate_snapshot_integrity,
)
from atlasquant_aion_developer_package import SCHEMA as PACKAGE_SCHEMA
from atlasquant_aion_observability import redact_text

SCHEMA = "ATLASQUANT_AION_DEVELOPER_CORRECTION_PLAN_V1"
MAX_TARGET_FILES = 24
MAX_TEST_CANDIDATES = 80

_OBJECTIVES = {
    "AssertionError": (
        "Reconciliar o comportamento observado com o contrato exercitado pelo teste, "
        "sem ampliar autoridade nem mascarar a asserção."
    ),
    "TypeError": (
        "Restaurar compatibilidade de tipos/assinaturas no menor escopo possível "
        "e provar o contrato com teste dirigido."
    ),
    "AttributeError": (
        "Restaurar a interface esperada ou ajustar o consumidor com evidência de contrato."
    ),
    "ImportError": (
        "Restaurar compatibilidade de import/dependência sem introduzir carregamento dinâmico."
    ),
    "ModuleNotFoundError": (
        "Restaurar resolução de módulo/dependência com mudança mínima e teste reproduzível."
    ),
    "SyntaxError": (
        "Corrigir apenas a estrutura sintática confirmada antes de avaliar comportamento."
    ),
    "IndentationError": (
        "Corrigir apenas a estrutura sintática confirmada antes de avaliar comportamento."
    ),
    "KeyError": (
        "Reconciliar o formato de dados/chave esperado com validação de fronteira."
    ),
    "IndexError": (
        "Reconciliar limites/forma dos dados com validação explícita de fronteira."
    ),
}


def _clean(value: Any, limit: int = 1200) -> str:
    return " ".join(redact_text(value).replace("\x00", "").split())[:limit]


def _digest(value: Any, length: int = 18) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )
    return sha256(raw.encode("utf-8")).hexdigest()[:length].upper()


def _snapshot_rows(snapshot: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("path") or ""): dict(row)
        for row in list(snapshot.get("files") or [])
        if isinstance(row, Mapping) and str(row.get("path") or "")
    }


def _validate_inputs(
    snapshot: Mapping[str, Any],
    diagnostic: Mapping[str, Any],
    package: Mapping[str, Any],
) -> str:
    if snapshot.get("schema") != INTELLIGENCE_SCHEMA:
        raise ValueError("invalid Developer Intelligence snapshot")
    snapshot_digest = str(snapshot.get("snapshot_digest") or "")
    if not snapshot_digest:
        raise ValueError("snapshot digest required")
    validate_snapshot_integrity(snapshot)

    unsafe_snapshot = (
        bool(snapshot.get("content_included"))
        or bool(snapshot.get("executes_repository_code"))
        or bool(snapshot.get("writes_files"))
        or bool(snapshot.get("network_called"))
        or bool(snapshot.get("subprocess_called"))
    )
    if unsafe_snapshot:
        raise ValueError("unsafe repository snapshot")

    if diagnostic.get("schema") != DIAGNOSTIC_SCHEMA:
        raise ValueError("invalid developer diagnostic")
    if diagnostic.get("state") != "FAILURE_EVIDENCE":
        raise ValueError("diagnostic must contain failure evidence")
    if bool(diagnostic.get("cause_confirmed")):
        raise ValueError("correction planner expects unconfirmed root cause")
    if str(diagnostic.get("cause_truth_status") or "").upper() != "UNKNOWN":
        raise ValueError("diagnostic root cause truth must remain UNKNOWN")
    if str(diagnostic.get("snapshot_digest") or "") != snapshot_digest:
        raise ValueError("diagnostic snapshot lineage mismatch")

    if package.get("schema") != PACKAGE_SCHEMA:
        raise ValueError("invalid developer package")
    if str(package.get("state") or "") != "WAITING_HUMAN":
        raise ValueError("developer package must remain WAITING_HUMAN")
    plan = package.get("plan") if isinstance(package.get("plan"), Mapping) else {}
    if str(plan.get("snapshot_digest") or "") != snapshot_digest:
        raise ValueError("developer package snapshot lineage mismatch")

    if bool(package.get("automatic_edit")) or bool(package.get("automatic_commit")):
        raise ValueError("unsafe developer package authority")
    if bool(package.get("automatic_merge")) or bool(package.get("automatic_deploy")):
        raise ValueError("unsafe developer package release authority")
    if bool(package.get("production_change_allowed")) or bool(package.get("real_trading_enabled")):
        raise ValueError("unsafe developer package production authority")
    return snapshot_digest


def _ordered_unique(values: list[str], limit: int) -> list[str]:
    out: list[str] = []
    for raw in values:
        text = _clean(raw, 500)
        if text and text not in out:
            out.append(text)
        if len(out) >= limit:
            break
    return out


def build_correction_plan(
    snapshot: Mapping[str, Any],
    diagnostic: Mapping[str, Any],
    package: Mapping[str, Any],
) -> dict[str, Any]:
    """Create a human-gated correction plan from same-snapshot evidence."""
    snapshot_digest = _validate_inputs(snapshot, diagnostic, package)
    rows = _snapshot_rows(snapshot)
    package_plan = package.get("plan") if isinstance(package.get("plan"), Mapping) else {}
    strategy = (
        package.get("test_strategy")
        if isinstance(package.get("test_strategy"), Mapping)
        else {}
    )

    requested_targets = [
        str(x) for x in list(diagnostic.get("affected_files") or [])
    ] + [
        str(x) for x in list(package_plan.get("impacted_files") or [])
    ]
    target_files = _ordered_unique(
        [path for path in requested_targets if path in rows],
        MAX_TARGET_FILES,
    )
    if not target_files:
        raise ValueError("no repository target file linked to evidence")

    risk_tags = sorted({
        str(tag)
        for path in target_files
        for tag in list(rows[path].get("risk_tags") or [])
        if str(tag)
    })
    test_candidates = _ordered_unique(
        [str(x) for x in list(diagnostic.get("recommended_tests") or [])]
        + [str(x) for x in list(strategy.get("required_test_candidates") or [])],
        MAX_TEST_CANDIDATES,
    )

    hypotheses = []
    for item in list(diagnostic.get("hypotheses") or []):
        if not isinstance(item, Mapping):
            continue
        if str(item.get("truth_status") or "").upper() != "UNKNOWN":
            raise ValueError("diagnostic hypothesis must remain UNKNOWN")
        hypotheses.append({
            "label": _clean(item.get("label"), 120),
            "truth_status": "UNKNOWN",
            "rationale": _clean(item.get("rationale"), 700),
        })
    if not hypotheses:
        hypotheses = [{
            "label": "CAUSE_NOT_YET_CONFIRMED",
            "truth_status": "UNKNOWN",
            "rationale": "A evidência confirma a falha, não a causa raiz.",
        }]

    exception_type = _clean(diagnostic.get("exception_type"), 120) or "UNKNOWN_FAILURE"
    objective = _OBJECTIVES.get(
        exception_type,
        "Produzir a menor mudança possível que explique a falha reproduzida, "
        "preservando contratos existentes e exigindo evidência antes de concluir causa raiz.",
    )

    evidence_required = [
        "REPRODUCIBLE_FAILING_TEST_OR_EQUIVALENT",
        "BEFORE_AFTER_EVIDENCE",
        "TARGETED_TEST_PASS",
        "RISK_REGRESSION_TESTS_PASS",
        "INDEPENDENT_REVIEW_EVIDENCE",
        "INDEPENDENT_BREAKER_EVIDENCE",
        "ROLLBACK_PLAN_RECORDED",
    ]

    correction_seed = {
        "snapshot_digest": snapshot_digest,
        "diagnostic_id": diagnostic.get("diagnostic_id"),
        "package_id": package.get("package_id"),
        "targets": target_files,
        "tests": test_candidates,
    }
    correction_id = "DEVCORR-" + _digest(correction_seed)

    builder_packet = {
        "role": "BUILDER",
        "state": "WAITING_HUMAN_ASSIGNMENT",
        "objective": objective,
        "allowed_scope": target_files,
        "test_candidates": test_candidates,
        "hypotheses": hypotheses,
        "constraints": [
            "Não declarar causa raiz sem evidência de reprodução.",
            "Não ampliar autoridade, scopes ou efeitos externos.",
            "Preferir mudança mínima dentro do escopo alvo.",
            "Não alterar produção, deploy, billing ou trading real.",
            "Não remover teste para transformar falha em sucesso.",
        ],
        "evidence_required": evidence_required[:4],
        "executes_action": False,
    }

    reviewer_packet = {
        "role": "REVIEWER",
        "state": "INDEPENDENT_REVIEW_REQUIRED",
        "must_be_independent_from_builder": True,
        "checks": [
            "A mudança permanece no escopo autorizado.",
            "A causa declarada é sustentada por evidência, não inferência.",
            "Os testes dirigidos e de risco cobrem a alteração.",
            "Nenhuma proteção, Guardian ou gate foi contornado.",
            "Rollback está definido antes de release review.",
        ],
        "evidence_required": evidence_required[1:6],
        "executes_action": False,
    }

    breaker_packet = {
        "role": "BREAKER",
        "state": "INDEPENDENT_BREAKER_REQUIRED",
        "must_be_independent_from_builder_and_reviewer": True,
        "checks": list(ADVERSARIAL_CHECKS),
        "focus_risks": risk_tags,
        "evidence_required": [
            "ADVERSARIAL_FINDINGS",
            "CRITICAL_FINDINGS_RESOLVED_OR_BLOCKED",
        ],
        "executes_action": False,
    }

    gaps = []
    if not test_candidates:
        gaps.append("NO_TEST_CANDIDATES")
    if diagnostic.get("unmatched_code"):
        gaps.append("DIAGNOSTIC_UNMATCHED_CODE")
    if package.get("gaps"):
        gaps.extend(str(x) for x in list(package.get("gaps") or []))
    gaps = _ordered_unique(gaps, 30)

    return {
        "schema": SCHEMA,
        "correction_id": correction_id,
        "state": "WAITING_HUMAN",
        "lineage": {
            "snapshot_digest": snapshot_digest,
            "diagnostic_id": str(diagnostic.get("diagnostic_id") or ""),
            "diagnostic_log_digest": str(diagnostic.get("log_digest") or ""),
            "package_id": str(package.get("package_id") or ""),
            "developer_workflow_id": str(
                (
                    package.get("developer_workflow")
                    if isinstance(package.get("developer_workflow"), Mapping)
                    else {}
                ).get("workflow_id") or ""
            ),
        },
        "exception_type": exception_type,
        "objective": objective,
        "target_files": target_files,
        "risk_tags": risk_tags,
        "test_candidates": test_candidates,
        "hypotheses": hypotheses,
        "evidence_required": evidence_required,
        "gaps": gaps,
        "builder_packet": builder_packet,
        "reviewer_packet": reviewer_packet,
        "breaker_packet": breaker_packet,
        "rollback": {
            "state": "REQUIRED",
            "plan": "",
            "must_exist_before_release_review": True,
        },
        "root_cause_confirmed": False,
        "root_cause_truth_status": "UNKNOWN",
        "patch_generated": False,
        "analysis_only": True,
        "persists_checkpoint": False,
        "executes_repository_code": False,
        "runs_tests": False,
        "writes_files": False,
        "network_called": False,
        "subprocess_called": False,
        "automatic_fix": False,
        "automatic_commit": False,
        "automatic_merge": False,
        "automatic_deploy": False,
        "production_change_allowed": False,
        "real_trading_enabled": False,
        "tool_output_is_authority": False,
    }


__all__ = [
    "SCHEMA",
    "MAX_TARGET_FILES",
    "MAX_TEST_CANDIDATES",
    "build_correction_plan",
]
