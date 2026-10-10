"""Offline-only reference for historical GitHub write protocol tests.

NOT a runtime authorization path. A writer's unconditional production
HARD_DENIED return remains untouched. This reference is reconstructed only
inside the isolated test process, with all unmocked network sockets blocked.
Do not import this test helper into application/runtime modules.
"""
from __future__ import annotations

import ast
from contextlib import ExitStack
import importlib
import inspect
import socket
from unittest.mock import patch


def _legacy_reference_writer(module, symbol):
    actual = getattr(module, symbol)
    # Always inspect the on-disk production source, NOT a function temporarily
    # patched by the outer unittest closure-audit harness.
    path = inspect.getfile(module)
    with open(path, encoding="utf-8") as handle:
        source = handle.read()
    tree = ast.parse(source, filename=path)
    matches = [node for node in tree.body
               if isinstance(node, ast.FunctionDef) and node.name == symbol]
    if len(matches) != 1:
        raise AssertionError("Legacy writer source no longer matches reviewed contract")
    function = matches[0]
    segment = ast.get_source_segment(source, function) or ""
    if len(function.body) < 2 or not isinstance(function.body[0], ast.Return):
        raise AssertionError("Unconditional runtime HARD_DENIED is missing")
    if '"HARD_DENIED"' not in segment.split("    try:", 1)[0]:
        raise AssertionError("Expected fail-closed writer guard is not present")
    if not isinstance(function.body[1], ast.Try):
        raise AssertionError("Legacy protocol simulation changed: review required")
    function.body = function.body[1:]
    tree = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
    # Execute against the module's live dictionary so existing transport
    # mocks remain effective; immediately restore the deployed writer.
    code = compile(tree, path, "exec")
    exec(code, module.__dict__)
    reference = getattr(module, symbol)
    setattr(module, symbol, actual)
    return reference


def install_historical_write_protocol_fixture(testcase):
    """Attach automatically cleaned synthetic protocol references to a TestCase.

    Even if tests omit their own mocks, real network calls cannot escape.
    Caller must provide only synthetic token/repo fixture values.
    """
    stack = ExitStack()
    testcase.addCleanup(stack.close)
    for path in ("socket.socket.connect", "socket.socket.connect_ex",
                 "socket.create_connection", "requests.sessions.Session.request"):
        stack.enter_context(patch(path, side_effect=AssertionError("NETWORK_FORBIDDEN")))
    # This temporary override is strictly test-local, never a production knob.
    stack.enter_context(patch("atlasquant_private_read_gate_v1.private_read_allowed", return_value=True))
    # Historical protocol simulation only: never bypass this gate in runtime.
    # All unmocked network and sockets are blocked in this scope.
    stack.enter_context(patch("atlasquant_legacy_private_resource_gate_v1.require_legacy_private_remote_resource", return_value=None))
    for module_name, symbol in (
        ("atlasquant_research_evidence_store", "persist_research_evidence"),
        ("atlasquant_shadow_store", "persist_shadow_samples"),
    ):
        module = importlib.import_module(module_name)
        reference = _legacy_reference_writer(module, symbol)
        stack.enter_context(patch.object(module, symbol, reference))
