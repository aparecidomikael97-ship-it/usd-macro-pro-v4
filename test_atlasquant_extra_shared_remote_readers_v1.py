"""Offline regression for independent shared-file readers outside primary entrypoint.

Neither valid session membership nor cached Streamlit data identifies the
tenant that owns a shared legacy remote GitHub file. Real production reader
function bodies are run with fully synthetic dependency sentinels.
"""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parent

class EmptyFrame:
    empty = True
    def __len__(self):
        return 0

def production_function(path, name, scope):
    source = (ROOT / path).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=path)
    funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name]
    if len(funcs) != 1:
        raise AssertionError("reader not unique: " + path + "/" + name)
    fn = funcs[0]
    if fn.decorator_list:
        raise AssertionError("private loader must not return cached results without running gate")
    unit = ast.Module(body=[
        ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
        fn,
    ], type_ignores=[])
    globals_ = dict(scope)
    exec(compile(ast.fix_missing_locations(unit), path, "exec"), globals_)
    return globals_[name]

class IndependentRemoteReaderTests(unittest.TestCase):
    def setUp(self):
        self.network = Mock(side_effect=AssertionError("NETWORK_FORBIDDEN"))
        self.cfg = Mock(side_effect=AssertionError("TOKEN_OR_CONFIG_LOOKUP_FORBIDDEN"))
        self.branch = Mock(side_effect=AssertionError("BRANCH_LOOKUP_FORBIDDEN"))
        self.frame_factory = Mock(side_effect=lambda: EmptyFrame())

    def ctx(self, session_valid, *, owner="tenant_one"):
        self.assertIn(owner, ("tenant_one", "tenant_two"))
        return {
            "private_read_allowed": Mock(return_value=session_valid),
            "legacy_private_remote_resource_allowed": Mock(return_value=False),
            "STATUS_PATH": "dados/autopilot_status_v107.json",
            "LIVE_NOWCAST_PATH": "dados/news_nowcast_predictions_v1.csv",
            "_cfg": self.cfg,
            "require_runtime_branch": self.branch,
            "pd": SimpleNamespace(DataFrame=self.frame_factory),
            "requests": SimpleNamespace(get=self.network),
        }

    def test_autopilot_panel_invalid_session_denies_before_config_and_network(self):
        fn = production_function("autopilot_panel_v107.py", "_load_status", self.ctx(False))
        status, reason = fn()
        self.assertEqual(status, {})
        self.assertEqual(reason, "ACCESS_DENIED")
        self.cfg.assert_not_called()
        self.network.assert_not_called()

    def test_autopilot_valid_admin_in_two_tenants_cannot_read_shared_status(self):
        for tenant in ("tenant_one", "tenant_two"):
            with self.subTest(tenant=tenant):
                ctx = self.ctx(True, owner=tenant)
                fn = production_function("autopilot_panel_v107.py", "_load_status", ctx)
                self.assertEqual(fn(), ({}, "TENANT_SOURCE_UNBOUND"))
                ctx["private_read_allowed"].assert_called_once_with()
                ctx["legacy_private_remote_resource_allowed"].assert_called_once_with(
                    "dados/autopilot_status_v107.json"
                )
        self.cfg.assert_not_called()
        self.network.assert_not_called()

    def test_news_nowcast_invalid_session_returns_empty_before_branch(self):
        fn = production_function("atlasquant_news_research_panel.py",
                                 "load_live_nowcast_runtime", self.ctx(False))
        frame, status = fn(repo="synthetic/repo", branch="atlasquant-runtime",
                           token="FAKE_NO_REAL_SECRETS")
        self.assertTrue(frame.empty)
        self.assertEqual(status["reason"], "ACCESS_DENIED")
        self.branch.assert_not_called()
        self.network.assert_not_called()

    def test_news_nowcast_valid_admin_A_B_can_never_load_same_shared_csv(self):
        for tenant in ("tenant_one", "tenant_two"):
            with self.subTest(tenant=tenant):
                ctx = self.ctx(True, owner=tenant)
                fn = production_function("atlasquant_news_research_panel.py",
                                         "load_live_nowcast_runtime", ctx)
                frame, status = fn(repo="synthetic/repo", branch="atlasquant-runtime",
                                   token="FAKE_NO_REAL_SECRETS")
                self.assertTrue(frame.empty)
                self.assertFalse(status["ok"])
                self.assertEqual(status["reason"], "TENANT_SOURCE_UNBOUND")
                ctx["legacy_private_remote_resource_allowed"].assert_called_once_with(
                    "dados/news_nowcast_predictions_v1.csv"
                )
        self.branch.assert_not_called()
        self.network.assert_not_called()

    def test_news_nowcast_loader_has_no_shared_streamlit_data_cache(self):
        path = ROOT / "atlasquant_news_research_panel.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                  and n.name == "load_live_nowcast_runtime")
        self.assertFalse(fn.decorator_list)
        self.assertFalse(any(isinstance(n, ast.Call) and
                             isinstance(n.func, ast.Attribute) and
                             n.func.attr == "cache_data" for n in ast.walk(fn)))

    def test_readers_gate_before_io_and_nonredirect_transport_is_pinned(self):
        for path, method in (("autopilot_panel_v107.py", "_load_status"),
                             ("atlasquant_news_research_panel.py", "load_live_nowcast_runtime")):
            with self.subTest(path=path):
                src = (ROOT / path).read_text(encoding="utf-8")
                tree = ast.parse(src)
                fn = next(x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == method)
                invocations = [x for x in ast.walk(fn) if isinstance(x, ast.Call)]
                provenance = [x for x in invocations if isinstance(x.func, ast.Name)
                              and x.func.id == "legacy_private_remote_resource_allowed"]
                getter = [x for x in invocations if isinstance(x.func, ast.Attribute)
                          and x.func.attr == "get" and isinstance(x.func.value, ast.Name)
                          and x.func.value.id == "requests"]
                self.assertEqual(len(provenance), 1)
                self.assertEqual(len(getter), 1)
                self.assertLess(provenance[0].lineno, getter[0].lineno)
                self.assertTrue(any(kw.arg == "allow_redirects" and isinstance(kw.value, ast.Constant)
                                    and kw.value.value is False for kw in getter[0].keywords))
                self.assertIn("guard_github_token_read_destination(", src)
                self.assertIn("reject_github_read_unexpected_status(", src)

    def test_public_market_data_and_local_user_csv_not_blanket_blocked(self):
        news = (ROOT / "atlasquant_news_research_panel.py").read_text(encoding="utf-8")
        self.assertIn("pd.read_csv(uploaded)", news)
        app = (ROOT / "usd_macro_pro_v4_cloud.py").read_text(encoding="utf-8")
        self.assertIn("https://api.stlouisfed.org/fred/", app)
        self.assertNotIn('legacy_private_remote_resource_allowed("FRED")', app)

if __name__ == "__main__":
    unittest.main()
