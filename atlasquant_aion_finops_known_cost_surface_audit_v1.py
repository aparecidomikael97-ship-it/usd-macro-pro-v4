"""AION known live-cost entrypoint inventory, static source review V1.

Read-only, narrow allowlisted source audit. It is NOT a live billing inventory,
complete codebase call graph, authentication, execution guard or deployment.
Findings describe only inspected source text; never approve production spend.
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
from typing import Any, Mapping

SCHEMA = "ATLASQUANT_AION_FINOPS_KNOWN_COST_SOURCE_AUDIT_V1"
SOURCE_PATHS = (
    "render.yaml",
    "requirements.txt",
    "atlasquant_aion_provider.py",
    "atlasquant_aion_model_gateway_v2.py",
    "atlasquant_aion_finops_metering.py",
    "atlasquant_aion_owner_brl200_finops_ceiling_v1.py",
    "atlasquant_aion_finops_ephemeral_sqlite_reservation_cas_v1.py",
    "atlasquant_aion_chat_render_production_composition_v1.py",
)
CHECKS = (
    "KNOWN_OPENAI_HTTP_POST",
    "OPENAI_ADAPTER_HAS_USD_ESTIMATE_GATE",
    "OPENAI_ADAPTER_CONNECTED_TO_BRL200_OWNER_PREFLIGHT",
    "OPENAI_ADAPTER_CONNECTED_TO_DURABLE_OWNER_RESERVATION",
    "OPENAI_ADAPTER_APPROVAL_BOOLEAN_EXISTS",
    "MODEL_GATEWAY_LOCAL_DETERMINISTIC_LANE",
    "MODEL_GATEWAY_PRICE_DENOMINATED_USD",
    "FINOPS_EXISTING_USD_ADMISSION",
    "OWNER_BRL200_CONTRACT_PRESENT",
    "OWNER_RESERVATION_CI_ONLY",
    "RENDER_AUTODEPLOY_EXPLICITLY_OFF",
    "RENDER_REAL_WEB_SERVICE_DEFINED",
    "REQUIREMENTS_CONTAINS_HTTP_CLIENT",
    "CHAT_PRODUCTION_PERSISTENCE_OPT_IN",
)
FLAG_FIELDS = (
    "real_provider_invoice_inventory_complete",
    "owner_brl200_cap_enforced_on_actual_openai_post",
    "real_paid_api_spend_intercepted",
    "live_paid_provider_allowlist_complete",
    "cloud_service_billing_proven_zero",
    "local_llm_model_running_on_owner_pc",
    "full_codebase_network_effects_audited",
    "owner_approval_verified",
    "production_enforcement_deployed",
    "billable_api_called_during_scan",
    "owner_device_accessed",
    "secrets_examined_or_exported",
    "deploy_executed",
    "worker_activated",
)
MAX_TEXT = 512_000


def _find_function(tree: ast.AST, name: str) -> ast.FunctionDef | None:
    for node in getattr(tree, "body", ()):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def _calls(fn: ast.FunctionDef | None) -> set[str]:
    if fn is None:
        return set()
    names = set()
    for n in ast.walk(fn):
        if isinstance(n, ast.Call):
            target=n.func
            if isinstance(target, ast.Name):
                names.add(target.id)
            elif isinstance(target, ast.Attribute):
                names.add(target.attr)
    return names


def _parse_sources(sources: Any) -> tuple[dict[str, ast.Module], dict[str, str], list[str]]:
    errors: list[str] = []
    if not isinstance(sources, Mapping) or set(sources) != set(SOURCE_PATHS):
        return {}, {}, ["EXACT_KNOWN_SOURCE_SET_REQUIRED"]
    parsed: dict[str, ast.Module] = {}
    text: dict[str, str] = {}
    for name in SOURCE_PATHS:
        source=sources[name]
        if type(source) is not str or not 1 <= len(source) <= MAX_TEXT:
            errors.append("SOURCE_NOT_TEXT_OR_TOO_LARGE:" + name)
            continue
        if "\x00" in source:
            errors.append("SOURCE_CONTAINS_NULL:" + name)
            continue
        text[name]=source
        if name.endswith(".py"):
            try:
                parsed[name]=ast.parse(source, filename=name)
            except (SyntaxError, MemoryError, RecursionError, ValueError):
                errors.append("SOURCE_PYTHON_AST_INVALID:" + name)
    return parsed, text, errors


def known_cost_source_audit(sources: Any) -> dict[str, Any]:
    """Explain observable missing enforcement; FAIL CLOSED for incomplete input."""
    parsed, src, errors = _parse_sources(sources)
    found: dict[str, bool] = {name: False for name in CHECKS}
    adapter = parsed.get("atlasquant_aion_provider.py")
    provider_fn = _find_function(adapter,"execute_openai_answer") if adapter else None
    provider_calls=_calls(provider_fn)
    found["KNOWN_OPENAI_HTTP_POST"] = "post" in provider_calls and (
        "OPENAI_RESPONSES_URL" in src.get("atlasquant_aion_provider.py","")
    )
    found["OPENAI_ADAPTER_HAS_USD_ESTIMATE_GATE"] = (
        "budget_decision" in provider_calls and "estimate_request_cost" in provider_calls
    )
    found["OPENAI_ADAPTER_CONNECTED_TO_BRL200_OWNER_PREFLIGHT"] = (
        "preflight_owner_paid_request" in provider_calls
    )
    found["OPENAI_ADAPTER_CONNECTED_TO_DURABLE_OWNER_RESERVATION"] = (
        # Only the presence of the named call: still NOT evidence of secure binding.
        "reserve_owner_paid_request" in provider_calls
    )
    found["OPENAI_ADAPTER_APPROVAL_BOOLEAN_EXISTS"] = bool(
        provider_fn and {a.arg for a in provider_fn.args.kwonlyargs}
        >= {"request_approved","external_feature_enabled"}
    )
    g=src.get("atlasquant_aion_model_gateway_v2.py","")
    gate=parsed.get("atlasquant_aion_model_gateway_v2.py")
    found["MODEL_GATEWAY_LOCAL_DETERMINISTIC_LANE"] = bool(
        _find_function(gate,"route_model_request") if gate else None
    ) and "LOCAL_DETERMINISTIC" in g
    found["MODEL_GATEWAY_PRICE_DENOMINATED_USD"] = "budget_remaining_usd" in g
    m=src.get("atlasquant_aion_finops_metering.py","")
    found["FINOPS_EXISTING_USD_ADMISSION"] = (
        "window_budget_usd" in m
        and bool(_find_function(parsed.get("atlasquant_aion_finops_metering.py"),
                                "evaluate_finops_budget"))
    )
    b=src.get("atlasquant_aion_owner_brl200_finops_ceiling_v1.py","")
    found["OWNER_BRL200_CONTRACT_PRESENT"] = bool(re.search(
        r"^HARD_CAP_CENTS\s*=\s*20_?000\s*$",b,re.M
    )) and "preflight_owner_paid_request" in b
    reserve=src.get("atlasquant_aion_finops_ephemeral_sqlite_reservation_cas_v1.py","")
    found["OWNER_RESERVATION_CI_ONLY"] = (
        "AION_FINOPS_CI_EPHEMERAL" in reserve and
        "GITHUB_EVENT_NAME" in reserve and
        "BEGIN IMMEDIATE" in reserve
    )
    render=src.get("render.yaml","")
    # This checks only a text blueprint; it DOES NOT query Render settings.
    found["RENDER_AUTODEPLOY_EXPLICITLY_OFF"] = bool(re.search(
        r"(?m)^\s*autoDeployTrigger:\s*off\s*$",render
    ))
    found["RENDER_REAL_WEB_SERVICE_DEFINED"] = bool(
        re.search(r"(?m)^\s*-\s*type:\s*web\s*$",render)
        and re.search(r"(?m)^\s*runtime:\s*python\s*$",render)
    )
    req=src.get("requirements.txt","")
    found["REQUIREMENTS_CONTAINS_HTTP_CLIENT"] = bool(re.search(
        r"(?m)^\s*requests(?:[=><!~]|\s|$)",req
    ))
    pg=src.get("atlasquant_aion_chat_render_production_composition_v1.py","")
    found["CHAT_PRODUCTION_PERSISTENCE_OPT_IN"] = (
        "AION_CHAT_PRODUCTION_PERSISTENCE_ENABLED" in pg
        and "resolve_production_postgres_config" in pg
    )
    if not found["KNOWN_OPENAI_HTTP_POST"]:
        errors.append("KNOWN_EXTERNAL_CALL_TARGET_UNRESOLVED")
    if not found["OPENAI_ADAPTER_HAS_USD_ESTIMATE_GATE"]:
        errors.append("EXISTING_PROVIDER_COST_GATE_UNRESOLVED")
    if not found["RENDER_AUTODEPLOY_EXPLICITLY_OFF"]:
        errors.append("RENDER_AUTODEPLOY_NOT_DEMONSTRABLY_OFF")
    if not found["OWNER_BRL200_CONTRACT_PRESENT"]:
        errors.append("OWNER_200_CAP_CONTRACT_NOT_FOUND")
    if not found["OWNER_RESERVATION_CI_ONLY"]:
        errors.append("CI_RESERVATION_BOUNDARY_UNEXPECTED")
    if not found["MODEL_GATEWAY_LOCAL_DETERMINISTIC_LANE"]:
        errors.append("LOCAL_DETERMINISTIC_ROUTER_NOT_FOUND")
    errors=list(dict.fromkeys(errors))
    # Distinguish expected findings from errors: missing real BRL binding is
    # a HIGH-priority review item, not a reason to fail source audit itself.
    findings=[]
    if found["KNOWN_OPENAI_HTTP_POST"] and not found["OPENAI_ADAPTER_CONNECTED_TO_BRL200_OWNER_PREFLIGHT"]:
        findings.append({
            "code":"LIVE_OPENAI_POST_NOT_DIRECTLY_BOUND_TO_OWNER_BRL200_PREFLIGHT",
            "priority":"HIGH",
            "path":"atlasquant_aion_provider.py",
            "scope":"KNOWN_ADAPTER_ONLY",
        })
    if found["KNOWN_OPENAI_HTTP_POST"] and not found["OPENAI_ADAPTER_CONNECTED_TO_DURABLE_OWNER_RESERVATION"]:
        findings.append({
            "code":"LIVE_OPENAI_POST_NOT_DIRECTLY_BOUND_TO_DURABLE_OWNER_RESERVATION",
            "priority":"HIGH",
            "path":"atlasquant_aion_provider.py",
            "scope":"KNOWN_ADAPTER_ONLY",
        })
    if found["RENDER_REAL_WEB_SERVICE_DEFINED"]:
        findings.append({
            "code":"RENDER_BLUEPRINT_PRESENT_BILLING_TIER_UNVERIFIED",
            "priority":"REQUIRES_REAL_BILLING_REVIEW",
            "path":"render.yaml",
            "scope":"CONFIGURATION_NOT_CURRENT_PROVIDER_STATE",
        })
    if found["CHAT_PRODUCTION_PERSISTENCE_OPT_IN"]:
        findings.append({
            "code":"POTENTIAL_POSTGRES_MONTHLY_CHARGE_AND_CREDENTIAL_SCOPE_REVIEW",
            "priority":"REQUIRES_REAL_BILLING_REVIEW",
            "path":"atlasquant_aion_chat_render_production_composition_v1.py",
            "scope":"CODE_NOT_DATABASE_PROVISIONING_EVIDENCE",
        })
    if found["MODEL_GATEWAY_LOCAL_DETERMINISTIC_LANE"]:
        findings.append({
            "code":"LOCAL_DETERMINISTIC_IS_NOT_PROOF_OF_LOCAL_LLM_INFERENCE",
            "priority":"HARDWARE_AND_MODEL_TEST_REQUIRED",
            "path":"atlasquant_aion_model_gateway_v2.py",
            "scope":"PLANNING_ROUTER_ONLY",
        })
    return {
        "schema":SCHEMA,
        "state":"BLOCKED" if errors else "KNOWN_COST_SURFACES_STATIC_REVIEW_REQUIRED",
        "blockers":errors,
        "source_file_count":len(src),
        "checks":found,
        "findings":findings if not errors else [],
        "source_sha256":{
            k:hashlib.sha256(src[k].encode("utf-8")).hexdigest()
            for k in sorted(src)
        },
        "no_real_spend_or_invoice_amounts_discovered":True,
        "static_source_only":True,
        **{f:False for f in FLAG_FIELDS},
    }
