"""Documentary audit of a proposed FX28 first-M15 scheduled command.

LAB only. This never executes a command, opens an MT5 terminal, reads AM12,
or edits an automation. A syntactically acceptable command is STILL not
proof that its local implementation is installed or byte-verified.
"""
from __future__ import annotations
import ntpath
import re
import shlex
from typing import Any

from atlasquant_trader_fx28_first_m15_atomic_claim_lab import WINDOW

SCHEMA = "ATLASQUANT_FX28_FIRST_M15_SCHEDULED_COMMAND_AUDIT_LAB_V1"
SAFE_SCRIPT = "atlasquant_trader_fx28_first_m15_claimed_cli_lab.py"
LEGACY_SCRIPT = "run_fx28_m15_capture_lab.py"
EXPECTED_TERMINAL = r"C:\Program Files\Pepperstone MetaTrader 5\terminal64.exe"
EXPECTED_ARCHIVE_END = r"\AtlasQuant\LAB\FX28_NY17_M15"
# All 5 required flags are exact; no shell, alternative executable or
# parameter expansion is supported by this documentary checker.
ALLOWED_FLAGS = frozenset(("--mode", "--confirm-window", "--terminal-path",
                           "--archive-root"))
UNCHECKED_FIELDS = ("local_script_sha256", "actual_task_matches_supplied_text",
                    "local_script_executed", "broker_source_authenticated")


def audit_scheduled_command_lab(raw_command: Any) -> dict[str, Any]:
    out = {
        "schema": SCHEMA,
        "state": "LAB_FX28_SCHEDULED_COMMAND_NOT_SAFE_TO_RUN_NO_GO",
        "reason": "INVALID_OR_UNSUPPLIED_COMMAND",
        "expected_window": WINDOW,
        "expected_protected_script": SAFE_SCRIPT,
        "legacy_script_must_not_be_executed": LEGACY_SCRIPT,
        "structural_guard_satisfied": False,
        "local_script_sha256_verified": False,
        "actual_task_configuration_independently_verified": False,
        "local_am12_available": False,
        "source_or_broker_verified": False,
        "scheduler_modified": False,
        "command_executed": False,
        "mt5_calls": 0,
        "file_writes": 0,
        "trade_calls": 0,
        "trade_authorized": False,
        "publishable": False,
        "operational_bias": "AGUARDAR",
    }
    if type(raw_command) is not str or not 10 <= len(raw_command) <= 2048:
        return out
    # Parse only. No subprocess/shell invocation anywhere in this module.
    if any(c in raw_command for c in ("\n", "\r", ";", "|", "&", "<", ">", "%", "$", "`")):
        out["reason"] = "SHELL_OR_EXPANSION_SYNTAX_REJECTED"
        return out
    try:
        lexer = shlex.shlex(raw_command, posix=False)
        lexer.whitespace_split = True
        lexer.commenters = ""
        tokens = [s.strip('"') for s in lexer]
    except ValueError:
        out["reason"] = "MALFORMED_COMMAND_QUOTING"
        return out
    if len(tokens) < 4:
        out["reason"] = "INCOMPLETE_SCHEDULED_COMMAND"
        return out
    head = [s.lower() for s in tokens[:3]]
    if head != ["py", "-3.12", "-u"]:
        out["reason"] = "PYTHON_LAUNCHER_NOT_PINNED_TO_3_12"
        return out
    executable = ntpath.basename(tokens[3]).casefold()
    if executable == LEGACY_SCRIPT:
        out["reason"] = "LEGACY_WRAPPER_HAS_NO_VERIFIED_ATOMIC_CLAIM"
        return out
    if executable != SAFE_SCRIPT:
        out["reason"] = "UNRECOGNIZED_SCHEDULED_SCRIPT"
        return out
    if not ntpath.isabs(tokens[3]) or len(tokens[4:]) != len(ALLOWED_FLAGS) * 2:
        out["reason"] = "EXPECTED_EXACT_ARGUMENT_COUNT_AND_ABSOLUTE_SCRIPT"
        return out
    args = tokens[4:]
    if any(args[i] not in ALLOWED_FLAGS for i in range(0, len(args), 2)):
        out["reason"] = "UNRECOGNIZED_OR_UNPAIRED_FLAGS"
        return out
    props = dict(zip(args[::2], args[1::2]))
    if (len(props) != len(ALLOWED_FLAGS)
            or props.get("--mode") != "capture-once"
            or props.get("--confirm-window") != WINDOW):
        out["reason"] = "MISSING_DUPLICATE_OR_WRONG_CAPTURE_FLAGS"
        return out
    term = props.get("--terminal-path", "")
    root = props.get("--archive-root", "")
    if (ntpath.normcase(ntpath.normpath(term))
            != ntpath.normcase(ntpath.normpath(EXPECTED_TERMINAL))
            or not ntpath.isabs(root)
            or not ntpath.normcase(ntpath.normpath(root)).endswith(
                ntpath.normcase(EXPECTED_ARCHIVE_END))):
        out["reason"] = "UNEXPECTED_BROKER_TERMINAL_OR_ARCHIVE_ROOT"
        return out
    out.update({
        "state": "LAB_FX28_SCHEDULED_COMMAND_STRUCTURE_ACCEPTABLE_LOCAL_UNVERIFIED_NO_GO",
        "reason": "COMMAND_TEXT_ONLY_NOT_INSTALLED_OR_WIRED_OR_AUTHORIZED",
        "structural_guard_satisfied": True,
    })
    return out


__all__ = ("SCHEMA", "SAFE_SCRIPT", "LEGACY_SCRIPT",
           "audit_scheduled_command_lab")
