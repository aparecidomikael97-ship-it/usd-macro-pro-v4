from __future__ import annotations

import unittest

from atlasquant_reference_ui import module_panel, reference_html


def pilot_model():
    return {
        "schema": "ATLASQUANT_AION_B2B_PILOT_PLANNING_READ_MODEL_V1",
        "state": "READY",
        "scope": {
            "owner_id": "owner-a",
            "tenant_id": "tenant-a",
            "workspace_id": "business",
        },
        "pilot_id": "pilot-001",
        "proposal_id": "proposal-001",
        "activation_state": "BLOCKED_UNTIL_OWNER_APPROVAL",
        "duration_days": 14,
        "max_monthly_infra_brl": 150.0,
        "pilot_scope_item_count": 2,
        "objective_count": 2,
        "quick_win_count": 2,
        "kpi_count": 3,
        "stop_condition_count": 3,
        "rollback_step_count": 2,
        "handoff_digest": "sha256:handoff",
        "contract_digest": "sha256:contract",
        "read_only": True,
        "owner_review_required": True,
        "activation_control_exposed": False,
        "raw_evidence_exposed": False,
        "candidate_identity_exposed": False,
        "automatic_activation": False,
        "automatic_customer_contact": False,
        "automatic_billing": False,
        "automatic_deploy": False,
        "crm_write": False,
        "provider_called": False,
        "production_mutation": False,
        "grants_authority": False,
        "executes_action": False,
    }


def value_model(**overrides):
    row = {
        "schema": "ATLASQUANT_AION_B2B_PILOT_VALUE_READ_MODEL_V1",
        "view": "ADMIN",
        "state": "READY",
        "scope": {
            "owner_id": "owner-a",
            "tenant_id": "tenant-a",
            "workspace_id": "business",
        },
        "pilot_id": "pilot-001",
        "value_state": "STRONG_VALUE",
        "recommendation": "EXPANSION_REVIEW_CANDIDATE",
        "health_score": 90.0,
        "value_trend": "IMPROVING",
        "quick_win_completion_pct": 100.0,
        "quick_win_achieved_pct": 100.0,
        "observed_savings_brl": 3000.0,
        "observed_roi_pct": 100.0,
        "customer_fee_brl": 1500.0,
        "customer_value_to_fee_ratio": 2.0,
        "customer_net_value_brl": 1500.0,
        "customer_payback_covered": True,
        "provider_delivery_cost_brl": 1000.0,
        "provider_gross_margin_brl": 1000.0,
        "provider_gross_margin_pct": 50.0,
        "retention_risk": "LOW",
        "retention_risk_score": 0.0,
        "low_value_alert": False,
        "review_reasons": [
            "VALUE_TREND_IMPROVING",
            "QUICK_WINS_STRONG",
        ],
        "evidence_digest": "sha256:" + "1" * 64,
        "owner_review_required": True,
        "read_only": True,
        "internal_economics_visible": True,
        "customer_safe": False,
        "renewal_control_exposed": False,
        "expansion_control_exposed": False,
        "billing_control_exposed": False,
        "customer_contact_control_exposed": False,
        "grants_authority": False,
        "executes_action": False,
    }
    row.update(overrides)
    return row


class AionB2BPilotValueUITests(unittest.TestCase):
    def test_b2b_renders_internal_value_review_read_only(self):
        html = module_panel(
            "negocios",
            "b2b",
            pilot_planning_read_model=pilot_model(),
            pilot_value_read_model=value_model(),
        )
        self.assertIn('data-pilot-readonly="true"', html)
        self.assertIn('data-pilot-value-readonly="true"', html)
        self.assertIn("VALOR", html)
        self.assertIn("STRONG_VALUE", html)
        self.assertIn("ROI OBSERVADO", html)
        self.assertIn("100%", html)
        self.assertIn("ECONOMIA", html)
        self.assertIn("R$ 3000.00", html)
        self.assertIn("QUICK WINS", html)
        self.assertIn("MARGEM", html)
        self.assertIn("50%", html)
        self.assertIn("RETENÇÃO", html)
        self.assertIn("LOW", html)
        self.assertIn("REVISAR EXPANSÃO", html)
        self.assertIn("SOMENTE LEITURA", html)

    def test_value_panel_contains_no_business_action_controls(self):
        html = module_panel(
            "negocios",
            "b2b",
            pilot_planning_read_model=pilot_model(),
            pilot_value_read_model=value_model(),
        )
        for forbidden in (
            ">Renovar<",
            ">Expandir<",
            ">Cobrar<",
            ">Contatar cliente<",
            ">Ativar piloto<",
            ">Executar<",
            "data-action="renew",
            "data-action="expand",
            "data-action="bill",
        ):
            self.assertNotIn(forbidden, html)

    def test_low_value_alert_is_visible_without_auto_action(self):
        html = module_panel(
            "negocios",
            "b2b",
            pilot_planning_read_model=pilot_model(),
            pilot_value_read_model=value_model(
                value_state="VALUE_AT_RISK",
                recommendation="REMEDIATE_REVIEW_CANDIDATE",
                low_value_alert=True,
                retention_risk="HIGH",
            ),
        )
        self.assertIn(
            "ALERTA DE VALOR BAIXO · REVISÃO HUMANA OBRIGATÓRIA",
            html,
        )
        self.assertIn("REVISAR REMEDIAÇÃO", html)
        self.assertNotIn(">Remediar<", html)

    def test_unsafe_value_model_is_not_rendered(self):
        html = module_panel(
            "negocios",
            "b2b",
            pilot_planning_read_model=pilot_model(),
            pilot_value_read_model=value_model(
                expansion_control_exposed=True
            ),
        )
        self.assertIn('data-pilot-readonly="true"', html)
        self.assertNotIn('data-pilot-value-readonly="true"', html)

    def test_reference_html_marks_value_as_validated_but_execution_blocked(self):
        html = reference_html(
            "negocios",
            selected="b2b",
            pilot_planning_read_model=pilot_model(),
            pilot_value_read_model=value_model(),
        )
        self.assertIn("VALOR DO PILOTO VALIDADO", html)
        self.assertIn(
            "SOMENTE LEITURA · revisão de valor e retenção",
            html,
        )
        self.assertIn("<small>EXECUÇÃO</small><strong>BLOQUEADA</strong>", html)

    def test_value_panel_is_b2b_only(self):
        html = module_panel(
            "negocios",
            "proposals",
            pilot_planning_read_model=pilot_model(),
            pilot_value_read_model=value_model(),
        )
        self.assertNotIn('data-pilot-value-readonly="true"', html)


if __name__ == "__main__":
    unittest.main()
