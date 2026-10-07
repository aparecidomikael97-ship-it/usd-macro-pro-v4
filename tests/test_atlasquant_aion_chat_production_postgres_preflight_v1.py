from __future__ import annotations

import inspect
import unittest
from dataclasses import replace

import atlasquant_aion_chat_production_postgres_preflight_v1 as preflight


def provider_ready(**overrides):
    values = dict(
        ephemeral_binding_validated=True,
        core_v1_frozen=True,
        provider_name="managed-postgres",
        pricing_verified=True,
        monthly_cost_brl=100.0,
        plan_persistent=True,
        private_connectivity_supported=True,
        tls_supported=True,
        backup_supported=True,
    )
    values.update(overrides)
    return preflight.ProductionPostgresPreflightEvidence(**values)


def provisioned_ready(**overrides):
    base = provider_ready(
        provider_instance_provisioned=True,
        same_region_as_app=True,
        private_connectivity_enabled=True,
        public_access_disabled=True,
        tls_required=True,
        least_privilege_role=True,
        secret_injected_outside_repo=True,
        backup_enabled=True,
        recovery_point_verified=True,
    )
    return replace(base, **overrides)


def migrated_ready(**overrides):
    base = provisioned_ready(
        migration_applied=True,
        migration_version=1,
        migration_checksum="sha256:ci-evidence-only",
        migration_checksum_verified=True,
        schema_version_compatible=True,
        schema_constraints_healthy=True,
        transaction_health=True,
        scope_policy_healthy=True,
        cursor_signing_key_stable=True,
        restore_drill_verified=True,
    )
    return replace(base, **overrides)


class ProductionPostgresPreflightV1Tests(unittest.TestCase):
    def test_empty_evidence_is_fail_closed(self):
        result = preflight.evaluate_production_postgres_preflight(
            preflight.ProductionPostgresPreflightEvidence()
        )
        self.assertEqual(result["state"], preflight.BLOCKED)
        self.assertIn(
            "EPHEMERAL_POSTGRES_BINDING_NOT_VALIDATED",
            result["blockers"],
        )
        self.assertIn("CORE_V1_FREEZE_NOT_PROVEN", result["blockers"])

    def test_verified_provider_plan_within_budget_reaches_provisioning_gate(self):
        result = preflight.evaluate_production_postgres_preflight(provider_ready())
        self.assertEqual(
            result["state"],
            preflight.READY_FOR_PROVIDER_PROVISIONING,
        )
        self.assertEqual(result["blockers"], [])
        self.assertFalse(result["provider_mutation_executed"])

    def test_owner_monthly_ceiling_is_fail_closed(self):
        exact = preflight.evaluate_production_postgres_preflight(
            provider_ready(monthly_cost_brl=200.0)
        )
        self.assertEqual(
            exact["state"],
            preflight.READY_FOR_PROVIDER_PROVISIONING,
        )

        over = preflight.evaluate_production_postgres_preflight(
            provider_ready(monthly_cost_brl=200.01)
        )
        self.assertEqual(over["state"], preflight.BLOCKED)
        self.assertIn("MONTHLY_COST_EXCEEDS_OWNER_CEILING", over["blockers"])

    def test_verified_pricing_requires_normalized_brl_cost(self):
        result = preflight.evaluate_production_postgres_preflight(
            provider_ready(monthly_cost_brl=None)
        )
        self.assertEqual(result["state"], preflight.BLOCKED)
        self.assertIn(
            "VERIFIED_PRICING_REQUIRES_MONTHLY_COST_BRL",
            result["blockers"],
        )

    def test_provisioned_instance_requires_all_security_evidence(self):
        evidence = provider_ready(provider_instance_provisioned=True)
        result = preflight.evaluate_production_postgres_preflight(evidence)
        self.assertEqual(result["state"], preflight.BLOCKED)
        self.assertIn(
            "MISSING_PROVISIONED_SECURITY_EVIDENCE:private_connectivity_enabled",
            result["blockers"],
        )
        self.assertIn(
            "MISSING_PROVISIONED_SECURITY_EVIDENCE:public_access_disabled",
            result["blockers"],
        )
        self.assertIn(
            "MISSING_PROVISIONED_SECURITY_EVIDENCE:least_privilege_role",
            result["blockers"],
        )

    def test_secured_provisioned_instance_reaches_isolated_migration_gate(self):
        result = preflight.evaluate_production_postgres_preflight(
            provisioned_ready()
        )
        self.assertEqual(
            result["state"],
            preflight.READY_FOR_ISOLATED_MIGRATION,
        )
        self.assertFalse(result["migration_executed"])
        self.assertFalse(result["deploy_authorized"])

    def test_superuser_or_secret_commit_is_hard_blocker(self):
        superuser = preflight.evaluate_production_postgres_preflight(
            provider_ready(app_role_is_superuser=True)
        )
        self.assertEqual(superuser["state"], preflight.BLOCKED)
        self.assertIn(
            "APPLICATION_ROLE_MUST_NOT_BE_SUPERUSER",
            superuser["blockers"],
        )

        secret = preflight.evaluate_production_postgres_preflight(
            provider_ready(secrets_committed_to_repo=True)
        )
        self.assertEqual(secret["state"], preflight.BLOCKED)
        self.assertIn(
            "SECRET_MATERIAL_COMMITTED_TO_REPOSITORY",
            secret["blockers"],
        )

    def test_deploy_worker_or_core_mutation_never_passes_preflight(self):
        for field, blocker in (
            ("deploy_executed", "DEPLOY_OCCURRED_OUTSIDE_THIS_PREFLIGHT"),
            ("worker_armed", "WORKER_ARMED_OUTSIDE_THIS_PREFLIGHT"),
            ("core_mutated", "CORE_V1_MUTATED"),
        ):
            with self.subTest(field=field):
                result = preflight.evaluate_production_postgres_preflight(
                    provider_ready(**{field: True})
                )
                self.assertEqual(result["state"], preflight.BLOCKED)
                self.assertIn(blocker, result["blockers"])

    def test_applied_migration_requires_checksum_schema_scope_and_restore_evidence(self):
        incomplete = provisioned_ready(
            migration_applied=True,
            migration_version=1,
            migration_checksum="sha256:test",
        )
        result = preflight.evaluate_production_postgres_preflight(incomplete)
        self.assertEqual(result["state"], preflight.BLOCKED)
        self.assertIn(
            "MISSING_POST_MIGRATION_EVIDENCE:migration_checksum_verified",
            result["blockers"],
        )
        self.assertIn(
            "MISSING_POST_MIGRATION_EVIDENCE:restore_drill_verified",
            result["blockers"],
        )

    def test_full_post_migration_evidence_reaches_connection_attestation_only(self):
        result = preflight.evaluate_production_postgres_preflight(
            migrated_ready()
        )
        self.assertEqual(
            result["state"],
            preflight.READY_FOR_CONNECTION_ATTESTATION,
        )
        self.assertEqual(result["blockers"], [])
        self.assertFalse(result["deploy_authorized"])
        self.assertFalse(result["worker_authorized"])
        self.assertFalse(result["core_write_authorized"])

    def test_policy_has_zero_runtime_authority(self):
        policy = preflight.preflight_policy()
        for key in (
            "provider_network_called",
            "database_connection_opened",
            "secret_resolved",
            "migration_executed",
            "deploy_executed",
            "worker_armed",
            "external_action_executed",
            "core_checkpoint_write",
        ):
            self.assertIs(policy[key], False, key)

        source = inspect.getsource(preflight)
        self.assertNotIn("psycopg.connect", source)
        self.assertNotIn("requests.", source)
        self.assertNotIn("subprocess", source)

    def test_invalid_budget_ceiling_is_rejected(self):
        with self.assertRaises(ValueError):
            preflight.evaluate_production_postgres_preflight(
                provider_ready(),
                max_monthly_brl=0,
            )


if __name__ == "__main__":
    unittest.main()
