"""Actual capture/store functions with synthetic state and blocked transports."""
import ast
import base64
import hashlib
import importlib
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

import requests

# Streamlit is optional in this offline suite. Do not read secrets or start UI.
with patch.dict(sys.modules, {"streamlit": ModuleType("streamlit")}):
    shadow = importlib.import_module("atlasquant_shadow_capture")
    research = importlib.import_module("atlasquant_research_evidence_capture")

CONFIG = dict(repo="example/repository", branch="atlasquant-runtime", token="SYNTHETIC_NON_REAL")
UNKNOWN = dict(ok=False, reason="UNKNOWN_OUTCOME", added=0, write_outcome="UNKNOWN",
               write_attempted=True, reconciliation_required=True, safe_to_retry=False)
ROOT = Path(__file__).resolve().parents[1]


def response(status, payload):
    return SimpleNamespace(status_code=status, json=lambda: payload, raise_for_status=lambda: None)


def contents(rows, serialize):
    raw = serialize(rows).encode("utf-8")
    sha = hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()
    return response(200, dict(encoding="base64", content=base64.b64encode(raw).decode("ascii"), sha=sha))


class CaptureReconciliationTests(unittest.TestCase):
    def setUp(self):
        for target in ("socket.socket.connect", "socket.socket.connect_ex", "socket.create_connection",
                       "requests.sessions.Session.request"):
            guard = patch(target, side_effect=AssertionError("NETWORK_FORBIDDEN"))
            guard.start()
            self.addCleanup(guard.stop)
        self.states = {}
        for module, config_name in ((shadow, "shadow_persistence_config"), (research, "research_evidence_config")):
            state = {module.HYDRATED_KEY: True, module.SESSION_KEY: []}
            self.states[module] = state
            for guard in (patch.object(module, "st", SimpleNamespace(session_state=state)),
                          patch.object(module, config_name, return_value=dict(CONFIG))):
                guard.start()
                self.addCleanup(guard.stop)

    def capture(self, module, identity="first", persist=True):
        if module is shadow:
            # Batch construction has its own deterministic tests; use exact
            # synthetic rows so these regressions isolate state transitions.
            with patch.object(shadow, "build_shadow_batch", return_value=[{"sample_id": identity, "value": 1}]):
                return shadow.capture_shadow_batch([], champion_version="fixture")
        return research.capture_research_evidence(strategy="FVG", source="OFFLINE_FIXTURE", passport={},
                                                  evidence={"value": identity}, captured_at="2026-10-09T12:00:00Z",
                                                  persist=persist)

    def writer_name(self, module):
        return "persist_shadow_samples" if module is shadow else "persist_research_evidence"

    def assert_pending(self, result):
        self.assertEqual(result["reason"], "UNKNOWN_OUTCOME", result)
        self.assertIs(result["ok"], False)
        self.assertIs(result["reconciliation_required"], True)
        self.assertIs(result["safe_to_retry"], False)

    def test_real_accepted_put_then_lost_readback_blocks_another_write(self):
        for module in (shadow, research):
            with self.subTest(module=module.__name__):
                def receipt(*args, **kwargs):
                    raw = base64.b64decode(kwargs["json"]["content"])
                    sha = hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()
                    return response(201, {"content": {"sha": sha}})
                with patch.object(requests, "get", side_effect=[response(404, {}), requests.Timeout("readback-lost")]) as get, \
                     patch.object(requests, "put", side_effect=receipt) as put:
                    self.assert_pending(self.capture(module))
                    self.assert_pending(self.capture(module, "second"))
                self.assertEqual((get.call_count, put.call_count), (2, 1))

    def test_real_timeout_then_duplicate_new_capture_or_persist_has_only_one_put(self):
        for module in (shadow, research):
            for action in ("duplicate", "new", "persist"):
                if module is shadow and action == "persist":
                    continue
                with self.subTest(module=module.__name__, action=action):
                    self.states[module].clear()
                    self.states[module].update({module.HYDRATED_KEY: True, module.SESSION_KEY: []})
                    with patch.object(requests, "get", return_value=response(404, {})) as get, \
                         patch.object(requests, "put", side_effect=requests.Timeout("fixture-lost-ack")) as put:
                        first = self.capture(module)
                        self.assert_pending(first)
                        followup = (research.persist_session_research_evidence() if action == "persist"
                                    else self.capture(module, "second" if action == "new" else "first"))
                    self.assert_pending(followup)
                    self.assertEqual((get.call_count, put.call_count), (1, 1))
                    self.assertEqual(len(self.states[module][module.SESSION_KEY]), 2 if action == "new" else 1)

    def test_remote_id_presence_cannot_reconcile_an_uncertain_write(self):
        for module, serialize in ((shadow, importlib.import_module("atlasquant_shadow_store").serialize_samples),
                                  (research, importlib.import_module("atlasquant_research_evidence_store").serialize_evidence_records)):
            with self.subTest(module=module.__name__):
                with patch.object(module, self.writer_name(module), return_value=dict(UNKNOWN)):
                    self.capture(module)
                remote = contents(self.states[module][module.SESSION_KEY], serialize)
                with patch.object(requests, "get", return_value=remote) as get, patch.object(requests, "put") as put:
                    result = (research.persist_session_research_evidence() if module is research else self.capture(module))
                self.assert_pending(result)
                get.assert_not_called()
                put.assert_not_called()

    def test_new_apparently_successful_write_cannot_hide_pending_operation(self):
        for module in (shadow, research):
            with self.subTest(module=module.__name__):
                with patch.object(module, self.writer_name(module), return_value=dict(UNKNOWN)):
                    self.capture(module)
                with patch.object(module, self.writer_name(module), return_value={"ok": True, "reason": "SAVED"}) as writer:
                    result = self.capture(module, "second")
                self.assert_pending(result)
                writer.assert_not_called()

    def test_session_only_new_and_duplicate_research_preserve_pending(self):
        with patch.object(research, "persist_research_evidence", return_value=dict(UNKNOWN)):
            self.capture(research)
        with patch.object(research, "load_research_evidence") as load, \
             patch.object(research, "persist_research_evidence") as writer:
            self.assert_pending(self.capture(research, persist=False))
            self.assert_pending(self.capture(research, "second", persist=False))
            self.assert_pending(research.persist_session_research_evidence())
        load.assert_not_called()
        writer.assert_not_called()
        self.assertEqual(len(self.states[research][research.SESSION_KEY]), 2)

    def test_rehydration_cannot_erase_pending_even_with_empty_local_cache(self):
        for module, hydrate, loader in ((shadow, shadow.ensure_shadow_hydrated, "load_shadow_samples"),
                                        (research, research.ensure_research_evidence_hydrated, "load_research_evidence")):
            with self.subTest(module=module.__name__):
                with patch.object(module, self.writer_name(module), return_value=dict(UNKNOWN)):
                    self.capture(module)
                self.states[module][module.HYDRATED_KEY] = False
                self.states[module][module.SESSION_KEY] = []
                with patch.object(module, loader, return_value=[]) as load:
                    rows, result = hydrate()
                self.assert_pending(result)
                self.assertEqual(rows, [])
                load.assert_not_called()
                if module is research:
                    with patch.object(research, "persist_research_evidence") as writer:
                        self.assert_pending(research.persist_session_research_evidence())
                    writer.assert_not_called()

    def test_display_status_overwrite_cannot_clear_separate_pending_marker(self):
        for module in (shadow, research):
            with self.subTest(module=module.__name__):
                with patch.object(module, self.writer_name(module), return_value=dict(UNKNOWN)):
                    original = self.capture(module)
                original["reason"] = "SAVED"  # caller's returned dict is not the ledger
                self.states[module][module.STATUS_KEY] = {"ok": True, "reason": "SAVED"}
                with patch.object(module, self.writer_name(module)) as writer:
                    self.assert_pending(self.capture(module, "second"))
                writer.assert_not_called()

    def test_legacy_unknown_status_without_new_marker_is_adopted(self):
        for module in (shadow, research):
            with self.subTest(module=module.__name__):
                self.states[module][module.STATUS_KEY] = {"ok": True, "reason": "UNKNOWN_OUTCOME"}
                with patch.object(module, self.writer_name(module)) as writer:
                    self.assert_pending(self.capture(module))
                writer.assert_not_called()

    def test_reconciliation_flag_overrides_apparent_saved_receipt(self):
        for module in (shadow, research):
            with self.subTest(module=module.__name__):
                self.states[module][module.STATUS_KEY] = dict(ok=True, reason="SAVED", verified=True,
                    readback_matching_content=True, reconciliation_required=True)
                with patch.object(module, self.writer_name(module)) as writer:
                    result = self.capture(module)
                self.assert_pending(result)
                self.assertFalse(result["verified"])
                self.assertFalse(result["readback_matching_content"])
                self.assertFalse(result["persistence_confirmed"])
                writer.assert_not_called()

    def test_scope_configuration_change_cannot_clear_pending(self):
        for module, cfg in ((shadow, "shadow_persistence_config"), (research, "research_evidence_config")):
            with self.subTest(module=module.__name__):
                with patch.object(module, self.writer_name(module), return_value=dict(UNKNOWN)):
                    self.capture(module)
                with patch.object(module, cfg, return_value=dict(CONFIG, branch="different-runtime")), \
                     patch.object(module, self.writer_name(module)) as writer:
                    result = self.capture(module, "second")
                self.assert_pending(result)
                self.assertEqual(result["local_added"], 1)
                writer.assert_not_called()

    def test_reported_conflict_and_validation_rejection_also_require_reconciliation(self):
        for module in (shadow, research):
            for reason in ("CONFLICT", "VALIDATION_REJECTED"):
                with self.subTest(module=module.__name__, reason=reason):
                    self.states[module].clear()
                    self.states[module].update({module.HYDRATED_KEY: True, module.SESSION_KEY: []})
                    failed = dict(UNKNOWN, reason=reason)
                    with patch.object(module, self.writer_name(module), return_value=failed):
                        self.capture(module)
                    with patch.object(module, self.writer_name(module)) as writer:
                        result = self.capture(module, "second")
                    self.assertEqual(result["reason"], reason)
                    self.assertFalse(result["ok"])
                    self.assertTrue(result["reconciliation_required"])
                    writer.assert_not_called()

    def test_local_duplicate_never_claims_remote_presence(self):
        for module in (shadow, research):
            with self.subTest(module=module.__name__):
                with patch.object(module, self.writer_name(module), return_value={"ok": False, "reason": "NOT_CONFIGURED"}):
                    self.capture(module)
                with patch.object(module, self.writer_name(module)) as writer:
                    result = self.capture(module)
                self.assertEqual(result["reason"], "LOCAL_ALREADY_PRESENT")
                self.assertEqual(result["source"], "session")
                self.assertFalse(result["persistence_confirmed"])
                writer.assert_not_called()

    def test_session_only_capture_and_duplicate_need_no_remote_read(self):
        self.states[research][research.HYDRATED_KEY] = False
        with patch.object(research, "load_research_evidence") as load, \
             patch.object(research, "persist_research_evidence") as writer:
            first = self.capture(research, persist=False)
            duplicate = self.capture(research, persist=False)
        self.assertEqual(first["reason"], "SESSION_ONLY")
        self.assertEqual(duplicate["reason"], "LOCAL_ALREADY_PRESENT")
        self.assertFalse(first["persistence_confirmed"])
        load.assert_not_called()
        writer.assert_not_called()

    def test_legitimate_verified_save_still_works(self):
        for module in (shadow, research):
            with self.subTest(module=module.__name__):
                def accepted(*args, **kwargs):
                    return response(201, {"content": {"sha": hashlib.sha1(
                        b"blob " + str(len(base64.b64decode(kwargs["json"]["content"]))).encode("ascii") + b"\0" +
                        base64.b64decode(kwargs["json"]["content"])).hexdigest()}})
                def readback(*args, **kwargs):
                    rows = self.states[module][module.SESSION_KEY]
                    serialize = (importlib.import_module("atlasquant_shadow_store").serialize_samples if module is shadow
                                 else importlib.import_module("atlasquant_research_evidence_store").serialize_evidence_records)
                    return contents(rows, serialize)
                with patch.object(requests, "get") as get, \
                     patch.object(requests, "put", side_effect=accepted) as put:
                    # Build readback after capture has populated the session.
                    get.side_effect = lambda *a, **k: response(404, {}) if not put.called else readback()
                    result = self.capture(module)
                self.assertEqual(result["reason"], "SAVED")
                self.assertTrue(result["verified"])
                self.assertTrue(result["persistence_confirmed"])
                self.assertEqual(result["confirmation_scope"], "CURRENT_WRITE_BATCH")
                self.assertEqual((get.call_count, put.call_count), (2, 1))

    def test_bulk_research_save_remains_available_without_pending(self):
        self.capture(research, persist=False)
        with patch.object(research, "persist_research_evidence", return_value=dict(
                ok=True, reason="SAVED", verified=True, readback_matching_content=True)) as writer:
            result = research.persist_session_research_evidence()
        self.assertTrue(result["persistence_confirmed"])
        writer.assert_called_once()

    def test_remote_id_dedup_is_not_full_content_confirmation(self):
        self.capture(research, persist=False)
        with patch.object(research, "persist_research_evidence", return_value=dict(ok=True, reason="ALREADY_PRESENT")):
            result = research.persist_session_research_evidence()
        self.assertEqual(result["reason"], "ALREADY_PRESENT")
        self.assertFalse(result["persistence_confirmed"])

    def test_latest_local_research_remains_readable_without_clearing_pending(self):
        with patch.object(research, "persist_research_evidence", return_value=dict(UNKNOWN)):
            self.capture(research)
        with patch.object(research, "load_research_evidence") as load:
            latest = research.latest_research_evidence()
        self.assertIn("FVG", latest)
        self.assert_pending(self.states[research][research.STATUS_KEY])
        load.assert_not_called()

    def test_independent_sessions_do_not_share_local_data_or_quarantine(self):
        for module in (shadow, research):
            with self.subTest(module=module.__name__):
                with patch.object(module, self.writer_name(module), return_value=dict(UNKNOWN)):
                    self.capture(module)
                original_rows = list(self.states[module][module.SESSION_KEY])
                other = {module.HYDRATED_KEY: True, module.SESSION_KEY: []}
                with patch.object(module, "st", SimpleNamespace(session_state=other)), \
                     patch.object(module, self.writer_name(module), return_value=dict(ok=False, reason="NOT_CONFIGURED")):
                    result = self.capture(module, "other-session", persist=False)
                self.assertNotEqual(result["reason"], "UNKNOWN_OUTCOME")
                self.assertEqual(len(other[module.SESSION_KEY]), 1)
                self.assertNotEqual(other[module.SESSION_KEY], original_rows)
                self.assertEqual(self.states[module][module.SESSION_KEY], original_rows)
                self.assert_pending(self.states[module][module.STATUS_KEY])

    def test_admin_button_is_disabled_while_reconciliation_is_pending(self):
        source = ast.parse((ROOT / "atlasquant_admin_research_panel.py").read_text(encoding="utf-8"))
        button = next(node for node in ast.walk(source) if isinstance(node, ast.Call)
                      and isinstance(node.func, ast.Attribute) and node.func.attr == "button"
                      and any(isinstance(k.value, ast.Constant)
                      and k.value.value == "atlasquant_admin_persist_research_evidence" for k in node.keywords))
        disabled = next(k.value for k in button.keywords if k.arg == "disabled")
        code = compile(ast.Expression(disabled), "actual-button-disabled-expression", "eval")
        self.assertTrue(eval(code, dict(research_records=[{}], research_status=dict(UNKNOWN))))
        self.assertFalse(eval(code, dict(research_records=[{}], research_status={})))

    def test_admin_button_never_shows_success_for_pending_result(self):
        source = ast.parse((ROOT / "atlasquant_admin_research_panel.py").read_text(encoding="utf-8"))
        button = next(node for node in ast.walk(source) if isinstance(node, ast.If)
                      and isinstance(node.test, ast.Call) and isinstance(node.test.func, ast.Attribute)
                      and node.test.func.attr == "button" and any(isinstance(k.value, ast.Constant)
                      and k.value.value == "atlasquant_admin_persist_research_evidence" for k in node.test.keywords))
        messages = []
        ui = SimpleNamespace(button=lambda *a, **k: True,
                             info=lambda x: messages.append(("info", x)),
                             success=lambda x: messages.append(("success", x)),
                             warning=lambda x: messages.append(("warning", x)))
        # Execute the real consumer branch, with the real blocked service.
        with patch.object(research, "persist_research_evidence", return_value=dict(UNKNOWN)):
            self.capture(research)
        with patch.object(research, "persist_research_evidence") as writer:
            exec(compile(ast.Module(body=[button], type_ignores=[]), "admin-consumer", "exec"),
                 dict(st=ui, research_records=[{}], research_status=dict(UNKNOWN),
                      persist_session_research_evidence=research.persist_session_research_evidence))
        writer.assert_not_called()
        self.assertEqual([kind for kind, text in messages], ["warning"])


if __name__ == "__main__":
    unittest.main()
