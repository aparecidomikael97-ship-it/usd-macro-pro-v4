"""AION core domain registry.

Official registration of AION domains with data, memory, sharing, offline and
online policies. Pure/offline and deterministic: the registry is built from a
static table, lookups are fail-closed, and a private domain never crosses its
boundary without an explicit sharing rule.

This module does not execute anything, does not call providers, and does not
replace the routing in atlasquant_aion_core (route_context). It registers the
domains that route_context and the specialists operate on.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Mapping, Sequence
import json
import unicodedata

SCHEMA = "ATLASQUANT_AION_CORE_DOMAIN_REGISTRY_V1"
REGISTRY_VERSION = 1

DOMAIN_IDS = (
    "CORE",
    "NEGOCIOS",
    "TRADER",
    "INVESTIMENTOS",
    "BIBLIOTECA",
    "ADMIN",
    "SEGURANCA",
    "MEMORIA",
    "ORQUESTRACAO",
)

RISK_CLASSIFICATIONS = ("LOW", "MEDIUM", "HIGH", "CRITICAL")

_MEMORY_POLICIES = ("PRIVATE", "SHARED_WITH_PROVENANCE", "READ_ONLY")
_SHARING_POLICIES = ("NONE", "EXPLICIT_RULE_ONLY", "CURATED_EXPORT")
_OFFLINE_POLICIES = ("FULL_LOCAL", "DEGRADED_LOCAL", "UNAVAILABLE")
_ONLINE_POLICIES = ("ADAPTERS_ALLOWED", "LOCAL_ONLY_PREFERRED", "DISABLED")


def _norm_id(value: Any) -> str:
    raw = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(ch for ch in raw if not unicodedata.combining(ch)).strip().upper()


@dataclass(frozen=True)
class DomainSpec:
    domain_id: str
    name: str
    description: str
    version: int
    capabilities: tuple[str, ...]
    allowed_data: tuple[str, ...]
    prohibited_data: tuple[str, ...]
    memory_policy: str
    sharing_policy: str
    offline_policy: str
    online_policy: str
    risk_classification: str
    owner: str
    status: str

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for key in ("capabilities", "allowed_data", "prohibited_data"):
            data[key] = list(data[key])
        return data


def _spec(
    domain_id: str,
    name: str,
    description: str,
    *,
    capabilities: Sequence[str],
    allowed_data: Sequence[str],
    prohibited_data: Sequence[str],
    memory_policy: str,
    sharing_policy: str,
    offline_policy: str,
    online_policy: str,
    risk_classification: str,
    owner: str,
    status: str = "ACTIVE",
) -> DomainSpec:
    if memory_policy not in _MEMORY_POLICIES:
        raise ValueError("invalid memory policy")
    if sharing_policy not in _SHARING_POLICIES:
        raise ValueError("invalid sharing policy")
    if offline_policy not in _OFFLINE_POLICIES:
        raise ValueError("invalid offline policy")
    if online_policy not in _ONLINE_POLICIES:
        raise ValueError("invalid online policy")
    if risk_classification not in RISK_CLASSIFICATIONS:
        raise ValueError("invalid risk classification")
    return DomainSpec(
        domain_id=domain_id,
        name=name,
        description=description,
        version=REGISTRY_VERSION,
        capabilities=tuple(str(c) for c in capabilities),
        allowed_data=tuple(str(d) for d in allowed_data),
        prohibited_data=tuple(str(d) for d in prohibited_data),
        memory_policy=memory_policy,
        sharing_policy=sharing_policy,
        offline_policy=offline_policy,
        online_policy=online_policy,
        risk_classification=risk_classification,
        owner=owner,
        status=status,
    )


_DOMAINS: tuple[DomainSpec, ...] = (
    _spec(
        "CORE",
        "AION Core",
        "Núcleo central: identidade, política, memória e orquestração.",
        capabilities=("identity", "policy", "memory", "orchestration"),
        allowed_data=("identity_manifest", "policy_decision", "memory_record", "audit_event"),
        prohibited_data=("secrets", "raw_client_pii", "financial_execution"),
        memory_policy="SHARED_WITH_PROVENANCE",
        sharing_policy="EXPLICIT_RULE_ONLY",
        offline_policy="FULL_LOCAL",
        online_policy="LOCAL_ONLY_PREFERRED",
        risk_classification="MEDIUM",
        owner="AION_ADMIN",
    ),
    _spec(
        "NEGOCIOS",
        "AION Negócios",
        "Gestão comercial, funil, clientes e receita.",
        capabilities=("diagnosis", "funnel_analysis", "client_summary", "roi_estimate"),
        allowed_data=("tenant_business_metrics", "crm_snapshot", "pipeline_state"),
        prohibited_data=("other_tenant_private", "trader_positions", "secrets"),
        memory_policy="PRIVATE",
        sharing_policy="EXPLICIT_RULE_ONLY",
        offline_policy="DEGRADED_LOCAL",
        online_policy="ADAPTERS_ALLOWED",
        risk_classification="MEDIUM",
        owner="AION_ADMIN",
    ),
    _spec(
        "TRADER",
        "AION Trader",
        "Leitura macro/operacional de mercados. Execução real bloqueada.",
        capabilities=("macro_read", "market_context", "signal_review"),
        allowed_data=("market_snapshot", "macro_indicators", "radar_state"),
        prohibited_data=("real_orders", "broker_credentials", "other_tenant_private"),
        memory_policy="PRIVATE",
        sharing_policy="EXPLICIT_RULE_ONLY",
        offline_policy="DEGRADED_LOCAL",
        online_policy="ADAPTERS_ALLOWED",
        risk_classification="HIGH",
        owner="AION_ADMIN",
    ),
    _spec(
        "INVESTIMENTOS",
        "AION Investimentos",
        "Comparação e análise de investimentos sem execução.",
        capabilities=("comparison", "scenario_analysis", "risk_review"),
        allowed_data=("asset_snapshots", "portfolio_view", "scenario_inputs"),
        prohibited_data=("real_orders", "broker_credentials", "other_tenant_private"),
        memory_policy="PRIVATE",
        sharing_policy="EXPLICIT_RULE_ONLY",
        offline_policy="DEGRADED_LOCAL",
        online_policy="ADAPTERS_ALLOWED",
        risk_classification="HIGH",
        owner="AION_ADMIN",
    ),
    _spec(
        "BIBLIOTECA",
        "Biblioteca AION",
        "Conhecimento local com proveniência e direitos de uso.",
        capabilities=("retrieval", "classification", "conflict_detection"),
        allowed_data=("document_metadata", "extracted_passages", "provenance_record"),
        prohibited_data=("full_copyrighted_text_export", "other_tenant_private", "secrets"),
        memory_policy="SHARED_WITH_PROVENANCE",
        sharing_policy="CURATED_EXPORT",
        offline_policy="FULL_LOCAL",
        online_policy="LOCAL_ONLY_PREFERRED",
        risk_classification="LOW",
        owner="AION_ADMIN",
    ),
    _spec(
        "ADMIN",
        "AION Admin",
        "Administração global do ecossistema AION.",
        capabilities=("session_audit", "entitlement_review", "configuration_read"),
        allowed_data=("account_audit", "entitlement_records", "config_public"),
        prohibited_data=("secrets", "raw_client_pii", "other_admin_sessions"),
        memory_policy="PRIVATE",
        sharing_policy="NONE",
        offline_policy="FULL_LOCAL",
        online_policy="DISABLED",
        risk_classification="CRITICAL",
        owner="MIKAEL",
    ),
    _spec(
        "SEGURANCA",
        "AION Segurança",
        "Guardiões, incidentes e fail-closed do núcleo.",
        capabilities=("guardian_posture", "incident_review", "reliability_snapshot"),
        allowed_data=("guardian_decision", "incident_record", "reliability_state"),
        prohibited_data=("secrets_value", "other_tenant_private", "raw_client_pii"),
        memory_policy="PRIVATE",
        sharing_policy="EXPLICIT_RULE_ONLY",
        offline_policy="FULL_LOCAL",
        online_policy="DISABLED",
        risk_classification="CRITICAL",
        owner="AION_ADMIN",
    ),
    _spec(
        "MEMORIA",
        "Memória AION",
        "Memória em camadas com quarentena e promoção explícita.",
        capabilities=("remember", "recall", "quarantine", "promotion_review"),
        allowed_data=("memory_record", "quarantine_candidate", "promotion_receipt"),
        prohibited_data=("secrets", "other_tenant_private", "authority_claims"),
        memory_policy="SHARED_WITH_PROVENANCE",
        sharing_policy="EXPLICIT_RULE_ONLY",
        offline_policy="FULL_LOCAL",
        online_policy="LOCAL_ONLY_PREFERRED",
        risk_classification="MEDIUM",
        owner="AION_ADMIN",
    ),
    _spec(
        "ORQUESTRACAO",
        "Orquestração AION",
        "Roteamento de solicitações entre especialistas sem executar.",
        capabilities=("routing", "specialist_selection", "escalation"),
        allowed_data=("route_decision", "task_plan", "escalation_record"),
        prohibited_data=("execution_authority", "secrets", "other_tenant_private"),
        memory_policy="PRIVATE",
        sharing_policy="EXPLICIT_RULE_ONLY",
        offline_policy="FULL_LOCAL",
        online_policy="LOCAL_ONLY_PREFERRED",
        risk_classification="MEDIUM",
        owner="AION_ADMIN",
    ),
)


def build_domain_registry() -> dict[str, Any]:
    """Deterministic registry snapshot. Same input, same bytes."""
    domains = {spec.domain_id: spec.as_dict() for spec in _DOMAINS}
    return {
        "schema": SCHEMA,
        "version": REGISTRY_VERSION,
        "domain_ids": list(DOMAIN_IDS),
        "domains": domains,
        "executes_action": False,
        "calls_external": False,
    }


def get_domain(domain_id: Any) -> dict[str, Any] | None:
    """Fail-closed lookup by domain id. Unknown ids return None."""
    key = _norm_id(domain_id)
    for spec in _DOMAINS:
        if spec.domain_id == key:
            return spec.as_dict()
    return None


def require_domain(domain_id: Any) -> dict[str, Any]:
    """Lookup that raises for unknown domains."""
    domain = get_domain(domain_id)
    if domain is None:
        raise KeyError(f"unknown AION domain: {domain_id!r}")
    return domain


def data_access_allowed(domain_id: Any, data_kind: Any) -> bool:
    """Allowed data is open; prohibited data is always denied; unknown stays denied."""
    domain = get_domain(domain_id)
    if domain is None:
        return False
    kind = str(data_kind or "").strip().lower()
    if not kind:
        return False
    if kind in {d.lower() for d in domain["prohibited_data"]}:
        return False
    return kind in {d.lower() for d in domain["allowed_data"]}


def cross_domain_read_allowed(
    source_domain: Any,
    target_domain: Any,
    data_kind: Any,
    *,
    explicit_rule: bool = False,
) -> dict[str, Any]:
    """Cross-domain read needs an explicit rule plus provenance-classified data.

    The default sharing policy never opens access: without explicit_rule the
    answer is denied, even when both domains exist.
    """
    source = get_domain(source_domain)
    target = get_domain(target_domain)
    reasons: list[str] = []
    if source is None:
        reasons.append("source_domain_unknown")
    if target is None:
        reasons.append("target_domain_unknown")
    kind = str(data_kind or "").strip().lower()
    if not kind:
        reasons.append("data_kind_missing")
    if target is not None and kind in {d.lower() for d in target["prohibited_data"]}:
        reasons.append("target_prohibits_data")
    if target is not None and kind not in {d.lower() for d in target["allowed_data"]}:
        reasons.append("data_not_allowed_by_target")
    if target is not None and target["sharing_policy"] == "NONE":
        reasons.append("target_sharing_none")
    if explicit_rule is not True:
        reasons.append("explicit_rule_required")
    allowed = not reasons
    return {
        "schema": SCHEMA,
        "allowed": allowed,
        "reasons": reasons,
        "requires_provenance": True,
        "auditable": True,
        "executes_action": False,
    }


def registry_digest(registry: Mapping[str, Any] | None) -> str:
    import hashlib
    raw = json.dumps(dict(registry or {}), ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


__all__ = [
    "SCHEMA",
    "REGISTRY_VERSION",
    "DOMAIN_IDS",
    "RISK_CLASSIFICATIONS",
    "DomainSpec",
    "build_domain_registry",
    "get_domain",
    "require_domain",
    "data_access_allowed",
    "cross_domain_read_allowed",
    "registry_digest",
]
