import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock

import atlasquant_aion_local_executor as executor
from atlasquant_aion_local_executor import (
    ALLOWED_KINDS,
    FORBIDDEN_KINDS,
    SCHEMA,
    execute_local_tool,
    local_allowlist,
    sanitize_local_arguments,
)
from atlasquant_aion_memory import default_checkpoint
from atlasquant_aion_memory_layers import default_memory_layers, remember
from atlasquant_aion_portable import default_portable_core, new_connector
from atlasquant_aion_tool_hub import default_tool_hub

ROOT = Path(__file__).resolve().parent
NOW = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
ADMIN = {"role": "ADMIN", "session": {"username": "mikael", "role": "ADMIN"}}
USER = {"role": "USER", "session": {"username": "cliente", "role": "USER"}}
LOCAL_IDS = (
    "aion.memory.search",
    "aion.memory.recall",
    "aion.checkpoint.inspect",
    "aion.status.read",
    "aion.tasks.summary",
    "aion.missions.summary",
    "aion.durable.summary",
    "aion.approvals.summary",
    "aion.events.summary",
    "aion.specialists.snapshot",
    "aion.secretary.draft_brief",
)


def _call(tool_id, **kwargs):
    kwargs.setdefault("access", ADMIN)
    kwargs.setdefault("authenticated_admin", True)
    kwargs.setdefault("approved", False)
    kwargs.setdefault("source_kind", "ADMIN")
    return execute_local_tool(tool_id, **kwargs)


def _memory(content, *, valid_until=""):
    return remember(
        default_memory_layers(),
        layer="knowledge",
        content=content,
        origin="local-test",
        category="note",
        truth_state="CONFIRMED",
        valid_until=valid_until,
        persona="trader",
    )


class RegistryTests(unittest.TestCase):
    def test_exactly_eleven_local_tools_match_the_hub(self):
        catalog = local_allowlist()
        self.assertEqual([item["tool_id"] for item in catalog], list(LOCAL_IDS))
        self.assertEqual({item["kind"] for item in catalog}, set(ALLOWED_KINDS))
        self.assertFalse({item["kind"] for item in catalog} & FORBIDDEN_KINDS)
        hub = {item["tool_id"]: item for item in default_tool_hub()["tools"]}
        self.assertEqual(len(hub), 12)
        for item in catalog:
            tool = hub[item["tool_id"]]
            self.assertEqual(tool["kind"], item["kind"])
            self.assertEqual(tool["state"], "LOCAL_READY")
            self.assertEqual(tool["connector_id"], "")
            self.assertFalse(tool["external_side_effects"])
        prepare = hub["aion.checkpoint.prepare_save"]
        self.assertEqual(prepare["kind"], "WRITE")
        self.assertNotIn(prepare["tool_id"], LOCAL_IDS)

    def test_source_has_no_dynamic_dispatch(self):
        text = (ROOT / "atlasquant_aion_local_executor.py").read_text(encoding="utf-8")
        for banned in (
            "import subprocess", "from subprocess", "eval(", "exec(", "__import__",
            "importlib", "import socket", "urllib", "import requests", "os.system", "Popen(",
            "getattr(",
        ):
            self.assertNotIn(banned, text)
        admin = (ROOT / "atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("Tool Hub local", admin)
        self.assertIn("Esta seção não executa ferramenta.", admin)
        self.assertNotIn("execute_local_tool", admin)


class PreflightTests(unittest.TestCase):
    def test_blocked_preflight_does_not_call_the_handler(self):
        spy = Mock(return_value={"truth_state": "CONFIRMED"})
        original = executor._HANDLERS["aion.memory.search"]
        executor._HANDLERS["aion.memory.search"] = spy
        try:
            missing = _call("aion.missing.tool")
            disabled_hub = default_tool_hub()
            for tool in disabled_hub["tools"]:
                if tool["tool_id"] == "aion.memory.search":
                    tool["state"] = "DISABLED"
            disabled = _call("aion.memory.search", hub=disabled_hub)
            core = default_portable_core()
            core["connectors"] = [new_connector(
                "github-dev", label="GitHub", protocol="MCP", workspace_id="development",
            )]
            external_hub = default_tool_hub()
            external_hub["tools"].append({
                "tool_id": "dev.repo.read",
                "label": "Repo",
                "workspace_id": "development",
                "connector_id": "github-dev",
                "kind": "READ",
                "guardian_action": "read",
                "state": "CONFIGURED",
                "required_scopes": ["repo:read"],
                "external_side_effects": False,
            })
            executor._HANDLERS["dev.repo.read"] = spy
            external = _call("dev.repo.read", hub=external_hub, portable_core=core)
            untrusted = _call("aion.memory.search", source_kind="EXTERNAL_AI", authenticated_admin=False)
            guardian = _call("aion.memory.search", access=USER, authenticated_admin=True)
            executor._HANDLERS["aion.checkpoint.prepare_save"] = spy
            write = _call("aion.checkpoint.prepare_save", approved=True)
            for kind, action in (
                ("PUBLISH", "publish_social"),
                ("PRODUCTION", "deploy_production"),
                ("SECRETS", "read_secret"),
                ("FINANCIAL", "charge_customer"),
            ):
                tool_id = f"aion.blocked.{kind.lower()}"
                hub = default_tool_hub()
                hub["tools"].append({
                    "tool_id": tool_id,
                    "label": kind,
                    "workspace_id": "administration",
                    "connector_id": "",
                    "kind": kind,
                    "guardian_action": action,
                    "state": "LOCAL_READY",
                    "required_scopes": [],
                    "external_side_effects": False,
                })
                executor._HANDLERS[tool_id] = spy
                blocked = _call(tool_id, hub=hub, approved=True)
                self.assertEqual(blocked["state"], "BLOCKED", kind)
        finally:
            executor._HANDLERS.clear()
            executor._HANDLERS.update({
                "aion.memory.search": original,
                "aion.memory.recall": executor._memory_recall,
                "aion.checkpoint.inspect": executor._checkpoint_inspect,
                "aion.status.read": executor._status_read,
                "aion.tasks.summary": executor._tasks,
                "aion.missions.summary": executor._missions,
                "aion.durable.summary": executor._durable,
                "aion.approvals.summary": executor._approvals,
                "aion.events.summary": executor._events_summary,
                "aion.specialists.snapshot": executor._specialists,
                "aion.secretary.draft_brief": executor._secretary,
            })
        self.assertEqual(missing["state"], "BLOCKED")
        self.assertIn("TOOL_NOT_REGISTERED", missing["preflight"]["blockers"])
        self.assertEqual(disabled["state"], "BLOCKED")
        self.assertIn("TOOL_DISABLED", disabled["preflight"]["blockers"])
        self.assertEqual(external["state"], "BLOCKED")
        self.assertIn("CONNECTOR_NOT_ACTIVATED", external["preflight"]["blockers"])
        self.assertEqual(untrusted["state"], "BLOCKED")
        self.assertIn("SOURCE_HAS_NO_COMMAND_AUTHORITY", untrusted["preflight"]["blockers"])
        self.assertEqual(guardian["state"], "BLOCKED")
        self.assertIn("GUARDIAN_DENIED", guardian["preflight"]["blockers"])
        self.assertEqual(write["state"], "BLOCKED")
        self.assertFalse(spy.called)
        for out in (missing, disabled, external, untrusted, guardian, write):
            self.assertRegex(out["contract_fingerprint"], r"^AION-LCL-[0-9A-F]{16}$")
            self.assertFalse(out["external_action_executed"])
            self.assertFalse(out["security"]["network_called"])
            self.assertFalse(out["real_orders_enabled"])


    def test_privilege_flags_require_exact_boolean_true(self):
        blocked_plan = {
            "state": "BLOCK",
            "reason": "synthetic",
            "blockers": ["SYNTHETIC_BLOCK"],
            "tool": {},
        }
        with patch(
            "atlasquant_aion_local_executor.plan_tool_call",
            return_value=blocked_plan,
        ) as preflight:
            execute_local_tool(
                "aion.memory.search",
                access=ADMIN,
                source_kind="ADMIN",
                authenticated_admin="false",
                approved=1,
            )
            kwargs = preflight.call_args.kwargs
            self.assertFalse(kwargs["authenticated_admin"])
            self.assertFalse(kwargs["approved"])

            execute_local_tool(
                "aion.memory.search",
                access=ADMIN,
                source_kind="ADMIN",
                authenticated_admin=True,
                approved=True,
            )
            kwargs = preflight.call_args.kwargs
            self.assertTrue(kwargs["authenticated_admin"])
            self.assertTrue(kwargs["approved"])

        source = (ROOT / "atlasquant_aion_local_executor.py").read_text(encoding="utf-8")
        self.assertNotIn("authenticated_admin=bool(authenticated_admin)", source)
        self.assertNotIn("approved=bool(approved)", source)

class ExecutionTests(unittest.TestCase):
    def test_search_and_recall_stay_separate_and_do_not_promote_truth(self):
        fresh = _memory("Radar local sem ordem.")
        search = _call("aion.memory.search", arguments={"query": "aion"})
        recall = _call("aion.memory.recall", arguments={
            "memory_layers": fresh,
            "persona": "trader",
            "now": NOW,
        })
        self.assertEqual(search["state"], "SUCCESS")
        self.assertEqual(search["schema"], SCHEMA)
        self.assertRegex(search["contract_fingerprint"], r"^AION-LCL-[0-9A-F]{16}$")
        self.assertGreaterEqual(search["result"]["canonical_count"], 1)
        self.assertNotIn("layered", search["result"])
        self.assertEqual(search["truth"]["status"], "UNKNOWN")
        self.assertEqual(recall["result"]["layered"][0]["truth_state"], "CONFIRMED")
        self.assertNotIn("canonical", recall["result"])
        self.assertEqual(recall["truth"]["status"], "UNKNOWN")
        expired = _memory("Leitura vencida.", valid_until=(NOW - timedelta(days=1)).isoformat())
        hidden = _call("aion.memory.recall", arguments={"memory_layers": expired, "persona": "trader", "now": NOW})
        shown = _call("aion.memory.recall", arguments={
            "memory_layers": expired,
            "persona": "trader",
            "now": NOW,
            "include_expired": True,
        })
        self.assertEqual(hidden["result"]["layered"], [])
        self.assertEqual(shown["result"]["layered"][0]["truth_state"], "UNKNOWN")
        self.assertEqual(shown["result"]["layered"][0]["status"], "EXPIRED")

    def test_arguments_are_sanitized_before_the_handler_and_datetime_survives(self):
        seen = {}

        def capture(arguments, runtime):
            seen["arguments"] = arguments
            seen["runtime_now"] = runtime.get("now")
            return {"truth_state": "UNKNOWN", "note": "password=hunter2"}

        original = executor._HANDLERS["aion.memory.search"]
        executor._HANDLERS["aion.memory.search"] = capture
        try:
            moment = NOW
            out = _call("aion.memory.search", arguments={
                "query": "aion",
                "api_key": "sk-" + ("a" * 24),
                "nested": {"client_secret": "super-secret", "when": moment},
            }, runtime_context={"now": moment})
        finally:
            executor._HANDLERS["aion.memory.search"] = original
        self.assertNotIn("api_key", seen["arguments"])
        self.assertNotIn("client_secret", seen["arguments"]["nested"])
        self.assertIsInstance(seen["arguments"]["nested"]["when"], datetime)
        self.assertIsInstance(seen["runtime_now"], datetime)
        self.assertNotIn("hunter2", str(out["result"]))
        self.assertEqual(out["result"]["truth_state"], "UNKNOWN")
        self.assertEqual(out["truth"]["status"], "UNKNOWN")
        self.assertTrue(out["security"]["sanitized"])

    def test_senha_is_removed_before_handler_and_from_result(self):
        seen = {}

        def capture(arguments, runtime):
            del runtime
            seen["arguments"] = arguments
            return {
                "truth_state": "UNKNOWN",
                "senha": "deveria-sumir",
                "note": "senha=segredo-retornado",
            }

        original = executor._HANDLERS["aion.memory.search"]
        executor._HANDLERS["aion.memory.search"] = capture
        try:
            out = _call("aion.memory.search", arguments={
                "query": "aion",
                "senha": "segredo-entrada",
                "nested": {
                    "senha_admin": "segredo-aninhado",
                    "note": "senha=segredo-textual",
                },
            })
        finally:
            executor._HANDLERS["aion.memory.search"] = original

        rendered_args = str(seen["arguments"])
        rendered_out = str(out["result"])
        self.assertNotIn("senha", seen["arguments"])
        self.assertNotIn("senha_admin", seen["arguments"]["nested"])
        self.assertNotIn("segredo-entrada", rendered_args)
        self.assertNotIn("segredo-aninhado", rendered_args)
        self.assertNotIn("segredo-textual", rendered_args)
        self.assertNotIn("deveria-sumir", rendered_out)
        self.assertNotIn("segredo-retornado", rendered_out)

    def test_handler_exception_is_a_closed_error(self):
        def boom(arguments, runtime):
            del arguments, runtime
            raise RuntimeError("password=hunter2 token=abc123secrettokenvalue")

        original = executor._HANDLERS["aion.status.read"]
        executor._HANDLERS["aion.status.read"] = boom
        try:
            out = _call("aion.status.read", request_id="req-1")
        finally:
            executor._HANDLERS["aion.status.read"] = original
        self.assertEqual(out["state"], "ERROR")
        self.assertEqual(out["error_type"], "RuntimeError")
        self.assertEqual(out["message"], "A ferramenta local falhou de forma fechada.")
        rendered = str(out)
        self.assertNotIn("hunter2", rendered)
        self.assertNotIn("abc123secrettokenvalue", rendered)
        self.assertNotIn("Traceback", rendered)
        self.assertIsNone(out["result"])
        self.assertFalse(out["security"]["network_called"])
        self.assertFalse(out["external_action_executed"])

    def test_real_checkpoint_events_feed_observability_and_secretary(self):
        checkpoint = default_checkpoint()
        checkpoint["operating"]["events"].append({
            "event_type": "local.check",
            "message": "token=abc123secrettokenvalue",
            "severity": "WARNING",
            "truth_state": "CONFIRMED",
        })
        checkpoint["operating"]["tasks"].append({
            "title": "Revisar fila",
            "domain": "secretary",
            "action": "read",
            "status": "WAITING_APPROVAL",
        })
        self.assertNotIn("events", checkpoint)
        observed = _call("aion.events.summary", runtime_context={"checkpoint": checkpoint})
        brief = _call("aion.secretary.draft_brief", runtime_context={
            "checkpoint": checkpoint,
            "market_context": {"summary": "sem confirmação"},
        })
        inspected = _call("aion.checkpoint.inspect", runtime_context={"checkpoint": checkpoint})
        self.assertEqual(observed["result"]["by_truth"]["CONFIRMED"], 1)
        self.assertNotIn("abc123secrettokenvalue", str(observed))
        self.assertFalse(observed["result"]["remote_logging"])
        self.assertGreaterEqual(brief["result"]["observability"]["warnings"], 1)
        self.assertEqual(brief["kind"], "DRAFT")
        self.assertTrue(brief["result"]["draft_only"])
        self.assertFalse(brief["result"]["published"])
        self.assertFalse(brief["result"]["real_orders_enabled"])
        self.assertEqual(brief["result"]["market"]["truth_state"], "UNKNOWN")
        self.assertEqual(inspected["result"]["checkpoint_version"], 18)
        self.assertEqual(inspected["result"]["project"], "AtlasQuant")
        self.assertEqual(inspected["result"]["counts"]["events"], 1)
        self.assertEqual(inspected["result"]["counts"]["tasks"], 1)
        self.assertIn("task_digest", inspected["result"]["digests"])
        self.assertFalse(inspected["result"]["aion"]["real_trading"])
        self.assertFalse(inspected["result"]["saved"])
        self.assertFalse(inspected["result"]["write_safe"])
        self.assertFalse(inspected["writes_checkpoint"] if "writes_checkpoint" in inspected else inspected["security"]["external_side_effects"])

    def test_remaining_readers_do_not_write_publish_or_trade(self):
        checkpoint = default_checkpoint()
        for tool_id in (
            "aion.status.read",
            "aion.tasks.summary",
            "aion.missions.summary",
            "aion.durable.summary",
            "aion.approvals.summary",
            "aion.specialists.snapshot",
        ):
            out = _call(tool_id, runtime_context={"checkpoint": checkpoint, "specialist": "market"})
            self.assertEqual(out["state"], "SUCCESS", tool_id)
            self.assertIn(out["kind"], ALLOWED_KINDS)
            self.assertEqual(out["preflight"]["state"], "READY_FOR_EXECUTOR")
            self.assertFalse(out["executes_action"])
            self.assertFalse(out["external_action_executed"])
            self.assertFalse(out["real_orders_enabled"])
            self.assertFalse(out["tool_output_is_authority"])
            self.assertTrue(out["provenance"]["local_only"])
            self.assertFalse(out["security"]["connector_called"])
        specialist = _call("aion.specialists.snapshot", runtime_context={"specialist": "market"})
        self.assertNotEqual(specialist["result"].get("truth_state"), "CONFIRMED")

    def test_sanitize_helper_drops_secrets_and_keeps_scalars(self):
        moment = NOW
        clean = sanitize_local_arguments({
            "ready": True,
            "count": 2,
            "ratio": 0.5,
            "empty": None,
            "when": moment,
            "api_key": "secret-value",
            "note": "password=hunter2",
        })
        self.assertTrue(clean["ready"])
        self.assertEqual(clean["count"], 2)
        self.assertEqual(clean["ratio"], 0.5)
        self.assertIsNone(clean["empty"])
        self.assertIs(clean["when"], moment)
        self.assertNotIn("api_key", clean)
        self.assertNotIn("hunter2", clean["note"])


if __name__ == "__main__":
    unittest.main()
