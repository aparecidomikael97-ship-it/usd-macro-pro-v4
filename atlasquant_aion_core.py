"""AtlasQuant AION core contracts.

Pure/offline foundation for the AtlasQuant administrative assistant.
This module deliberately does not call external AI providers, social networks,
marketplaces, brokers, payment providers, or production deployment APIs.

Core principles:
- truth before fluency;
- zero-cost by default;
- explicit approval before costly/irreversible actions;
- strict role boundaries;
- real-money trading remains blocked;
- every answer/action exposes evidence and uncertainty.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Sequence
import hashlib
import json
import unicodedata

SCHEMA = "ATLASQUANT_AION_CORE_V1"
AION_NAME = "AION"
AION_VERSION = "0.1-foundation"

DOMAINS = (
    "central",
    "trading",
    "studio",
    "business",
    "laboratory",
    "secretary",
    "development",
    "promotions",
)

RISKY_EXTERNAL_FEATURES = {
    "external_llm": False,
    "social_publish": False,
    "marketplace_publish": False,
    "marketplace_orders": False,
    "payment_provider": False,
    "promotion_activation": False,
    "production_deploy": False,
    "auto_merge": False,
    "real_broker_execution": False,
}

CANONICAL_MEMORY_SOURCES = (
    "CONTEXTO_DO_PROJETO.md",
    "HISTORICO_DE_ALTERACOES.md",
    "docs/continuidade/",
    "docs/release/ATLASQUANT_RELEASE_FINAL.md",
)

TRUTH_RULES = (
    "Nunca inventar fatos, estados, resultados ou integrações.",
    "Separar fato confirmado, inferência, hipótese e desconhecido.",
    "Quando não houver evidência suficiente, declarar que não está confirmado.",
    "Não dizer que algo está pronto sem checar código, testes, runtime ou checkpoint aplicável.",
    "Não transformar score de mercado em probabilidade de lucro.",
    "Não afirmar publicação, cobrança, venda, deploy ou execução sem evidência correspondente.",
)

ZERO_COST_RULES = (
    "Preferir recurso local, gratuito, open-source ou já contratado.",
    "Não iniciar cobrança, upgrade ou assinatura automaticamente.",
    "Exibir custo estimado e alternativa gratuita antes de pedir aprovação.",
    "Bloquear ação com custo positivo quando não houver aprovação explícita.",
)


class TruthKind(str, Enum):
    CONFIRMED = "CONFIRMED"
    INFERENCE = "INFERENCE"
    HYPOTHESIS = "HYPOTHESIS"
    UNKNOWN = "UNKNOWN"


class GuardianRisk(str, Enum):
    READ = "READ"
    DRAFT = "DRAFT"
    WRITE = "WRITE"
    PUBLISH = "PUBLISH"
    FINANCIAL = "FINANCIAL"
    PRODUCTION = "PRODUCTION"
    SECRETS = "SECRETS"
    REAL_TRADING = "REAL_TRADING"


@dataclass(frozen=True)
class TruthRecord:
    kind: str
    value: Any
    source: str
    checked_at: str
    note: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GuardianDecision:
    allowed: bool
    risk: str
    reason: str
    requires_explicit_approval: bool
    feature_flag: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm(value: object) -> str:
    raw = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(ch for ch in raw if not unicodedata.combining(ch)).casefold()


def _role(access: Mapping[str, Any] | None) -> str:
    if not isinstance(access, Mapping):
        return ""
    return str(access.get("role") or "").strip().upper()


def is_admin(access: Mapping[str, Any] | None) -> bool:
    return _role(access) == "ADMIN"


def truth_record(
    value: Any,
    *,
    source: str = "",
    confirmed: bool = False,
    inference: bool = False,
    hypothesis: bool = False,
    note: str = "",
) -> dict[str, Any]:
    """Create an explicit truth-status record.

    Precedence is conservative: confirmed > inference > hypothesis > unknown.
    A value alone never means confirmed.
    """
    if confirmed:
        kind = TruthKind.CONFIRMED
    elif inference:
        kind = TruthKind.INFERENCE
    elif hypothesis:
        kind = TruthKind.HYPOTHESIS
    else:
        kind = TruthKind.UNKNOWN
    return TruthRecord(
        kind=kind.value,
        value=value,
        source=str(source or "").strip(),
        checked_at=utc_now_iso(),
        note=str(note or "").strip(),
    ).as_dict()


def all_confirmed(records: Sequence[Mapping[str, Any]] | None) -> bool:
    values = list(records or [])
    return bool(values) and all(str(x.get("kind")) == TruthKind.CONFIRMED.value for x in values)


def route_context(text: object) -> dict[str, Any]:
    """Route natural language into one AION workspace without executing anything."""
    q = _norm(text)
    patterns = (
        ("development", (
            "codigo", "program", "desenvolv", "github", "pull request", "commit",
            "deploy", "interface", "bug", "erro", "sistema", "checkpoint",
        )),
        ("studio", (
            "video", "imagem", "instagram", "youtube", "tiktok", "rede social",
            "roteiro", "legenda", "capa", "thumbnail", "publica",
        )),
        ("business", (
            "mercado livre", "tiktok shop", "produto", "fornecedor", "estoque",
            "margem", "venda", "negocio", "receita", "lucro",
        )),
        ("promotions", (
            "promoc", "cupom", "codigo promocional", "gratuito", "dias gratis",
            "assinatura", "mensalidade", "desconto",
        )),
        ("laboratory", (
            "laboratorio", "sandbox", "backtest", "forward test", "teste",
            "validacao", "experimento", "benchmark",
        )),
        ("secretary", (
            "agenda", "tarefa", "lembrete", "pendencia", "compromisso",
            "cliente novo", "prioridade", "secretario",
        )),
        ("trading", (
            "trading", "trader", "radar", "forex", "macro", "mercado", "par",
            "dolar", "euro", "fed", "operacional", "sinal",
        )),
    )
    scores: dict[str, int] = {}
    for domain, terms in patterns:
        scores[domain] = sum(1 for term in terms if term in q)
    winner = max(scores, key=scores.get) if scores else "central"
    if not scores or scores.get(winner, 0) <= 0:
        winner = "central"
    return {
        "schema": SCHEMA,
        "domain": winner,
        "scores": scores,
        "text_present": bool(q),
        "executes_action": False,
    }


def cost_guard(
    estimated_monthly_cost_usd: Any,
    *,
    approved: bool = False,
) -> dict[str, Any]:
    try:
        cost = float(estimated_monthly_cost_usd)
    except Exception:
        cost = 0.0
    cost = max(0.0, cost)
    if cost <= 0:
        allowed = True
        reason = "Custo estimado zero; política Custo Zero preservada."
    elif approved:
        allowed = True
        reason = "Custo positivo explicitamente aprovado pelo administrador."
    else:
        allowed = False
        reason = "Custo positivo bloqueado até aprovação explícita do administrador."
    return {
        "schema": SCHEMA,
        "allowed": allowed,
        "estimated_monthly_cost_usd": round(cost, 4),
        "requires_explicit_approval": cost > 0,
        "approved": bool(approved),
        "reason": reason,
    }


_ACTION_RISK = {
    "read": GuardianRisk.READ,
    "summarize": GuardianRisk.READ,
    "search": GuardianRisk.READ,
    "draft": GuardianRisk.DRAFT,
    "save_checkpoint": GuardianRisk.WRITE,
    "write_runtime": GuardianRisk.WRITE,
    "publish_social": GuardianRisk.PUBLISH,
    "publish_marketplace": GuardianRisk.PUBLISH,
    "activate_promotion": GuardianRisk.FINANCIAL,
    "charge_customer": GuardianRisk.FINANCIAL,
    "deploy_production": GuardianRisk.PRODUCTION,
    "merge_main": GuardianRisk.PRODUCTION,
    "read_secret": GuardianRisk.SECRETS,
    "write_secret": GuardianRisk.SECRETS,
    "real_trade": GuardianRisk.REAL_TRADING,
}

_ACTION_FEATURE_FLAG = {
    "publish_social": "social_publish",
    "publish_marketplace": "marketplace_publish",
    "activate_promotion": "promotion_activation",
    "charge_customer": "payment_provider",
    "deploy_production": "production_deploy",
    "merge_main": "auto_merge",
    "real_trade": "real_broker_execution",
}


def guardian_decision(
    action: object,
    access: Mapping[str, Any] | None,
    *,
    approved: bool = False,
    feature_flags: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Fail-closed authorization for AION actions.

    Unknown actions are denied. REAL_TRADING is always denied in this release.
    """
    action_key = str(action or "").strip().lower()
    risk = _ACTION_RISK.get(action_key)
    flags = dict(RISKY_EXTERNAL_FEATURES)
    if isinstance(feature_flags, Mapping):
        for key in flags:
            if key in feature_flags:
                flags[key] = bool(feature_flags[key])

    if risk is None:
        return GuardianDecision(
            False,
            "UNKNOWN",
            "Ação desconhecida; Guardian falha fechado.",
            True,
        ).as_dict()

    if risk is GuardianRisk.REAL_TRADING:
        return GuardianDecision(
            False,
            risk.value,
            "Execução real em corretora permanece bloqueada por desenho.",
            True,
            _ACTION_FEATURE_FLAG.get(action_key, ""),
        ).as_dict()

    if not is_admin(access):
        return GuardianDecision(
            False,
            risk.value,
            "AION oficial exige sessão ADMIN para esta ação.",
            risk not in {GuardianRisk.READ},
            _ACTION_FEATURE_FLAG.get(action_key, ""),
        ).as_dict()

    flag = _ACTION_FEATURE_FLAG.get(action_key, "")
    if flag and not flags.get(flag, False):
        return GuardianDecision(
            False,
            risk.value,
            f"Feature flag {flag} está desligada.",
            True,
            flag,
        ).as_dict()

    requires = risk in {
        GuardianRisk.WRITE,
        GuardianRisk.PUBLISH,
        GuardianRisk.FINANCIAL,
        GuardianRisk.PRODUCTION,
        GuardianRisk.SECRETS,
    }
    if requires and not approved:
        return GuardianDecision(
            False,
            risk.value,
            "Ação sensível bloqueada até aprovação explícita.",
            True,
            flag,
        ).as_dict()

    return GuardianDecision(
        True,
        risk.value,
        "Ação permitida pelo Guardian dentro do escopo atual.",
        requires,
        flag,
    ).as_dict()


def mission_plan(objective: object, *, domain: str | None = None) -> dict[str, Any]:
    """Create a deterministic mission skeleton; it does not execute tasks."""
    objective_text = str(objective or "").strip()
    routed = route_context(objective_text)
    selected = domain if domain in DOMAINS else routed["domain"]
    steps = [
        "Confirmar estado atual e evidências.",
        "Definir mudança mínima e reversível.",
        "Executar em Sandbox/branch de feature.",
        "Rodar testes e checagens aplicáveis.",
        "Registrar checkpoint e evidências.",
        "Pedir aprovação antes de ação crítica ou externa.",
    ]
    mission_id = hashlib.sha256(
        (selected + "|" + objective_text).encode("utf-8")
    ).hexdigest()[:12]
    return {
        "schema": SCHEMA,
        "mission_id": mission_id,
        "domain": selected,
        "objective": objective_text,
        "steps": steps,
        "status": "PLANNED",
        "executes_action": False,
    }


def boot_briefing(
    *,
    system: Mapping[str, Any] | None = None,
    memory: Mapping[str, Any] | None = None,
    market: Mapping[str, Any] | None = None,
    clients: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a truth-labeled startup briefing.

    Callers must provide records that already reflect the evidence they actually have.
    """
    return {
        "schema": SCHEMA,
        "generated_at": utc_now_iso(),
        "sections": {
            "system": dict(system or {}),
            "memory": dict(memory or {}),
            "market": dict(market or {}),
            "clients": dict(clients or {}),
        },
        "truth_rules": list(TRUTH_RULES),
        "real_orders_enabled": False,
        "automatic_paid_actions": False,
        "automatic_external_publish": False,
    }


def feature_flag_snapshot(overrides: Mapping[str, Any] | None = None) -> dict[str, bool]:
    flags = dict(RISKY_EXTERNAL_FEATURES)
    if isinstance(overrides, Mapping):
        for key in flags:
            if key in overrides:
                flags[key] = bool(overrides[key])
    return flags


def deterministic_fingerprint(payload: Any) -> str:
    try:
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    except Exception:
        raw = repr(payload)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def truth_policy_text() -> str:
    return " ".join(TRUTH_RULES)
