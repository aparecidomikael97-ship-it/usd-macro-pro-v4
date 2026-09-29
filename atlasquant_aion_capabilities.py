"""Capability registry for the AION central orchestrator.

Capabilities describe what AION may plan. They do not execute tools or widen
Guardian permissions. The registry is deterministic, provider-neutral and
extensible through validated metadata.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from itertools import islice
from typing import Any, Iterable, Mapping, Sequence
import math
import re
import unicodedata

SCHEMA = "ATLASQUANT_AION_CAPABILITY_REGISTRY_V1"
RISK_LEVELS = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
AVAILABILITY = ("AVAILABLE", "DEGRADED", "UNAVAILABLE", "EXPERIMENTAL")
ROLES = ("USER", "SALES", "ADMIN")
EXECUTION_MODES = ("READ_ONLY", "DRAFT_ONLY", "SANDBOX", "EXTERNAL")
AION_FEATURE_FLAGS = {
    "AION_CORE_ENABLED": True,
    "AION_DEV_ENABLED": True,
    "AION_RESEARCH_ENABLED": True,
    "AION_STUDIO_ENABLED": True,
    "AION_BUSINESS_ENABLED": True,
    "AION_INVEST_ENABLED": True,
    "AION_EXTERNAL_ACTIONS_ENABLED": False,
    "REAL_TRADING_ENABLED": False,
}
SPECIALIST_FEATURE_FLAGS = {
    "dev": "AION_DEV_ENABLED",
    "research": "AION_RESEARCH_ENABLED",
    "studio": "AION_STUDIO_ENABLED",
    "business": "AION_BUSINESS_ENABLED",
    "invest": "AION_INVEST_ENABLED",
}


def _norm(value: Any) -> str:
    raw = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(ch for ch in raw if not unicodedata.combining(ch)).casefold()


def _tokens(value: Any) -> set[str]:
    return {
        token for token in re.findall(r"[a-z0-9][a-z0-9._/-]{2,}", _norm(value))
        if token not in {"para", "com", "uma", "isso", "como", "sobre", "the"}
    }


@dataclass(frozen=True)
class Capability:
    capability_id: str
    specialist: str
    domains: tuple[str, ...]
    description: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    risk: str = "LOW"
    allowed_tools: tuple[str, ...] = ()
    allowed_roles: tuple[str, ...] = ("ADMIN",)
    requires_confirmation: bool = False
    estimated_cost_usd: float = 0.0
    availability: str = "AVAILABLE"
    execution_mode: str = "READ_ONLY"
    aliases: tuple[str, ...] = ()
    guardian_action: str = "read"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _tuple_text(value: Any, *, limit: int = 40) -> tuple[str, ...]:
    items = value if isinstance(value, (list, tuple, set)) else ()
    out: list[str] = []
    for raw in islice(items, max(0, limit)):
        text = " ".join(str(raw or "").split())[:160]
        if text and text not in out:
            out.append(text)
    return tuple(out)


def normalize_capability(raw: Capability | Mapping[str, Any]) -> Capability:
    if isinstance(raw, Capability):
        item = raw.as_dict()
    elif isinstance(raw, Mapping):
        item = dict(raw)
    else:
        raise TypeError("capability must be a mapping")
    capability_id = str(item.get("capability_id") or "").strip().lower()
    if not re.fullmatch(r"[a-z][a-z0-9_.-]{2,95}", capability_id):
        raise ValueError("invalid capability id")
    specialist = str(item.get("specialist") or "").strip().lower()
    if not re.fullmatch(r"[a-z][a-z0-9_.-]{1,63}", specialist):
        raise ValueError("invalid specialist id")
    risk = str(item.get("risk") or "LOW").upper()
    availability = str(item.get("availability") or "AVAILABLE").upper()
    mode = str(item.get("execution_mode") or "READ_ONLY").upper()
    if risk not in RISK_LEVELS:
        risk = "CRITICAL"
    if availability not in AVAILABILITY:
        availability = "UNAVAILABLE"
    if mode not in EXECUTION_MODES:
        mode = "READ_ONLY"
    roles = tuple(x for x in _tuple_text(item.get("allowed_roles")) if x.upper() in ROLES)
    roles = tuple(x.upper() for x in roles) or ("ADMIN",)
    raw_cost = item.get("estimated_cost_usd", 0.0)
    if raw_cost in (None, ""):
        cost = 0.0
    elif isinstance(raw_cost, bool) or not isinstance(raw_cost, (int, float)):
        raise ValueError("invalid estimated cost")
    elif not math.isfinite(raw_cost) or raw_cost < 0:
        raise ValueError("invalid estimated cost")
    else:
        cost = float(raw_cost)
    return Capability(
        capability_id=capability_id,
        specialist=specialist,
        domains=_tuple_text(item.get("domains")) or ("central",),
        description=" ".join(str(item.get("description") or "").split())[:500],
        inputs=_tuple_text(item.get("inputs")),
        outputs=_tuple_text(item.get("outputs")),
        risk=risk,
        allowed_tools=_tuple_text(item.get("allowed_tools")),
        allowed_roles=roles,
        requires_confirmation=item.get("requires_confirmation") is True,
        estimated_cost_usd=round(cost, 6),
        availability=availability,
        execution_mode=mode,
        aliases=_tuple_text(item.get("aliases")),
        guardian_action=str(item.get("guardian_action") or "read").strip().lower()[:80],
    )


DEFAULT_CAPABILITIES: tuple[Capability, ...] = tuple(normalize_capability(row) for row in (
    {
        "capability_id": "central.conversation", "specialist": "core",
        "domains": ["central", "conversation"], "description": "Conversa geral e explicação simples.",
        "inputs": ["question"], "outputs": ["answer"], "allowed_roles": ROLES,
        "aliases": ["conversa", "explicar", "ajuda", "pergunta"],
    },
    {
        "capability_id": "development.inspect", "specialist": "dev",
        "domains": ["development", "debugging", "architecture"],
        "description": "Inspecionar código, dependências, logs, erros e testes sem modificar produção.",
        "inputs": ["request", "repository_state"], "outputs": ["plan", "diagnosis"],
        "allowed_roles": ["ADMIN"], "allowed_tools": ["repository.read", "tests.read"],
        "aliases": ["codigo", "bug", "debug", "arquitetura", "teste", "logs"],
    },
    {
        "capability_id": "development.sandbox", "specialist": "dev",
        "domains": ["development", "debugging"], "description": "Preparar mudança reversível em sandbox/branch.",
        "inputs": ["approved_plan"], "outputs": ["changes", "tests", "review"],
        "risk": "MEDIUM", "allowed_roles": ["ADMIN"], "requires_confirmation": True,
        "execution_mode": "SANDBOX", "guardian_action": "save_checkpoint",
        "aliases": ["implementar", "corrigir", "patch", "refatorar"],
    },
    {
        "capability_id": "research.synthesize", "specialist": "research",
        "domains": ["research", "documentation", "geopolitics"],
        "description": "Decompor pesquisa, comparar fontes, preservar conflitos e sintetizar.",
        "inputs": ["question", "sources"], "outputs": ["evidence", "synthesis"],
        "allowed_roles": ROLES, "allowed_tools": ["aion.memory.search"],
        "aliases": ["pesquisar", "comparar", "fonte", "documentacao", "geopolitica"],
    },
    {
        "capability_id": "market.explain", "specialist": "market",
        "domains": ["market", "trading"], "description": "Explicar Radar, força, sessão e risco sem gerar ordem.",
        "inputs": ["market_snapshot"], "outputs": ["context", "risk"], "allowed_roles": ROLES,
        "aliases": ["mercado", "radar", "forex", "indices", "cripto", "sessao"],
    },
    {
        "capability_id": "macro.explain", "specialist": "macro",
        "domains": ["macro", "economics"], "description": "Explicar indicadores, bancos centrais e cenários macro.",
        "inputs": ["macro_evidence"], "outputs": ["macro_context"], "allowed_roles": ROLES,
        "aliases": ["cpi", "pce", "nfp", "fomc", "fed", "ecb", "inflacao", "juros"],
    },
    {
        "capability_id": "ict.explain", "specialist": "ict",
        "domains": ["ict", "smc", "technical"], "description": "Explicar estrutura ICT/SMC com regras e evidência.",
        "inputs": ["technical_evidence"], "outputs": ["technical_context"], "allowed_roles": ROLES,
        "aliases": ["ict", "smc", "fvg", "order block", "bos", "choch", "liquidez"],
    },
    {
        "capability_id": "risk.assess", "specialist": "risk",
        "domains": ["risk", "guardian"], "description": "Avaliar impacto, reversibilidade e bloqueios.",
        "inputs": ["proposed_action"], "outputs": ["risk_assessment"], "allowed_roles": ROLES,
        "aliases": ["risco", "guardian", "seguranca", "bloqueio"],
    },
    {
        "capability_id": "laboratory.inspect", "specialist": "lab",
        "domains": ["laboratory", "backtest"], "description": "Consultar evidências, backtests e comparações registradas.",
        "inputs": ["experiment_query"], "outputs": ["evidence_summary"], "allowed_roles": ROLES,
        "aliases": ["laboratorio", "backtest", "evidencia", "setup", "timeframe"],
    },
    {
        "capability_id": "invest.compare", "specialist": "invest",
        "domains": ["investments", "treasury"], "description": "Comparar produtos e cenários sem movimentar dinheiro.",
        "inputs": ["proven_product_data"], "outputs": ["comparison"], "allowed_roles": ROLES,
        "aliases": ["investimento", "renda fixa", "tesouro", "fii", "dividendo", "liquidez"],
    },
    {
        "capability_id": "business.analyze", "specialist": "business",
        "domains": ["business", "sales"], "description": "Analisar produto, margem, CAC, LTV e funil.",
        "inputs": ["business_data"], "outputs": ["analysis", "draft"], "allowed_roles": ["SALES", "ADMIN"],
        "aliases": ["negocio", "vendas", "produto", "margem", "cac", "ltv", "fornecedor"],
    },
    {
        "capability_id": "studio.prepare", "specialist": "studio",
        "domains": ["content", "video", "image", "social"], "description": "Preparar conteúdo e mídia para aprovação.",
        "inputs": ["authorized_content", "brief"], "outputs": ["draft_assets"], "allowed_roles": ["ADMIN"],
        "execution_mode": "DRAFT_ONLY", "aliases": ["video", "imagem", "roteiro", "thumbnail", "legenda"],
    },
    {
        "capability_id": "admin.status", "specialist": "admin",
        "domains": ["administration", "system"], "description": "Consolidar estado, incidentes, tarefas e pendências.",
        "inputs": ["system_evidence"], "outputs": ["executive_status"], "allowed_roles": ["ADMIN"],
        "aliases": ["administrar", "status", "incidente", "pendencia", "checkpoint", "cliente"],
    },
))


class CapabilityRegistry:
    def __init__(self, capabilities: Iterable[Capability | Mapping[str, Any]] = DEFAULT_CAPABILITIES):
        self._items: dict[str, Capability] = {}
        for capability in capabilities:
            self.register(capability)

    def register(self, capability: Capability | Mapping[str, Any]) -> Capability:
        item = normalize_capability(capability)
        if item.capability_id in self._items:
            raise ValueError(f"duplicate capability: {item.capability_id}")
        self._items[item.capability_id] = item
        return item

    def get(self, capability_id: Any) -> Capability | None:
        return self._items.get(str(capability_id or "").strip().lower())

    def list(self) -> list[Capability]:
        return [self._items[key] for key in sorted(self._items)]

    def route(
        self,
        request: Any,
        *,
        domain_hint: Any = "",
        limit: int = 3,
    ) -> list[dict[str, Any]]:
        query_tokens = _tokens(request)
        hint = _norm(domain_hint).strip()
        scored: list[tuple[float, Capability, list[str]]] = []
        for capability in self._items.values():
            metadata = " ".join((
                capability.capability_id,
                capability.specialist,
                capability.description,
                " ".join(capability.domains),
                " ".join(capability.aliases),
            ))
            metadata_tokens = _tokens(metadata)
            matches = sorted(query_tokens & metadata_tokens)
            score = float(len(matches) * 10)
            if hint and hint in {_norm(x) for x in capability.domains}:
                score += 18.0
            if capability.capability_id == "central.conversation":
                score += 0.5
            if score > 0:
                scored.append((score, capability, matches))
        scored.sort(key=lambda row: (-row[0], row[1].capability_id))
        return [{
            **capability.as_dict(),
            "route_score": score,
            "matched_metadata": matches,
        } for score, capability, matches in scored[: max(1, min(int(limit), 8))]]


def default_registry() -> CapabilityRegistry:
    return CapabilityRegistry()


def capability_feature_flags(overrides: Mapping[str, Any] | None = None) -> dict[str, bool]:
    flags = dict(AION_FEATURE_FLAGS)
    for key in flags:
        if isinstance(overrides, Mapping) and key in overrides:
            flags[key] = overrides[key] is True
    # These two flags are immutable-off in this release.
    flags["AION_EXTERNAL_ACTIONS_ENABLED"] = False
    flags["REAL_TRADING_ENABLED"] = False
    return flags


__all__ = [
    "SCHEMA", "RISK_LEVELS", "AVAILABILITY", "ROLES", "EXECUTION_MODES",
    "AION_FEATURE_FLAGS", "SPECIALIST_FEATURE_FLAGS",
    "Capability", "CapabilityRegistry", "DEFAULT_CAPABILITIES",
    "normalize_capability", "default_registry", "capability_feature_flags",
]
