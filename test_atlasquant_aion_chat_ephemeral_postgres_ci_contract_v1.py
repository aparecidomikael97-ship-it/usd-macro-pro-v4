from __future__ import annotations

import unittest

import atlasquant_aion_chat_ephemeral_postgres_ci_contract_v1 as contract


def ready_inputs():
    return {
        "environment": {
            "name": "CI",
            "pr_or_dispatch_only": True,
            "production_environment_injected": False,
        },
        "database": {
            "kind": "EPHEMERAL_POSTGRES_SERVICE",
            "persistent_volume": False,
            "recreated_per_job": True,
            "host_class": "CI_SERVICE",
            "render_endpoint_used": False,
            "public_endpoint_used": False,
        },
        "credential_policy": {
            "test_only_credentials": True,
            "platform_secret_used": False,
            "production_dsn_used": False,
            "job_scoped": True,
            "credential_value_from_repository": False,
        },
        "evidence_policy": {
            "may_infer_production_readiness": False,
            "explicit_nonproduction_label": True,
            "unique_test_database": True,
            "cleanup_required": True,
            "fail_closed_on_unexpected_host": True,
            "attests_render_postgres": False,
        },
    }


class EphemeralPostgresCIContractV1Tests(unittest.TestCase):
    def zero(self, out):
        for key in contract.FALSE_FIELDS:
            self.assertIs(out[key], False, key)

    def test_ready_unlocks_ci_implementation_only(self):
        out = contract.evaluate_ephemeral_postgres_ci_contract(**ready_inputs())
        self.assertEqual(out["state"], contract.READY)
        self.assertFalse(out["production_equivalence"])
        self.assertTrue(out["may_prove_driver_connectivity"])
        self.zero(out)

    def test_only_ci_environment_is_allowed(self):
        data = ready_inputs()
        data["environment"]["name"] = "PRODUCTION"
        out = contract.evaluate_ephemeral_postgres_ci_contract(**data)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("CI_ENVIRONMENT_REQUIRED", out["blockers"])
        self.zero(out)

    def test_persistent_storage_is_forbidden(self):
        data = ready_inputs()
        data["database"]["persistent_volume"] = True
        out = contract.evaluate_ephemeral_postgres_ci_contract(**data)
        self.assertIn("NO_PERSISTENT_VOLUME_REQUIRED", out["blockers"])
        self.zero(out)

    def test_render_or_public_endpoint_is_forbidden(self):
        data = ready_inputs()
        data["database"]["render_endpoint_used"] = True
        data["database"]["public_endpoint_used"] = True
        out = contract.evaluate_ephemeral_postgres_ci_contract(**data)
        self.assertIn("NO_RENDER_ENDPOINT_REQUIRED", out["blockers"])
        self.assertIn("NO_PUBLIC_DATABASE_ENDPOINT_REQUIRED", out["blockers"])
        self.zero(out)

    def test_production_secret_or_dsn_is_forbidden(self):
        data = ready_inputs()
        data["credential_policy"]["platform_secret_used"] = True
        data["credential_policy"]["production_dsn_used"] = True
        out = contract.evaluate_ephemeral_postgres_ci_contract(**data)
        self.assertIn("NO_PLATFORM_SECRET_REQUIRED", out["blockers"])
        self.assertIn("NO_PRODUCTION_DSN_REQUIRED", out["blockers"])
        self.zero(out)

    def test_ci_evidence_cannot_be_promoted_to_production_attestation(self):
        data = ready_inputs()
        data["evidence_policy"]["may_infer_production_readiness"] = True
        data["evidence_policy"]["attests_render_postgres"] = True
        out = contract.evaluate_ephemeral_postgres_ci_contract(**data)
        self.assertIn("NO_PRODUCTION_READINESS_INFERENCE_REQUIRED", out["blockers"])
        self.assertIn("CI_HARNESS_MUST_NOT_ATTEST_RENDER_PRODUCTION", out["blockers"])
        self.zero(out)

    def test_repo_stored_db_credential_is_forbidden(self):
        data = ready_inputs()
        data["credential_policy"]["credential_value_from_repository"] = True
        out = contract.evaluate_ephemeral_postgres_ci_contract(**data)
        self.assertIn("REPOSITORY_STORED_DB_CREDENTIAL_FORBIDDEN", out["blockers"])
        self.zero(out)


if __name__ == "__main__":
    unittest.main()
