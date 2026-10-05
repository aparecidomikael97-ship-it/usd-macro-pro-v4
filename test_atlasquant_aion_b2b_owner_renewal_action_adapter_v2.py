from __future__ import annotations

from copy import deepcopy
import inspect
from pathlib import Path
import unittest
from unittest.mock import patch

import atlasquant_aion_b2b_owner_renewal_action_adapter_plan as adapter_v1
import atlasquant_aion_b2b_owner_renewal_action_adapter_plan_v2 as adapter
import atlasquant_aion_b2b_owner_renewal_action_adapter_dry_run_v2 as dry
import atlasquant_aion_b2b_owner_renewal_action_adapter_receipt_v2 as receipts
from atlasquant_aion_b2b_owner_renewal_action_command_plan import (
    build_owner_renewal_action_command_plan,
)
from atlasquant_aion_b2b_owner_renewal_action_command_plan_v2 import (
    build_owner_renewal_action_command_plan_v2,
)
from test_atlasquant_aion_b2b_owner_renewal_action_command_plan import (
    SCOPE,
    persisted,
    writer,
    preflight,
)

NOW = "2026-10-05T23:20:30Z"
ISSUED = "2026-10-05T23:20:00Z"
EXPIRES = "2026-10-05T23:22:00Z"


def args_v2(family="RENEWAL"):
    choice = next(
        key
        for key, value in adapter_v1.ACTION_FAMILY.items()
        if value == family
    )
    p = persisted(action_family=family, requested_choice=choice)
    w = writer(action_family=family, requested_choice=choice)
    f = preflight(action_family=family, requested_choice=choice)
    command = build_owner_renewal_action_command_plan_v2(
        execution_persistence_attestation=p,
        execution_writer_attestation=w,
        execution_preflight=f,
    )
    cp = command["command_plan"]
    binding = {
        "scope": deepcopy(command["scope"]),
        **{key: cp[key] for key in adapter.BINDING_FIELDS_V2},
        "command_plan_digest": command["command_plan_digest"],
    }
    environment = {
        "schema": adapter.ENVIRONMENT_SCHEMA,
        "synthetic": True,
        "binding": binding,
        "as_of": ISSUED,
        "expires_at": EXPIRES,
        "evidence_refs": ["synthetic:adapter-v2-evidence"],
        "provider_state": "SYNTHETIC_READY",
        "rollback_state": "SYNTHETIC_READY",
        "capacity_sufficient": True,
        "rollback_supported": True,
        "finops_monthly_cents": 20000,
        **{key: False for key in adapter.RISKS},
    }
    return {
        "command_plan": command,
        "execution_persistence_attestation": p,
        "execution_writer_attestation": w,
        "execution_preflight": f,
        "adapter_environment": environment,
        "now_ts": NOW,
    }


def dry_args_v2(plan=None, family="RENEWAL"):
    plan = plan or adapter.build_owner_renewal_action_adapter_plan_v2(
        **args_v2(family)
    )
    body = plan["adapter_plan"]
    provider = {
        "schema": dry.SNAPSHOT_SCHEMA,
        "synthetic": True,
        "binding": deepcopy(body["binding"]),
        "environment": deepcopy(body["environment"]),
    }
    provider["state_digest"] = adapter_v1.digest(provider)
    service = {
        "schema": dry.SERVICE_SCHEMA,
        "synthetic": True,
        "binding": deepcopy(body["binding"]),
        "environment": deepcopy(body["environment"]),
        "contract_state": "SYNTHETIC_VALID",
        "service_state": "SYNTHETIC_HEALTHY",
        "before_state": {
            "staging_revision": 0,
            "change_pending": False,
        },
    }
    service["state_digest"] = adapter_v1.digest(service)
    return {
        "adapter_plan": plan,
        "synthetic_adapter_capabilities": list(body["required_capabilities"]),
        "synthetic_provider_snapshot": provider,
        "synthetic_contract_service_state": service,
        "now_ts": NOW,
    }


def receipt_args_v2():
    inputs = dry_args_v2()
    out = dry.build_owner_renewal_action_adapter_dry_run_v2(**inputs)
    simulation = out["simulation"]
    binding = simulation["binding"]
    row = {
        "schema": receipts.SYNTHETIC_RECEIPT_SCHEMA,
        "synthetic": True,
        "binding": deepcopy(binding),
        "command_plan_digest": binding["command_plan_digest"],
        "adapter_plan_digest": simulation["adapter_plan_digest"],
        "dry_run_digest": out["dry_run_digest"],
        "rollback_plan_digest": simulation["rollback_plan_digest"],
        "owner_execution_authorization_digest":
            receipts.owner_execution_binding_digest_v2(binding),
        "action_family": binding["action_family"],
        "customer_id": binding["customer_id"],
        "pilot_id": binding["pilot_id"],
        "package": binding["package"],
        "idempotency_key_digest": simulation["idempotency_key_digest"],
        "before_state_digest": simulation["before_state_digest"],
        "after_state_digest": simulation["after_state_digest"],
        "timestamp": NOW,
        "writer_identity_ref": "synthetic:writer-v2",
        "provider_identity_ref": "synthetic:provider-v2",
        "evidence_refs": list(simulation["evidence_refs"]),
        **{key: False for key in adapter.FALSE_FIELDS},
    }
    row["receipt_digest"] = adapter_v1.digest(row)
    return {**inputs, "dry_run": out, "receipt": row}


class AdapterV2ReconciliationTests(unittest.TestCase):
    def assert_flags(self, out):
        for key in adapter.FALSE_FIELDS:
            self.assertIs(out[key], False, key)

    def test_public_v2_chain_has_no_trusted_scope_argument(self):
        for fn in (
            adapter.build_owner_renewal_action_adapter_plan_v2,
            adapter.validate_adapter_plan_v2,
            dry.build_owner_renewal_action_adapter_dry_run_v2,
            dry.validate_dry_run_v2,
            receipts.validate_synthetic_owner_renewal_action_receipt_v2,
        ):
            self.assertNotIn("trusted_scope", inspect.signature(fn).parameters)

    def test_happy_path_uses_command_plan_v2_and_persisted_scope(self):
        out = adapter.build_owner_renewal_action_adapter_plan_v2(**args_v2())
        self.assertEqual(out["state"], adapter.READY)
        self.assertEqual(out["command_plan_schema"],
            "ATLASQUANT_AION_B2B_OWNER_RENEWAL_ACTION_COMMAND_PLAN_V2")
        self.assertEqual(out["scope_source"], "PERSISTED_EXECUTION_RECORD")
        self.assertEqual(
            out["operation_kind_source"],
            "DERIVED_FROM_ACTION_FAMILY",
        )
        body = adapter.validate_adapter_plan_v2(out, NOW)
        self.assertEqual(body["binding"]["scope"], SCOPE)
        self.assertIn("execution_request_digest", body["binding"])
        self.assert_flags(out)

    def test_v1_command_plan_is_not_accepted_by_v2_adapter(self):
        data = args_v2()
        p = data["execution_persistence_attestation"]
        w = data["execution_writer_attestation"]
        f = data["execution_preflight"]
        data["command_plan"] = build_owner_renewal_action_command_plan(
            trusted_scope=SCOPE,
            execution_persistence_attestation=p,
            execution_writer_attestation=w,
            execution_preflight=f,
        )
        out = adapter.build_owner_renewal_action_adapter_plan_v2(**data)
        self.assertEqual(out["state"], "BLOCKED")

    def test_scope_overflow_blocks_before_adapter_ready(self):
        data = args_v2()
        long_owner = "o" * 121
        p = data["execution_persistence_attestation"]
        p["scope"] = dict(p["scope"])
        p["scope"]["owner_id"] = long_owner
        p["owner_id"] = long_owner
        f = data["execution_preflight"]
        f["scope"] = dict(f["scope"])
        f["scope"]["owner_id"] = long_owner
        f["owner_id"] = long_owner
        data["command_plan"] = build_owner_renewal_action_command_plan_v2(
            execution_persistence_attestation=p,
            execution_writer_attestation=data["execution_writer_attestation"],
            execution_preflight=f,
        )
        out = adapter.build_owner_renewal_action_adapter_plan_v2(**data)
        self.assertEqual(out["state"], "BLOCKED")

    def test_command_plan_tamper_blocks_even_with_rehashed_local_copy(self):
        data = args_v2()
        data["command_plan"]["command_plan"]["customer_id"] = "other-customer"
        data["command_plan"]["customer_id"] = "other-customer"
        data["command_plan"]["command_plan_digest"] = adapter_v1.digest(
            data["command_plan"]["command_plan"]
        )
        out = adapter.build_owner_renewal_action_adapter_plan_v2(**data)
        self.assertEqual(out["state"], "BLOCKED")

    def test_execution_request_digest_is_bound_into_adapter(self):
        out = adapter.build_owner_renewal_action_adapter_plan_v2(**args_v2())
        body = out["adapter_plan"]
        self.assertEqual(
            body["binding"]["execution_request_digest"],
            args_v2()["execution_persistence_attestation"][
                "execution_request_digest"
            ],
        )
        self.assertEqual(
            body["binding"]["command_plan_digest"],
            args_v2()["command_plan"]["command_plan_digest"],
        )

    def test_all_action_families_remain_synthetic_only(self):
        for family in adapter.CAPABILITIES:
            with self.subTest(family=family):
                out = adapter.build_owner_renewal_action_adapter_plan_v2(
                    **args_v2(family)
                )
                self.assertEqual(out["state"], adapter.READY)
                self.assert_flags(out)
                self.assertEqual(
                    out["adapter_plan"]["provider_class"],
                    "SYNTHETIC_MANAGED_SERVICE",
                )

    def test_finops_cap_and_irreversible_boundary_remain_fail_closed(self):
        data = args_v2()
        data["adapter_environment"]["finops_monthly_cents"] = 20001
        self.assertEqual(
            adapter.build_owner_renewal_action_adapter_plan_v2(**data)["state"],
            "BLOCKED",
        )
        data = args_v2()
        data["adapter_environment"]["irreversible_boundary_detected"] = True
        self.assertEqual(
            adapter.build_owner_renewal_action_adapter_plan_v2(**data)["state"],
            "BLOCKED",
        )

    def test_missing_rollback_support_blocks(self):
        data = args_v2()
        data["adapter_environment"]["rollback_supported"] = False
        self.assertEqual(
            adapter.build_owner_renewal_action_adapter_plan_v2(**data)["state"],
            "BLOCKED",
        )

    def test_v2_dry_run_is_detached_synthetic_staging_only(self):
        out = dry.build_owner_renewal_action_adapter_dry_run_v2(
            **dry_args_v2()
        )
        self.assertEqual(out["state"], "DRY_RUN_READY")
        simulation = out["simulation"]
        self.assertEqual(simulation["adapter_contract_version"], "V2")
        self.assertEqual(
            simulation["scope_source"],
            "PERSISTED_EXECUTION_RECORD",
        )
        self.assertEqual(
            simulation["expected_mutations"],
            ["SYNTHETIC_STAGING_CHANGE_ONLY"],
        )
        self.assertEqual(
            simulation["expected_customer_impact"],
            "NO_REAL_CUSTOMER_CHANGE",
        )
        self.assertEqual(
            simulation["expected_finops_impact"],
            "NO_REAL_CHARGE_OR_QUOTA_CHANGE",
        )
        self.assert_flags(out)
        self.assert_flags(simulation)

    def test_missing_capability_blocks_v2_dry_run(self):
        data = dry_args_v2()
        data["synthetic_adapter_capabilities"].pop()
        out = dry.build_owner_renewal_action_adapter_dry_run_v2(**data)
        self.assertEqual(out["state"], "DRY_RUN_BLOCKED")

    def test_v2_synthetic_receipt_validates_without_real_execution_claim(self):
        data = receipt_args_v2()
        out = receipts.validate_synthetic_owner_renewal_action_receipt_v2(
            **data
        )
        self.assertEqual(out["state"], "SYNTHETIC_RECEIPT_VALIDATED")
        self.assertFalse(out["actual_receipt_generated"])
        self.assertFalse(out["provider_identity_authenticated"])
        self.assertFalse(out["writer_identity_authenticated"])
        self.assertFalse(out["execution_verified"])
        self.assert_flags(out)

    def test_receipt_execution_request_binding_cannot_be_swapped(self):
        data = receipt_args_v2()
        data["receipt"]["binding"]["execution_request_digest"] = (
            "sha256:" + "f" * 64
        )
        data["receipt"]["receipt_digest"] = adapter_v1.digest(
            {
                key: value
                for key, value in data["receipt"].items()
                if key != "receipt_digest"
            }
        )
        out = receipts.validate_synthetic_owner_renewal_action_receipt_v2(
            **data
        )
        self.assertEqual(out["state"], "BLOCKED")

    def test_v2_contract_is_schema_only_and_non_authorizing(self):
        out = receipts.owner_renewal_action_receipt_contract_v2()
        self.assertEqual(out["state"], "FUTURE_RECEIPT_SCHEMA_ONLY")
        self.assertTrue(
            out["future_real_receipt_requires_separate_authenticated_verifier"]
        )
        self.assertFalse(out["actual_receipt_generated"])
        self.assert_flags(out)

    def test_v2_chain_deterministic(self):
        first = adapter.build_owner_renewal_action_adapter_plan_v2(**args_v2())
        second = adapter.build_owner_renewal_action_adapter_plan_v2(**args_v2())
        self.assertEqual(first, second)
        first_dry = dry.build_owner_renewal_action_adapter_dry_run_v2(
            **dry_args_v2(first)
        )
        second_dry = dry.build_owner_renewal_action_adapter_dry_run_v2(
            **dry_args_v2(second)
        )
        self.assertEqual(first_dry, second_dry)

    def test_v2_modules_import_no_provider_executor_or_network_stack(self):
        import ast
        for module in (adapter, dry, receipts):
            tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    names = (
                        [node.module]
                        if isinstance(node, ast.ImportFrom)
                        else [item.name for item in node.names]
                    )
                    for name in names:
                        self.assertFalse(
                            any(
                                part in (name or "")
                                for part in (
                                    "requests",
                                    "httpx",
                                    "socket",
                                    "subprocess",
                                    "executor",
                                    "billing",
                                    "crm",
                                    "provider",
                                )
                            ),
                            name,
                        )

    def test_v2_runtime_attempts_zero_external_io(self):
        adapter_inputs = args_v2()
        dry_inputs = dry_args_v2()
        receipt_inputs = receipt_args_v2()

        def forbidden(*args, **kwargs):
            raise AssertionError("forbidden side effect attempted")

        targets = (
            "builtins.open",
            "os.system",
            "socket.socket",
            "socket.create_connection",
            "subprocess.Popen",
            "subprocess.run",
            "atlasquant_aion_checkpoint_master.append_checkpoint_patch",
        )
        from contextlib import ExitStack
        with ExitStack() as stack:
            mocks = [
                stack.enter_context(patch(target, side_effect=forbidden))
                for target in targets
            ]
            a = adapter.build_owner_renewal_action_adapter_plan_v2(
                **adapter_inputs
            )
            d = dry.build_owner_renewal_action_adapter_dry_run_v2(**dry_inputs)
            r = receipts.validate_synthetic_owner_renewal_action_receipt_v2(
                **receipt_inputs
            )
            self.assertEqual(a["state"], adapter.READY)
            self.assertEqual(d["state"], "DRY_RUN_READY")
            self.assertEqual(r["state"], "SYNTHETIC_RECEIPT_VALIDATED")
            for mock in mocks:
                mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
