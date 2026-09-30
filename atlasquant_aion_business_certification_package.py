"""AION BUSINESS certification evidence package.

Pure/offline. This module binds the approved BUSINESS product scope to technical
specialist evidence without activating runtime or performing external actions.
A valid CI attestation can move BUSINESS to TESTED; exact human review is still
required for CERTIFIED, and certification still does not activate runtime.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence
import re

from atlasquant_aion_core_validation import (
    BUSINESS_REQUIRED_GATES,
    business_certification_readiness,
)
from atlasquant_aion_specialist_certification import (
    assess_specialist_certification,
    evidence_fingerprint,
)
from atlasquant_aion_specialist_router import (
    evaluate_specialist_request,
    present_domain_evidence,
    route_specialist,
)

SCHEMA = "ATLASQUANT_AION_BUSINESS_CERTIFICATION_PACKAGE_V1"
VERSION = "1"
ATTESTATION_SCHEMA = "ATLASQUANT_AION_BUSINESS_TEST_ATTESTATION_V1"
SUITE = "test_atlasquant_aion_business_certification_package.py"
PROVENANCE = "github-actions:aion-business-certification-package-v1"
EVIDENCE_ID = "AION-BUSINESS-CERTIFICATION-PACKAGE-V1"
MAX_REFS = 20
_SHA = re.compile(r"^[0-9a-f]{7,64}$")

PRIMARY_ENGINES = (
    {
        "id": "B2B_AUTOMATION",
        "name": "Automação B2B e Agentes de IA",
        "purpose": "Diagnosticar gargalos e preparar automações de atendimento, operação e produtividade.",
    },
    {
        "id": "AION_MICRO_SAAS",
        "name": "Micro-SaaS / Software próprio com AION",
        "purpose": "Transformar capacidades validadas em software recorrente com escopo controlado.",
    },
    {
        "id": "AI_SERVICES",
        "name": "Serviços de IA",
        "purpose": "Entregar implantação, conteúdo, automação e melhoria operacional para empresas.",
    },
    {
        "id": "REVENUE_OPS",
        "name": "Revenue Operations e Captação",
        "purpose": "Organizar lead, qualificação, follow-up, conversão, retenção e indicadores comerciais.",
    },
    {
        "id": "DIGITAL_PRODUCTS",
        "name": "Produtos Digitais Próprios",
        "purpose": "Criar ativos digitais próprios somente depois de escopo, demonstração e qualidade validados.",
    },
)

STARTER_BUNDLE = {
    "id": "AION_PRESENCA_CONVERSAO",
    "name": "AION Presença & Conversão",
    "provisional_name": True,
    "components": (
        "conteudo_e_criativos",
        "atendimento_inicial_e_faq",
        "reativacao_e_followup_de_leads",
        "relatorio_simples_de_resultados",
    ),
    "delivery_model": "MANAGED_HYBRID",
    "recurrence_model": "IMPLANTACAO_MAIS_MANUTENCAO",
}

CLIENT_OPERATING_LAYER = (
    "diagnostico_da_empresa",
    "radar_do_negocio",
    "portal_do_cliente",
    "onboarding_e_checklist",
    "suporte_e_sla",
    "saude_do_cliente",
    "central_financeira_e_margem",
    "lgpd_privacidade_e_consentimento",
    "auditoria_e_rollback",
    "hub_de_integracoes",
    "demo_sandbox",
    "capacidade_e_quotas_por_cliente",
    "treinamento_do_administrador",
)

EXCLUDED_PRIMARY_LEGACY = (
    "dropshipping",
    "afiliados",
    "marketplace_shopee",
    "marketplace_mercado_livre",
    "tiktok_shop_como_motor_principal",
    "ecommerce_generico",
)


def _exact_true(value: Any) -> bool:
    return type(value) is bool and value is True


def _clean(value: Any, limit: int = 240) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _refs(values: Any) -> list[str]:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes, bytearray)):
        return []
    out: list[str] = []
    for raw in list(values)[:MAX_REFS]:
        value = _clean(raw, 300)
        if value and value not in out:
            out.append(value)
    return sorted(out)


def business_primary_scope() -> dict[str, Any]:
    """Canonical product scope used by the BUSINESS certification package."""
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "specialist": "BUSINESS",
        "engines": [dict(item) for item in PRIMARY_ENGINES],
        "starter_bundle": {
            **STARTER_BUNDLE,
            "components": list(STARTER_BUNDLE["components"]),
        },
        "client_operating_layer": list(CLIENT_OPERATING_LAYER),
        "excluded_primary_legacy": list(EXCLUDED_PRIMARY_LEGACY),
        "legacy_marketplace_code_may_remain_for_compatibility": True,
        "legacy_marketplace_is_primary_scope": False,
        "commercial_model": "PACOTE_FECHADO_COM_IMPLANTACAO_E_RECORRENCIA",
        "simple_client_experience": True,
        "complexity_stays_inside_aion": True,
        "promises_revenue": False,
        "executes_action": False,
    }


def _routing_probe() -> dict[str, Any]:
    selected = route_specialist(domain="BUSINESS")
    ambiguous = route_specialist(intent="business e investimentos")
    return {
        "correct_specialist_selected": (
            selected.get("status") == "SELECTED"
            and selected.get("specialist") == "BUSINESS_EXPERT"
            and selected.get("domain") == "BUSINESS"
        ),
        "ambiguous_not_silently_selected": (
            ambiguous.get("status") == "CLARIFICATION_REQUIRED"
            and ambiguous.get("specialist") is None
            and ambiguous.get("silent_fallback") is False
        ),
    }


def _isolation_probe() -> dict[str, Any]:
    foreign = {"domain": "TRADER", "truth_state": "UNKNOWN", "claim": "market note"}
    blocked = present_domain_evidence(
        foreign,
        target_domain="BUSINESS",
        accessor_profile="BUSINESS_EXPERT",
        explicit_domains=["TRADER"],
    )
    core = present_domain_evidence(
        foreign,
        target_domain="BUSINESS",
        accessor_profile="AION_CORE",
        explicit_domains=["TRADER"],
    )
    return {
        "memory_separated": blocked.get("visible") is False,
        "evidence_separated": (
            blocked.get("visible") is False
            and core.get("visible") is True
            and core.get("promoted") is False
            and core.get("used_as_current_fact") is False
        ),
        "automatic_cross_domain_access": bool(
            blocked.get("automatic_cross_domain_access")
            or core.get("automatic_cross_domain_access")
        ),
    }


def _permission_probe() -> dict[str, Any]:
    selected = route_specialist(domain="BUSINESS")
    decision = evaluate_specialist_request(
        selected,
        requested_roles=["ADMIN", "SALES"],
        requested_tools=["payment", "publish", "external_contact"],
        requested_scopes=["business.read", "business.analyze", "*", "payments.write"],
        requested_actions=["payment", "publish", "external_contact", "sign_contract"],
        guardian_scopes=["business.read", "business.analyze"],
        runtime_enabled=False,
    )
    forbidden_grant = bool(
        decision.get("granted_roles")
        or decision.get("granted_tools")
        or decision.get("granted_scopes")
        or decision.get("granted_actions")
    )
    return {
        "scope_escalated": bool(decision.get("scope_escalated")) or forbidden_grant,
        "role_escalated": bool(decision.get("role_escalated")) or forbidden_grant,
        "undeclared_tool": bool(decision.get("tool_escalated")) or bool(decision.get("granted_tools")),
    }


def _truth_probe() -> dict[str, Any]:
    states = ("UNKNOWN", "STALE", "CONFLICT", "INCOMPLETE")
    observed: dict[str, dict[str, Any]] = {}
    for truth in states:
        observed[truth] = present_domain_evidence(
            {"domain": "BUSINESS", "truth_state": truth, "claim": "business evidence"},
            target_domain="BUSINESS",
            accessor_profile="BUSINESS_EXPERT",
        )
    return {
        "unknown_promoted": observed["UNKNOWN"].get("truth_state") != "UNKNOWN" or observed["UNKNOWN"].get("promoted") is True,
        "stale_promoted": observed["STALE"].get("truth_state") != "STALE" or observed["STALE"].get("promoted") is True,
        "conflict_resolved_silently": observed["CONFLICT"].get("truth_state") != "CONFLICT" or observed["CONFLICT"].get("promoted") is True,
        "incomplete_promoted": observed["INCOMPLETE"].get("truth_state") != "INCOMPLETE" or observed["INCOMPLETE"].get("promoted") is True,
    }


def _safety_probe() -> dict[str, Any]:
    selected = route_specialist(domain="BUSINESS")
    decision = evaluate_specialist_request(
        selected,
        requested_tools=["real_trade", "payment", "publish", "deploy", "external_contact"],
        requested_actions=["real_trade", "payment", "publication", "deploy", "external_contact"],
        runtime_enabled=False,
    )
    side_effect = bool(
        selected.get("external_action_executed")
        or decision.get("external_action_executed")
        or selected.get("executes_action")
        or decision.get("executes_action")
    )
    return {
        "real_trading_enabled": bool(selected.get("real_trading_enabled") or decision.get("real_trading_enabled")),
        "payment_executed": bool(selected.get("payment_executed") or decision.get("payment_executed")),
        "publication_executed": bool(selected.get("publication_executed") or decision.get("publication_executed")),
        "deploy_executed": bool(selected.get("deploy_executed") or decision.get("deploy_executed")),
        "external_side_effects": side_effect,
    }


def business_technical_probe() -> dict[str, Any]:
    """Collect deterministic local evidence without provider or external write."""
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "specialist": "BUSINESS",
        "routing": _routing_probe(),
        "isolation": _isolation_probe(),
        "permissions": _permission_probe(),
        "truth": _truth_probe(),
        "safety": _safety_probe(),
        "provider_called": False,
        "external_write": False,
        "runtime_activated": False,
    }


def normalize_ci_attestation(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    data = dict(raw or {}) if isinstance(raw, Mapping) else {}
    sha = _clean(data.get("sha"), 80).lower()
    refs = _refs(data.get("refs"))
    valid = (
        data.get("schema") == ATTESTATION_SCHEMA
        and data.get("state") == "VERIFIED"
        and _exact_true(data.get("tests_passed"))
        and _exact_true(data.get("evidence_verified"))
        and _exact_true(data.get("provenance_verified"))
        and _clean(data.get("specialist"), 40).upper() == "BUSINESS"
        and _clean(data.get("version"), 80) == VERSION
        and _clean(data.get("suite"), 180) == SUITE
        and _clean(data.get("provenance"), 240) == PROVENANCE
        and _clean(data.get("evidence_id"), 80) == EVIDENCE_ID
        and bool(_SHA.fullmatch(sha))
        and bool(refs)
    )
    count = data.get("test_count")
    test_count = count if isinstance(count, int) and not isinstance(count, bool) and count > 0 else 0
    return {
        "schema": ATTESTATION_SCHEMA,
        "state": "VERIFIED" if valid else "REJECTED",
        "valid": valid,
        "tests_passed": valid,
        "evidence_verified": valid,
        "provenance_verified": valid,
        "specialist": "BUSINESS",
        "version": VERSION,
        "suite": SUITE,
        "provenance": PROVENANCE,
        "evidence_id": EVIDENCE_ID,
        "sha": sha if bool(_SHA.fullmatch(sha)) else "",
        "refs": refs,
        "fingerprint": _clean(data.get("fingerprint"), 128).lower(),
        "test_count": test_count,
    }


def build_business_specialist_evidence(
    ci_attestation: Mapping[str, Any] | None,
) -> dict[str, Any]:
    probe = business_technical_probe()
    attestation = normalize_ci_attestation(ci_attestation)
    tests_passed = attestation["valid"]
    evidence = {
        "version": VERSION,
        "routing": dict(probe["routing"]),
        "isolation": dict(probe["isolation"]),
        "permissions": dict(probe["permissions"]),
        "truth": dict(probe["truth"]),
        "safety": dict(probe["safety"]),
        "tests": {
            "state": "PASS" if tests_passed else "NOT_EVIDENCED",
            "passed": tests_passed,
            "suite": SUITE,
            "provenance": PROVENANCE,
            "version": VERSION,
            "sha": attestation["sha"],
            "refs": list(attestation["refs"]),
            "evidence_id": EVIDENCE_ID,
            "fingerprint": "",
        },
    }
    evidence["tests"]["fingerprint"] = evidence_fingerprint(evidence, specialist="BUSINESS")
    return evidence


def business_attestation_verifier(
    ci_attestation: Mapping[str, Any] | None,
):
    """Create a verifier bound to caller-supplied CI evidence, not payload claims."""
    attestation = normalize_ci_attestation(ci_attestation)

    def verify(envelope: Mapping[str, Any]) -> dict[str, Any]:
        claimed = _clean(envelope.get("claimed_fingerprint"), 128).lower()
        calculated = _clean(envelope.get("fingerprint"), 128).lower()
        refs = _refs(envelope.get("refs"))
        valid = bool(
            attestation["valid"]
            and claimed
            and calculated
            and claimed == calculated
            and attestation["fingerprint"] == calculated
            and attestation["sha"] == _clean(envelope.get("sha"), 80).lower()
            and attestation["refs"] == refs
            and _clean(envelope.get("specialist"), 40).upper() == "BUSINESS"
            and _clean(envelope.get("version"), 80) == VERSION
            and _clean(envelope.get("provenance"), 240) == PROVENANCE
        )
        body = envelope.get("body") if isinstance(envelope.get("body"), Mapping) else {}
        tests = body.get("tests") if isinstance(body.get("tests"), Mapping) else {}
        return {
            "state": "VERIFIED" if valid else "REJECTED",
            "fingerprint": calculated if valid else "",
            "provenance_verified": valid,
            "evidence_verified": valid,
            "specialist": "BUSINESS",
            "version": VERSION,
            "suite": SUITE,
            "evidence_id": _clean(tests.get("evidence_id"), 80) if valid else "",
            "bound_refs": list(refs) if valid else [],
            "sha": attestation["sha"] if valid else "",
        }

    return verify


def business_package_readiness(
    product_evidence: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Bind product readiness to the approved primary BUSINESS scope."""
    data = dict(product_evidence or {}) if isinstance(product_evidence, Mapping) else {}
    evidence = {name: data.get(name) for name in BUSINESS_REQUIRED_GATES}
    evidence["evidence_refs"] = data.get("evidence_refs")
    readiness = business_certification_readiness(evidence)
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "scope": business_primary_scope(),
        "readiness": readiness,
        "ready_for_certification_review": readiness.get("ready_for_certification_review") is True,
        "certification_state": "NOT_CERTIFIED",
        "runtime_activated": False,
        "executes_action": False,
    }


def assess_business_certification_package(
    *,
    product_evidence: Mapping[str, Any] | None,
    ci_attestation: Mapping[str, Any] | None,
    human_review_approved: Any = False,
) -> dict[str, Any]:
    """Assess BUSINESS while preserving product, technical and human gates."""
    product = business_package_readiness(product_evidence)
    evidence = build_business_specialist_evidence(ci_attestation)
    attestation = normalize_ci_attestation(ci_attestation)

    # Bind the supplied attestation to the exact evidence fingerprint. A caller
    # cannot gain TESTED/CERTIFIED by passing a generic green CI result.
    if attestation["fingerprint"] != evidence["tests"]["fingerprint"]:
        verifier = business_attestation_verifier(None)
    else:
        verifier = business_attestation_verifier(ci_attestation)

    technical = assess_specialist_certification(
        "BUSINESS",
        evidence,
        human_review_approved=human_review_approved,
        evidence_verifier=verifier,
    )
    product_ready = product["ready_for_certification_review"]
    if not product_ready:
        published_state = "NOT_READY"
    elif technical["state"] == "CERTIFIED":
        published_state = "CERTIFIED"
    elif technical["state"] == "TESTED":
        published_state = "TESTED"
    else:
        published_state = "READY_FOR_CERTIFICATION_REVIEW"

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "specialist": "BUSINESS",
        "state": published_state,
        "product": product,
        "technical": technical,
        "product_ready": product_ready,
        "technical_state": technical["state"],
        "human_review_approved": technical["human_review_approved"],
        "certification_state": "CERTIFIED" if published_state == "CERTIFIED" else "NOT_CERTIFIED",
        "runtime_capability_available": False,
        "runtime_activated": False,
        "external_action_executed": False,
        "payment_executed": False,
        "publication_executed": False,
        "deploy_executed": False,
        "real_trading_enabled": False,
        "authorizes_contract_signature": False,
        "authorizes_external_contact": False,
        "authorizes_spend": False,
        "authorizes_merge": False,
        "authorizes_deploy": False,
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "ATTESTATION_SCHEMA",
    "SUITE",
    "PROVENANCE",
    "EVIDENCE_ID",
    "PRIMARY_ENGINES",
    "STARTER_BUNDLE",
    "CLIENT_OPERATING_LAYER",
    "EXCLUDED_PRIMARY_LEGACY",
    "business_primary_scope",
    "business_technical_probe",
    "normalize_ci_attestation",
    "build_business_specialist_evidence",
    "business_attestation_verifier",
    "business_package_readiness",
    "assess_business_certification_package",
]
