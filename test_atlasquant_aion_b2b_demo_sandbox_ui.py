import unittest

from atlasquant_reference_ui import module_panel, reference_html


def sandbox_model(**overrides):
    row = {
        "schema": "ATLASQUANT_AION_B2B_DEMO_SANDBOX_READ_MODEL_V1",
        "state": "READY",
        "sandbox_state": "REVIEWABLE",
        "sandbox_decision": "SANDBOX_REVIEW_CANDIDATE",
        "sandbox_id": "sandbox-demo-a",
        "service_tenant_id": "tenant-demo-a",
        "package": "PROFISSIONAL",
        "dataset_class": "SYNTHETIC",
        "duration_hours": 24,
        "synthetic_records": 1000,
        "concurrent_sessions": 2,
        "evidence_digest": "sha256:" + "1" * 64,
        "owner_sandbox_approval_required": True,
        "read_only": True,
        "synthetic_only": True,
        "customer_identity_exposed": False,
        "evidence_internals_exposed": False,
        "credential_details_exposed": False,
        "provider_details_exposed": False,
        "sandbox_creation_control_exposed": False,
        "tenant_creation_control_exposed": False,
        "quota_control_exposed": False,
        "provisioning_control_exposed": False,
        "billing_control_exposed": False,
        "customer_contact_control_exposed": False,
        "grants_authority": False,
        "executes_action": False,
    }
    row.update(overrides)
    return row


class DemoSandboxUITests(unittest.TestCase):
    def test_sandbox_route_renders_synthetic_read_only_summary(self):
        html = module_panel(
            "negocios",
            "sandbox",
            demo_sandbox_read_model=sandbox_model(),
        )
        self.assertIn('data-demo-sandbox-readonly="true"', html)
        self.assertIn("sandbox-demo-a", html)
        self.assertIn("SINTÉTICOS", html)
        self.assertIn("PROFISSIONAL", html)
        self.assertIn("tenant-demo-a", html)
        self.assertIn("24h", html)
        self.assertIn("1000", html)
        self.assertIn("EXECUÇÃO", html)
        self.assertIn("BLOQUEADA", html)
        self.assertIn("SEM INTEGRAÇÃO LIVE", html)

    def test_customer_identity_and_sensitive_internals_are_absent(self):
        html = module_panel(
            "negocios",
            "sandbox",
            demo_sandbox_read_model=sandbox_model(),
        )
        for forbidden in (
            "customer-secret",
            "customer_id",
            "evidence_digest",
            "credential",
            "provider_details",
            "api_key",
            "secret",
        ):
            self.assertNotIn(forbidden, html.lower())

    def test_no_operational_controls_are_rendered(self):
        html = module_panel(
            "negocios",
            "sandbox",
            demo_sandbox_read_model=sandbox_model(),
        )
        for forbidden in (
            ">Criar sandbox<",
            ">Ativar sandbox<",
            ">Criar tenant<",
            ">Provisionar<",
            ">Integrar<",
            ">Cobrar<",
            ">Contatar cliente<",
            ">Deploy<",
            'data-action="sandbox',
            'data-action="provision',
            'data-action="billing',
        ):
            self.assertNotIn(forbidden, html)

    def test_unsafe_read_model_is_not_rendered(self):
        html = module_panel(
            "negocios",
            "sandbox",
            demo_sandbox_read_model=sandbox_model(
                sandbox_creation_control_exposed=True
            ),
        )
        self.assertNotIn('data-demo-sandbox-readonly="true"', html)

    def test_reference_html_marks_synthetic_sandbox_validated(self):
        html = reference_html(
            "negocios",
            selected="sandbox",
            demo_sandbox_read_model=sandbox_model(),
        )
        self.assertIn("SANDBOX SINTÉTICO VALIDADO", html)
        self.assertIn(
            "SOMENTE LEITURA · sandbox sintético em revisão",
            html,
        )
        self.assertIn(
            "<small>EXECUÇÃO</small><strong>BLOQUEADA</strong>",
            html,
        )

    def test_other_business_routes_do_not_render_sandbox_panel(self):
        html = module_panel(
            "negocios",
            "companies",
            demo_sandbox_read_model=sandbox_model(),
        )
        self.assertNotIn('data-demo-sandbox-readonly="true"', html)


if __name__ == "__main__":
    unittest.main()
