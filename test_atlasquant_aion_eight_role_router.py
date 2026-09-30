import ast
import unittest
from pathlib import Path

from atlasquant_aion_core_master_checkpoint_bootstrap import (
    master_checkpoint_bootstrap_snapshot,
)
from atlasquant_aion_eight_role_router import (
    MAX_ACTIVE_ROLES,
    ROLE_IDS,
    role_registry,
    route_logical_roles,
)
from atlasquant_aion_core_runtime_bridge import handle_runtime_intent


def _snapshot():
    return master_checkpoint_bootstrap_snapshot()


def _access():
    return {
        "allowed": True,
        "mode": "AUTHENTICATED",
        "role": "ADMIN",
        "session": {
            "username": "mikael",
            "role": "ADMIN",
            "credential_fingerprint": "a1b2c3d4e5f60718293a4b5c",
            "permissions": ["app:read", "admin:read", "aion:admin"],
        },
    }


class AionEightRoleRouterTests(unittest.TestCase):
    def test_registry_matches_checkpoint_eight_roles(self):
        registry = role_registry(_snapshot())
        self.assertEqual(registry["state"], "EIGHT_ROLE_REGISTRY_VALID")
        self.assertEqual(
            tuple(row["role_id"] for row in registry["roles"]),
            ROLE_IDS,
        )
        self.assertEqual(registry["role_count"], 8)
        self.assertEqual(registry["independent_ai_count"], 0)
        self.assertFalse(registry["physical_execution_authorized"])

    def test_cost_question_selects_finops(self):
        route = route_logical_roles(
            "analise custo de API, orçamento e margem do cliente",
            _snapshot(),
        )
        self.assertEqual(route["state"], "LOGICAL_ROLE_ROUTE_READY")
        self.assertIn("orchestrator", route["selected_roles"])
        self.assertIn("finops", route["selected_roles"])
        self.assertFalse(route["executes_action"])

    def test_architecture_improvement_selects_architect(self):
        route = route_logical_roles(
            "quero melhorar a arquitetura e atualizar a interface do sistema",
            _snapshot(),
        )
        self.assertIn("architect", route["selected_roles"])

    def test_checkpoint_question_selects_memory(self):
        route = route_logical_roles(
            "leia o checkpoint mestre e a memória das decisões",
            _snapshot(),
        )
        self.assertIn("memory", route["selected_roles"])

    def test_incident_selects_reliability(self):
        route = route_logical_roles(
            "houve falha, cheque saúde, observabilidade e recuperação",
            _snapshot(),
        )
        self.assertIn("reliability", route["selected_roles"])

    def test_client_onboarding_selects_customer_success(self):
        route = route_logical_roles(
            "prepare onboarding, suporte e retenção deste cliente",
            _snapshot(),
        )
        self.assertIn("customer_success", route["selected_roles"])

    def test_critical_execution_requires_guardian_and_separate_gate(self):
        route = route_logical_roles(
            "execute merge e deploy em produção",
            _snapshot(),
        )
        self.assertIn("guardian", route["selected_roles"])
        self.assertIn("executor", route["selected_roles"])
        self.assertTrue(route["separate_gate_required"])
        self.assertEqual(route["reasoning_tier"], "STRONG_REVIEW")
        self.assertFalse(route["physical_execution_authorized"])
        self.assertFalse(route["deploy_authorized"])

    def test_unknown_intent_uses_only_orchestrator(self):
        route = route_logical_roles("olá aion", _snapshot())
        self.assertEqual(route["selected_roles"], ["orchestrator"])
        self.assertEqual(route["primary_role"], "orchestrator")
        self.assertEqual(route["reasoning_tier"], "LOCAL_LIGHT")

    def test_selection_is_bounded(self):
        route = route_logical_roles(
            "arquitetura custo cliente incidente checkpoint executar deploy segurança",
            _snapshot(),
        )
        self.assertLessEqual(len(route["selected_roles"]), MAX_ACTIVE_ROLES)

    def test_tampered_role_registry_fails_closed(self):
        snapshot = _snapshot()
        snapshot["multiagent_roles"] = snapshot["multiagent_roles"][:-1]
        registry = role_registry(snapshot)
        self.assertEqual(registry["state"], "EIGHT_ROLE_REGISTRY_BLOCKED")
        route = route_logical_roles("custo", snapshot)
        self.assertEqual(route["state"], "LOGICAL_ROLE_ROUTE_BLOCKED")

    def test_runtime_bridge_exposes_logical_role_route(self):
        result = handle_runtime_intent(
            _access(),
            "analise custo, margem e orçamento do ecossistema",
            system_context={},
        )
        self.assertEqual(
            result["logical_role_route"]["state"],
            "LOGICAL_ROLE_ROUTE_READY",
        )
        self.assertIn(
            "finops",
            result["logical_role_route"]["selected_roles"],
        )
        self.assertFalse(
            result["logical_role_route"]["physical_execution_authorized"]
        )

    def test_module_has_no_network_or_executor_imports(self):
        source = Path("atlasquant_aion_eight_role_router.py").read_text(
            encoding="utf-8"
        )
        tree = ast.parse(source)
        imported = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
        for banned in (
            "requests",
            "urllib",
            "httpx",
            "socket",
            "subprocess",
            "github",
            "paramiko",
            "docker",
            "kubernetes",
        ):
            self.assertNotIn(banned, imported)


if __name__ == "__main__":
    unittest.main()
