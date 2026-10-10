"""Offline source-level + synthetic authorization regression. Zero network/secrets."""
import ast
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch

from atlasquant_access_control import AccessUser, credential_fingerprint
from atlasquant_private_read_gate_v1 import (
    DISPLAY_KEYS, PENDING_KEYS, QUARANTINE_KEY, SCOPE_KEY,
    clear_private_ui_state, private_read_decision, private_read_allowed,
)

ROOT = Path(__file__).resolve().parent


def extracted(path, function, globals_):
    source = (ROOT / path).read_text(encoding="utf-8")
    module = ast.parse(source, filename=path)
    found = [node for node in module.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function]
    if len(found) != 1:
        raise AssertionError(f"expected one {function} in {path}")
    namespace = {"DEFAULT_MAX_SAMPLES": 10000, "DEFAULT_MAX_RECORDS": 5000, "DEFAULT_MAX_RUNTIME_ROWS": 10000, **globals_}
    future = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[future, *found], type_ignores=[])), path, "exec"), namespace)
    return namespace[function]


class PrivateReadGateTests(unittest.TestCase):
    def setUp(self):
        self.now = 2000000000.0
        self.user = AccessUser("owner.01", "ADMIN", "synthetic-pbkdf2-fixture", True)
        self.users = {"owner.01": self.user}
        self.session = {
            "schema": "ATLASQUANT_ACCESS_V1", "username": "owner.01",
            "role": "ADMIN", "credential_fingerprint": credential_fingerprint(self.user),
            "authenticated_at": self.now - 40, "last_seen": self.now - 10,
        }
        self.args = {
            "session": self.session, "users": self.users, "auth_required": True,
            "time_valid": True, "workspace_id": "tenant_one",
            "memberships": {"tenant_one": ["owner.01"]}, "policy_generation": "7",
        }

    def test_explicit_admin_member_is_allowed_only_for_private_read(self):
        allowed, scope = private_read_decision(**self.args)
        self.assertTrue(allowed)
        self.assertEqual(len(scope), 64)

    def test_denies_open_preview_expired_revoked_and_forged(self):
        variants = (
            {"auth_required": False}, {"session": None}, {"time_valid": False},
            {"workspace_id": ""}, {"workspace_id": "tenant_two"},
            {"memberships": {"tenant_two": ["owner.01"]}},
            {"memberships": {}}, {"policy_generation": ""},
            {"policy_generation": "0"},
            {"session": dict(self.session, schema="OPEN")},
            {"session": dict(self.session, role="USER")},
            {"session": dict(self.session, credential_fingerprint="forged")},
            {"users": {"owner.01": AccessUser("owner.01", "ADMIN", "rotated", True)}},
            {"users": {"owner.01": AccessUser("owner.01", "ADMIN", "synthetic-pbkdf2-fixture", False)}},
        )
        for diff in variants:
            with self.subTest(diff=diff):
                self.assertEqual(private_read_decision(**(self.args | diff)), (False, ""))

    def test_binding_changes_on_actor_session_policy_and_membership(self):
        base = private_read_decision(**self.args)[1]
        self.assertNotEqual(base, private_read_decision(**(self.args | {"session": dict(self.session, authenticated_at=self.now - 3)}))[1])
        self.assertNotEqual(base, private_read_decision(**(self.args | {"policy_generation": "8"}))[1])
        self.assertNotEqual(base, private_read_decision(**(self.args | {"memberships": {"tenant_one": ["owner.01", "other.01"]}}))[1])

    def test_clear_keeps_unknown_outcome_and_quarantines(self):
        state = {k: "STALE_PRIVATE_VALUE" for k in DISPLAY_KEYS}
        state[SCOPE_KEY] = "scope-a"
        state[PENDING_KEYS[0]] = {"reason": "UNKNOWN_OUTCOME"}
        clear_private_ui_state(state)
        self.assertTrue(state[QUARANTINE_KEY])
        self.assertIn(PENDING_KEYS[0], state)
        for k in (*DISPLAY_KEYS, SCOPE_KEY):
            self.assertNotIn(k, state)

    def test_live_wrapper_ignores_old_hydrated_cache_when_unconfigured(self):
        state = {"atlasquant_shadow_samples": [{"secret": "A"}], "atlasquant_shadow_hydrated": True}
        st = types.ModuleType("streamlit")
        st.session_state = state
        ap = types.ModuleType("atlasquant_access_panel")
        ap.access_required = lambda: False
        ap.current_session = lambda: self.session
        ap.configured_users = lambda: self.users
        ap.session_time_status = lambda session, now: {"valid": True}
        ap._setting = lambda key, default="": ""
        with patch.dict(sys.modules, {"streamlit": st, "atlasquant_access_panel": ap}):
            self.assertFalse(private_read_allowed())
        self.assertNotIn("atlasquant_shadow_samples", state)
        self.assertNotIn("atlasquant_shadow_hydrated", state)

    def test_legacy_uncertain_display_status_becomes_pending_before_clear(self):
        for status_key, pending_key in (
            ("atlasquant_shadow_persistence_status", PENDING_KEYS[0]),
            ("atlasquant_research_evidence_status", PENDING_KEYS[1]),
        ):
            with self.subTest(status_key=status_key):
                state = {status_key: {"reason": "UNKNOWN_OUTCOME", "write_attempted": True}}
                clear_private_ui_state(state)
                self.assertNotIn(status_key, state)
                self.assertTrue(state[QUARANTINE_KEY])
                self.assertTrue(state[pending_key]["write_attempted"])

    def test_legacy_private_cache_without_binding_is_dropped_for_valid_admin(self):
        state = {
            "atlasquant_shadow_samples": [{"secret": "from-A"}],
            "atlasquant_shadow_hydrated": True,
            "atlasquant_research_evidence_records": [{"secret": "from-A"}],
        }
        st = types.ModuleType("streamlit")
        st.session_state = state
        ap = types.ModuleType("atlasquant_access_panel")
        ap.access_required = lambda: True
        ap.current_session = lambda: self.session
        ap.configured_users = lambda: self.users
        ap.session_time_status = lambda session, now: {"valid": True}
        config = {
            "ATLASQUANT_PRIVATE_MEMBERSHIPS_JSON": '{"tenant_one":["owner.01"]}',
            "ATLASQUANT_PRIVATE_WORKSPACE_ID": "tenant_one",
            "ATLASQUANT_PRIVATE_POLICY_GENERATION": "7",
        }
        ap._setting = lambda key, default="": config.get(key, default)
        with patch.dict(sys.modules, {"streamlit": st, "atlasquant_access_panel": ap}):
            self.assertTrue(private_read_allowed())
        self.assertNotIn("atlasquant_shadow_samples", state)
        self.assertNotIn("atlasquant_shadow_hydrated", state)
        self.assertNotIn("atlasquant_research_evidence_records", state)
        self.assertEqual(len(state[SCOPE_KEY]), 64)

    def test_cross_login_quarantines_pending_without_erasing(self):
        state = {
            SCOPE_KEY: "scope-of-user-A",
            PENDING_KEYS[1]: {"reason": "UNKNOWN_OUTCOME"},
            "atlasquant_research_evidence_records": [{"private": "A"}],
        }
        st = types.ModuleType("streamlit")
        st.session_state = state
        ap = types.ModuleType("atlasquant_access_panel")
        ap.access_required = lambda: True
        ap.current_session = lambda: self.session
        ap.configured_users = lambda: self.users
        ap.session_time_status = lambda session, now: {"valid": True}
        config = {
            "ATLASQUANT_PRIVATE_MEMBERSHIPS_JSON": '{"tenant_one":["owner.01"]}',
            "ATLASQUANT_PRIVATE_WORKSPACE_ID": "tenant_one",
            "ATLASQUANT_PRIVATE_POLICY_GENERATION": "7",
        }
        ap._setting = lambda key, default="": config.get(key, default)
        with patch.dict(sys.modules, {"streamlit": st, "atlasquant_access_panel": ap}):
            self.assertFalse(private_read_allowed())
        self.assertTrue(state[QUARANTINE_KEY])
        self.assertNotIn("atlasquant_research_evidence_records", state)
        self.assertEqual(state[PENDING_KEYS[1]]["reason"], "UNKNOWN_OUTCOME")


class PrivateReadNoIoTests(unittest.TestCase):
    def test_hydrators_deny_even_when_cache_claims_hydrated(self):
        for path, func, key in (
            ("atlasquant_shadow_capture.py", "ensure_shadow_hydrated", "atlasquant_shadow_samples"),
            ("atlasquant_research_evidence_capture.py", "ensure_research_evidence_hydrated", "atlasquant_research_evidence_records"),
        ):
            network = Mock(side_effect=AssertionError("PRIVATE NETWORK CALLED"))
            state = {key: [{"private": "from-A"}], "atlasquant_shadow_hydrated": True,
                     "atlasquant_research_evidence_hydrated": True}
            st = types.SimpleNamespace(session_state=state)
            ctx = {"private_read_allowed": lambda: False, "st": st,
                   "load_shadow_samples": network, "load_research_evidence": network}
            hydrate = extracted(path, func, ctx)
            with self.subTest(func=func):
                rows, status = hydrate()
                self.assertEqual(rows, [])
                self.assertEqual(status["reason"], "ACCESS_DENIED")
                network.assert_not_called()

    def test_stores_never_request_get_when_permission_is_denied(self):
        for path in ("atlasquant_shadow_store.py", "atlasquant_research_evidence_store.py"):
            network = Mock(side_effect=AssertionError("GET SENT"))
            fetch = extracted(path, "_fetch", {"requests": types.SimpleNamespace(get=network)})
            with self.subTest(path=path), patch("atlasquant_private_read_gate_v1.private_read_allowed", return_value=False):
                with self.assertRaises(PermissionError):
                    fetch("repo", "runtime", "synthetic", 1)
                network.assert_not_called()

    def test_paper_runtime_loader_denies_before_network(self):
        network = Mock(side_effect=AssertionError("PAPER GET SENT"))
        loader = extracted(
            "atlasquant_paper_setup_bridge.py", "_load_runtime_csv",
            {
                "private_read_allowed": lambda: False,
                "pd": types.SimpleNamespace(DataFrame=lambda: []),
                "requests": types.SimpleNamespace(get=network),
            },
        )
        with patch("atlasquant_private_read_gate_v1.private_read_allowed", return_value=False):
            rows, status = loader(path="dados/private.csv", repo="repo", branch="runtime", token="synthetic")
        self.assertEqual(rows, [])
        self.assertEqual(status["reason"], "ACCESS_DENIED")
        network.assert_not_called()

    def test_legacy_github_readers_and_writers_deny_before_token_or_network(self):
        network = Mock(side_effect=AssertionError("LEGACY GITHUB I/O"))
        ctx = {
            "private_read_allowed": lambda: False,
            "requests": types.SimpleNamespace(get=network, put=network),
            "os": types.SimpleNamespace(getenv=lambda *args: "1"),
        }
        json_read = extracted("usd_macro_pro_v4_cloud.py", "_github_get_json_v937", ctx)
        self.assertEqual(json_read("dados/autopilot_status_v107.json", {}), ({}, "ACCESS_DENIED"))
        legacy_csv = extracted("usd_macro_pro_v4_cloud.py", "_github_ler_csv_v84", ctx)
        self.assertIsNone(legacy_csv())
        scanner = extracted("usd_macro_pro_v4_cloud.py", "_scanner_load_v934", ctx)
        self.assertEqual(scanner()["_erro"], "ACCESS_DENIED")
        for name, args in (
            ("_github_salvar_csv_v84", ([],)),
            ("_github_put_bytes_v104", ("dados/private.csv", b"synthetic", "test")),
            ("_salvar_feedback_v104", ({"synthetic": True}, None, None)),
            ("_autopilot_save_inputs_v107", ()),
        ):
            with self.subTest(writer=name):
                writer = extracted("usd_macro_pro_v4_cloud.py", name, ctx)
                self.assertEqual(writer(*args)[0], False)
        network.assert_not_called()

    def test_private_entrypoint_config_read_and_legacy_write_have_zero_io(self):
        network = Mock(side_effect=AssertionError("GITHUB I/O"))
        ctx = {
            "private_read_allowed": lambda: False,
            "pd": types.SimpleNamespace(DataFrame=lambda **kw: kw),
            "_config_cols_v937": lambda: ["id_config"],
            "requests": types.SimpleNamespace(get=network, put=network),
        }
        read = extracted("usd_macro_pro_v4_cloud.py", "_config_ler_v937", ctx)
        write = extracted("usd_macro_pro_v4_cloud.py", "_config_salvar_v937", ctx)
        df, reason = read()
        self.assertEqual(df, {"columns": ["id_config"]})
        self.assertEqual(reason, "ACCESS_DENIED")
        self.assertFalse(write(df)[0])
        network.assert_not_called()

    def test_legacy_stores_hard_deny_put_even_with_fake_credentials(self):
        for path, func, args in (
            ("atlasquant_shadow_store.py", "persist_shadow_samples", ([{"id": "x"}],)),
            ("atlasquant_research_evidence_store.py", "persist_research_evidence", ([{"id": "x"}],)),
        ):
            network = Mock(side_effect=AssertionError("GET OR PUT SENT"))
            persist = extracted(path, func, {"requests": types.SimpleNamespace(get=network, put=network)})
            with self.subTest(path=path):
                status = persist(*args, repo="synthetic", branch="runtime", token="synthetic")
                self.assertFalse(status["ok"])
                self.assertEqual(status["reason"], "HARD_DENIED")
                network.assert_not_called()

    def test_both_shadow_callsites_and_validation_private_reads_are_guarded(self):
        entry = (ROOT / "usd_macro_pro_v4_cloud.py").read_text(encoding="utf-8")
        center = entry.split("if _aq_active_index == 13:", 1)[1].split("\n# =========================================================", 1)[0]
        tree = ast.parse("if True:" + center)
        call_names = [
            node.func.id for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        ]
        self.assertEqual(call_names.count("ensure_shadow_hydrated"), 2)
        self.assertGreaterEqual(call_names.count("private_read_allowed"), 1)
        # The validation private GitHub JSON calls are behind a local decision.
        self.assertIn('if not private_read_allowed():\n                        raise PermissionError("PRIVATE_READ_DENIED")', center)
        # Missing hydrator must not surface stale session rows.
        self.assertNotIn('st.session_state.get("atlasquant_shadow_samples", [])', center)


if __name__ == "__main__":
    unittest.main()
