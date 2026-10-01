import unittest

from aion_core.domain_registry import (
    DOMAIN_IDS,
    build_domain_registry,
    cross_domain_read_allowed,
    data_access_allowed,
    get_domain,
    registry_digest,
    require_domain,
)

REQUIRED = ("CORE", "NEGOCIOS", "TRADER", "INVESTIMENTOS", "BIBLIOTECA", "ADMIN", "SEGURANCA", "MEMORIA", "ORQUESTRACAO")


class DomainRegistryTests(unittest.TestCase):
    def test_all_required_domains_exist(self):
        registry = build_domain_registry()
        for domain_id in REQUIRED:
            self.assertIn(domain_id, registry["domains"])

    def test_domain_ids_are_unique(self):
        self.assertEqual(len(set(DOMAIN_IDS)), len(DOMAIN_IDS))
        registry = build_domain_registry()
        self.assertEqual(len(registry["domains"]), len(REQUIRED))

    def test_build_is_deterministic(self):
        self.assertEqual(build_domain_registry(), build_domain_registry())

    def test_get_domain_finds_valid(self):
        domain = get_domain("trader")
        self.assertIsNotNone(domain)
        self.assertEqual(domain["domain_id"], "TRADER")

    def test_get_domain_unknown_fail_closed(self):
        self.assertIsNone(get_domain("NAO_EXISTE"))
        self.assertIsNone(get_domain(None))
        self.assertIsNone(get_domain(""))

    def test_require_domain_unknown_raises(self):
        with self.assertRaises(KeyError):
            require_domain("NAO_EXISTE")

    def test_prohibited_data_prevalent(self):
        # TRADER allows market_snapshot but prohibits real_orders.
        self.assertTrue(data_access_allowed("TRADER", "market_snapshot"))
        self.assertFalse(data_access_allowed("TRADER", "real_orders"))
        # ADMIN prohibits secrets even though config_public is allowed.
        self.assertTrue(data_access_allowed("ADMIN", "config_public"))
        self.assertFalse(data_access_allowed("ADMIN", "secrets"))

    def test_unknown_domain_no_access(self):
        self.assertFalse(data_access_allowed("NAO_EXISTE", "anything"))
        self.assertFalse(data_access_allowed(None, "market_snapshot"))

    def test_cross_domain_without_explicit_rule_denied(self):
        decision = cross_domain_read_allowed("CORE", "TRADER", "market_snapshot")
        self.assertFalse(decision["allowed"])
        self.assertIn("explicit_rule_required", decision["reasons"])

    def test_sharing_none_denies_even_with_rule(self):
        decision = cross_domain_read_allowed("CORE", "ADMIN", "config_public", explicit_rule=True)
        self.assertFalse(decision["allowed"])
        self.assertIn("target_sharing_none", decision["reasons"])

    def test_cross_domain_with_explicit_rule_allowed(self):
        decision = cross_domain_read_allowed("CORE", "TRADER", "market_snapshot", explicit_rule=True)
        self.assertTrue(decision["allowed"])
        self.assertEqual(decision["reasons"], [])

    def test_offline_and_online_policy_declared_for_all(self):
        registry = build_domain_registry()
        for domain in registry["domains"].values():
            self.assertTrue(domain["offline_policy"])
            self.assertTrue(domain["online_policy"])
            self.assertIn(domain["memory_policy"], ("PRIVATE", "SHARED_WITH_PROVENANCE", "READ_ONLY"))
            self.assertIn(domain["sharing_policy"], ("NONE", "EXPLICIT_RULE_ONLY", "CURATED_EXPORT"))

    def test_registry_digest_deterministic(self):
        registry = build_domain_registry()
        self.assertEqual(registry_digest(registry), registry_digest(build_domain_registry()))

    def test_relevant_change_changes_digest(self):
        registry = build_domain_registry()
        mutated = build_domain_registry()
        mutated["domains"]["TRADER"]["risk_classification"] = "LOW"
        self.assertNotEqual(registry_digest(registry), registry_digest(mutated))


if __name__ == "__main__":
    unittest.main()
