from atlasquant_aion_b2b_commercial_golden_path import (
    SCHEMA,
    STAGE_ORDER,
    build_commercial_golden_path,
)
from atlasquant_aion_b2b_commercial_golden_path_ui import (
    commercial_golden_path_html,
    commercial_golden_path_ready,
)
from atlasquant_aion_b2b_diagnostic_intake import SCHEMA as DIAGNOSTIC_SCHEMA
from atlasquant_aion_b2b_managed_service_control import SCHEMA as MANAGED_SERVICE_SCHEMA
from atlasquant_aion_b2b_pilot_activation_status_read_model import SCHEMA as ACTIVATION_SCHEMA
from atlasquant_aion_b2b_pilot_planning_read_model import SCHEMA as PLANNING_SCHEMA
from atlasquant_aion_b2b_pilot_readiness import SCHEMA as READINESS_SCHEMA
from atlasquant_aion_b2b_pilot_value_read_model import SCHEMA as VALUE_SCHEMA
from atlasquant_aion_b2b_portal_read_model import SCHEMA as PORTAL_SCHEMA
from atlasquant_aion_b2b_proposal_draft import SCHEMA as PROPOSAL_SCHEMA
from atlasquant_aion_b2b_recurring_customer_projection import SCHEMA as RECURRING_SCHEMA
from atlasquant_aion_b2b_revops_read_model import SCHEMA as REVOPS_SCHEMA
from atlasquant_reference_ui import reference_html


SCOPE = {
    "owner_id": "owner-1",
    "tenant_id": "tenant-1",
    "workspace_id": "workspace-1",
}


def _safe_rows():
    return {
        "revops_read_model": {
            "schema": REVOPS_SCHEMA,
            "state": "READY",
            "scope": SCOPE,
            "evidence_digest": "sha256:revops",
            "read_only": True,
            "executes_action": False,
        },
        "diagnostic": {
            "schema": DIAGNOSTIC_SCHEMA,
            "state": "READY_FOR_HUMAN_SCORING",
            "dossier": {**SCOPE, "candidate_id": "cand-1"},
            "diagnostic_digest": "sha256:diagnostic",
            "executes_action": False,
        },
        "readiness": {
            "schema": READINESS_SCHEMA,
            "state": "READY_FOR_OWNER_REVIEW",
            "scope": SCOPE,
            "decision": "PILOT_REVIEW_CANDIDATE",
            "human_owner_decision_required": True,
            "evidence_digest": "sha256:readiness",
            "executes_action": False,
        },
        "proposal_draft": {
            "schema": PROPOSAL_SCHEMA,
            "state": "DRAFT_FOR_HUMAN_REVIEW",
            "proposal": {**SCOPE, "proposal_id": "proposal-1"},
            "proposal_digest": "sha256:proposal",
            "non_binding": True,
            "owner_review_required": True,
            "customer_send_allowed": False,
            "contract_ready": False,
            "executes_action": False,
        },
        "pilot_planning_read_model": {
            "schema": PLANNING_SCHEMA,
            "state": "READY",
            "scope": SCOPE,
            "activation_state": "BLOCKED_UNTIL_OWNER_APPROVAL",
            "handoff_digest": "sha256:planning",
            "read_only": True,
            "executes_action": False,
        },
        "pilot_activation_status_read_model": {
            "schema": ACTIVATION_SCHEMA,
            "state": "READY",
            "scope": SCOPE,
            "execution_state": "BLOCKED_PENDING_HUMAN_CONFIRMATION",
            "human_execution_confirmation_required": True,
            "read_only": True,
            "executes_action": False,
        },
        "pilot_value_read_model": {
            "schema": VALUE_SCHEMA,
            "state": "READY",
            "scope": SCOPE,
            "view": "ADMIN",
            "owner_review_required": True,
            "read_only": True,
            "evidence_digest": "sha256:value",
            "executes_action": False,
        },
        "managed_service_contract": {
            "schema": MANAGED_SERVICE_SCHEMA,
            "state": "DRAFT_FOR_OWNER_ACTIVATION",
            "activation_state": "BLOCKED_UNTIL_OWNER_ACTIVATION",
            "contract": {**SCOPE, "customer_id": "customer-1"},
            "contract_digest": "sha256:service",
            "owner_activation_required": True,
            "executes_action": False,
        },
        "portal_read_model": {
            "schema": PORTAL_SCHEMA,
            "state": "READY",
            "scope": SCOPE,
            "read_only": True,
            "evidence_digest": "sha256:portal",
            "executes_action": False,
        },
        "recurring_projection": {
            "schema": RECURRING_SCHEMA,
            "state": "READY",
            "scope": SCOPE,
            "read_only": True,
            "customer_safe": True,
            "allowed": True,
            "evidence_digest": "sha256:recurring",
            "executes_action": False,
        },
    }


def test_full_golden_path_is_read_only_and_ends_in_recurring_monitoring():
    result = build_commercial_golden_path(trusted_scope=SCOPE, **_safe_rows())

    assert result["schema"] == SCHEMA
    assert result["state"] == "READY"
    assert result["current_stage"] == "recurring_customer"
    assert result["next_human_action"] == "MANTER_REVISAO_PERIODICA_DE_VALOR"
    assert [row["key"] for row in result["stages"]] == list(STAGE_ORDER)
    assert result["lineage_gaps"] == []
    assert result["blockers"] == []
    assert result["read_only"] is True
    assert result["grants_authority"] is False
    assert result["executes_action"] is False
    assert result["crm_write"] is False
    assert result["automatic_outreach"] is False
    assert result["automatic_pricing"] is False
    assert result["automatic_contract"] is False
    assert result["automatic_billing"] is False
    assert result["automatic_activation"] is False
    assert result["automatic_deploy"] is False


def test_downstream_evidence_without_upstream_lineage_is_visible_but_flagged():
    rows = _safe_rows()
    proposal = rows["proposal_draft"]
    result = build_commercial_golden_path(
        trusted_scope=SCOPE,
        proposal_draft=proposal,
    )

    assert result["state"] == "READY_WITH_GAPS"
    assert result["current_stage"] == "proposal"
    assert result["next_human_action"] == "REVISAR_PROPOSTA_E_ESCOPO"
    assert set(("revops", "diagnostic", "qualification")).issubset(result["lineage_gaps"])
    assert result["executes_action"] is False


def test_cross_tenant_evidence_blocks_instead_of_advancing():
    rows = _safe_rows()
    rows["pilot_value_read_model"] = {
        **rows["pilot_value_read_model"],
        "scope": {**SCOPE, "tenant_id": "tenant-other"},
    }
    result = build_commercial_golden_path(trusted_scope=SCOPE, **rows)

    assert result["state"] == "BLOCKED"
    value = next(row for row in result["stages"] if row["key"] == "pilot_value")
    assert value["status"] == "BLOCKED"
    assert "PILOT_VALUE:SCOPE_MISMATCH" in result["blockers"]
    assert result["grants_authority"] is False
    assert result["executes_action"] is False


def test_automatic_billing_or_contact_flag_blocks_commercial_projection():
    rows = _safe_rows()
    rows["managed_service_contract"] = {
        **rows["managed_service_contract"],
        "automatic_billing": True,
    }
    result = build_commercial_golden_path(trusted_scope=SCOPE, **rows)

    assert result["state"] == "BLOCKED"
    assert "MANAGED_SERVICE:UNSAFE_FLAG:automatic_billing" in result["blockers"]


def test_empty_journey_is_safe_and_does_not_invent_progress():
    result = build_commercial_golden_path(trusted_scope=SCOPE)

    assert result["state"] == "EMPTY"
    assert result["current_stage"] == ""
    assert result["next_human_action"] == "CAPTURAR_E_VALIDAR_LEAD"
    assert all(row["status"] == "NOT_STARTED" for row in result["stages"])
    assert result["executes_action"] is False


def test_ui_is_read_only_and_contains_no_execution_buttons():
    model = build_commercial_golden_path(trusted_scope=SCOPE, **_safe_rows())
    html = commercial_golden_path_html(model)

    assert commercial_golden_path_ready(model)
    assert 'data-read-only="true"' in html
    assert "Jornada comercial unificada" in html
    assert "Próxima ação humana" in html
    assert html.count('class="aq-b2b-journey-stage"') == len(STAGE_ORDER)
    assert "<button" not in html
    assert "não envia mensagens" in html
    assert "não cobra" in html


def test_negocios_home_projects_golden_path_without_action_authority():
    model = build_commercial_golden_path(trusted_scope=SCOPE, **_safe_rows())
    html = reference_html(
        "negocios",
        name="Mikael",
        commercial_journey_read_model=model,
    )

    assert 'data-workspace="negocios"' in html
    assert "GOLDEN PATH COMERCIAL · LEITURA" in html
    assert "SEM AÇÃO AUTOMÁTICA" in html
    assert "MANTER REVISAO PERIODICA DE VALOR" in html.upper()
    assert 'data-read-only="true"' in html
