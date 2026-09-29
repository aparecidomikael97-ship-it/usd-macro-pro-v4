"""AION/Núcleo zero-cost night validation runner.

Runs a fixed, local-only validation plan and emits one JSON report.
It does not install dependencies, call network services, deploy, merge,
publish, trade, mutate runtime data, or use provider credentials.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Sequence


SCHEMA = "AION_NIGHT_VALIDATION_REPORT_V1"
DEFAULT_REPORT = "aion-night-validation-report.json"
MAX_OUTPUT_CHARS = 5000


@dataclass(frozen=True)
class Step:
    name: str
    command: tuple[str, ...]
    timeout_seconds: int


def build_steps(*, full: bool = True) -> list[Step]:
    py = sys.executable
    steps = [
        Step(
            "critical_core",
            (
                py, "-m", "unittest",
                "test_atlasquant_aion_memory",
                "test_atlasquant_aion_global_worker",
                "test_atlasquant_aion_worker_runtime",
                "test_atlasquant_aion_recovery",
                "test_atlasquant_aion_background_executor",
            ),
            2400,
        ),
        Step(
            "adversarial_core",
            (
                py, "-m", "unittest",
                "test_atlasquant_aion_security_adversarial",
                "test_atlasquant_aion_hardening",
                "test_atlasquant_aion_post_audit",
                "test_atlasquant_aion_chaos_recovery",
                "test_atlasquant_aion_core_independence",
                "test_atlasquant_aion_global_worker_readiness",
                "test_atlasquant_aion_global_worker_live_verification",
                "test_atlasquant_aion_global_worker_supervision",
                "test_atlasquant_aion_global_worker_recovery_closure",
                "test_atlasquant_aion_global_worker_incident_reconciliation",
            ),
            2400,
        ),
    ]
    if full:
        steps.append(
            Step(
                "full_unittest_discover",
                (py, "-m", "unittest", "discover"),
                10800,
            )
        )
    steps.extend([
        Step(
            "compileall",
            (py, "-m", "compileall", "-q", "."),
            1200,
        ),
        Step(
            "git_diff_check",
            ("git", "diff", "--check"),
            300,
        ),
    ])
    return steps


_SECRET_RE = re.compile(
    r"(?i)([a-z0-9_]*(?:token|api[_-]?key|authorization|password|secret)[a-z0-9_]*)"
    r"(\s*[:=]\s*)([^\s,;]+)"
)


def _redact(text: str) -> str:
    if not text:
        return ""
    cleaned = _SECRET_RE.sub(lambda m: m.group(1) + m.group(2) + "[REDACTED]", text)
    if len(cleaned) > MAX_OUTPUT_CHARS:
        cleaned = "...[truncated]...\n" + cleaned[-MAX_OUTPUT_CHARS:]
    return cleaned


def _git_value(root: Path, *args: str) -> str:
    try:
        proc = subprocess.run(
            ("git", *args),
            cwd=root,
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
        return proc.stdout.strip() if proc.returncode == 0 else ""
    except Exception:
        return ""


def run_step(step: Step, *, root: Path) -> dict:
    started = datetime.now(timezone.utc).isoformat()
    monotonic_start = time.monotonic()
    try:
        proc = subprocess.run(
            step.command,
            cwd=root,
            text=True,
            capture_output=True,
            timeout=step.timeout_seconds,
            check=False,
        )
        elapsed = round(time.monotonic() - monotonic_start, 3)
        return {
            "name": step.name,
            "status": "PASS" if proc.returncode == 0 else "FAIL",
            "returncode": proc.returncode,
            "timeout": False,
            "duration_seconds": elapsed,
            "started_at": started,
            "stdout_tail": _redact(proc.stdout),
            "stderr_tail": _redact(proc.stderr),
        }
    except subprocess.TimeoutExpired as exc:
        elapsed = round(time.monotonic() - monotonic_start, 3)
        stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        return {
            "name": step.name,
            "status": "TIMEOUT",
            "returncode": None,
            "timeout": True,
            "duration_seconds": elapsed,
            "started_at": started,
            "stdout_tail": _redact(stdout),
            "stderr_tail": _redact(stderr),
        }
    except Exception as exc:
        elapsed = round(time.monotonic() - monotonic_start, 3)
        return {
            "name": step.name,
            "status": "ERROR",
            "returncode": None,
            "timeout": False,
            "duration_seconds": elapsed,
            "started_at": started,
            "stdout_tail": "",
            "stderr_tail": type(exc).__name__,
        }


def build_report(
    *,
    root: Path,
    full: bool,
    results: Sequence[dict],
) -> dict:
    failures = [row["name"] for row in results if row.get("status") != "PASS"]
    return {
        "schema": SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "FULL" if full else "QUICK",
        "status": "PASS" if not failures else "FAIL",
        "failed_steps": failures,
        "repo_root": str(root),
        "git_branch": _git_value(root, "branch", "--show-current"),
        "git_head": _git_value(root, "rev-parse", "HEAD"),
        "cost_mode": "ZERO_COST_DEFAULT",
        "network_actions_performed": False,
        "dependency_install_performed": False,
        "deploy_performed": False,
        "merge_performed": False,
        "runtime_mutation_performed": False,
        "provider_call_performed": False,
        "real_trading_performed": False,
        "continue_between_safe_checks": True,
        "steps": list(results),
    }


def _resolve_report_path(root: Path, value: str) -> Path:
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved_root = root.resolve()
    resolved = candidate.resolve()
    if resolved != resolved_root and resolved_root not in resolved.parents:
        raise ValueError("report path must stay inside repository")
    return resolved


def _write_report(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the fixed local-only AION/Núcleo night validation plan."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--full", action="store_true", help="Run the full suite (default).")
    mode.add_argument("--quick", action="store_true", help="Skip full unittest discover.")
    parser.add_argument(
        "--report",
        default=DEFAULT_REPORT,
        help="JSON report path relative to the repository root.",
    )
    args = parser.parse_args(argv)

    full = not args.quick
    root = Path(__file__).resolve().parents[1]
    try:
        report_path = _resolve_report_path(root, args.report)
    except ValueError as exc:
        parser.error(str(exc))

    steps = build_steps(full=full)
    results = []
    for step in steps:
        print(f"[AION NIGHT] {step.name}: RUN", flush=True)
        result = run_step(step, root=root)
        results.append(result)
        print(
            f"[AION NIGHT] {step.name}: {result['status']} "
            f"({result['duration_seconds']}s)",
            flush=True,
        )

    report = build_report(root=root, full=full, results=results)
    _write_report(report_path, report)
    print(json.dumps({
        "schema": SCHEMA,
        "status": report["status"],
        "failed_steps": report["failed_steps"],
        "report": str(report_path),
    }, ensure_ascii=False, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
