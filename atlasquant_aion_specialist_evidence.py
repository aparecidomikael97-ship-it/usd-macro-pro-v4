"""Read-only local evidence for AION specialists.

Each reader calls an existing pure function. It does not open the network,
load secrets, invent prices, or treat a code contract as a live market fact.
The snapshot never answers the user's question by itself.
"""
from __future__ import annotations

import os
from typing import Any, Mapping

from atlasquant_aion_cognitive_orchestrator import build_research_plan
from atlasquant_aion_core import guardian_decision
from atlasquant_aion_developer_engine import definition_of_done, new_development_workflow
from atlasquant_aion_fortress import emergency_cutoff_posture
from atlasquant_aion_specialists import SPECIALIST_MODULES
from atlasquant_content_pipeline import provider_readiness
from atlasquant_fx_universe import universe_integrity
from atlasquant_lab_matrix import lab_matrix
from atlasquant_macro_briefing import build_macro_briefing
from atlasquant_scanner_queue import scanner_queue

def _approval_inbox(checkpoint):
    from atlasquant_aion_approval_inbox import collect_approval_inbox
    return collect_approval_inbox(checkpoint)


def _business_summary(products):
    from atlasquant_aion_business import business_summary
    return business_summary(products)


def _investment_comparison(products):
    from atlasquant_investment_ecosystem import investment_product_comparison
    return investment_product_comparison(products)


SCHEMA = "ATLASQUANT_AION_SPECIALIST_EVIDENCE_V1"
_FIXED_AT = "2026-09-27T00:00:00+00:00"


def _claim(
    claim: str,
    value: Any,
    *,
    source: str,
    source_ref: str,
    truth: str = "CONFIRMED",
) -> dict[str, Any]:
    return {
        "claim": claim,
        "value": value,
        "truth_state": truth,
        "source": source,
        "source_ref": source_ref,
        "source_tier": "PRIMARY",
        "time_sensitive": False,
    }


def _envelope(
    specialist: str,
    *,
    state: str,
    summary: str,
    observations: Mapping[str, Any],
    claims: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "specialist": specialist,
        "module": SPECIALIST_MODULES.get(specialist, ""),
        "state": state,
        "summary": summary,
        "observations": dict(observations),
        "claims": claims,
        "scope": "LOCAL_CONTRACT",
        "answer_truth": "UNKNOWN",
        "answers_user_question": False,
        "provider_called": False,
        "network_called": False,
        "tool_called": False,
        "executes_action": False,
        "real_orders_enabled": False,
        "invented_values": False,
        "secrets_included": False,
    }


def _market() -> dict[str, Any]:
    universe = universe_integrity()
    queue = scanner_queue({}, now_ts=0.0)
    counts = dict(queue.get("counts") or {})
    return _envelope(
        "market",
        state="LOCAL_CONTRACT",
        summary=(
            f"Contrato do universo Forex: {universe['pair_count']} pares G8 únicos, "
            f"válido={bool(universe['valid'])}. Esta consulta não recebeu leituras "
            f"persistidas, então a fila local marca {counts.get('MISSING', 0)} pares "
            "como MISSING. Isso não é cotação, TOP 10 nem viés. Worker contínuo não "
            "configurado. Ordens reais bloqueadas."
        ),
        observations={
            "pair_count": universe["pair_count"],
            "universe_valid": bool(universe["valid"]),
            "queue_population": queue["population"],
            "missing_without_persisted_input": counts.get("MISSING", 0),
            "fresh_readings": counts.get("FRESH", 0),
            "live_feed_consulted": False,
            "continuous_worker_configured": bool(queue["continuous_worker_configured"]),
            "real_orders_enabled": False,
        },
        claims=[
            _claim(
                "forex_universe_contract",
                f"{universe['pair_count']} pares G8 únicos",
                source="atlasquant_fx_universe.universe_integrity",
                source_ref="OFFICIAL_PAIRS",
            ),
            _claim(
                "live_market_reading",
                "NÃO CONSULTADA",
                source="atlasquant_scanner_queue.scanner_queue",
                source_ref="empty_local_input",
                truth="UNKNOWN",
            ),
        ],
    )


def _macro() -> dict[str, Any]:
    briefing = build_macro_briefing(None, generated_at=_FIXED_AT)
    return _envelope(
        "macro",
        state="NO_LOCAL_INPUT",
        summary=(
            f"Briefing macro sem linhas de moeda, evento ou banco central nesta "
            f"consulta. Estado: {briefing['state']}. Nenhum viés foi estimado."
        ),
        observations={
            "state": briefing["state"],
            "data_sufficient": bool(briefing["data_sufficient"]),
            "currency_rows_supplied": 0,
            "live_calendar_consulted": False,
        },
        claims=[
            _claim(
                "macro_briefing_input",
                briefing["state"],
                source="atlasquant_macro_briefing.build_macro_briefing",
                source_ref="empty_currency_rows",
            ),
            _claim(
                "live_macro_reading",
                "NÃO CONSULTADA",
                source="atlasquant_macro_briefing.build_macro_briefing",
                source_ref="no_upstream_state",
                truth="UNKNOWN",
            ),
        ],
    )


def _ict() -> dict[str, Any]:
    matrix = lab_matrix()
    counts = dict(matrix.get("counts") or {})
    blocked = sorted({
        str(cell.get("setup_id"))
        for cell in list(matrix.get("cells") or [])
        if cell.get("state") == "BLOQUEADO"
    })
    return _envelope(
        "ict",
        state="NO_RECORDED_EVIDENCE",
        summary=(
            "Matriz do laboratório sem registros fornecidos: "
            f"{counts.get('SEM_EVIDENCIA', 0)} células SEM_EVIDENCIA e "
            f"{counts.get('BLOQUEADO', 0)} BLOQUEADO ({', '.join(blocked) or 'nenhum'}). "
            "Nenhum backtest foi executado e nenhuma métrica foi preenchida."
        ),
        observations={
            "counts": counts,
            "blocked_setups": blocked,
            "fabricated_values": bool(matrix.get("fabricated_values")),
            "runs_backtest": bool(matrix.get("runs_backtest")),
            "real_orders_enabled": False,
        },
        claims=[
            _claim(
                "lab_matrix_without_supplied_evidence",
                counts,
                source="atlasquant_lab_matrix.lab_matrix",
                source_ref="empty_evidence_rows",
            ),
        ],
    )


def _risk() -> dict[str, Any]:
    posture = emergency_cutoff_posture()
    return _envelope(
        "risk",
        state="POSTURE_ONLY",
        summary=(
            f"Postura de corte: {posture['state']}, porque a integridade de política "
            "e permissão não foi comprovada nesta consulta. Corte automático desligado. "
            "Ordens reais bloqueadas. Isto é postura, não um incidente confirmado."
        ),
        observations={
            "posture": posture["state"],
            "reasons": list(posture.get("reasons") or []),
            "automatic_cutoff": bool(posture["automatic_cutoff"]),
            "incident_confirmed": False,
            "real_orders_enabled": False,
        },
        claims=[
            _claim(
                "sensitive_tool_posture",
                posture["state"],
                source="atlasquant_aion_fortress.emergency_cutoff_posture",
                source_ref="default_unknown_integrity",
            ),
            _claim(
                "confirmed_security_incident",
                "NÃO CONFIRMADO",
                source="atlasquant_aion_fortress.emergency_cutoff_posture",
                source_ref="no_incident_input",
                truth="UNKNOWN",
            ),
        ],
    )


def _lab() -> dict[str, Any]:
    credential_present = bool(os.getenv("GITHUB_TOKEN_HISTORICO") or os.getenv("GITHUB_TOKEN"))
    return _envelope(
        "lab",
        state="NOT_CONSULTED",
        summary=(
            "A evidência remota de pesquisa não foi carregada e a rede não foi chamada. "
            + (
                "Existe variável de credencial no ambiente; o valor não é lido nem registrado."
                if credential_present else
                "Nenhuma credencial de histórico foi detectada no ambiente."
            )
        ),
        observations={
            "remote_store_consulted": False,
            "credential_present": credential_present,
            "records_loaded": 0,
        },
        claims=[
            _claim(
                "research_evidence_remote_load",
                "NOT_CONSULTED",
                source="atlasquant_aion_specialist_evidence",
                source_ref="lab.remote_store",
            ),
        ],
    )


def _invest() -> dict[str, Any]:
    comparison = _investment_comparison(None)
    return _envelope(
        "invest",
        state="NO_OBSERVED_PRODUCTS",
        summary=(
            "Comparador sem produtos observados nesta consulta. "
            f"Estado {comparison['state']}. Recomendação personalizada desligada "
            "e nenhuma rentabilidade foi estimada."
        ),
        observations={
            "state": comparison["state"],
            "rows": len(list(comparison.get("rows") or [])),
            "personalized_recommendation": bool(comparison["personalized_recommendation"]),
            "automatic_orders": bool(comparison["automatic_orders"]),
        },
        claims=[
            _claim(
                "investment_products_in_this_call",
                comparison["state"],
                source="atlasquant_investment_ecosystem.investment_product_comparison",
                source_ref="empty_records",
            ),
        ],
    )


def _business() -> dict[str, Any]:
    summary = _business_summary(None)
    return _envelope(
        "business",
        state="EMPTY_LOCAL_CATALOG",
        summary=(
            "Catálogo de negócios vazio nesta consulta: "
            f"{summary['total']} produtos e {summary['live']} anúncios LIVE. "
            "Publicação, gasto e anúncio não foram executados."
        ),
        observations={
            "total": summary["total"],
            "live": summary["live"],
            "checkpoint_supplied": False,
            "publication_executed": False,
        },
        claims=[
            _claim(
                "business_catalog_in_this_call",
                summary["total"],
                source="atlasquant_aion_business.business_summary",
                source_ref="empty_rows",
            ),
        ],
    )


def _studio() -> dict[str, Any]:
    ready = provider_readiness()
    providers = {
        name: row.get("state")
        for name, row in dict(ready.get("providers") or {}).items()
    }
    return _envelope(
        "studio",
        state="NOT_CONFIGURED",
        summary=(
            "Nenhum provider de transcrição, vídeo, imagem ou voz foi informado: "
            "todos NOT_CONFIGURED. Publicação não configurada e nenhuma mídia foi gerada."
        ),
        observations={
            "providers": providers,
            "publishing_configured": bool(ready["publishing_configured"]),
            "executes_external_call": bool(ready["executes_external_call"]),
        },
        claims=[
            _claim(
                "content_providers_in_this_call",
                "NOT_CONFIGURED",
                source="atlasquant_content_pipeline.provider_readiness",
                source_ref="default_flags_false",
            ),
        ],
    )


def _dev() -> dict[str, Any]:
    workflow = new_development_workflow(
        "leitura local",
        branch="none",
        baseline_ref="none",
        requested_by="aion-local-reader",
        created_at=_FIXED_AT,
    )
    done = definition_of_done(workflow)
    return _envelope(
        "dev",
        state="CONTRACT_ONLY",
        summary=(
            f"Workflow de desenvolvimento de exemplo permanece {done['status']}. "
            "Merge automático, deploy automático e trading real estão desligados. "
            "Release continua em revisão humana."
        ),
        observations={
            "status": done["status"],
            "automatic_merge": bool(done["automatic_merge"]),
            "automatic_deploy": bool(done["automatic_deploy"]),
            "production_change_allowed": bool(done["production_change_allowed"]),
            "real_trading_enabled": bool(done["real_trading_enabled"]),
            "repository_mutated": False,
        },
        claims=[
            _claim(
                "developer_release_gate",
                done["status"],
                source="atlasquant_aion_developer_engine.definition_of_done",
                source_ref="empty_example_workflow",
            ),
        ],
    )


def _research() -> dict[str, Any]:
    plan = build_research_plan("", specialists=[])
    return _envelope(
        "research",
        state="PLAN_ONLY",
        summary=(
            "Plano de pesquisa local preparado sem executar busca. "
            f"Pesquisa web={plan['web_research_executed']}; "
            f"modelo externo={plan['external_model_executed']}; "
            "mercado ao vivo não confirmado."
        ),
        observations={
            "web_research_executed": bool(plan["web_research_executed"]),
            "external_model_executed": bool(plan["external_model_executed"]),
            "market_live_confirmed": bool(plan["market_live_confirmed"]),
            "step_count": len(list(plan.get("steps") or [])),
        },
        claims=[
            _claim(
                "research_execution",
                "NOT_EXECUTED",
                source="atlasquant_aion_cognitive_orchestrator.build_research_plan",
                source_ref="empty_question",
            ),
        ],
    )


def _admin() -> dict[str, Any]:
    inbox = _approval_inbox(None)
    return _envelope(
        "admin",
        state="NO_CHECKPOINT",
        summary=(
            "Inbox calculada sem checkpoint: "
            f"{inbox['total']} pendências nesta consulta. Isso não afirma que a "
            "produção está vazia. Aprovação automática permanece desligada."
        ),
        observations={
            "pending_in_this_call": inbox["total"],
            "checkpoint_supplied": False,
            "automatic_approval": bool(inbox["automatic_approval"]),
            "real_orders_enabled": False,
        },
        claims=[
            _claim(
                "approval_inbox_without_checkpoint",
                inbox["total"],
                source="atlasquant_aion_approval_inbox.collect_approval_inbox",
                source_ref="empty_checkpoint",
            ),
        ],
    )


def _core() -> dict[str, Any]:
    denied = guardian_decision("real_trade", {"role": "ADMIN"}, approved=True)
    return _envelope(
        "core",
        state="GUARDIAN_CONTRACT",
        summary=(
            "Guardian nega real_trade mesmo com papel ADMIN e aprovação explícita. "
            f"Motivo: {denied['reason']} Ordens reais permanecem bloqueadas."
        ),
        observations={
            "real_trade_allowed": bool(denied["allowed"]),
            "risk": denied["risk"],
            "approved_flag_ignored_for_real_trade": True,
            "real_orders_enabled": False,
        },
        claims=[
            _claim(
                "real_trade_guardian",
                "DENIED",
                source="atlasquant_aion_core.guardian_decision",
                source_ref="real_trade",
            ),
        ],
    )


_READERS = {
    "core": _core,
    "dev": _dev,
    "research": _research,
    "market": _market,
    "macro": _macro,
    "ict": _ict,
    "risk": _risk,
    "lab": _lab,
    "invest": _invest,
    "business": _business,
    "studio": _studio,
    "admin": _admin,
}


def read_specialist_evidence(
    specialist: Any,
    session: Any = None,
    *,
    now: Any = None,
) -> dict[str, Any]:
    """Return a local specialist snapshot. Unknown specialists fail closed.

    Without ``session`` the reader keeps the local-contract behavior. With a
    session, it reads only an already loaded snapshot and does not fetch.
    """
    if session is not None:
        from atlasquant_aion_specialist_session import read_loaded_specialist_snapshot

        return read_loaded_specialist_snapshot(specialist, session, now=now)
    key = str(specialist or "").strip().lower()
    reader = _READERS.get(key)
    if reader is None:
        return _envelope(
            key,
            state="UNKNOWN_SPECIALIST",
            summary="Especialista não registrado. Nenhuma evidência foi inventada.",
            observations={},
            claims=[],
        )
    snapshot = reader()
    snapshot["provider_called"] = False
    snapshot["network_called"] = False
    snapshot["tool_called"] = False
    snapshot["executes_action"] = False
    snapshot["real_orders_enabled"] = False
    snapshot["invented_values"] = False
    snapshot["answers_user_question"] = False
    snapshot["answer_truth"] = "UNKNOWN"
    snapshot["secrets_included"] = False
    return snapshot


__all__ = ["SCHEMA", "read_specialist_evidence"]
