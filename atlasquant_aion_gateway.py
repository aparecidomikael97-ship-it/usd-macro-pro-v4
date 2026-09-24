"""AION model gateway contract.

Version 1 intentionally keeps external model execution disabled by default.
It provides deterministic routing and a truthful zero-cost local fallback so the
UI can work before any paid AI API is approved.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence
import os

from atlasquant_aion_core import feature_flag_snapshot, route_context

SCHEMA = "ATLASQUANT_AION_GATEWAY_V1"


def provider_status(
    *,
    feature_flags: Mapping[str, Any] | None = None,
    env: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    values = dict(env or {})
    flags = feature_flag_snapshot(feature_flags)
    provider = str(
        values.get("AION_MODEL_PROVIDER")
        or os.getenv("AION_MODEL_PROVIDER", "")
        or "offline"
    ).strip().lower()
    external_requested = provider not in {"", "offline", "local", "zero-cost"}
    external_enabled = bool(flags.get("external_llm", False))
    if external_requested and not external_enabled:
        state = "BLOCKED_BY_FEATURE_FLAG"
    elif external_requested:
        state = "CONFIGURED_EXTERNAL"
    else:
        state = "ZERO_COST_LOCAL"
    return {
        "schema": SCHEMA,
        "provider": provider or "offline",
        "state": state,
        "external_enabled": bool(external_requested and external_enabled),
        "cost_mode": "ZERO_COST_DEFAULT",
        "automatic_billing": False,
    }


def route_model(
    task: object,
    *,
    complexity: str = "normal",
    feature_flags: Mapping[str, Any] | None = None,
    env: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    status = provider_status(feature_flags=feature_flags, env=env)
    context = route_context(task)
    complexity_norm = str(complexity or "normal").strip().lower()
    lane = "external_provider" if status["external_enabled"] else "local_deterministic"
    return {
        "schema": SCHEMA,
        "lane": lane,
        "domain": context["domain"],
        "complexity": complexity_norm,
        "provider": status["provider"],
        "provider_state": status["state"],
        "executes_action": False,
    }


def _checkpoint_line(checkpoint: Mapping[str, Any] | None) -> str:
    cp = dict(checkpoint or {})
    aion = cp.get("aion") if isinstance(cp.get("aion"), Mapping) else {}
    priority = str((aion or {}).get("priority") or "não registrada")
    pending = cp.get("pending")
    count = len(pending) if isinstance(pending, list) else 0
    return f"Prioridade registrada: {priority}. Pendências registradas: {count}."


def local_answer(
    question: object,
    *,
    checkpoint: Mapping[str, Any] | None = None,
    memory_hits: Sequence[Mapping[str, Any]] | None = None,
    system_context: Mapping[str, Any] | None = None,
    feature_flags: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Truthful local response when no external LLM has been approved.

    It never pretends to be a general-purpose model. Evidence is returned
    separately so the UI can show provenance.
    """
    q = str(question or "").strip()
    route = route_context(q)
    hits = [dict(x) for x in list(memory_hits or [])[:5] if isinstance(x, Mapping)]
    system = dict(system_context or {})
    provider = provider_status(feature_flags=feature_flags)

    if not q:
        answer = "Escreva uma pergunta ou missão para o AION."
    elif route["domain"] == "development":
        answer = (
            "Entendi como Desenvolvimento. "
            + _checkpoint_line(checkpoint)
            + " Nesta fundação eu consigo consultar o Checkpoint Mestre e organizar a missão. "
            "Alterações de código, deploy ou merge continuam protegidas pelo Guardian."
        )
    elif route["domain"] == "studio":
        answer = (
            "Entendi como Studio. Posso organizar roteiro, imagem, vídeo, legenda, capa e plano de publicação. "
            "Publicação automática permanece desligada até existir integração aprovada e feature flag liberada."
        )
    elif route["domain"] == "business":
        answer = (
            "Entendi como Negócios. Posso estruturar pesquisa de produto, tendência, margem, fornecedor e meta de receita. "
            "Compra, anúncio ou publicação em marketplace não é executada sem integração e aprovação."
        )
    elif route["domain"] == "promotions":
        answer = (
            "Entendi como Promoções. Posso preparar regras de cupom, dias grátis, desconto e limites de uso. "
            "Ativação real depende do provedor comercial e de aprovação explícita."
        )
    elif route["domain"] == "laboratory":
        answer = (
            "Entendi como Laboratório. A regra é testar em Sandbox, medir, registrar evidência e só promover depois de validação. "
            "Backtest ou forward test não autoriza operação real."
        )
    elif route["domain"] == "secretary":
        answer = (
            "Entendi como Secretaria. Posso consolidar prioridades, pendências, aprovações e checkpoints. "
            "Agenda e clientes só são afirmados quando houver uma fonte realmente conectada."
        )
    elif route["domain"] == "trading":
        market_state = str(system.get("market_status") or "não confirmado nesta tela")
        answer = (
            f"Entendi como Trading. Estado de mercado disponível para esta resposta: {market_state}. "
            "Sem dado fresco confirmado, o AION não inventa direção nem oportunidade."
        )
    else:
        answer = (
            "Estou na Central AION. Posso encaminhar a pergunta para Trading, Studio, Negócios, "
            "Laboratório, Secretaria, Desenvolvimento ou Promoções."
        )

    if hits:
        answer += f" Encontrei {len(hits)} referência(s) na memória canônica para apoiar a resposta."
    if provider["state"] == "ZERO_COST_LOCAL":
        answer += " O modo atual é local e custo zero; um modelo externo mais potente ainda não foi ativado."

    return {
        "schema": SCHEMA,
        "answer": answer,
        "domain": route["domain"],
        "provider": provider,
        "evidence": hits,
        "truth_state": "CONFIRMED_LOCAL_CONTRACT",
        "executes_action": False,
        "real_orders_enabled": False,
    }
