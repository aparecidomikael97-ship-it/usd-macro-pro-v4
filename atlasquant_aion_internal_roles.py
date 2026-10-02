"""Canonical internal-role registry for the AION nucleus.

The eight roles are architectural responsibilities inside one shared AION Core.
They are not eight independent AIs and never receive autonomous execution authority.
"""
from __future__ import annotations

from typing import Any

SCHEMA = "ATLASQUANT_AION_INTERNAL_ROLES_V1"

_INTERNAL_ROLES = (
    ("orchestrator", "Orquestrador", "Coordena prioridades, contexto e handoffs entre capacidades."),
    ("architect", "Arquiteto / Estrategista", "Define arquitetura, evolução, dependências e desenho de soluções."),
    ("guardian", "Guardião / Auditor", "Aplica políticas, bloqueios, revisão, segurança e trilha de auditoria."),
    ("executor", "Executor / Operador", "Executa apenas ações explicitamente permitidas pelos gates e aprovações."),
    ("memory", "Memória / Conhecimento", "Preserva contexto, proveniência, checkpoint e conhecimento validado."),
    ("finops", "FinOps / Controle de Custos", "Controla orçamento, custos, quotas, margem e uso econômico de recursos."),
    ("observability", "Observabilidade / Confiabilidade", "Monitora saúde, incidentes, logs, SLOs, recuperação e confiabilidade."),
    ("customer_success", "Sucesso do Cliente / Comercial", "Acompanha valor entregue, adoção, saúde, suporte e oportunidades comerciais."),
)


def internal_roles_snapshot() -> dict[str, Any]:
    rows = [
        {
            "role_id": role_id,
            "label": label,
            "purpose": purpose,
            "shared_core": True,
            "independent_ai": False,
            "external_action_authority": False,
            "real_trading_enabled": False,
            "automatic_merge": False,
            "automatic_deploy": False,
        }
        for role_id, label, purpose in _INTERNAL_ROLES
    ]
    return {
        "schema": SCHEMA,
        "count": len(rows),
        "roles": rows,
        "single_shared_aion_core": True,
        "roles_are_responsibilities_not_independent_ais": True,
        "execution_authority": False,
        "external_action_executed": False,
    }


__all__ = ["SCHEMA", "internal_roles_snapshot"]
