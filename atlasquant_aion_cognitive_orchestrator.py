"""AION Cognitive Orchestrator.

A deterministic, zero-cost orchestration layer inspired by modern frontier-AI
architectures: specialist routing, research planning, evidence verification and
critic gates before synthesis.

This module intentionally does NOT:
- expose private chain-of-thought;
- call the web or any model/provider by itself;
- execute external actions;
- modify production rules, model weights or trading state;
- promote unsupported claims to facts.

It returns structured plans, evidence requirements, conflicts and verification
results that other AION layers may use.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence
import re
import unicodedata

from atlasquant_aion_intelligence import evidence_audit, evidence_confidence

SCHEMA = "ATLASQUANT_AION_COGNITIVE_ORCHESTRATOR_V1"

TRUTH_STATES = ("CONFIRMED", "INFERENCE", "HYPOTHESIS", "UNKNOWN")

SPECIALISTS = (
    {
        "id": "macro",
        "name": "Macro & Bancos Centrais",
        "domain": "trading",
        "keywords": (
            "cpi","pce","payroll","nfp","fed","fomc","ecb","bce","boe","boj",
            "juros","inflacao","inflação","pib","gdp","pmi","ism","macro",
            "dxy","treasury","yield",
        ),
        "evidence": ("official_macro", "calendar", "market_reaction"),
    },
    {
        "id": "market_structure",
        "name": "Trading & Estrutura de Mercado",
        "domain": "trading",
        "keywords": (
            "trading","trade","forex","fvg","order block","breaker","ict","smc",
            "liquidez","liquidity","bos","choch","swing","judas","vwap",
            "radar","setup","entrada","stop","alvo",
        ),
        "evidence": ("market_data", "technical_state", "backtest"),
    },
    {
        "id": "research",
        "name": "Deep Research & Evidências",
        "domain": "research",
        "keywords": (
            "pesquisa","research","compare","comparar","investigue","investigar",
            "fonte","evidencia","evidência","estudo","documento","noticia","notícia",
            "geopolit","tendencia","tendência",
        ),
        "evidence": ("primary_sources", "independent_sources", "recency"),
    },
    {
        "id": "security",
        "name": "Segurança, Privacidade & Guardian",
        "domain": "laboratory",
        "keywords": (
            "seguranca","segurança","privacidade","vazamento","espionar","hack",
            "ataque","guardian","permissao","permissão","senha","chave","secret",
            "offline","criptografia","telemetria",
        ),
        "evidence": ("runtime_security", "policy", "integrity"),
    },
    {
        "id": "development",
        "name": "Desenvolvimento & Arquitetura",
        "domain": "development",
        "keywords": (
            "codigo","código","github","render","deploy","bug","erro","teste",
            "interface","api","banco","database","arquitetura","app","sistema",
            "implement","desenvolv",
        ),
        "evidence": ("repository", "tests", "runtime_identity"),
    },
    {
        "id": "memory",
        "name": "Memória, Continuidade & Aprendizado",
        "domain": "secretary",
        "keywords": (
            "memoria","memória","lembra","checkpoint","aprend","evoluir",
            "continuidade","onde paramos","historico","histórico","conhecimento",
            "sabedoria","wisdom","esquecer",
        ),
        "evidence": ("checkpoint", "canonical_memory", "learning_history"),
    },
    {
        "id": "business",
        "name": "Negócios, Vendas & Growth",
        "domain": "business",
        "keywords": (
            "venda","vendas","produto","mercado livre","tiktok shop","margem",
            "receita","marketing","anuncio","anúncio","cliente","fornecedor",
            "digital","growth","conversao","conversão",
        ),
        "evidence": ("sales_data", "marketplace_data", "cost_margin"),
    },
    {
        "id": "studio",
        "name": "Studio & Conteúdo",
        "domain": "studio",
        "keywords": (
            "video","vídeo","imagem","roteiro","instagram","youtube","tiktok",
            "post","publicar","conteudo","conteúdo","thumbnail","capa","legenda",
        ),
        "evidence": ("brief", "brand_rules", "publication_status"),
    },
)


def _clean(value: Any, limit: int = 1200) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _norm(value: Any) -> str:
    raw = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(ch for ch in raw if not unicodedata.combining(ch)).casefold().strip()


def _truth(value: Any) -> str:
    out = _clean(value, 40).upper()
    return out if out in TRUTH_STATES else "UNKNOWN"


def _domain_boost(specialist: Mapping[str, Any], domain_hint: str) -> int:
    domain = _norm(specialist.get("domain"))
    hint = _norm(domain_hint)
    if not hint:
        return 0
    if domain == hint:
        return 8
    if hint == "central":
        return 1
    return 0


def route_specialists(
    question: Any,
    *,
    domain_hint: Any = "",
    max_specialists: int = 5,
) -> dict[str, Any]:
    text = _norm(question)
    scored: list[dict[str, Any]] = []
    for spec in SPECIALISTS:
        matches = [kw for kw in spec["keywords"] if _norm(kw) in text]
        score = len(matches) * 10 + _domain_boost(spec, str(domain_hint or ""))
        if score > 0:
            scored.append({
                "id": spec["id"],
                "name": spec["name"],
                "domain": spec["domain"],
                "score": score,
                "matched_terms": matches[:8],
                "evidence_requirements": list(spec["evidence"]),
            })

    if not scored:
        defaults = [
            spec for spec in SPECIALISTS
            if spec["id"] in {"research", "memory"}
        ]
        scored = [{
            "id": spec["id"],
            "name": spec["name"],
            "domain": spec["domain"],
            "score": 1,
            "matched_terms": [],
            "evidence_requirements": list(spec["evidence"]),
        } for spec in defaults]

    scored.sort(key=lambda row: (-int(row["score"]), str(row["id"])))
    selected = scored[: max(1, min(int(max_specialists), 8))]
    cross_domain = len({row["domain"] for row in selected}) > 1

    return {
        "schema": SCHEMA,
        "question": _clean(question, 1200),
        "domain_hint": _clean(domain_hint, 80),
        "selected": selected,
        "selected_count": len(selected),
        "cross_domain": cross_domain,
        "critic_required": True,
        "research_specialist_selected": any(x["id"] == "research" for x in selected),
        "executes_model_call": False,
        "executes_action": False,
    }


def build_research_plan(
    question: Any,
    *,
    specialists: Sequence[Mapping[str, Any]] | None,
    system_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    system = dict(system_context or {})
    selected = [dict(x) for x in list(specialists or []) if isinstance(x, Mapping)]
    evidence_types: list[str] = []
    for row in selected:
        for item in list(row.get("evidence_requirements") or []):
            item = _clean(item, 80)
            if item and item not in evidence_types:
                evidence_types.append(item)

    reliability = (
        system.get("reliability")
        if isinstance(system.get("reliability"), Mapping)
        else {}
    )
    degraded = (
        reliability.get("degraded_mode")
        if isinstance(reliability.get("degraded_mode"), Mapping)
        else {}
    )
    source_mesh = (
        system.get("source_mesh")
        if isinstance(system.get("source_mesh"), Mapping)
        else {}
    )

    market_live = bool(source_mesh.get("market_live_confirmed", False))
    degraded_state = _clean(degraded.get("state") or "UNKNOWN", 60).upper()
    q = _norm(question)
    time_sensitive = any(term in q for term in (
        "agora","hoje","atual","tempo real","latest","recente","noticia","notícia",
        "mercado","cotacao","cotação","evento","geopolit",
    ))

    steps: list[dict[str, Any]] = [
        {
            "stage": "DECOMPOSE",
            "instruction": "Dividir a pergunta em subproblemas verificáveis sem criar fatos.",
        },
        {
            "stage": "RETRIEVE",
            "instruction": (
                "Buscar evidência primária/canônica para cada subproblema; "
                "fontes secundárias devem ser identificadas como tais."
            ),
        },
        {
            "stage": "CROSS_CHECK",
            "instruction": (
                "Comparar fontes independentes e preservar conflitos em vez de escolher silenciosamente."
            ),
        },
        {
            "stage": "CRITIC",
            "instruction": (
                "Verificar afirmações, proveniência, frescor, contradições e lacunas antes da síntese."
            ),
        },
        {
            "stage": "SYNTHESIZE",
            "instruction": (
                "Responder separando CONFIRMED, INFERENCE, HYPOTHESIS e UNKNOWN."
            ),
        },
    ]

    blockers: list[str] = []
    if degraded_state == "FAIL_CLOSED":
        blockers.append("Reliability está FAIL_CLOSED; capacidades sensíveis devem permanecer bloqueadas.")
    if time_sensitive and not market_live:
        blockers.append("Pergunta é sensível a tempo, mas mercado/live data não está confirmado.")

    return {
        "schema": SCHEMA,
        "question": _clean(question, 1200),
        "steps": steps,
        "required_evidence_types": evidence_types,
        "time_sensitive": time_sensitive,
        "market_live_confirmed": market_live,
        "reliability_state": degraded_state,
        "blockers": blockers,
        "minimum_independent_sources": 2 if time_sensitive else 1,
        "stop_when": (
            "Evidência suficiente para separar fato, inferência, hipótese e desconhecido; "
            "conflitos relevantes explicitados."
        ),
        "web_research_executed": False,
        "external_model_executed": False,
        "executes_action": False,
    }


def verify_claims(
    claims: Sequence[Mapping[str, Any]] | None,
    *,
    evidence: Sequence[Mapping[str, Any]] | None = None,
    reliability: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    rows = [dict(x) for x in list(claims or []) if isinstance(x, Mapping)]
    ev = [dict(x) for x in list(evidence or []) if isinstance(x, Mapping)]
    audit = evidence_audit(ev)
    confidence = evidence_confidence(audit)

    reliability_map = dict(reliability or {})
    degraded = (
        reliability_map.get("degraded_mode")
        if isinstance(reliability_map.get("degraded_mode"), Mapping)
        else {}
    )
    degraded_state = _clean(degraded.get("state") or "UNKNOWN", 60).upper()

    issues: list[dict[str, Any]] = []
    verified: list[dict[str, Any]] = []
    for idx, claim in enumerate(rows):
        text = _clean(claim.get("claim") or claim.get("text"), 900)
        truth = _truth(claim.get("truth_state") or claim.get("kind"))
        refs = [
            _clean(x, 180) for x in list(claim.get("source_refs") or [])
            if _clean(x, 180)
        ]
        action_claim = bool(claim.get("external_action_claim", False))
        if not text:
            continue
        claim_issues: list[str] = []
        if truth == "CONFIRMED" and not refs:
            claim_issues.append("CONFIRMED_WITHOUT_SOURCE")
        if action_claim and not refs:
            claim_issues.append("ACTION_CLAIM_WITHOUT_EVIDENCE")
        if degraded_state == "FAIL_CLOSED" and bool(claim.get("sensitive", False)):
            claim_issues.append("SENSITIVE_CLAIM_DURING_FAIL_CLOSED")
        if truth == "UNKNOWN" and bool(claim.get("assertive_wording", False)):
            claim_issues.append("UNKNOWN_STATED_ASSERTIVELY")

        result = {
            "index": idx,
            "claim": text,
            "truth_state": truth,
            "source_refs": refs,
            "issues": claim_issues,
            "passes": not claim_issues,
        }
        verified.append(result)
        for issue in claim_issues:
            issues.append({"claim": text, "issue": issue})

    if any(item["issue"] in {
        "ACTION_CLAIM_WITHOUT_EVIDENCE",
        "SENSITIVE_CLAIM_DURING_FAIL_CLOSED",
    } for item in issues):
        state = "BLOCK"
    elif issues or int(audit.get("conflict_count") or 0) > 0:
        state = "REVISE"
    elif rows:
        state = "PASS"
    else:
        state = "NO_CLAIMS"

    return {
        "schema": SCHEMA,
        "state": state,
        "claims": verified,
        "claim_count": len(verified),
        "issue_count": len(issues),
        "issues": issues,
        "evidence_audit": audit,
        "evidence_confidence": confidence,
        "reliability_state": degraded_state,
        "private_chain_of_thought_exposed": False,
        "executes_action": False,
        "real_orders_enabled": False,
    }


def orchestrator_snapshot(
    question: Any,
    *,
    domain_hint: Any = "",
    memory_hits: Sequence[Mapping[str, Any]] | None = None,
    system_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    routing = route_specialists(question, domain_hint=domain_hint)
    plan = build_research_plan(
        question,
        specialists=routing["selected"],
        system_context=system_context,
    )
    hits = [dict(x) for x in list(memory_hits or [])[:8] if isinstance(x, Mapping)]
    memory_sources = [
        _clean(hit.get("path") or hit.get("source") or "memory", 180)
        for hit in hits
    ]

    if plan["blockers"]:
        readiness = "RESEARCH_REQUIRED"
    elif hits:
        readiness = "READY_FOR_EVIDENCE_REVIEW"
    else:
        readiness = "RESEARCH_REQUIRED"

    return {
        "schema": SCHEMA,
        "question": _clean(question, 1200),
        "routing": routing,
        "research_plan": plan,
        "memory_evidence_count": len(hits),
        "memory_sources": memory_sources,
        "readiness": readiness,
        "critic_gate": {
            "required": True,
            "must_check": [
                "provenance",
                "freshness",
                "source independence",
                "contradictions",
                "unsupported factual claims",
                "action claims",
                "truth-state wording",
            ],
        },
        "synthesis_contract": {
            "show_conclusion": True,
            "show_evidence": True,
            "show_conflicts": True,
            "show_unknowns": True,
            "show_private_chain_of_thought": False,
        },
        "automatic_web_research": False,
        "automatic_external_model_call": False,
        "automatic_action": False,
        "real_orders_enabled": False,
    }


__all__ = [
    "SCHEMA",
    "TRUTH_STATES",
    "SPECIALISTS",
    "route_specialists",
    "build_research_plan",
    "verify_claims",
    "orchestrator_snapshot",
]
