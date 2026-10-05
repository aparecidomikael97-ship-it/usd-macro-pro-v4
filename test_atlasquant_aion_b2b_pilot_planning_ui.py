from __future__ import annotations

import unittest

from atlasquant_reference_ui import module_panel, reference_html


def pilot_model(**overrides):
    row = {
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
        "quick_win_count": 1,
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
    row.update(overrides)
    return row


class AionB2BPilotPlanningUITests(unittest.TestCase):
    def test_b2b_route_renders_planned_pilot_summary(self):
        html = module_panel(
            "negocios",
            "b2b",
            pilot_planning_read_model=pilot_model(),
        )
        self.assertIn('data-pilot-readonly="true"', html)
        self.assertIn("pilot-001", html)
        self.assertIn("14 dias", html)
        self.assertIn("R$ 150", html)
        self.assertIn("KPIs", html)
        self.assertIn(">3<", html)
        self.assertIn("ATIVAÇÃO", html)
        self.assertIn("BLOQUEADA", html)
        self.assertIn("AGUARDANDO APROVAÇÃO DO PROPRIETÁRIO", html)

    def test_b2b_route_exposes_no_candidate_or_raw_evidence(self):
        html = module_panel(
            "negocios",
            "b2b",
            pilot_planning_read_model=pilot_model(),
        )
        for forbidden in (
            "candidate_id",
            "candidate-secret",
            "evidence_refs",
            "source_ref",
            "planner_ref",
        ):
            self.assertNotIn(forbidden, html)

    def test_b2b_route_contains_no_activation_or_customer_action_control(self):
        html = module_panel(
            "negocios",
            "b2b",
            pilot_planning_read_model=pilot_model(),
        )
        for forbidden in (
            "Ativar piloto",
            "Iniciar piloto",
            "Aprovar e ativar",
            "Enviar ao cliente",
            "Cobrar",
            "Assinar contrato",
            "Provisionar",
        ):
            self.assertNotIn(forbidden, html)

    def test_invalid_pilot_model_falls_back_to_preview(self):
        html = module_panel(
            "negocios",
            "b2b",
            pilot_planning_read_model=pilot_model(state="BLOCKED"),
        )
        self.assertNotIn('data-pilot-readonly="true"', html)
        self.assertNotIn("pilot-001", html)
        self.assertIn("PRÉVIA", html)

    def test_activation_state_flip_blocks_rendering(self):
        html = module_panel(
            "negocios",
            "b2b",
            pilot_planning_read_model=pilot_model(
                activation_state="ACTIVE"
            ),
        )
        self.assertNotIn('data-pilot-readonly="true"', html)
        self.assertNotIn("pilot-001", html)

    def test_automatic_activation_flip_blocks_rendering(self):
        html = module_panel(
            "negocios",
            "b2b",
            pilot_planning_read_model=pilot_model(
                automatic_activation=True
            ),
        )
        self.assertNotIn('data-pilot-readonly="true"', html)
        self.assertNotIn("pilot-001", html)

    def test_any_external_action_flag_flip_blocks_rendering(self):
        for key in (
            "automatic_customer_contact",
            "automatic_billing",
            "automatic_deploy",
            "crm_write",
            "provider_called",
            "production_mutation",
            "grants_authority",
            "executes_action",
        ):
            with self.subTest(key=key):
                model = pilot_model()
                model[key] = True
                html = module_panel(
                    "negocios",
                    "b2b",
                    pilot_planning_read_model=model,
                )
                self.assertNotIn('data-pilot-readonly="true"', html)

    def test_other_routes_do_not_reuse_pilot_model(self):
        html = module_panel(
            "negocios",
            "proposals",
            pilot_planning_read_model=pilot_model(),
        )
        self.assertNotIn("pilot-001", html)
        self.assertNotIn('data-pilot-readonly="true"', html)

    def test_reference_html_accepts_pilot_planning_model(self):
        html = reference_html(
            "negocios",
            selected="b2b",
            pilot_planning_read_model=pilot_model(),
        )
        self.assertIn("Automação B2B", html)
        self.assertIn("pilot-001", html)
        self.assertIn("EXECUÇÃO", html)
        self.assertIn("BLOQUEADA", html)
        self.assertIn("PILOTO PLANEJADO", html)


if __name__ == "__main__":
    unittest.main()
