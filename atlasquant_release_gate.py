"""Fail-closed release gate for AtlasQuant/AION.

Combines only evidence already available to the running app. The gate does not
query GitHub, trigger Render, deploy code, change permissions or enable trading.
It separates source identity, critical-interface validation, runtime/main
alignment and explicit production verification.
"""
from __future__ import annotations

from typing import Any, Mapping

SCHEMA = "ATLASQUANT_AION_RELEASE_GATE_V1"


def _text(value: Any, limit: int = 240) -> str:
    return str(value or "").strip()[:limit]


def _stage(
    stage_id: str,
    label: str,
    state: str,
    evidence: str,
    next_action: str,
) -> dict[str, str]:
    normalized = str(state or "UNKNOWN").upper()
    if normalized not in {"CONFIRMED", "PENDING", "BLOCKED", "UNKNOWN"}:
        normalized = "UNKNOWN"
    return {
        "id": stage_id,
        "label": label,
        "state": normalized,
        "evidence": _text(evidence, 500),
        "next_action": _text(next_action, 500),
    }


def release_gate(
    *,
    publication_truth: Mapping[str, Any] | None = None,
    interface_validation: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    publication = dict(publication_truth or {})
    validation = dict(interface_validation or {})

    source_build = _text(publication.get("source_build"), 80)
    source_state = "CONFIRMED" if source_build else "UNKNOWN"
    source = _stage(
        "source",
        "Código / bundle",
        source_state,
        (
            f"Bundle identificado: {source_build}."
            if source_build
            else "Nenhuma identidade de bundle foi confirmada nesta execução."
        ),
        (
            "Manter a identidade do bundle como evidência desta execução."
            if source_build
            else "Identificar o bundle em execução antes de avançar no gate."
        ),
    )

    validation_state = str(validation.get("state") or "UNKNOWN").upper()
    validation_complete = bool(
        validation.get("all_confirmed_current_build", False)
    )
    validation_failed = int(validation.get("failed") or 0)
    confirmed = int(validation.get("confirmed") or 0)
    total = int(validation.get("total") or 3)

    if validation_failed > 0 or validation_state == "ATTENTION":
        interface_state = "BLOCKED"
    elif validation_complete:
        interface_state = "CONFIRMED"
    elif source_build:
        interface_state = "PENDING"
    else:
        interface_state = "UNKNOWN"

    interface = _stage(
        "critical_interface",
        "Telas críticas",
        interface_state,
        f"{confirmed}/{total} telas críticas confirmadas no build atual.",
        (
            str(validation.get("next_action") or "Revalidar a próxima tela crítica no build atual.")
            if interface_state != "CONFIRMED"
            else "As telas críticas deste build já têm evidência suficiente nesta sessão."
        ),
    )

    main_match = str(publication.get("main_match") or "UNKNOWN").upper()
    if main_match == "MATCH":
        main_state = "CONFIRMED"
    elif main_match == "MISMATCH":
        main_state = "BLOCKED"
    elif source_build:
        main_state = "PENDING"
    else:
        main_state = "UNKNOWN"

    runtime_sha = _text(publication.get("runtime_commit"), 64)
    expected_sha = _text(publication.get("expected_main_commit"), 64)
    main_alignment = _stage(
        "main_alignment",
        "Runtime × main",
        main_state,
        (
            f"Runtime {runtime_sha[:8] or '—'} · main esperada {expected_sha[:8] or '—'} · "
            f"comparação {main_match}."
        ),
        (
            str(publication.get("next_action") or "Confirmar a identidade do runtime e da main.")
            if main_state != "CONFIRMED"
            else "Runtime e main esperada possuem a mesma identidade confirmada."
        ),
    )

    production_verification = str(
        publication.get("production_verification") or "UNKNOWN"
    ).upper()
    can_claim_live = bool(
        publication.get("can_claim_latest_main_live", False)
    )
    if production_verification == "MISMATCH":
        production_state = "BLOCKED"
    elif production_verification == "VERIFIED" and can_claim_live:
        production_state = "CONFIRMED"
    elif source_build:
        production_state = "PENDING"
    else:
        production_state = "UNKNOWN"

    production = _stage(
        "production",
        "Produção / Render",
        production_state,
        f"Validação explícita de produção: {production_verification}.",
        (
            "Produção possui prova explícita compatível com o runtime/main."
            if production_state == "CONFIRMED"
            else "Validar a versão realmente servida em produção antes de declarar o deploy concluído."
        ),
    )

    stages = [source, interface, main_alignment, production]
    blocked = [x for x in stages if x["state"] == "BLOCKED"]
    unknown = [x for x in stages if x["state"] == "UNKNOWN"]
    pending = [x for x in stages if x["state"] == "PENDING"]
    confirmed_count = sum(1 for x in stages if x["state"] == "CONFIRMED")

    if blocked:
        state = "BLOCKED"
        next_stage = blocked[0]
    elif unknown:
        state = "UNKNOWN"
        next_stage = unknown[0]
    elif pending:
        if interface["state"] != "CONFIRMED":
            state = "VALIDATE_BUILD"
            next_stage = interface
        elif main_alignment["state"] != "CONFIRMED":
            state = "CONFIRM_MAIN"
            next_stage = main_alignment
        else:
            state = "VERIFY_PRODUCTION"
            next_stage = production
    else:
        state = "COMPLETE"
        next_stage = {}

    progress_pct = round((confirmed_count / len(stages)) * 100.0, 1)
    release_claim_allowed = bool(
        state == "COMPLETE"
        and all(x["state"] == "CONFIRMED" for x in stages)
    )

    return {
        "schema": SCHEMA,
        "state": state,
        "truth_state": "CONFIRMED" if source_build else "UNKNOWN",
        "stages": stages,
        "confirmed_stages": confirmed_count,
        "total_stages": len(stages),
        "progress_pct": progress_pct,
        "next_stage": str(next_stage.get("id") or ""),
        "next_label": str(next_stage.get("label") or ""),
        "next_action": str(next_stage.get("next_action") or ""),
        "has_blocker": bool(blocked),
        "release_claim_allowed": release_claim_allowed,
        "latest_main_live_claim_allowed": bool(
            release_claim_allowed and can_claim_live
        ),
        "deployment_action_allowed": False,
        "automatic_deploy": False,
        "automatic_repair": False,
        "real_orders_enabled": False,
    }


def release_gate_rows(snapshot: Mapping[str, Any] | None) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for stage in list((snapshot or {}).get("stages", []) or []):
        if not isinstance(stage, Mapping):
            continue
        rows.append({
            "Etapa": str(stage.get("label") or ""),
            "Estado": str(stage.get("state") or "UNKNOWN"),
            "Evidência": str(stage.get("evidence") or ""),
            "Próxima ação": str(stage.get("next_action") or ""),
        })
    return rows


__all__ = ["SCHEMA", "release_gate", "release_gate_rows"]
