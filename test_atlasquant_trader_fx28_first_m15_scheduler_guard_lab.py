"""Adversarial purely offline checks for FX28 scheduled invocation gate."""
from __future__ import annotations
import unittest
from atlasquant_trader_fx28_first_m15_scheduler_guard_lab import (
    LEGACY_SCRIPT, SAFE_SCRIPT, audit_scheduled_command_lab as audit,
)
from atlasquant_trader_fx28_first_m15_atomic_claim_lab import WINDOW

ROOT = r"C:\Users\apare\AppData\Local\AtlasQuant\LAB\FX28_NY17_M15"
SCRIPTBASE = r"C:\Users\apare\AppData\Local\AtlasQuant\lab_capture_modules\"
TERMINAL = r"C:\Program Files\Pepperstone MetaTrader 5\terminal64.exe"
LEGACY = (
    "py -3.12 -u " + SCRIPTBASE + LEGACY_SCRIPT + " --window " + WINDOW
    + ' --terminal-path "' + TERMINAL + '" .')
PROPOSED = (
    "py -3.12 -u " + SCRIPTBASE + SAFE_SCRIPT
    + " --mode capture-once --confirm-window " + WINDOW
    + ' --terminal-path "' + TERMINAL + '"'
    + ' --archive-root "' + ROOT + '"')


class ScheduledGuardTests(unittest.TestCase):
    def check(self, command):
        result = audit(command)
        self.assertFalse(result["trade_authorized"])
        self.assertFalse(result["publishable"])
        self.assertFalse(result["local_script_sha256_verified"])
        self.assertFalse(result["actual_task_configuration_independently_verified"])
        self.assertFalse(result["command_executed"])
        self.assertEqual(result["mt5_calls"], 0)
        return result

    def test_actual_legacy_task_invocation_rejected(self):
        r = self.check(LEGACY)
        self.assertFalse(r["structural_guard_satisfied"])
        self.assertEqual(r["reason"], "LEGACY_WRAPPER_HAS_NO_VERIFIED_ATOMIC_CLAIM")

    def test_explicit_claimed_invocation_only_structurally_accepted(self):
        r = self.check(PROPOSED)
        self.assertTrue(r["structural_guard_satisfied"])
        self.assertEqual(r["state"],
            "LAB_FX28_SCHEDULED_COMMAND_STRUCTURE_ACCEPTABLE_LOCAL_UNVERIFIED_NO_GO")

    def test_no_window_confirmation_rejected(self):
        r = self.check(PROPOSED.replace("--confirm-window " + WINDOW,
                                        "--confirm-window REHEARSAL"))
        self.assertFalse(r["structural_guard_satisfied"])

    def test_capture_without_atomic_script_rejected(self):
        r = self.check(PROPOSED.replace(SAFE_SCRIPT, "other_script.py"))
        self.assertEqual(r["reason"], "UNRECOGNIZED_SCHEDULED_SCRIPT")

    def test_shell_append_rejected(self):
        r = self.check(PROPOSED + " & echo unsafe")
        self.assertEqual(r["reason"], "SHELL_OR_EXPANSION_SYNTAX_REJECTED")

    def test_duplicate_mode_rejected(self):
        r = self.check(PROPOSED + " --mode preflight")
        self.assertFalse(r["structural_guard_satisfied"])

    def test_changed_terminal_rejected(self):
        r = self.check(PROPOSED.replace("Pepperstone MetaTrader 5", "Other MT5"))
        self.assertFalse(r["structural_guard_satisfied"])

    def test_relative_archive_rejected(self):
        r = self.check(PROPOSED.replace(ROOT, r".\FX28_NY17_M15"))
        self.assertFalse(r["structural_guard_satisfied"])

    def test_missing_flags_rejected(self):
        r = self.check(PROPOSED.replace("--mode capture-once ", ""))
        self.assertFalse(r["structural_guard_satisfied"])

    def test_not_pinned_python_launcher_rejected(self):
        r = self.check(PROPOSED.replace("-3.12", "-3.11"))
        self.assertEqual(r["reason"], "PYTHON_LAUNCHER_NOT_PINNED_TO_3_12")

    def test_bad_inputs_rejected(self):
        for x in (None, 0, "", "echo hello"):
            self.assertFalse(self.check(x)["structural_guard_satisfied"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
