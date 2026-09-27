"""Adversarial regression matrix for the local AION command path.

The flow under test is:

    user command -> local orchestrator -> Tool Hub -> plan_tool_call()
    -> Guardian -> local executor -> allowlisted handler -> sanitized envelope

Production modules are not modified here. Two gaps are locked as expected
failures in RecordedProductionGaps so a later fix is reviewed on purpose.
"""
import json
import unittest
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

import atlasquant_aion_command_orchestrator as command
import atlasquant_aion_local_executor as executor
from atlasquant_aion_command_orchestrator import (
    BUNDLE_SAFE_KINDS,
    MAX_BUNDLE_TOOLS,
    orchestrate_local_command,
    plan_local_bundle,
    plan_local_command,
)
from atlasquant_aion_local_executor import (
    ALLOWED_KINDS,
    FORBIDDEN_KINDS,
    SCHEMA,
    execute_local_tool,
    local_allowlist,
    sanitize_local_arguments,
)
from atlasquant_aion_memory import default_checkpoint
from atlasquant_aion_memory_layers import remember
from atlasquant_aion_portable import default_portable_core
from atlasquant_aion_tool_hub import default_tool_hub, plan_tool_call


LOCAL_TOOLS = (
    ("aion.memory.search", "SEARCH", "central"),
    ("aion.memory.recall", "SEARCH", "central"),
    ("aion.checkpoint.inspect", "READ", "administration"),
    ("aion.status.read", "READ", "central"),
    ("aion.tasks.summary", "READ", "administration"),
    ("aion.missions.summary", "READ", "administration"),
    ("aion.durable.summary", "READ", "development"),
    ("aion.approvals.summary", "READ", "administration"),
    ("aion.events.summary", "READ", "administration"),
    ("aion.specialists.snapshot", "READ", "central"),
    ("aion.secretary.draft_brief", "DRAFT", "administration"),
)
WRITE_TOOL = "aion.checkpoint.prepare_save"
ADMIN = {"role": "ADMIN", "session": {"username": "mikael", "role": "ADMIN"}}
USER = {"role": "USER", "session": {"username": "cliente", "role": "USER"}}
SENTINEL = "hunter2-matrix"
TOKEN = "ghp_MATRIXSECRETVALUE1234567890"
_MISSING = object()


def _dump(payload) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)


def _hub_replacing(tool_id, **changes):
    hub = default_tool_hub()
    tools = []
    for tool in hub["tools"]:
        item = dict(tool)
        if item["tool_id"] == tool_id:
            item.update(changes)
        tools.append(item)
    hub["tools"] = tools
    return hub


def _hub_plus(**fields):
    hub = default_tool_hub()
    base = {
        "tool_id": "aion.security.probe",
        "label": "Sonda local",
        "workspace_id": "central",
        "connector_id": "",
        "kind": "READ",
        "guardian_action": "read",
        "state": "LOCAL_READY",
        "required_scopes": ["status:read"],
        "external_side_effects": False,
    }
    base.update(fields)
    hub["tools"] = list(hub["tools"]) + [base]
    return hub


def _hub_without(tool_id):
    hub = default_tool_hub()
    hub["tools"] = [dict(tool) for tool in hub["tools"] if tool["tool_id"] != tool_id]
    return hub


def _configured_connector_core():
    core = default_portable_core()
    core["connectors"] = [{
        "connector_id": "market-feed",
        "label": "Market feed",
        "protocol": "API",
        "workspace_id": "central",
        "state": "READY",
        "enabled": True,
        "activation_approved": True,
    }]
    return core


def _runtime():
    checkpoint = default_checkpoint()
    checkpoint["operating"]["events"] = [{
        "event_type": "matriz_local",
        "message": "evento-somente-operating",
        "severity": "WARNING",
        "truth_state": "UNKNOWN",
        "created_at": "2026-09-27T12:00:00+00:00",
    }]
    checkpoint["events"] = [{
        "event_type": "decoy",
        "message": "evento-topo-falso",
        "severity": "CRITICAL",
        "truth_state": "CONFIRMED",
        "created_at": "2026-09-27T12:00:00+00:00",
    }]
    checkpoint["password"] = SENTINEL
    checkpoint["aion"] = dict(checkpoint["aion"])
    checkpoint["aion"]["api_key"] = TOKEN
    return {"checkpoint": checkpoint, "persona": "admin"}


def _layers():
    first = remember(
        None,
        layer="decision",
        content="fato antigo confirmado",
        origin="admin",
        category="decision",
        memory_key="matriz:decisao",
        truth_state="CONFIRMED",
    )
    return remember(
        first,
        layer="decision",
        content="fato vigente sem promocao",
        origin="admin",
        category="decision",
        memory_key="matriz:decisao",
        truth_state="INFERENCE",
    )


@contextmanager
def _handler(tool_id, fn):
    previous = executor._HANDLERS.get(tool_id, _MISSING)
    executor._HANDLERS[tool_id] = fn
    try:
        yield fn
    finally:
        if previous is _MISSING:
            executor._HANDLERS.pop(tool_id, None)
        else:
            executor._HANDLERS[tool_id] = previous


class MatrixCase(unittest.TestCase):
    def assert_closed(self, payload):
        self.assertFalse(payload.get("external_action_executed", False))
        self.assertFalse(payload.get("real_orders_enabled", False))
        self.assertFalse(payload.get("tool_output_is_authority", False))
        self.assertFalse(payload.get("executes_action", False))
        security = payload.get("security") if isinstance(payload.get("security"), dict) else {}
        if security:
            self.assertTrue(security.get("sanitized"))
            self.assertFalse(security["network_called"])
            self.assertFalse(security["connector_called"])
            self.assertFalse(security["external_side_effects"])
            self.assertFalse(security["permissions_expanded"])
            self.assertFalse(security["secrets_included"])
        provenance = payload.get("provenance") if isinstance(payload.get("provenance"), dict) else {}
        if provenance:
            self.assertTrue(provenance.get("local_only"))
        for row in payload.get("tool_results") or []:
            if isinstance(row, dict):
                self.assert_closed(row)
        nested = payload.get("tool_result")
        if isinstance(nested, dict) and nested is not payload and "schema" in nested:
            self.assert_closed(nested)

    def assert_handler_blocked(self, tool_id, **kwargs):
        spy = Mock(return_value={"called": True, "secret": SENTINEL})
        with _handler(tool_id, spy):
            out = execute_local_tool(
                tool_id,
                arguments=kwargs.pop("arguments", None),
                runtime_context=kwargs.pop("runtime_context", _runtime()),
                approved=kwargs.pop("approved", False),
                request_id=kwargs.pop("request_id", "matrix"),
                **kwargs,
            )
        spy.assert_not_called()
        self.assertIn(out["state"], {"BLOCKED", "DEGRADED"})
        self.assertEqual(out["schema"], SCHEMA)
        self.assertIsNone(out["result"])
        self.assert_closed(out)
        self.assertNotIn(SENTINEL, _dump(out))
        self.assertNotIn(TOKEN, _dump(out))
        return out


class ClosedCatalogTests(MatrixCase):
    def test_allowlist_hub_and_catalog_are_the_same_eleven_tools(self):
        allow = local_allowlist()
        hub = {tool["tool_id"]: tool for tool in default_tool_hub()["tools"]}
        catalog = {row["tool_id"]: row for row in command.command_catalog()}
        ids = tuple(tool_id for tool_id, _kind, _workspace in LOCAL_TOOLS)
        self.assertEqual(tuple(row["tool_id"] for row in allow), ids)
        self.assertEqual(set(catalog), set(ids))
        self.assertEqual(len(catalog), 11)
        self.assertEqual(len(ids), 11)
        self.assertEqual(set(executor._HANDLERS), set(ids))
        for tool_id, kind, workspace in LOCAL_TOOLS:
            tool = hub[tool_id]
            self.assertEqual(tool["kind"], kind)
            self.assertEqual(tool["workspace_id"], workspace)
            self.assertEqual(tool["state"], "LOCAL_READY")
            self.assertEqual(tool["connector_id"], "")
            self.assertFalse(tool["external_side_effects"])
            self.assertIn(kind, ALLOWED_KINDS)
            self.assertNotIn(kind, FORBIDDEN_KINDS)
            self.assertTrue(callable(executor._HANDLERS[tool_id]))

    def test_prepare_save_stays_write_and_outside_local_execution(self):
        hub = {tool["tool_id"]: tool for tool in default_tool_hub()["tools"]}
        tool = hub[WRITE_TOOL]
        self.assertEqual(tool["kind"], "WRITE")
        self.assertTrue(tool["external_side_effects"])
        self.assertNotIn(WRITE_TOOL, executor._HANDLERS)
        self.assertNotIn(WRITE_TOOL, {row["tool_id"] for row in local_allowlist()})
        self.assertNotIn(WRITE_TOOL, {row["tool_id"] for row in command.command_catalog()})
        self.assertNotIn(WRITE_TOOL, [row[0] for row in command._RULES])

    def test_static_dispatch_has_no_dynamic_execution_primitives(self):
        root = Path(__file__).resolve().parent
        for name in (
            "atlasquant_aion_local_executor.py",
            "atlasquant_aion_command_orchestrator.py",
        ):
            source = (root / name).read_text(encoding="utf-8")
            for banned in (
                "eval(", "exec(", "__import__", "importlib", "import subprocess",
                "os.system", "Popen(", "getattr(",
            ):
                self.assertNotIn(banned, source, name)


class AuthorityPreflightTests(MatrixCase):
    def test_authenticated_admin_read_reaches_handler_with_approval_false(self):
        seen = {}
        real = executor.plan_tool_call

        def spy_plan(*args, **kwargs):
            seen["approved"] = kwargs.get("approved")
            seen["authenticated_admin"] = kwargs.get("authenticated_admin")
            return real(*args, **kwargs)

        executor.plan_tool_call = spy_plan
        try:
            out = execute_local_tool(
                "aion.tasks.summary",
                runtime_context=_runtime(),
                access=ADMIN,
                source_kind="ADMIN",
                authenticated_admin=True,
                request_id="admin-read",
            )
        finally:
            executor.plan_tool_call = real
        self.assertEqual(out["state"], "SUCCESS")
        self.assertEqual(out["preflight"]["state"], "READY_FOR_EXECUTOR")
        self.assertFalse(seen["approved"])
        self.assertTrue(seen["authenticated_admin"])
        self.assertEqual(out["truth"]["status"], "UNKNOWN")
        self.assert_closed(out)

    def test_untrusted_sources_never_call_the_handler(self):
        cases = {
            "user": dict(access=USER, source_kind="ADMIN", authenticated_admin=False),
            "external_ai": dict(access=ADMIN, source_kind="EXTERNAL_AI", authenticated_admin=True),
            "unknown_source": dict(access=ADMIN, source_kind="MARTIAN", authenticated_admin=True),
            "missing_session": dict(access={"role": "ADMIN"}, source_kind="ADMIN", authenticated_admin=False),
            "authenticated_flag_false": dict(access=ADMIN, source_kind="ADMIN", authenticated_admin=False),
            "empty_access": dict(access={}, source_kind="ADMIN", authenticated_admin=True),
            "absent_access": dict(access=None, source_kind="ADMIN", authenticated_admin=True),
            "nul_role": dict(access={"role": "ADMIN\x00", "session": {"role": "ADMIN"}}, source_kind="ADMIN", authenticated_admin=True),
            "nested_role": dict(access={"role": {"role": "ADMIN"}}, source_kind="ADMIN", authenticated_admin=True),
            "administrator_alias": dict(access={"role": "ADMINISTRATOR", "session": {"role": "ADMIN"}}, source_kind="ADMIN", authenticated_admin=True),
            "session_admin_access_user": dict(
                access={"role": "USER", "session": {"username": "mikael", "role": "ADMIN"}},
                source_kind="ADMIN",
                authenticated_admin=True,
            ),
        }
        for name, kwargs in cases.items():
            with self.subTest(name=name):
                out = self.assert_handler_blocked("aion.status.read", **kwargs)
                self.assertEqual(out["state"], "BLOCKED")
                blockers = out["preflight"]["blockers"]
                self.assertTrue(
                    "GUARDIAN_DENIED" in blockers or "SOURCE_HAS_NO_COMMAND_AUTHORITY" in blockers
                )

    def test_missing_disabled_and_connector_tools_do_not_call_the_handler(self):
        missing = self.assert_handler_blocked(
            "aion.does.not.exist",
            hub=_hub_without("aion.status.read"),
            access=ADMIN,
            source_kind="ADMIN",
            authenticated_admin=True,
        )
        self.assertIn("TOOL_NOT_REGISTERED", missing["preflight"]["blockers"])

        disabled = self.assert_handler_blocked(
            "aion.status.read",
            hub=_hub_replacing("aion.status.read", state="DISABLED"),
            access=ADMIN,
            source_kind="ADMIN",
            authenticated_admin=True,
        )
        self.assertIn("TOOL_DISABLED", disabled["preflight"]["blockers"])

        unregistered = self.assert_handler_blocked(
            "aion.status.read",
            hub=_hub_replacing("aion.status.read", connector_id="ghost-feed"),
            portable_core=default_portable_core(),
            access=ADMIN,
            source_kind="ADMIN",
            authenticated_admin=True,
        )
        self.assertIn("CONNECTOR_NOT_ACTIVATED", unregistered["preflight"]["blockers"])

        configured = self.assert_handler_blocked(
            "aion.status.read",
            hub=_hub_replacing("aion.status.read", connector_id="market-feed"),
            portable_core=_configured_connector_core(),
            access=ADMIN,
            source_kind="ADMIN",
            authenticated_admin=True,
        )
        self.assertIn("CONNECTOR_NOT_ACTIVATED", configured["preflight"]["blockers"])
        preview = plan_tool_call(
            "aion.status.read",
            hub=_hub_replacing("aion.status.read", connector_id="market-feed"),
            portable_core=_configured_connector_core(),
            access=ADMIN,
            source_kind="ADMIN",
            authenticated_admin=True,
            approved=False,
            scope="Consulta local allowlisted do Tool Hub.",
            uncertainty_pct=0,
            impact="LOW",
            reversible=True,
        )
        self.assertFalse(preview["connector"]["activated"])
        self.assertTrue(preview["connector"]["configured"])
        self.assertEqual(preview["connector"]["reason"], "CONNECTOR_NOT_ACTIVATED")
        self.assertFalse(preview["connector_called"])
        self.assertFalse(preview["tool_called"])

    def test_ready_preflight_with_connector_still_denies_before_handler(self):
        real = executor.plan_tool_call

        def ready_with_connector(*args, **kwargs):
            plan = real(*args, **kwargs)
            tool = dict(plan.get("tool") or {})
            tool["connector_id"] = "market-feed"
            tool["state"] = "LOCAL_READY"
            tool["kind"] = "READ"
            plan = dict(plan)
            plan["state"] = "READY_FOR_EXECUTOR"
            plan["tool"] = tool
            plan["blockers"] = []
            return plan

        executor.plan_tool_call = ready_with_connector
        try:
            out = self.assert_handler_blocked(
                "aion.status.read",
                access=ADMIN,
                source_kind="ADMIN",
                authenticated_admin=True,
            )
        finally:
            executor.plan_tool_call = real
        self.assertIn("LOCAL_EXECUTOR_DENIED", out["preflight"]["blockers"])

    def test_guardian_denial_wins_over_authenticated_flag(self):
        out = self.assert_handler_blocked(
            "aion.memory.search",
            arguments={"query": "AION"},
            access=USER,
            source_kind="ADMIN",
            authenticated_admin=True,
        )
        self.assertIn("GUARDIAN_DENIED", out["preflight"]["blockers"])


class ForbiddenKindTests(MatrixCase):
    def test_sensitive_kinds_never_call_a_handler(self):
        probes = {
            "WRITE": ("save_checkpoint", True),
            "PUBLISH": ("publish_social", False),
            "PRODUCTION": ("deploy_production", False),
            "SECRETS": ("read_secret", False),
            "FINANCIAL": ("charge_customer", False),
        }
        for kind, (action, side_effect) in probes.items():
            with self.subTest(kind=kind):
                out = self.assert_handler_blocked(
                    "aion.security.probe",
                    hub=_hub_plus(
                        kind=kind,
                        guardian_action=action,
                        external_side_effects=side_effect,
                    ),
                    access=ADMIN,
                    source_kind="ADMIN",
                    authenticated_admin=True,
                    approved=True,
                )
                self.assertEqual(out["state"], "BLOCKED")
                self.assertTrue(out["preflight"]["blockers"])

    def test_mislabeled_guardian_read_cannot_smuggle_a_forbidden_kind(self):
        for kind in ("WRITE", "PUBLISH", "PRODUCTION", "SECRETS", "FINANCIAL"):
            with self.subTest(kind=kind):
                out = self.assert_handler_blocked(
                    "aion.status.read",
                    hub=_hub_replacing("aion.status.read", kind=kind, guardian_action="read"),
                    access=ADMIN,
                    source_kind="ADMIN",
                    authenticated_admin=True,
                    approved=True,
                )
                self.assertIn("LOCAL_EXECUTOR_DENIED", out["preflight"]["blockers"])

    def test_prepare_save_stays_blocked_inside_executor_and_bundles(self):
        out = self.assert_handler_blocked(
            WRITE_TOOL,
            access=ADMIN,
            source_kind="ADMIN",
            authenticated_admin=True,
            approved=True,
        )
        self.assertEqual(out["state"], "BLOCKED")
        questions = (
            "checkpoint mestre",
            "estado do checkpoint",
            "onde paramos, o que falta e eventos locais",
            "memória canônica, resumo de tarefas e aprovações pendentes",
        )
        for question in questions:
            with self.subTest(question=question):
                bundle = plan_local_bundle(question)
                single = plan_local_command(question)
                self.assertNotIn(WRITE_TOOL, bundle.get("tool_ids") or [])
                self.assertNotEqual(single.get("tool_id"), WRITE_TOOL)
                self.assertNotIn("WRITE", bundle.get("kinds") or [])


class ElevenToolExecutionTests(MatrixCase):
    def test_each_local_tool_succeeds_without_becoming_authority(self):
        runtime = _runtime()
        layers = _layers()
        moment = datetime(2026, 9, 27, tzinfo=timezone.utc)
        arguments = {
            "aion.memory.search": {"query": "AION"},
            "aion.memory.recall": {
                "memory_layers": layers,
                "persona": "admin",
                "include_expired": False,
                "include_superseded": False,
                "now": moment,
            },
        }
        for tool_id, kind, workspace in LOCAL_TOOLS:
            with self.subTest(tool_id=tool_id):
                out = execute_local_tool(
                    tool_id,
                    arguments=arguments.get(tool_id, {}),
                    runtime_context=runtime,
                    access=ADMIN,
                    source_kind="ADMIN",
                    authenticated_admin=True,
                    approved=False,
                    request_id=f"eleven-{tool_id}",
                )
                self.assertEqual(out["state"], "SUCCESS")
                self.assertEqual(out["schema"], SCHEMA)
                self.assertEqual(out["kind"], kind)
                self.assertEqual(out["workspace_id"], workspace)
                self.assertEqual(out["preflight"]["state"], "READY_FOR_EXECUTOR")
                self.assertEqual(out["preflight"]["blockers"], [])
                self.assertEqual(out["truth"]["status"], "UNKNOWN")
                self.assertFalse(out["tool_output_is_authority"])
                self.assert_closed(out)
                self.assertNotIn(SENTINEL, _dump(out))
                self.assertNotIn(TOKEN, _dump(out))
                if tool_id == "aion.secretary.draft_brief":
                    self.assertFalse(out["result"]["published"])
                    self.assertFalse(out["result"]["real_orders_enabled"])
                    self.assertTrue(out["result"]["draft_only"])
                    self.assertEqual(out["result"]["market"]["truth_state"], "UNKNOWN")
                    self.assertEqual(out["result"]["clients"]["truth_state"], "UNKNOWN")


class MultiReadTests(MatrixCase):
    def test_explicit_compound_questions_are_ordered_and_capped(self):
        expected = {
            "onde paramos e o que falta?": ["aion.memory.search", "aion.tasks.summary"],
            "status geral e tarefas pendentes": ["aion.status.read", "aion.tasks.summary"],
            "missões ativas e aprovações pendentes": ["aion.missions.summary", "aion.approvals.summary"],
            "checkpoint mestre e eventos locais": ["aion.checkpoint.inspect", "aion.events.summary"],
            "memória canônica, resumo de tarefas e aprovações pendentes": [
                "aion.memory.search", "aion.tasks.summary", "aion.approvals.summary",
            ],
        }
        for question, tool_ids in expected.items():
            with self.subTest(question=question):
                first = plan_local_bundle(question)
                second = plan_local_bundle(question)
                self.assertEqual(first, second)
                self.assertEqual(first["state"], "READY_MULTI")
                self.assertEqual(first["tool_ids"], tool_ids)
                self.assertLessEqual(first["selected_count"], MAX_BUNDLE_TOOLS)
                self.assertTrue(all(kind in BUNDLE_SAFE_KINDS for kind in first["kinds"]))
                self.assertNotIn("DRAFT", first["kinds"])
                self.assertNotIn("WRITE", first["kinds"])
                self.assertNotIn(WRITE_TOOL, first["tool_ids"])
                self.assertNotIn("aion.secretary.draft_brief", first["tool_ids"])
                self.assertFalse(first["executes_tools"])

    def test_loose_words_do_not_invent_tasks_or_approvals(self):
        out = plan_local_bundle("memória canônica, tarefas e aprovações")
        self.assertEqual(out["tool_ids"], ["aion.memory.search"])
        self.assertEqual(out["state"], "SINGLE_OR_NONE")
        self.assertNotIn("aion.tasks.summary", out["tool_ids"])
        self.assertNotIn("aion.approvals.summary", out["tool_ids"])

    def test_fourth_intent_is_dropped_and_draft_never_enters(self):
        capped = plan_local_bundle(
            "onde paramos, o que falta, aprovações pendentes e eventos locais"
        )
        self.assertEqual(capped["selected_count"], 3)
        self.assertEqual(capped["tool_ids"], [
            "aion.memory.search", "aion.tasks.summary", "aion.approvals.summary",
        ])
        self.assertNotIn("aion.events.summary", capped["tool_ids"])

        mixed = plan_local_bundle(
            "briefing executivo, onde paramos, o que falta e eventos locais"
        )
        self.assertEqual(mixed["selected_count"], 3)
        self.assertTrue(mixed["excluded_draft_from_bundle"])
        self.assertNotIn("aion.secretary.draft_brief", mixed["tool_ids"])
        self.assertNotIn("DRAFT", mixed["kinds"])

    def test_preview_does_not_execute_and_execution_requires_the_flag(self):
        spy = Mock()
        original = command.execute_local_tool
        command.execute_local_tool = spy
        try:
            preview = orchestrate_local_command(
                "status geral e tarefas pendentes",
                execute=False,
                access=ADMIN,
                authenticated_admin=True,
            )
        finally:
            command.execute_local_tool = original
        self.assertEqual(preview["state"], "PLANNED_MULTI")
        self.assertFalse(preview["executor_invoked"])
        self.assertEqual(preview["tool_results"], [])
        spy.assert_not_called()
        self.assert_closed(preview)

        calls = []
        real = command.execute_local_tool

        def wrapped(tool_id, *args, **kwargs):
            calls.append((tool_id, kwargs))
            return real(tool_id, *args, **kwargs)

        command.execute_local_tool = wrapped
        try:
            executed = orchestrate_local_command(
                "status geral e tarefas pendentes",
                execute=True,
                runtime_context=_runtime(),
                access=ADMIN,
                source_kind="ADMIN",
                authenticated_admin=True,
                request_id="multi-status",
            )
        finally:
            command.execute_local_tool = real
        self.assertEqual(executed["state"], "SUCCESS")
        self.assertEqual([tool_id for tool_id, _kwargs in calls], [
            "aion.status.read", "aion.tasks.summary",
        ])
        self.assertTrue(all(kwargs["approved"] is False for _tool, kwargs in calls))
        self.assertEqual(len(executed["tool_results"]), 2)
        self.assertTrue(all(
            row["preflight"]["state"] == "READY_FOR_EXECUTOR"
            for row in executed["tool_results"]
        ))
        self.assertFalse(executed["stopped_early"])
        self.assert_closed(executed)

    def test_orchestrator_rejects_an_injected_approval_flag(self):
        with self.assertRaises(TypeError):
            orchestrate_local_command(
                "resumo de tarefas",
                execute=True,
                approved=True,
            )

    def test_bundle_stops_on_block_and_skips_later_tools(self):
        question = "onde paramos, o que falta e eventos locais"
        def _spy(fn):
            calls = {"n": 0}

            def wrapper(*args, **kwargs):
                calls["n"] += 1
                return fn(*args, **kwargs)

            wrapper.calls = calls
            wrapper.__name__ = fn.__name__
            return wrapper

        spies = {
            tool_id: _spy(executor._HANDLERS[tool_id])
            for tool_id in (
                "aion.memory.search", "aion.tasks.summary", "aion.events.summary",
            )
        }
        original = dict(executor._HANDLERS)
        executor._HANDLERS.update(spies)
        try:
            out = orchestrate_local_command(
                question,
                execute=True,
                runtime_context=_runtime(),
                hub=_hub_replacing("aion.tasks.summary", state="DISABLED"),
                access=ADMIN,
                source_kind="ADMIN",
                authenticated_admin=True,
            )
        finally:
            executor._HANDLERS.clear()
            executor._HANDLERS.update(original)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertTrue(out["stopped_early"])
        self.assertEqual(len(out["tool_results"]), 2)
        self.assertEqual(out["tool_results"][1]["tool_id"], "aion.tasks.summary")
        self.assertIn("TOOL_DISABLED", out["tool_results"][1]["preflight"]["blockers"])
        self.assertEqual(spies["aion.memory.search"].calls["n"], 1)
        self.assertEqual(spies["aion.tasks.summary"].calls["n"], 0)
        self.assertEqual(spies["aion.events.summary"].calls["n"], 0)
        self.assert_closed(out)

    def test_bundle_stops_on_handler_error_without_leaking_the_exception(self):
        def explode(_arguments, _runtime):
            raise RuntimeError(f"password={SENTINEL} token={TOKEN}")

        original = dict(executor._HANDLERS)
        later_calls = {"n": 0}

        def later(*args, **kwargs):
            later_calls["n"] += 1
            return original["aion.tasks.summary"](*args, **kwargs)

        later.__name__ = original["aion.tasks.summary"].__name__
        executor._HANDLERS["aion.memory.search"] = explode
        executor._HANDLERS["aion.tasks.summary"] = later
        try:
            out = orchestrate_local_command(
                "onde paramos e o que falta?",
                execute=True,
                runtime_context=_runtime(),
                access=ADMIN,
                source_kind="ADMIN",
                authenticated_admin=True,
            )
        finally:
            executor._HANDLERS.clear()
            executor._HANDLERS.update(original)
        self.assertEqual(out["state"], "ERROR")
        self.assertTrue(out["stopped_early"])
        self.assertEqual(later_calls["n"], 0)
        blob = _dump(out)
        self.assertNotIn(SENTINEL, blob)
        self.assertNotIn(TOKEN, blob)
        self.assertNotIn("Traceback", blob)
        self.assertEqual(out["tool_results"][0]["message"], "A ferramenta local falhou de forma fechada.")
        self.assert_closed(out)

    def test_bundle_stops_on_degraded_preflight_before_the_handler(self):
        real = executor.plan_tool_call
        original_tasks = executor._HANDLERS["aion.tasks.summary"]
        original_events = executor._HANDLERS["aion.events.summary"]
        task_calls = {"n": 0}
        event_calls = {"n": 0}

        def tasks(*args, **kwargs):
            task_calls["n"] += 1
            return original_tasks(*args, **kwargs)

        def events(*args, **kwargs):
            event_calls["n"] += 1
            return original_events(*args, **kwargs)

        tasks.__name__ = original_tasks.__name__
        events.__name__ = original_events.__name__

        def review_tasks(tool_id, *args, **kwargs):
            if tool_id == "aion.tasks.summary":
                return {
                    "state": "REVIEW",
                    "tool": {
                        "tool_id": tool_id,
                        "workspace_id": "administration",
                        "kind": "READ",
                        "connector_id": "",
                        "state": "LOCAL_READY",
                    },
                    "blockers": [],
                    "reason": "REVIEW",
                }
            return real(tool_id, *args, **kwargs)

        executor.plan_tool_call = review_tasks
        executor._HANDLERS["aion.tasks.summary"] = tasks
        executor._HANDLERS["aion.events.summary"] = events
        try:
            out = orchestrate_local_command(
                "onde paramos, o que falta e eventos locais",
                execute=True,
                runtime_context=_runtime(),
                access=ADMIN,
                source_kind="ADMIN",
                authenticated_admin=True,
            )
        finally:
            executor.plan_tool_call = real
            executor._HANDLERS["aion.tasks.summary"] = original_tasks
            executor._HANDLERS["aion.events.summary"] = original_events
        self.assertEqual(out["state"], "DEGRADED")
        self.assertTrue(out["stopped_early"])
        self.assertEqual(task_calls["n"], 0)
        self.assertEqual(event_calls["n"], 0)
        self.assert_closed(out)


class SensitiveIntentTests(MatrixCase):
    PHRASES = (
        "faça deploy",
        "faz o deploy",
        "execute deploy",
        "FAÇA O DEPLOY",
        "faça merge",
        "faz o MERGE",
        "publique",
        "PUBLIQUE agora",
        "publicar no Instagram",
        "salvar checkpoint",
        "SALVAR o Checkpoint",
        "grave o checkpoint",
        "mostrar token",
        "revelar senha",
        "ler API key",
        "ativar API paga",
        "cobrar cliente",
        "fazer pagamento",
        "comprar ativo real",
        "vender no mercado",
        "executar trade real",
        "enviar ordem real",
        "publicação imediata",
    )

    def test_sensitive_phrases_are_never_reread_as_local_queries(self):
        spy = Mock()
        original = command.execute_local_tool
        command.execute_local_tool = spy
        try:
            for phrase in self.PHRASES:
                with self.subTest(phrase=phrase):
                    single = plan_local_command(phrase)
                    bundle = plan_local_bundle(phrase)
                    executed = orchestrate_local_command(
                        phrase,
                        execute=True,
                        runtime_context=_runtime(),
                        access=ADMIN,
                        source_kind="ADMIN",
                        authenticated_admin=True,
                    )
                    self.assertIn(single["state"], {"BLOCKED_INTENT", "NO_MATCH"})
                    self.assertEqual(single["tool_id"], "")
                    self.assertNotIn(single.get("kind"), ALLOWED_KINDS)
                    self.assertEqual(bundle.get("tool_ids") or [], [])
                    self.assertEqual(executed["state"], single["state"])
                    self.assertFalse(executed["executor_invoked"])
                    self.assertEqual(executed["tool_ids"], [])
                    self.assert_closed(executed)
        finally:
            command.execute_local_tool = original
        spy.assert_not_called()


class SanitizationTests(MatrixCase):
    def test_arguments_are_sanitized_before_the_handler(self):
        moment = datetime(2026, 9, 27, 15, 4, tzinfo=timezone.utc)
        seen = {}

        def capture(arguments, runtime):
            seen["arguments"] = arguments
            seen["runtime"] = runtime
            return {"ok": True, "truth_state": "", "freshness": ""}

        payload = {
            "password": SENTINEL,
            "token": TOKEN,
            "api_key": "k-1",
            "api-key": "k-2",
            "secret": "s-1",
            "authorization": "Bearer " + TOKEN,
            "bearer_token": TOKEN,
            "cookies": "session=secret",
            "client_secret": SENTINEL,
            "note": f"password={SENTINEL} Bearer {TOKEN}",
            "when": moment,
            "flag": True,
            "count": 3,
            "ratio": 0.5,
            "empty": None,
            "items": [{"secret": SENTINEL, "label": "visivel", "token": TOKEN}],
            "box": {"level": {"authorization": "raw", "name": "local"}},
        }
        with _handler("aion.status.read", capture):
            out = execute_local_tool(
                "aion.status.read",
                arguments=payload,
                runtime_context={"checkpoint": default_checkpoint(), "password": SENTINEL},
                access=ADMIN,
                source_kind="ADMIN",
                authenticated_admin=True,
            )
        clean = seen["arguments"]
        for key in (
            "password", "token", "api_key", "api-key", "secret", "authorization",
            "bearer_token", "cookies", "client_secret",
        ):
            self.assertNotIn(key, clean)
        self.assertNotIn(SENTINEL, _dump(clean))
        self.assertNotIn(TOKEN, _dump(clean))
        self.assertIs(clean["when"], moment)
        self.assertIs(clean["flag"], True)
        self.assertEqual(clean["count"], 3)
        self.assertEqual(clean["ratio"], 0.5)
        self.assertIsNone(clean["empty"])
        self.assertEqual(clean["items"][0]["label"], "visivel")
        self.assertNotIn("secret", clean["items"][0])
        self.assertEqual(clean["box"]["level"]["name"], "local")
        self.assertNotIn("authorization", clean["box"]["level"])
        self.assertNotIn("password", seen["runtime"])
        self.assertEqual(out["state"], "SUCCESS")
        self.assertNotIn(SENTINEL, _dump(out))
        self.assertNotIn(TOKEN, _dump(out))

    def test_depth_and_size_limits_apply_before_and_after_the_handler(self):
        nested = {"value": "x"}
        for _ in range(8):
            nested = {"child": nested}
        wide = {f"field-{index}": "y" * 800 for index in range(40)}
        seen = {}

        def capture(arguments, _runtime):
            seen["arguments"] = arguments
            return {"blob": "z" * 800, "rows": list(range(40)), "password": SENTINEL}

        with _handler("aion.status.read", capture):
            out = execute_local_tool(
                "aion.status.read",
                arguments={"tree": nested, "wide": wide, "text": "q" * 800},
                runtime_context=_runtime(),
                access=ADMIN,
                source_kind="ADMIN",
                authenticated_admin=True,
            )
        self.assertIn("[TRUNCATED]", _dump(seen["arguments"]["tree"]))
        self.assertLessEqual(len(seen["arguments"]["wide"]), 24)
        self.assertLessEqual(len(seen["arguments"]["text"]), 500)
        self.assertTrue(out["truncated"])
        self.assertLessEqual(len(out["result"]["blob"]), 500)
        self.assertLessEqual(len(out["result"]["rows"]), 24)
        self.assertNotIn(SENTINEL, _dump(out["result"]))
        self.assertEqual(out["truth"]["status"], "UNKNOWN")

    def test_handler_exception_returns_a_closed_error(self):
        def explode(_arguments, _runtime):
            raise RuntimeError(f"password={SENTINEL} token={TOKEN}\nTraceback (most recent call last): secret")

        with _handler("aion.events.summary", explode):
            out = execute_local_tool(
                "aion.events.summary",
                runtime_context=_runtime(),
                access=ADMIN,
                source_kind="ADMIN",
                authenticated_admin=True,
            )
        self.assertEqual(out["state"], "ERROR")
        self.assertIsNone(out["result"])
        self.assertEqual(out["error_type"], "RuntimeError")
        self.assertEqual(out["message"], "A ferramenta local falhou de forma fechada.")
        blob = _dump(out)
        self.assertNotIn(SENTINEL, blob)
        self.assertNotIn(TOKEN, blob)
        self.assertNotIn("Traceback", blob)
        self.assert_closed(out)


class TruthFreshnessTests(MatrixCase):
    def test_success_without_declared_truth_stays_unknown(self):
        out = execute_local_tool(
            "aion.tasks.summary",
            runtime_context=_runtime(),
            access=ADMIN,
            source_kind="ADMIN",
            authenticated_admin=True,
        )
        self.assertEqual(out["state"], "SUCCESS")
        self.assertEqual(out["truth"]["status"], "UNKNOWN")
        self.assertEqual(out["truth"]["freshness"], "UNVERIFIED")
        self.assertFalse(out["tool_output_is_authority"])

    def test_expired_and_superseded_memory_are_not_promoted(self):
        moment = datetime(2026, 9, 27, tzinfo=timezone.utc)
        expired = remember(
            None,
            layer="working",
            content="segredo expirado",
            origin="admin",
            category="note",
            memory_key="matriz:expira",
            truth_state="CONFIRMED",
            valid_until="2020-01-01T00:00:00+00:00",
        )
        hidden = execute_local_tool(
            "aion.memory.recall",
            arguments={"memory_layers": expired, "now": moment, "include_expired": False},
            runtime_context={"now": moment},
            access=ADMIN,
            source_kind="ADMIN",
            authenticated_admin=True,
        )
        self.assertEqual(hidden["result"]["layered"], [])
        self.assertEqual(hidden["truth"]["status"], "UNKNOWN")

        shown = execute_local_tool(
            "aion.memory.recall",
            arguments={"memory_layers": expired, "now": moment, "include_expired": True},
            runtime_context={"now": moment},
            access=ADMIN,
            source_kind="ADMIN",
            authenticated_admin=True,
        )
        row = shown["result"]["layered"][0]
        self.assertEqual(row["status"], "EXPIRED")
        self.assertEqual(row["truth_state"], "UNKNOWN")
        self.assertNotEqual(shown["truth"]["status"], "CONFIRMED")

        layers = _layers()
        current = execute_local_tool(
            "aion.memory.recall",
            arguments={"memory_layers": layers, "include_superseded": False},
            access=ADMIN,
            source_kind="ADMIN",
            authenticated_admin=True,
        )
        contents = [item["content"] for item in current["result"]["layered"]]
        self.assertEqual(contents, ["fato vigente sem promocao"])
        self.assertNotEqual(current["truth"]["status"], "CONFIRMED")

        both = execute_local_tool(
            "aion.memory.recall",
            arguments={"memory_layers": layers, "include_superseded": True},
            access=ADMIN,
            source_kind="ADMIN",
            authenticated_admin=True,
        )
        both_contents = [item["content"] for item in both["result"]["layered"]]
        self.assertIn("fato antigo confirmado", both_contents)
        self.assertIn("fato vigente sem promocao", both_contents)
        self.assertNotEqual(both["truth"]["status"], "CONFIRMED")
        self.assertFalse(both["tool_output_is_authority"])

    def test_conflicting_memories_stay_visible_and_unconfirmed(self):
        left = remember(
            None,
            layer="working",
            content="lado A",
            origin="admin",
            category="note",
            memory_key="matriz:a",
            truth_state="CONFIRMED",
        )
        both = remember(
            left,
            layer="working",
            content="lado B",
            origin="admin",
            category="note",
            memory_key="matriz:b",
            truth_state="CONFIRMED",
        )
        out = execute_local_tool(
            "aion.memory.recall",
            arguments={"memory_layers": both},
            access=ADMIN,
            source_kind="ADMIN",
            authenticated_admin=True,
        )
        contents = {item["content"] for item in out["result"]["layered"]}
        self.assertEqual(contents, {"lado A", "lado B"})
        self.assertEqual(out["truth"]["status"], "UNKNOWN")
        self.assertFalse(out["tool_output_is_authority"])

    def test_missing_specialist_evidence_stays_unknown(self):
        out = execute_local_tool(
            "aion.specialists.snapshot",
            arguments={"specialist": "macro"},
            runtime_context=_runtime(),
            access=ADMIN,
            source_kind="ADMIN",
            authenticated_admin=True,
        )
        self.assertNotEqual(out["result"].get("truth_state"), "CONFIRMED")
        self.assertEqual(out["truth"]["status"], "UNKNOWN")
        self.assertFalse(out["tool_output_is_authority"])


class CheckpointEventTests(MatrixCase):
    def test_events_and_secretary_read_operating_events_from_the_real_checkpoint(self):
        runtime = _runtime()
        checkpoint = runtime["checkpoint"]
        self.assertIn("events", checkpoint["operating"])
        events = execute_local_tool(
            "aion.events.summary",
            runtime_context=runtime,
            access=ADMIN,
            source_kind="ADMIN",
            authenticated_admin=True,
        )
        blob = _dump(events["result"])
        self.assertIn("evento-somente-operating", blob)
        self.assertNotIn("evento-topo-falso", blob)
        self.assertNotIn(SENTINEL, blob)
        self.assertNotIn(TOKEN, blob)

        brief = execute_local_tool(
            "aion.secretary.draft_brief",
            runtime_context=runtime,
            access=ADMIN,
            source_kind="ADMIN",
            authenticated_admin=True,
        )
        brief_blob = _dump(brief["result"])
        self.assertIn("evento-somente-operating", brief_blob)
        self.assertNotIn("evento-topo-falso", brief_blob)
        self.assertFalse(brief["result"]["published"])
        self.assertFalse(brief["result"]["real_orders_enabled"])
        self.assertEqual(brief["truth"]["status"], "UNKNOWN")
        for invented in ("GitHub", "Render", "Instagram", "cliente novo", "ordem real"):
            self.assertNotIn(invented, brief_blob)

    def test_checkpoint_inspect_is_partial_and_does_not_save(self):
        runtime = _runtime()
        before = json.dumps(runtime["checkpoint"]["operating"]["events"], default=str)
        out = execute_local_tool(
            "aion.checkpoint.inspect",
            runtime_context=runtime,
            access=ADMIN,
            source_kind="ADMIN",
            authenticated_admin=True,
        )
        result = out["result"]
        self.assertEqual(result["checkpoint_version"], 18)
        self.assertEqual(result["project"], "AtlasQuant")
        self.assertTrue(result["updated_at"])
        self.assertEqual(result["aion"]["truth_policy"], "never_invent")
        self.assertEqual(result["aion"]["cost_mode"], "ZERO_COST_DEFAULT")
        self.assertFalse(result["aion"]["real_trading"])
        self.assertTrue(result["areas"])
        for key in ("pending", "tasks", "events", "missions", "durable_tasks", "approvals"):
            self.assertIn(key, result["counts"])
        self.assertEqual(result["counts"]["events"], 1)
        self.assertTrue(result["integrity"]["state"])
        self.assertIsInstance(result["integrity"]["mismatches"], list)
        self.assertIsInstance(result["integrity"]["migration_items"], list)
        self.assertIn("task_digest", result["digests"])
        self.assertIn("event_digest", result["digests"])
        self.assertFalse(result["saved"])
        self.assertFalse(result["write_safe"])
        self.assertFalse(out["executes_action"])
        blob = _dump(result)
        self.assertNotIn(SENTINEL, blob)
        self.assertNotIn(TOKEN, blob)
        self.assertNotIn("evento-topo-falso", blob)
        after = json.dumps(runtime["checkpoint"]["operating"]["events"], default=str)
        self.assertEqual(before, after)


class FuzzRobustnessTests(MatrixCase):
    def test_deterministic_awkward_inputs_stay_closed(self):
        samples = (
            "",
            "   ",
            "\x00\x00",
            "🚀🚀",
            "áéíóú àèìòù ãõ ç",
            "x" * 5000,
            None,
            12345,
            {"question": "sem frase segura"},
            "estatistica geral do painel",
            "minha tarefa urgente",
            "evento local isolado",
            "aprovar depois",
            "memoria do time",
            "resumo de tarefas resumo de tarefas",
        )
        for sample in samples:
            with self.subTest(sample=sample if isinstance(sample, str) else type(sample).__name__):
                single = plan_local_command(sample)
                bundle = plan_local_bundle(sample)
                executed = orchestrate_local_command(sample, execute=False)
                self.assertIn(single["state"], {
                    "NO_COMMAND", "NO_MATCH", "READY", "AMBIGUOUS", "BLOCKED_INTENT",
                })
                self.assertNotEqual(single.get("tool_id"), WRITE_TOOL)
                self.assertNotIn(WRITE_TOOL, bundle.get("tool_ids") or [])
                self.assertNotIn("DRAFT", bundle.get("kinds") or [])
                self.assertFalse(executed["executor_invoked"])
                self.assert_closed(executed)
                if sample is None or sample in ("", "   ", "\x00\x00"):
                    self.assertEqual(single["state"], "NO_COMMAND")
                if isinstance(sample, str) and sample in {
                    "estatistica geral do painel",
                    "minha tarefa urgente",
                    "evento local isolado",
                    "aprovar depois",
                    "memoria do time",
                    "🚀🚀",
                    "áéíóú àèìòù ãõ ç",
                }:
                    self.assertEqual(single["state"], "NO_MATCH")

    def test_equal_scores_do_not_guess_a_single_winner(self):
        question = "buscar na memoria e checkpoint mestre"
        single = plan_local_command(question)
        bundle = plan_local_bundle(question)
        self.assertEqual(single["state"], "AMBIGUOUS")
        self.assertEqual(single["tool_id"], "")
        self.assertEqual(bundle["tool_ids"], ["aion.memory.search", "aion.checkpoint.inspect"])
        self.assertTrue(all(kind in {"READ", "SEARCH"} for kind in bundle["kinds"]))
        preview = orchestrate_local_command(question, execute=False)
        self.assertFalse(preview["executor_invoked"])
        self.assert_closed(preview)

    def test_nul_and_case_do_not_turn_sensitive_text_into_a_read(self):
        for phrase in ("faça deploy\x00", "  EXECUTE DEPLOY  ", "Grave o CHECKPOINT agora"):
            with self.subTest(phrase=phrase):
                out = orchestrate_local_command(phrase, execute=True, access=ADMIN, authenticated_admin=True)
                self.assertEqual(out["state"], "BLOCKED_INTENT")
                self.assertFalse(out["executor_invoked"])

    def test_repeated_safe_intent_is_not_duplicated(self):
        out = plan_local_bundle("resumo de tarefas resumo de tarefas")
        self.assertEqual(out["tool_ids"], ["aion.tasks.summary"])
        self.assertEqual(out["selected_count"], 1)
        self.assertEqual(out["state"], "SINGLE_OR_NONE")


class FixedProductionRegressions(MatrixCase):
    def test_senha_is_removed_before_the_handler_and_from_the_result(self):
        """Regression: Portuguese 'senha' is removed/redacted before and after the handler."""
        seen = {}

        def capture(arguments, _runtime):
            seen["arguments"] = dict(arguments)
            return {"senha": arguments.get("senha"), "note": "senha=segredo-pt"}

        with _handler("aion.status.read", capture):
            out = execute_local_tool(
                "aion.status.read",
                arguments={"senha": "segredo-pt", "note": "senha=segredo-pt"},
                runtime_context=_runtime(),
                access=ADMIN,
                source_kind="ADMIN",
                authenticated_admin=True,
            )
        problems = []
        if "senha" in seen["arguments"] or seen["arguments"].get("senha") == "segredo-pt":
            problems.append("input")
        if "segredo-pt" in _dump(out):
            problems.append("output")
        self.assertEqual(problems, [])

    def test_words_that_only_contain_lembra_do_not_select_memory_search(self):
        """Regression: 'lembra' only matches as a whole phrase, never inside unrelated words."""
        for text in ("deslembrado do assunto", "lembranca fiscal"):
            with self.subTest(text=text):
                out = plan_local_command(text)
                self.assertEqual(out["state"], "NO_MATCH", text)
                self.assertEqual(out["tool_id"], "")


if __name__ == "__main__":
    unittest.main()
