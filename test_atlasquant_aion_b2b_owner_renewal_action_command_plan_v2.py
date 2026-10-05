from __future__ import annotations

import inspect
import unittest

from atlasquant_aion_b2b_owner_renewal_action_command_plan_v2 import (
    build_owner_renewal_action_command_plan_v2,
)
from test_atlasquant_aion_b2b_owner_renewal_action_command_plan import (
    AUTHORITY_FIELDS,
    persisted,
    preflight,
    writer,
)


def run(**overrides):
    args = {
        "execution_persistence_attestation": persisted(),
        "execution_writer_attestation": writer(),
        "execution_preflight": preflight(),
    }
    args.update(overrides)
    return build_owner_renewal_action_command_plan_v2(**args)


class OwnerRenewalActionCommandPlanV2Tests(unittest.TestCase):
    def test_v2_removes_loose_trusted_scope_input(self):
        params = inspect.signature(
            build_owner_renewal_action_command_plan_v2
        ).parameters
        self.assertNotIn("trusted_scope", params)

    def test_valid_chain_derives_scope_from_persisted_record(self):
        out = run()
        self.assertEqual(
            out["state"],
            "READY_FOR_BUSINESS_ACTION_COMMAND_ADAPTER_REVIEW",
        )
        self.assertEqual(out["scope_source"], "PERSISTED_EXECUTION_RECORD")
        self.assertEqual(
            out["operation_kind_source"],
            "DERIVED_FROM_ACTION_FAMILY",
        )
        self.assertTrue(
            out["red_team_hardening"]["loose_trusted_scope_input_removed"]
        )
        self.assertTrue(
            out["red_team_hardening"]["identity_truncation_rejected"]
        )
        self.assertTrue(
            out["red_team_hardening"][
                "operation_kind_deterministically_derived"
            ]
        )

    def test_scope_identity_over_limit_blocks_instead_of_truncating(self):
        long_owner = "o" * 121
        p = persisted()
        p["scope"] = dict(p["scope"])
        p["scope"]["owner_id"] = long_owner
        p["owner_id"] = long_owner
        e = preflight()
        e["scope"] = dict(e["scope"])
        e["scope"]["owner_id"] = long_owner
        e["owner_id"] = long_owner
        out = run(
            execution_persistence_attestation=p,
            execution_preflight=e,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("PERSISTED_EXECUTION_SCOPE_INVALID", out["blockers"])

    def test_customer_identity_over_limit_blocks(self):
        long_customer = "c" * 121
        p = persisted(customer_id=long_customer)
        w = writer(customer_id=long_customer)
        e = preflight(customer_id=long_customer)
        out = run(
            execution_persistence_attestation=p,
            execution_writer_attestation=w,
            execution_preflight=e,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "PERSISTED_IDENTITY_INVALID:customer_id",
            out["blockers"],
        )

    def test_noncanonical_identity_whitespace_blocks(self):
        p = persisted(customer_id="customer  a")
        w = writer(customer_id="customer  a")
        e = preflight(customer_id="customer  a")
        out = run(
            execution_persistence_attestation=p,
            execution_writer_attestation=w,
            execution_preflight=e,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "PERSISTED_IDENTITY_INVALID:customer_id",
            out["blockers"],
        )

    def test_execution_request_digest_is_required(self):
        out = run(
            execution_persistence_attestation=persisted(
                execution_request_digest="sha256:not-valid"
            )
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("EXECUTION_REQUEST_DIGEST_INVALID", out["blockers"])

    def test_operation_kind_is_derived_from_signed_family(self):
        out = run()
        self.assertEqual(out["action_family"], "RENEWAL")
        self.assertEqual(out["operation_kind"], "CONTRACT_CONTINUITY")
        self.assertEqual(
            out["operation_kind_source"],
            "DERIVED_FROM_ACTION_FAMILY",
        )
        self.assertNotIn("operation_kind", writer())

    def test_v2_digest_binds_v2_provenance(self):
        first = run()
        second = run()
        self.assertEqual(
            first["command_plan_digest"],
            second["command_plan_digest"],
        )
        self.assertNotEqual(
            first["command_plan_digest"],
            first["command_plan_v1_digest"],
        )
        self.assertEqual(
            first["command_plan"]["execution_request_digest"],
            persisted()["execution_request_digest"],
        )

    def test_v2_remains_non_executable(self):
        out = run()
        for key in (
            "provider_operation_materialized",
            "provider_adapter_selected",
            "provider_endpoint_included",
            "http_method_included",
            "headers_included",
            "executable_payload_included",
            "credential_material_included",
            "secret_material_included",
            "execution_token_issued",
            "shell_command_generated",
            "execution_command_generated",
            "execution_command_executed",
            *AUTHORITY_FIELDS,
        ):
            self.assertFalse(out[key], key)


if __name__ == "__main__":
    unittest.main()
