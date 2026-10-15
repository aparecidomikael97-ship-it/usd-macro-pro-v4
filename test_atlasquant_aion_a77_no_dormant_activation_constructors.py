"""A77 LAB regression: A74 denial must not retain dormant positive constructors.

No real issuer, external witness, feature-flag mutation or Worker invocation.
A74 and legacy fixtures remain unchanged; these checks are additive.
"""
import ast
import inspect
import textwrap
import unittest

import atlasquant_aion_global_worker_activation as activation


def _definition(function):
    return ast.parse(textwrap.dedent(inspect.getsource(function))).body[0]


def _string_constants(node):
    return {
        value.value for value in ast.walk(node)
        if isinstance(value, ast.Constant) and isinstance(value.value, str)
    }


def _hard_stop_is_terminal(function, reason):
    body = _definition(function).body
    terminals = [
        index for index, item in enumerate(body)
        if isinstance(item, ast.Return)
        and reason in _string_constants(item)
    ]
    return len(terminals) == 1 and terminals[0] == len(body) - 1


class A77NoDormantPositiveConstructors(unittest.TestCase):
    def test_plan_creator_has_no_positive_status_literal(self):
        statuses = _string_constants(_definition(
            activation.prepare_global_worker_activation_plan
        ))
        self.assertNotIn("ACTIVATION_PLAN_READY", statuses)

    def test_approval_creator_has_no_positive_status_literal(self):
        statuses = _string_constants(_definition(
            activation.approve_global_worker_activation_plan
        ))
        self.assertNotIn("APPROVED_FOR_ACTIVATION", statuses)

    def test_public_creators_end_at_independent_authority_denial(self):
        for function in (
            activation.prepare_global_worker_activation_plan,
            activation.approve_global_worker_activation_plan,
        ):
            with self.subTest(function=function.__name__):
                self.assertTrue(_hard_stop_is_terminal(
                    function, "INDEPENDENT_ACTIVATION_AUTHORITY_NOT_ENROLLED"
                ))

    def test_ticket_validator_has_no_approved_result(self):
        statuses = _string_constants(_definition(
            activation.validate_global_worker_activation_approval
        ))
        self.assertNotIn("APPROVED", statuses)


if __name__ == "__main__":
    unittest.main()
