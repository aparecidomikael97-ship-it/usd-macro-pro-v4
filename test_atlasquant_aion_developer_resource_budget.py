"""Exact-int resource budgets at every developer trust boundary."""
from __future__ import annotations

from copy import deepcopy
import unittest

from atlasquant_aion_developer_command_policy import build_command_policy_contract
from atlasquant_aion_developer_content_attestation import attestation_for_documents
from atlasquant_aion_developer_builder_sandbox import structural_builder_sandbox_request
from atlasquant_aion_developer_manifest import REQUIRED_MANDATORY_GATES
from atlasquant_aion_developer_patch_validation import canonical_patch_document
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
    return structural_builder_sandbox_request()


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
    patch = canonical_patch_document(request, preflight)
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
        patch = canonical_patch_document(request, preflight)
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
                    mutated["state"] = "BLOCKED"
                    mutated["preflight_passed"] = False
                    mutated["blockers"] = [spec["blocker"]]
                    mutated["preflight_id"] = expected_preflight_id(mutated)
                    with self.assertRaises(ValueError):
                        _runner(request, mutated)
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
