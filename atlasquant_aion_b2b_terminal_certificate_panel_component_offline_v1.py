"""AION B2B terminal-certificate panel component offline V1.

Offline-only, static, read-only and fail-closed.

Consumes only the validated UI runtime binding view-model and renders escaped
static HTML. This component has no event handlers, no action controls, no
database/network/provider access and no authority semantics.

The component is not mounted into the production/reference interface in this
version.
"""
from __future__ import annotations

from collections.abc import Mapping
from html import escape
from typing import Any

import atlasquant_aion_b2b_terminal_certificate_read_model_ui_runtime_binding_offline_v1 as binding

SCHEMA = "ATLASQUANT_AION_B2B_TERMINAL_CERTIFICATE_PANEL_COMPONENT_OFFLINE_V1"
MODE = "OFFLINE_STATIC_READ_ONLY_TERMINAL_CERTIFICATE_PANEL_COMPONENT"
NEXT_ALLOWED_STEP = "INTEGRATE_TERMINAL_CERTIFICATE_PANEL_IN_REFERENCE_UI_DRAFT_ONLY"

DISPLAY_STATES = binding.DISPLAY_STATES
REQUIRED_UI_SECTIONS = binding.REQUIRED_UI_SECTIONS

STATE_LABELS = {
    "VERIFIED": "Evidência verificada",
    "MISMATCH": "Inconsistência detectada",
    "UNAVAILABLE": "Evidência indisponível",
    "STALE": "Evidência desatualizada",
}

STATE_MESSAGES = {
    "VERIFIED": "Somente evidência. Não autoriza execução.",
    "MISMATCH": "Fail-closed. A evidência não pode ser tratada como verificada.",
    "UNAVAILABLE": "Fail-closed. Evidência obrigatória não está disponível.",
    "STALE": "Fail-closed. Atualização da evidência é necessária.",
}

FORBIDDEN_HTML_TOKENS = (
    "<button",
    "<form",
    "<input",
    "<select",
    "<textarea",
    "<script",
    "<iframe",
    "<object",
    "<embed",
    "<a ",
    "href=",
    "onclick=",
    "onchange=",
    "onsubmit=",
    "javascript:",
)

FALSE_FIELDS = (
    "component_interactive",
    "action_controls_present",
    "execution_authority_created",
    "retry_authorized",
    "reopen_authorized",
    "reconciliation_authorized",
    "rollback_authorized",
    "compensation_authorized",
    "external_effect_authorized",
    "network_called",
    "provider_called",
    "external_action_executed",
    "billing_authorized",
    "billing_executed",
    "customer_contact_authorized",
    "crm_write_authorized",
    "provisioning_authorized",
    "deploy_authorized",
    "production_mutation_authorized",
    "production_mutation_performed",
    "execution_allowed",
    "execution_command_generated",
    "execution_command_executed",
    "executes_action",
)


def _safe_text(value: Any, limit: int = 4096) -> str:
    if value is None:
        return "—"
    text = " ".join(str(value).split())
    if not text:
        return "—"
    return text[:limit]


def _section_value(label: str, value: Any, *, code: bool = False) -> str:
    tag = "code" if code else "span"
    return (
        '<div class="aq-tc-field">'
        '<small>' + escape(label) + '</small>'
        f'<{tag}>' + escape(_safe_text(value)) + f'</{tag}>'
        '</div>'
    )


def _render_section(section_id: str, section: Mapping[str, Any]) -> str:
    section = dict(section)
    rows: list[str] = []

    if section_id == "certificate_status":
        rows.append(_section_value("Estado", section.get("state")))
        rows.append(_section_value("Código", section.get("error_code") or "—", code=True))
    elif section_id == "execution_identity":
        rows.append(_section_value("Execution ID", section.get("execution_id"), code=True))
    elif section_id == "terminal_state":
        rows.append(_section_value("Estado terminal", section.get("final_execution_state")))
    elif section_id == "terminal_revision":
        rows.append(_section_value("Revisão terminal", section.get("terminal_revision")))
    elif section_id == "certificate_digest":
        rows.extend((
            _section_value("Manifest digest", section.get("certificate_manifest_digest"), code=True),
            _section_value("Certificate digest", section.get("certificate_digest"), code=True),
            _section_value(
                "Persistence record digest",
                section.get("certificate_persistence_record_digest"),
                code=True,
            ),
        ))
    elif section_id == "finalization_evidence":
        rows.extend((
            _section_value(
                "Finalization record digest",
                section.get("finalization_record_digest"),
                code=True,
            ),
            _section_value(
                "Terminal evidence set digest",
                section.get("terminal_evidence_set_digest"),
                code=True,
            ),
        ))
    elif section_id == "audit_seal_evidence":
        rows.extend((
            _section_value(
                "Audit seal manifest digest",
                section.get("audit_seal_manifest_digest"),
                code=True,
            ),
            _section_value(
                "Audit seal persistence digest",
                section.get("audit_seal_persistence_record_digest"),
                code=True,
            ),
            _section_value(
                "Pre-terminal audit chain digest",
                section.get("pre_terminal_audit_chain_digest"),
                code=True,
            ),
        ))
    elif section_id == "finops_evidence":
        rows.append(
            _section_value(
                "FinOps observation digest",
                section.get("finops_observation_digest"),
                code=True,
            )
        )
    elif section_id == "observability_trace":
        rows.extend((
            _section_value("Trace ID", section.get("observability_trace_id"), code=True),
            _section_value("Persistido em", section.get("persisted_at")),
            _section_value("Observado em", section.get("observed_at")),
            _section_value("Idade (s)", section.get("age_seconds")),
            _section_value("Janela máxima (s)", section.get("max_age_seconds")),
        ))
    elif section_id == "scope_boundary":
        rows.extend((
            _section_value("Owner", section.get("owner_id"), code=True),
            _section_value("Tenant", section.get("tenant_id"), code=True),
            _section_value("Workspace", section.get("workspace_id"), code=True),
        ))
    else:
        return ""

    title = section_id.replace("_", " ").title()
    return (
        '<section class="aq-tc-section" data-section="' + escape(section_id) + '">'
        '<h3>' + escape(title) + '</h3>'
        '<div class="aq-tc-fields">' + "".join(rows) + '</div>'
        '</section>'
    )


def render_terminal_certificate_panel_offline(
    *,
    panel_view_model: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Render one non-interactive HTML panel from a validated view-model."""
    row = dict(panel_view_model) if isinstance(panel_view_model, Mapping) else {}
    execution_id = _safe_text(row.get("execution_id"), 96)

    def fail(error_code: str) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "mode": MODE,
            "state": "MISMATCH",
            "execution_id": execution_id if execution_id != "—" else "",
            "error_code": error_code,
            "html": "",
            "html_rendered": False,
            "static_only": True,
            "read_only": True,
            "observational_only": True,
            "next_allowed_step": NEXT_ALLOWED_STEP,
            **{key: False for key in FALSE_FIELDS},
        }

    if row.get("schema") != binding.SCHEMA:
        return fail("PANEL_VIEW_MODEL_SCHEMA_MISMATCH")
    if row.get("mode") != binding.MODE:
        return fail("PANEL_VIEW_MODEL_MODE_MISMATCH")
    if row.get("next_allowed_step") != binding.NEXT_ALLOWED_STEP:
        return fail("PANEL_VIEW_MODEL_NEXT_STEP_INVALID")

    state = row.get("state")
    if state not in DISPLAY_STATES:
        return fail("PANEL_VIEW_MODEL_STATE_UNKNOWN")
    if row.get("action_controls_present") is not False:
        return fail("PANEL_VIEW_MODEL_ACTION_CONTROLS_FORBIDDEN")
    if tuple(row.get("controls") or ()) != ():
        return fail("PANEL_VIEW_MODEL_CONTROLS_MUST_BE_EMPTY")
    if row.get("panel_is_observational_only") is not True:
        return fail("PANEL_VIEW_MODEL_OBSERVATIONAL_BOUNDARY_MISSING")

    for key in binding.FALSE_FIELDS:
        if row.get(key) is not False:
            return fail("PANEL_VIEW_MODEL_UNSAFE_AUTHORITY_FIELD:" + key)

    badge = row.get("badge")
    if not isinstance(badge, Mapping):
        return fail("PANEL_VIEW_MODEL_BADGE_REQUIRED")
    badge = dict(badge)
    if badge.get("state") != state:
        return fail("PANEL_BADGE_STATE_MISMATCH")
    if badge.get("tone") != binding.BADGE_TONES[state]:
        return fail("PANEL_BADGE_TONE_MISMATCH")
    if badge.get("evidence_only") is not True:
        return fail("PANEL_BADGE_EVIDENCE_BOUNDARY_MISSING")

    sections = row.get("sections")
    if not isinstance(sections, Mapping):
        return fail("PANEL_SECTIONS_REQUIRED")
    sections = dict(sections)
    if tuple(sections.keys()) != REQUIRED_UI_SECTIONS:
        return fail("PANEL_SECTION_ORDER_MISMATCH")
    if tuple(row.get("visible_section_order") or ()) != REQUIRED_UI_SECTIONS:
        return fail("PANEL_VISIBLE_SECTION_ORDER_MISMATCH")

    rendered_sections: list[str] = []
    for section_id in REQUIRED_UI_SECTIONS:
        section = sections.get(section_id)
        if not isinstance(section, Mapping):
            return fail("PANEL_SECTION_INVALID:" + section_id)
        rendered = _render_section(section_id, section)
        if not rendered:
            return fail("PANEL_SECTION_RENDER_FAILED:" + section_id)
        rendered_sections.append(rendered)

    badge_html = (
        '<div class="aq-tc-badge aq-tc-badge-' + escape(state.lower()) + '" '
        'role="status" aria-live="polite">'
        '<strong>' + escape(STATE_LABELS[state]) + '</strong>'
        '<span>' + escape(STATE_MESSAGES[state]) + '</span>'
        '</div>'
    )

    html = (
        '<section class="aq-terminal-certificate-panel" '
        'data-component="terminal-certificate-panel-offline-v1" '
        'data-state="' + escape(state) + '" '
        'data-read-only="true" '
        'data-observational-only="true" '
        'aria-label="Terminal Execution Certificate">'
        '<header class="aq-tc-header">'
        '<div><small>AION B2B · EVIDÊNCIA TERMINAL</small>'
        '<h2>' + escape(_safe_text(row.get("title") or "Terminal Execution Certificate")) + '</h2>'
        '</div>' + badge_html + '</header>'
        '<p class="aq-tc-boundary">'
        'Painel somente leitura. Nenhum estado visual concede autoridade operacional.'
        '</p>'
        '<div class="aq-tc-grid">' + "".join(rendered_sections) + '</div>'
        '</section>'
    )

    lower = html.lower()
    for token in FORBIDDEN_HTML_TOKENS:
        if token in lower:
            return fail("FORBIDDEN_INTERACTIVE_HTML_TOKEN:" + token)

    return {
        "schema": SCHEMA,
        "mode": MODE,
        "state": state,
        "execution_id": execution_id if execution_id != "—" else "",
        "error_code": str(row.get("error_code") or ""),
        "html": html,
        "html_rendered": True,
        "static_only": True,
        "read_only": True,
        "observational_only": True,
        "section_count": len(rendered_sections),
        "next_allowed_step": NEXT_ALLOWED_STEP,
        **{key: False for key in FALSE_FIELDS},
    }


__all__ = [
    "SCHEMA",
    "MODE",
    "NEXT_ALLOWED_STEP",
    "DISPLAY_STATES",
    "REQUIRED_UI_SECTIONS",
    "STATE_LABELS",
    "STATE_MESSAGES",
    "FORBIDDEN_HTML_TOKENS",
    "FALSE_FIELDS",
    "render_terminal_certificate_panel_offline",
]
