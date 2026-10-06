"""Executable offline safety matrix. Every generated case is a unittest test."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
import time
import unittest
from unittest.mock import patch

import atlasquant_aion_b2b_owner_renewal_action_adapter_plan as adapter
import atlasquant_aion_b2b_owner_renewal_action_adapter_dry_run as dry
import atlasquant_aion_b2b_owner_renewal_action_adapter_receipt as receipts
from test_atlasquant_aion_b2b_owner_renewal_action_command_plan import (
    SCOPE, h, persisted, writer, preflight, run,
)

NOW = "2026-10-05T23:00:30Z"
ISSUED = "2026-10-05T23:00:00Z"
EXPIRES = "2026-10-05T23:02:00Z"


def args(family="RENEWAL"):
    choice = next(key for key, value in adapter.ACTION_FAMILY.items() if value == family)
    p = persisted(action_family=family, requested_choice=choice)
    w = writer(action_family=family, requested_choice=choice)
    f = preflight(action_family=family, requested_choice=choice)
    command = run(execution_persistence_attestation=p, execution_writer_attestation=w,
                  execution_preflight=f)
    cp = command["command_plan"]
    binding = {"scope": dict(SCOPE), **{key: cp[key] for key in adapter.BINDING_FIELDS},
               "command_plan_digest": command["command_plan_digest"]}
    environment = {
        "schema": adapter.ENVIRONMENT_SCHEMA, "synthetic": True, "binding": binding,
        "as_of": ISSUED, "expires_at": EXPIRES, "evidence_refs": ["synthetic:adapter-evidence"],
        "provider_state": "SYNTHETIC_READY", "rollback_state": "SYNTHETIC_READY",
        "capacity_sufficient": True, "rollback_supported": True, "finops_monthly_cents": 20000,
        **{key: False for key in adapter.RISKS},
    }
    return dict(trusted_scope=dict(SCOPE), command_plan=command,
        execution_persistence_attestation=p, execution_writer_attestation=w,
        execution_preflight=f, adapter_environment=environment, now_ts=NOW)


def dry_args(plan=None, family="RENEWAL"):
    plan = plan or adapter.build_owner_renewal_action_adapter_plan(**args(family))
    body = plan["adapter_plan"]
    provider = {"schema": dry.SNAPSHOT_SCHEMA, "synthetic": True,
        "binding": deepcopy(body["binding"]), "environment": deepcopy(body["environment"])}
    provider["state_digest"] = adapter.digest(provider)
    service = {"schema": dry.SERVICE_SCHEMA, "synthetic": True,
        "binding": deepcopy(body["binding"]), "environment": deepcopy(body["environment"]),
        "contract_state": "SYNTHETIC_VALID", "service_state": "SYNTHETIC_HEALTHY",
        "before_state": {"staging_revision": 0, "change_pending": False}}
    service["state_digest"] = adapter.digest(service)
    return dict(adapter_plan=plan, trusted_scope=dict(SCOPE),
        synthetic_adapter_capabilities=list(body["required_capabilities"]),
        synthetic_provider_snapshot=provider, synthetic_contract_service_state=service, now_ts=NOW)


def receipt_args():
    inputs = dry_args()
    out = dry.build_owner_renewal_action_adapter_dry_run(**inputs)
    s = out["simulation"]
    b = s["binding"]
    row = {
        "schema": receipts.SYNTHETIC_RECEIPT_SCHEMA, "synthetic": True, "binding": deepcopy(b),
        "command_plan_digest": b["command_plan_digest"], "adapter_plan_digest": s["adapter_plan_digest"],
        "dry_run_digest": out["dry_run_digest"], "rollback_plan_digest": s["rollback_plan_digest"],
        "owner_execution_authorization_digest": receipts.owner_execution_binding_digest(b),
        "action_family": b["action_family"], "customer_id": b["customer_id"], "pilot_id": b["pilot_id"],
        "package": b["package"], "idempotency_key_digest": s["idempotency_key_digest"],
        "before_state_digest": s["before_state_digest"], "after_state_digest": s["after_state_digest"],
        "timestamp": NOW, "writer_identity_ref": "synthetic:writer", "provider_identity_ref": "synthetic:provider",
        "evidence_refs": list(s["evidence_refs"]), **{key: False for key in adapter.FALSE_FIELDS},
    }
    row["receipt_digest"] = adapter.digest(row)
    return dict(inputs, dry_run=out, receipt=row)


def rehash_plan(plan):
    body = plan["adapter_plan"]
    body["rollback_plan_digest"] = adapter.digest(body["rollback_plan"])
    body["environment_digest"] = adapter.digest(body["environment"])
    plan["adapter_plan_digest"] = adapter.digest(body)


class Hostile:
    def __bool__(self): raise AssertionError("caller bool executed")
    def __str__(self): raise AssertionError("caller str executed")
    def __iter__(self): raise AssertionError("caller iter executed")


class HostileDict(dict):
    def items(self): raise AssertionError("caller mapping executed")


class AdapterSafetyTests(unittest.TestCase):
    def assert_flags(self, out):
        for key in adapter.FALSE_FIELDS:
            self.assertIs(out[key], False, key)

    def test_happy_path_rebuilds_existing_command_contract(self):
        inputs = args()
        out = adapter.build_owner_renewal_action_adapter_plan(**inputs)
        self.assertEqual(out["state"], adapter.READY)
        self.assert_flags(out)
        self.assertEqual(adapter.validate_adapter_plan(out, SCOPE, NOW), out["adapter_plan"])

    def test_offline_dry_run_and_receipt_are_not_execution(self):
        inputs = receipt_args()
        out = receipts.validate_synthetic_owner_renewal_action_receipt(**inputs)
        self.assertEqual(inputs["dry_run"]["state"], "DRY_RUN_READY")
        self.assertEqual(out["state"], "SYNTHETIC_RECEIPT_VALIDATED")
        for obj in (out, inputs["dry_run"], inputs["dry_run"]["simulation"], receipts.owner_renewal_action_receipt_contract()):
            self.assert_flags(obj)
        self.assertIs(out["execution_verified"], False)
        self.assertIs(out["provider_identity_authenticated"], False)
        self.assertIs(out["writer_identity_authenticated"], False)
        self.assertIs(out["actual_receipt_generated"], False)

    def test_inputs_outputs_are_independent_and_repeatable(self):
        inputs = args()
        saved = deepcopy(inputs)
        out = adapter.build_owner_renewal_action_adapter_plan(**inputs)
        saved_out = deepcopy(out)
        self.assertEqual(inputs, saved)
        for _ in range(100):
            self.assertEqual(adapter.build_owner_renewal_action_adapter_plan(**inputs), saved_out)
        inputs["adapter_environment"]["binding"]["scope"]["tenant_id"] = "other"
        inputs["adapter_environment"]["evidence_refs"].append("extra")
        inputs["command_plan"]["command_plan"]["customer_id"] = "other"
        self.assertEqual(out, saved_out)
        out["adapter_plan"]["required_capabilities"].clear()
        self.assertEqual(adapter.build_owner_renewal_action_adapter_plan(**saved), saved_out)

    def test_parallel_calls_do_not_share_lists_or_contaminate(self):
        inputs = args()
        with ThreadPoolExecutor(max_workers=8) as pool:
            outputs = list(pool.map(lambda _: adapter.build_owner_renewal_action_adapter_plan(**inputs), range(32)))
        self.assertTrue(all(row == outputs[0] for row in outputs))
        outputs[0]["adapter_plan"]["required_capabilities"].clear()
        self.assertTrue(outputs[1]["adapter_plan"]["required_capabilities"])

    def test_bounds_cycle_and_large_payload_finish_fail_closed(self):
        nested = {}
        cursor = nested
        for _ in range(100):
            cursor["nested"] = {}; cursor = cursor["nested"]
        cycle = {}; cycle["cycle"] = cycle
        start = time.perf_counter()
        for value in ([0] * 100000, nested, cycle, "x" * 1000000):
            inputs = args(); inputs["adapter_environment"] = value
            self.assertEqual(adapter.build_owner_renewal_action_adapter_plan(**inputs)["state"], "BLOCKED")
        self.assertLess(time.perf_counter() - start, 2.0)

    def test_large_input_rejection_has_bounded_additional_memory(self):
        import tracemalloc
        inputs = args(); inputs["adapter_environment"] = [0] * 100000
        tracemalloc.start()
        try:
            start = time.perf_counter()
            for _ in range(100):
                self.assertEqual(adapter.build_owner_renewal_action_adapter_plan(**inputs)["state"], "BLOCKED")
            _, peak = tracemalloc.get_traced_memory()
            self.assertLess(peak, 2 * 1024 * 1024)
            self.assertLess(time.perf_counter() - start, 2.0)
        finally:
            tracemalloc.stop()

    def test_no_input_string_or_extra_key_is_echoed_on_failure(self):
        inputs = args(); inputs["adapter_environment"]["token"] = "SECRET_CANARY"
        out = adapter.build_owner_renewal_action_adapter_plan(**inputs)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertNotIn("SECRET_CANARY", repr(out))

    def test_dry_and_receipt_inputs_not_modified(self):
        inputs = receipt_args(); saved = deepcopy(inputs)
        receipts.validate_synthetic_owner_renewal_action_receipt(**inputs)
        self.assertEqual(inputs, saved)
        out = dry.build_owner_renewal_action_adapter_dry_run(**dry_args())
        self.assertEqual(out, dry.build_owner_renewal_action_adapter_dry_run(**dry_args()))

    def test_zero_io_entire_new_chain(self):
        # Imports and synthetic fixtures are prepared before instrumenting.
        inputs = args(); dinputs = dry_args(); rinputs = receipt_args()
        from contextlib import ExitStack
        from atlasquant_aion_nonce_registry import PersistentNonceRegistry
        from atlasquant_aion_unified_journal_store import UnifiedJournalStore
        def forbidden(*a, **k): raise AssertionError("forbidden side effect attempted")
        targets = ["builtins.open", "pathlib.Path.open", "pathlib.Path.read_text",
            "pathlib.Path.read_bytes", "pathlib.Path.write_text", "pathlib.Path.write_bytes",
            "pathlib.Path.rename", "pathlib.Path.replace", "pathlib.Path.unlink", "io.open", "os.open",
            "os.rename", "os.replace", "os.remove", "os.system",
            "socket.socket", "socket.create_connection", "subprocess.Popen", "subprocess.run",
            "atlasquant_aion_checkpoint_master.append_checkpoint_patch"]
        with ExitStack() as stack:
            mocks = [stack.enter_context(patch(target, side_effect=forbidden)) for target in targets]
            mocks += [stack.enter_context(patch.object(cls, "__init__", side_effect=forbidden))
                      for cls in (PersistentNonceRegistry, UnifiedJournalStore)]
            a = adapter.build_owner_renewal_action_adapter_plan(**inputs)
            d = dry.build_owner_renewal_action_adapter_dry_run(**dinputs)
            r = receipts.validate_synthetic_owner_renewal_action_receipt(**rinputs)
            self.assertEqual(a["state"], adapter.READY)
            self.assertEqual(d["state"], "DRY_RUN_READY")
            self.assertEqual(r["state"], "SYNTHETIC_RECEIPT_VALIDATED")
            for mock in mocks: mock.assert_not_called()

    def test_imports_exclude_executor_and_provider_paths(self):
        import ast
        for module in (adapter, dry, receipts):
            tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    names = [node.module] if isinstance(node, ast.ImportFrom) else [n.name for n in node.names]
                    for name in names:
                        self.assertFalse(any(part in (name or "") for part in
                            ("requests", "httpx", "socket", "subprocess", "executor", "billing", "crm", "provider")), name)

    def test_real_upstream_writer_verifier_output_is_accepted_offline(self):
        # The established verifier handles keys and nonce persistence BEFORE the
        # adapter; those test-only operations are not part of the zero-I/O chain.
        import tempfile
        from test_atlasquant_aion_b2b_owner_renewal_action_execution_writer_attestation import (
            built, b64url, receipt as upstream_receipt, NOW as WRITER_NOW,
        )
        from atlasquant_aion_b2b_owner_renewal_action_execution_writer_attestation import (
            canonical_owner_execution_writer_bytes, verify_owner_execution_writer_attestation,
        )
        from atlasquant_aion_nonce_registry import PersistentNonceRegistry
        inputs = args(); p = inputs["execution_persistence_attestation"]
        raw = upstream_receipt(receipt_digest=p["receipt_digest"],
            after_checkpoint_digest=p["after_checkpoint_digest"], execution_record_digest=p["execution_record_digest"])
        p["receipt_digest"] = raw["receipt_digest"]
        private, registry, request, raw = built(raw)
        signature = b64url(private.sign(canonical_owner_execution_writer_bytes(request["request"])))
        with tempfile.TemporaryDirectory() as td:
            verified = verify_owner_execution_writer_attestation(request["request"],
                writer_signature_b64=signature, checkpoint_write_receipt=raw,
                writer_trust_roots=registry, nonce_registry=PersistentNonceRegistry(Path(td)/"nonce.sqlite3"),
                now_ts=WRITER_NOW)
            # Existing registry connections are scope-local but collect cycles;
            # collect before Windows attempts to delete the temporary WAL DB.
            import gc
            gc.collect()
        self.assertEqual(verified["state"], "EXECUTION_INTENT_CHECKPOINT_WRITER_AUTHORITY_ATTESTED")
        inputs["execution_writer_attestation"] = verified
        inputs["command_plan"] = run(execution_persistence_attestation=p,
            execution_writer_attestation=verified, execution_preflight=inputs["execution_preflight"])
        cp = inputs["command_plan"]["command_plan"]
        inputs["adapter_environment"]["binding"] = {"scope": dict(SCOPE),
            **{key: cp[key] for key in adapter.BINDING_FIELDS},
            "command_plan_digest": inputs["command_plan"]["command_plan_digest"]}
        self.assertEqual(adapter.build_owner_renewal_action_adapter_plan(**inputs)["state"], adapter.READY)


def add_case(name, exercise):
    def test(self): exercise(self)
    test.__name__ = "test_" + name
    setattr(AdapterSafetyTests, test.__name__, test)


def blocked_input(field, value):
    def exercise(self):
        inputs = args(); inputs[field] = value
        out = adapter.build_owner_renewal_action_adapter_plan(**inputs)
        self.assertEqual(out["state"], "BLOCKED")
        self.assert_flags(out)
    return exercise


for index, value in enumerate((None, True, False, 1, 0, "OK", [], Hostile(), HostileDict(),
        Decimal("1"), Fraction(1, 2), float("nan"), float("inf"), b"bytes")):
    for field in ("command_plan", "adapter_environment", "trusted_scope"):
        add_case(f"hostile_{field}_{index}", blocked_input(field, value))


for family in adapter.CAPABILITIES:
    def happy(self, family=family):
        out = adapter.build_owner_renewal_action_adapter_plan(**args(family))
        self.assertEqual(out["state"], adapter.READY)
        self.assertEqual(out["adapter_plan"]["required_capabilities"], list(adapter.CAPABILITIES[family]))
        result = dry.build_owner_renewal_action_adapter_dry_run(**dry_args(out))
        self.assertEqual(result["state"], "DRY_RUN_READY")
        self.assert_flags(result)
    add_case("family_" + family.lower(), happy)


for field in (*adapter.BINDING_FIELDS, "command_plan_digest"):
    def cross(self, field=field):
        inputs = args()
        inputs["adapter_environment"]["binding"][field] = h("f") if field.endswith("digest") else "OTHER"
        out = adapter.build_owner_renewal_action_adapter_plan(**inputs)
        self.assertEqual(out["state"], "BLOCKED")
    add_case("binding_" + field, cross)


for field in SCOPE:
    def cross(self, field=field):
        inputs = args(); inputs["trusted_scope"][field] = "cross-scope"
        self.assertEqual(adapter.build_owner_renewal_action_adapter_plan(**inputs)["state"], "BLOCKED")
    add_case("scope_" + field, cross)


ENV_BAD = {
    "future": ("as_of", "2026-10-06T00:00:00Z"),
    "old": ("expires_at", "2026-10-05T22:59:00Z"),
    "expired_equal": ("expires_at", NOW),
    "naive": ("as_of", "2026-10-05T23:00:00"),
    "invalid_zone": ("as_of", "2026-10-05T23:00:00+99:00"),
    "missing_time": ("as_of", None), "empty_time": ("as_of", ""),
    "long_window": ("expires_at", "2026-10-05T23:10:00Z"),
    "billing_dispute": ("billing_dispute", True),
    "security_incident": ("security_incident", True), "privacy_incident": ("privacy_incident", True),
    "contract_conflict": ("contract_conflict", True), "irreversible": ("irreversible_boundary_detected", True),
    "rollback_missing": ("rollback_supported", False), "rollback_degraded": ("rollback_state", "DEGRADED"),
    "provider_degraded": ("provider_state", "DEGRADED"), "capacity": ("capacity_sufficient", False),
    "missing_evidence": ("evidence_refs", []), "duplicate_evidence": ("evidence_refs", ["a", "a"]),
    "finops_over_cap": ("finops_monthly_cents", 20001), "finops_bool": ("finops_monthly_cents", True),
    "finops_negative": ("finops_monthly_cents", -1), "real_environment": ("synthetic", False),
    "future_schema": ("schema", "FUTURE"),
}
for label, (field, value) in ENV_BAD.items():
    def exercise(self, field=field, value=value):
        inputs = args(); inputs["adapter_environment"][field] = value
        self.assertEqual(adapter.build_owner_renewal_action_adapter_plan(**inputs)["state"], "BLOCKED")
    add_case("environment_" + label, exercise)


for field in adapter.FALSE_FIELDS:
    def flip(self, field=field):
        plan = adapter.build_owner_renewal_action_adapter_plan(**args())
        plan["adapter_plan"][field] = True; rehash_plan(plan)
        inputs = dry_args(); inputs["adapter_plan"] = plan
        out = dry.build_owner_renewal_action_adapter_dry_run(**inputs)
        self.assertEqual(out["state"], "DRY_RUN_BLOCKED")
        self.assert_flags(out)
    add_case("rehash_authority_" + field, flip)


for key in ("credential", "token", "endpoint", "payload", "http_method", "shell", "subprocess", "headers", "authorization", "api_key"):
    def inject(self, key=key):
        inputs = args(); inputs["adapter_environment"]["injected"] = {key: "CANARY"}
        out = adapter.build_owner_renewal_action_adapter_plan(**inputs)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertNotIn("CANARY", repr(out))
    add_case("leakage_" + key, inject)


for label in ("unknown_adapter", "unknown_family", "choice_family", "operation_kind", "missing_rollback", "impossible_rollback", "irreversible", "missing_capability", "unsafe_capability", "digest_mismatch"):
    def exercise(self, label=label):
        inputs = dry_args(); plan = inputs["adapter_plan"]; body = plan["adapter_plan"]
        if label == "unknown_adapter": body["adapter_kind"] = "UNKNOWN"
        elif label == "unknown_family": body["binding"]["action_family"] = "UNKNOWN"
        elif label == "choice_family": body["binding"]["requested_choice"] = "REPRICE_REVIEW"
        elif label == "operation_kind": body["binding"]["operation_kind"] = "OTHER"
        elif label == "missing_rollback": body.pop("rollback_plan")
        elif label == "impossible_rollback": body["rollback_plan"]["rollback_supported"] = False
        elif label == "irreversible": body["rollback_plan"]["irreversible_boundary_detected"] = True
        elif label == "missing_capability": inputs["synthetic_adapter_capabilities"].pop()
        elif label == "unsafe_capability": inputs["synthetic_adapter_capabilities"].append("EXECUTE_PRODUCTION")
        elif label == "digest_mismatch": plan["adapter_plan_digest"] = h("a")
        if label not in ("missing_rollback", "digest_mismatch"): rehash_plan(plan)
        out = dry.build_owner_renewal_action_adapter_dry_run(**inputs)
        self.assertEqual(out["state"], "DRY_RUN_BLOCKED")
    add_case("dry_" + label, exercise)


for field in receipts.REQUIRED_FIELDS:
    def bad_receipt(self, field=field):
        inputs = receipt_args(); row = inputs["receipt"]
        row[field] = "OTHER"
        row["receipt_digest"] = adapter.digest({k: v for k, v in row.items() if k != "receipt_digest"})
        self.assertEqual(receipts.validate_synthetic_owner_renewal_action_receipt(**inputs)["state"], "BLOCKED")
    add_case("receipt_rehash_" + field, bad_receipt)


for label, field, value in (("synthetic_claim", "synthetic", 1), ("real_writer", "writer_identity_ref", "production:writer"),
        ("stale", "now_ts", EXPIRES), ("unsigned_digest", "receipt_digest", h("b")),
        ("real_receipt", "schema", "EXECUTED"), ("future_timestamp", "timestamp", EXPIRES)):
    def exercise(self, field=field, value=value):
        inputs = receipt_args()
        if field == "now_ts": inputs[field] = value
        else: inputs["receipt"][field] = value
        self.assertEqual(receipts.validate_synthetic_owner_renewal_action_receipt(**inputs)["state"], "BLOCKED")
    add_case("receipt_" + label, exercise)


for snapshot_field in ("synthetic_provider_snapshot", "synthetic_contract_service_state"):
    for label, (field, value) in ENV_BAD.items():
        def exercise(self, snapshot_field=snapshot_field, field=field, value=value):
            inputs = dry_args(); snapshot = inputs[snapshot_field]
            snapshot["environment"][field] = value
            snapshot["state_digest"] = adapter.digest({k: v for k, v in snapshot.items() if k != "state_digest"})
            self.assertEqual(dry.build_owner_renewal_action_adapter_dry_run(**inputs)["state"], "DRY_RUN_BLOCKED")
        add_case(snapshot_field + "_" + label, exercise)


for field in adapter.FALSE_FIELDS:
    def exercise(self, field=field):
        inputs = receipt_args(); row = inputs["receipt"]; row[field] = True
        row["receipt_digest"] = adapter.digest({k: v for k, v in row.items() if k != "receipt_digest"})
        out = receipts.validate_synthetic_owner_renewal_action_receipt(**inputs)
        self.assertEqual(out["state"], "BLOCKED"); self.assert_flags(out)
    add_case("receipt_authority_" + field, exercise)


for label in ("zero_as_false", "false_as_revision", "pending_before_state", "conflicting_cost", "extra_fields", "cross_snapshot"):
    def exercise(self, label=label):
        inputs = dry_args(); service = inputs["synthetic_contract_service_state"]
        if label == "zero_as_false":
            inputs["adapter_plan"]["adapter_plan"]["executes_action"] = 0
            rehash_plan(inputs["adapter_plan"])
        elif label == "false_as_revision": service["before_state"]["staging_revision"] = False
        elif label == "pending_before_state": service["before_state"]["change_pending"] = True
        elif label == "conflicting_cost": service["environment"]["finops_monthly_cents"] = 19999
        elif label == "extra_fields": service["unknown"] = "VALUE"
        elif label == "cross_snapshot": service["binding"]["scope"]["workspace_id"] = "other"
        service["state_digest"] = adapter.digest({k: v for k, v in service.items() if k != "state_digest"})
        self.assertEqual(dry.build_owner_renewal_action_adapter_dry_run(**inputs)["state"], "DRY_RUN_BLOCKED")
    add_case("conflict_" + label, exercise)


for field in ("command_plan", "execution_persistence_attestation", "execution_writer_attestation", "execution_preflight"):
    def exercise(self, field=field):
        inputs = args(); row = inputs[field]
        if field == "command_plan":
            row["command_plan"]["customer_id"] = "other-customer"
            row["customer_id"] = "other-customer"
            row["command_plan_digest"] = adapter.digest(row["command_plan"])
        else: row["customer_id"] = "other-customer"
        self.assertEqual(adapter.build_owner_renewal_action_adapter_plan(**inputs)["state"], "BLOCKED")
    add_case("upstream_cross_" + field, exercise)


if __name__ == "__main__":
    unittest.main()
