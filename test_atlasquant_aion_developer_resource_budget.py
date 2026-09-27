"""Exact-int resource budgets at every developer trust boundary."""
from __future__ import annotations

from copy import deepcopy
import unittest

from atlasquant_aion_developer_command_policy import build_command_policy_contract
from atlasquant_aion_developer_content_attestation import attestation_for_documents
from atlasquant_aion_developer_manifest import (
    REQUIRED_MANDATORY_GATES,
    bind_builder_request_lineage,
    structural_request_roles,
)
from atlasquant_aion_developer_runner_contract import (
    _bind_runner_contract_ids,
    build_runner_contract,
)
from atlasquant_aion_developer_sandbox_preflight import (
    build_sandbox_preflight,
    expected_preflight_id,
    validate_resource_budget,
)


_FIELDS = {
    "runtime_seconds": {
        "valid": 1,
        "negative": -1,
        "zero": 0,
        "above": 901,
        "blocker": "RUNTIME_BUDGET_OUT_OF_RANGE",
        "numeric_string": "1",
    },
    "memory_mb": {
        "valid": 128,
        "negative": -1,
        "zero": 0,
        "above": 2049,
        "blocker": "MEMORY_BUDGET_OUT_OF_RANGE",
        "numeric_string": "128",
    },
    "output_bytes": {
        "valid": 1024,
        "negative": -1,
        "zero": 0,
        "above": 2_000_001,
        "blocker": "OUTPUT_BUDGET_OUT_OF_RANGE",
        "numeric_string": "1024",
    },
    "max_commands": {
        "valid": 1,
        "negative": -1,
        "zero": 0,
        "above": 25,
        "blocker": "COMMAND_BUDGET_OUT_OF_RANGE",
        "numeric_string": "1",
    },
}

_CLOSED = (
    "execution_authorized",
    "executor_attached",
    "commands_executed",
    "writes_files",
    "runs_tests",
    "network_called",
    "subprocess_called",
    "automatic_merge",
    "automatic_deploy",
    "real_trading_enabled",
)


def _request():
    return bind_builder_request_lineage({
        "schema": "ATLASQUANT_AION_DEVELOPER_BUILDER_SANDBOX_REQUEST_V1",
        "state": "READY_FOR_BUILDER_SANDBOX",
        "roles": structural_request_roles(),
        "lineage": {
            "snapshot_digest": "REPO-FIXTURE",
            "implementation_envelope_id": "DEVIMPL-FIXTURE",
            "implementation_authorization_id": "DEVAUTH-FIXTURE",
        },
        "branch_contract": {
            "branch": "cursor/fix",
            "baseline_ref": "main@aaa",
            "candidate_ref": "cursor/fix@bbb",
            "candidate_bound_to_branch": True,
            "main_branch_allowed": False,
            "force_push_allowed": False,
            "history_rewrite_allowed": False,
        },
        "scope": {
            "requested_files": ["test_module.py"],
            "authorized_files": ["test_module.py"],
            "scope_expansion_allowed": False,
            "new_file_allowed": False,
            "delete_file_allowed": False,
            "rename_file_allowed": False,
        },
        "test_contract": {
            "candidate_tests": ["test_module.py"],
            "mandatory_gates": list(REQUIRED_MANDATORY_GATES),
            "test_deletion_allowed": False,
            "test_weakening_allowed": False,
        },
        "blockers": [],
        "execution_authorized": False,
        "executor_attached": False,
        "writes_files": False,
    })


def _preflight(request=None, **budget):
    kwargs = {
        "environment_kind": "ISOLATED_WORKTREE",
        "environment_id": "sandbox-001",
        "isolated_worktree": True,
        "repository_root_bound": True,
        "network_disabled": True,
        "secrets_mounted": False,
        "command_policy": "ALLOWLIST_ONLY",
        "runtime_seconds": 900,
        "memory_mb": 2048,
        "output_bytes": 2_000_000,
        "max_commands": 24,
    }
    kwargs.update(budget)
    return build_sandbox_preflight(request or _request(), **kwargs)


def _runner(request, preflight):
    branch = request["branch_contract"]
    patch = {
        "schema": "ATLASQUANT_AION_DEVELOPER_PATCH_VALIDATION_V1",
        "validation_id": "DEVPATCHVAL-1",
        "state": "READY_FOR_PATCH_REVIEW",
        "builder_request_id": request["request_id"],
        "preflight_id": preflight["preflight_id"],
        "patch_digest": "DEVPATCH-ABC",
        "revision_binding": {
            "baseline_ref": branch["baseline_ref"],
            "candidate_ref": branch["candidate_ref"],
            "refs_match_approved_request": True,
            "revision_content_verified": True,
        },
        "blockers": [],
        "patch_applied": False,
        "execution_authorized": False,
        "executor_attached": False,
    }
    return build_runner_contract(
        request,
        preflight,
        patch,
        content_attestation=attestation_for_documents(request, preflight, patch),
        human_patch_reviewed=True,
        human_patch_reviewer="reviewer-independent",
        human_patch_review_refs=["review:patch:1"],
    )


def _assert_closed(test, document):
    for key in _CLOSED:
        if key in document:
            test.assertIs(document[key], False)


class ResourceBudgetTypeTests(unittest.TestCase):
    def test_each_field_rejects_non_exact_ints_and_enforces_range(self):
        bad_types = (True, False, None, 1.0, 1.9, [], {})
        for field, spec in _FIELDS.items():
            samples = bad_types + (spec["numeric_string"],)
            for value in samples:
                with self.subTest(field=field, value=value):
                    with self.assertRaises(ValueError):
                        _preflight(**{field: value})
                    with self.assertRaises(ValueError):
                        validate_resource_budget({
                            "runtime_seconds": 900,
                            "memory_mb": 2048,
                            "output_bytes": 2_000_000,
                            "max_commands": 24,
                            field: value,
                        })
            for label in ("negative", "zero", "above"):
                with self.subTest(field=field, label=label):
                    out = _preflight(**{field: spec[label]})
                    self.assertEqual(out["state"], "BLOCKED")
                    self.assertIn(spec["blocker"], out["blockers"])
                    self.assertIs(type(out["resource_budget"][field]), int)
                    self.assertEqual(out["resource_budget"][field], spec[label])
                    _assert_closed(self, out)
            with self.subTest(field=field, label="valid"):
                out = _preflight(**{field: spec["valid"]})
                self.assertEqual(out["state"], "READY_FOR_EXECUTOR_DESIGN_REVIEW")
                self.assertIs(type(out["resource_budget"][field]), int)
                self.assertEqual(out["resource_budget"][field], spec["valid"])
                self.assertEqual(out["preflight_id"], expected_preflight_id(out))
                _assert_closed(self, out)

    def test_true_and_one_do_not_share_a_preflight_digest(self):
        request = _request()
        valid = _preflight(request, runtime_seconds=1, max_commands=1)
        self.assertEqual(valid["resource_budget"]["runtime_seconds"], 1)
        self.assertEqual(valid["resource_budget"]["max_commands"], 1)
        mutated = deepcopy(valid)
        mutated["resource_budget"] = dict(mutated["resource_budget"])
        mutated["resource_budget"]["runtime_seconds"] = True
        self.assertEqual(mutated["preflight_id"], valid["preflight_id"])
        with self.assertRaises(ValueError):
            expected_preflight_id(mutated)
        with self.assertRaises(ValueError):
            _runner(request, mutated)
        with self.assertRaises(ValueError):
            _preflight(request, runtime_seconds=True)

    def test_max_commands_true_is_rejected_initially_and_after_mutation(self):
        request = _request()
        valid = _preflight(request, max_commands=1)
        self.assertEqual(valid["state"], "READY_FOR_EXECUTOR_DESIGN_REVIEW")
        self.assertEqual(valid["resource_budget"]["max_commands"], 1)
        mutated = deepcopy(valid)
        mutated["resource_budget"] = dict(mutated["resource_budget"])
        mutated["resource_budget"]["max_commands"] = True
        self.assertEqual(mutated["preflight_id"], valid["preflight_id"])
        with self.assertRaises(ValueError):
            expected_preflight_id(mutated)
        with self.assertRaises(ValueError):
            _runner(request, mutated)
        with self.assertRaises(ValueError):
            _preflight(request, max_commands=True)

    def test_recomputing_the_id_still_rejects_an_invalid_type(self):
        request = _request()
        valid = _preflight(request, runtime_seconds=1)
        mutated = deepcopy(valid)
        mutated["resource_budget"] = dict(mutated["resource_budget"])
        mutated["resource_budget"]["runtime_seconds"] = True
        with self.assertRaises(ValueError):
            mutated["preflight_id"] = expected_preflight_id(mutated)
        self.assertEqual(mutated["preflight_id"], valid["preflight_id"])
        commands = deepcopy(valid)
        commands["resource_budget"] = dict(commands["resource_budget"])
        commands["resource_budget"]["max_commands"] = True
        with self.assertRaises(ValueError):
            commands["preflight_id"] = expected_preflight_id(commands)

    def test_runner_and_command_policy_revalidate_every_boundary(self):
        request = _request()
        preflight = _preflight(request, runtime_seconds=1)
        runner = _runner(request, preflight)
        self.assertEqual(runner["state"], "READY_FOR_RUNNER_DESIGN_REVIEW")
        branch = request["branch_contract"]
        patch = {
            "schema": "ATLASQUANT_AION_DEVELOPER_PATCH_VALIDATION_V1",
            "validation_id": "DEVPATCHVAL-1",
            "state": "READY_FOR_PATCH_REVIEW",
            "builder_request_id": request["request_id"],
            "preflight_id": preflight["preflight_id"],
            "patch_digest": "DEVPATCH-ABC",
            "revision_binding": {
                "baseline_ref": branch["baseline_ref"],
                "candidate_ref": branch["candidate_ref"],
                "refs_match_approved_request": True,
                "revision_content_verified": True,
            },
            "blockers": [],
            "patch_applied": False,
            "execution_authorized": False,
            "executor_attached": False,
        }
        policy = build_command_policy_contract(
            runner,
            builder_request=request,
            preflight=preflight,
            patch_validation=patch,
            content_attestation=attestation_for_documents(request, preflight, patch),
        )
        self.assertEqual(policy["state"], "READY_FOR_EXECUTABLE_PINNING_REVIEW")
        _assert_closed(self, runner)
        _assert_closed(self, policy)
        for field, spec in _FIELDS.items():
            for value in (True, False, spec["numeric_string"], 1.0, 1.9, None, [], {}):
                with self.subTest(boundary="runner", field=field, value=value):
                    mutated = deepcopy(preflight)
                    mutated["resource_budget"] = dict(mutated["resource_budget"])
                    mutated["resource_budget"][field] = value
                    with self.assertRaises(ValueError):
                        expected_preflight_id(mutated)
                    with self.assertRaises(ValueError):
                        _runner(request, mutated)
                with self.subTest(boundary="command_policy", field=field, value=value):
                    mutated_runner = deepcopy(runner)
                    mutated_runner["resource_budget"] = dict(mutated_runner["resource_budget"])
                    mutated_runner["resource_budget"][field] = value
                    with self.assertRaises(ValueError):
                        build_command_policy_contract(mutated_runner)
            for label in ("negative", "zero", "above"):
                with self.subTest(boundary="runner_range", field=field, label=label):
                    mutated = deepcopy(preflight)
                    mutated["resource_budget"] = dict(mutated["resource_budget"])
                    mutated["resource_budget"][field] = spec[label]
                    mutated["preflight_id"] = expected_preflight_id(mutated)
                    out = _runner(request, mutated)
                    self.assertEqual(out["state"], "BLOCKED")
                    self.assertIn(spec["blocker"], out["blockers"])
                    self.assertIs(type(out["resource_budget"][field]), int)
                    _assert_closed(self, out)
                with self.subTest(boundary="command_policy_range", field=field, label=label):
                    mutated_runner = deepcopy(runner)
                    mutated_runner["resource_budget"] = dict(mutated_runner["resource_budget"])
                    mutated_runner["resource_budget"][field] = spec[label]
                    _bind_runner_contract_ids(mutated_runner)
                    out = build_command_policy_contract(mutated_runner)
                    self.assertEqual(out["state"], "BLOCKED")
                    self.assertIn(spec["blocker"], out["blockers"])
                    _assert_closed(self, out)


if __name__ == "__main__":
    unittest.main()
