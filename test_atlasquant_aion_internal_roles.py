import unittest

from atlasquant_aion_internal_roles import internal_roles_snapshot


class AionInternalRolesTests(unittest.TestCase):
    def test_exact_eight_roles_are_preserved(self):
        snapshot = internal_roles_snapshot()
        self.assertEqual(snapshot["count"], 8)
        labels = [row["label"] for row in snapshot["roles"]]
        self.assertEqual(labels, [
            "Orquestrador",
            "Arquiteto / Estrategista",
            "Guardião / Auditor",
            "Executor / Operador",
            "Memória / Conhecimento",
            "FinOps / Controle de Custos",
            "Observabilidade / Confiabilidade",
            "Sucesso do Cliente / Comercial",
        ])

    def test_roles_never_become_independent_authorities(self):
        snapshot = internal_roles_snapshot()
        self.assertTrue(snapshot["single_shared_aion_core"])
        self.assertTrue(snapshot["roles_are_responsibilities_not_independent_ais"])
        self.assertFalse(snapshot["execution_authority"])
        self.assertFalse(snapshot["external_action_executed"])
        for row in snapshot["roles"]:
            self.assertTrue(row["shared_core"])
            self.assertFalse(row["independent_ai"])
            self.assertFalse(row["external_action_authority"])
            self.assertFalse(row["real_trading_enabled"])
            self.assertFalse(row["automatic_merge"])
            self.assertFalse(row["automatic_deploy"])


if __name__ == "__main__":
    unittest.main()
