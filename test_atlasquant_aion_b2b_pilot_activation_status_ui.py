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


def activation_model(**overrides):
    row = {
        "schema": "ATLASQUANT_AION_B2B_PILOT_ACTIVATION_STATUS_READ_MODEL_V1",
        "state": "READY",
        "scope": {
            "owner_id": "owner-a",
            "tenant_id": "tenant-a",
            "workspace_id": "business",
        },
        "pilot_id": "pilot-001",
        "governance_state": "WAITING_HUMAN_EXECUTION_CONFIRMATION",
        "pilot_decision_state": "ATTESTED",
        "activation_preflight_state": "ATTESTED",
        "activation_authorization_state": "ATTESTED",
        "activation_persistence_state": "ATTESTED",
        "activation_writer_state": "ATTESTED",
        "execution_environment_state": "VERIFIED",
        "execution_state": "BLOCKED_PENDING_HUMAN_CONFIRMATION",
        "monthly_infra_cap_brl": 200.0,
        "human_execution_confirmation_required": True,
        "read_only": True,
        "activation_control_exposed": False,
        "activation_command_exposed": False,
        "raw_evidence_exposed": False,
        "candidate_identity_exposed": False,
        "cryptographic_digest_exposed": False,
        "writer_identity_exposed": False,
        "automatic_activation": False,
        "automatic_customer_contact": False,
        "automatic_billing": False,
        "automatic_provisioning": False,
        "automatic_deploy": False,
        "crm_write": False,
        "provider_called": False,
        "production_mutation": False,
        "grants_authority": False,
        "executes_action": False,
    }
    row.update(overrides)
    return row


class AionB2BPilotActivationStatusUITests(unittest.TestCase):
    def test_b2b_renders_planning_and_activation_governance_together(self):
        html = module_panel(
            "negocios",
            "b2b",
            pilot_planning_read_model=pilot_model(),
            pilot_activation_status_read_model=activation_model(),
        )
        self.assertIn('data-pilot-readonly="true"', html)
        self.assertIn('data-pilot-activation-readonly="true"', html)
        self.assertIn("pilot-001", html)
        self.assertIn("GOVERNANÇA", html)
        self.assertIn("VALIDADA", html)
        self.assertIn("PERSISTÊNCIA", html)
        self.assertIn("WRITER", html)
        self.assertIn("VERIFIED", html)
        self.assertIn("AGUARDANDO CONFIRMAÇÃO HUMANA", html)
        self.assertIn("SEM COMANDO DE ATIVAÇÃO", html)

    def test_governance_ui_exposes_no_candidate_digest_or_writer_identity(self):
        html = module_panel(
            "negocios",
            "b2b",
            pilot_planning_read_model=pilot_model(),
            pilot_activation_status_read_model=activation_model(),
        )
        for forbidden in (
            "candidate_id",
            "candidate-secret",
            "preflight_digest",
            "environment_digest",
            "activation_record_digest",
            "receipt_digest",
            "writer_key_id",
            "writer_public_key_fingerprint",
            "evidence_refs",
        ):
            self.assertNotIn(forbidden, html)

    def test_governance_ui_contains_no_activation_execution_controls(self):
        html = module_panel(
            "negocios",
            "b2b",
            pilot_planning_read_model=pilot_model(),
            pilot_activation_status_read_model=activation_model(),
        )
        for forbidden in (
            "Ativar piloto",
            "Executar ativação",
            "Confirmar execução",
            "Autorizar execução",
            "Provisionar",
            "Deploy",
            "Cobrar",
            "Enviar ao cliente",
        ):
            self.assertNotIn(forbidden, html)

    def test_invalid_activation_status_is_not_rendered(self):
        html = module_panel(
            "negocios",
            "b2b",
            pilot_planning_read_model=pilot_model(),
            pilot_activation_status_read_model=activation_model(
                state="BLOCKED"
            ),
        )
        self.assertIn('data-pilot-readonly="true"', html)
        self.assertNotIn('data-pilot-activation-readonly="true"', html)

    def test_any_authority_flip_suppresses_governance_panel(self):
        for key in (
            "activation_control_exposed",
            "activation_command_exposed",
            "automatic_activation",
            "automatic_customer_contact",
            "automatic_billing",
            "automatic_provisioning",
            "automatic_deploy",
            "crm_write",
            "provider_called",
            "production_mutation",
            "grants_authority",
            "executes_action",
        ):
            with self.subTest(key=key):
                html = module_panel(
                    "negocios",
                    "b2b",
                    pilot_planning_read_model=pilot_model(),
                    pilot_activation_status_read_model=activation_model(
                        **{key: True}
                    ),
                )
                self.assertNotIn(
                    'data-pilot-activation-readonly="true"',
                    html,
                )

    def test_reference_html_accepts_activation_governance_model(self):
        html = reference_html(
            "negocios",
            selected="b2b",
            pilot_planning_read_model=pilot_model(),
            pilot_activation_status_read_model=activation_model(),
        )
        self.assertIn("Automação B2B", html)
        self.assertIn("GOVERNANÇA DE ATIVAÇÃO VALIDADA", html)
        self.assertIn(
            "SOMENTE LEITURA · aguardando confirmação humana de execução",
            html,
        )
        self.assertIn("EXECUÇÃO", html)
        self.assertIn("BLOQUEADA", html)

    def test_other_routes_do_not_render_activation_governance(self):
        html = module_panel(
            "negocios",
            "proposals",
            pilot_planning_read_model=pilot_model(),
            pilot_activation_status_read_model=activation_model(),
        )
        self.assertNotIn('data-pilot-activation-readonly="true"', html)


if __name__ == "__main__":
    unittest.main()
