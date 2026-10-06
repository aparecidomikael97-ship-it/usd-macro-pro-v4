#!/usr/bin/env python3
"""Read-only readiness gate for the AION Core V1 formal closure ceremony.

Default behavior is fail-closed and performs no signature, nonce claim, runtime
write, merge, deploy, worker arming or worker activation.

A runtime network read is performed only when --check-runtime-read is supplied.
Credential values are never printed.
"""
from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

from atlasquant_aion_memory import load_runtime_checkpoint, runtime_configuration_status
from atlasquant_aion_trust_root import TrustRootRegistry
from ops.aion_core_v1_formal_closure.validate_unsigned_v220_packet import (
    read_json,
    validate_packet,
)

TARGET = "662eab4dc4f5bb009fa1ca89f87530df74d30ddf"
EXPECTED_RUNTIME_SHA = "020facc9991c5d2d4ce457e0840b04c875f8cfae"
EXPECTED_RUNTIME_SOURCE = "GitHub:atlasquant-runtime:dados/aion/checkpoint_master.json"
EXPECTED_PACKET_DIGEST = "sha256:14ca8f5231465136826518d9133092420c9f19f0f0de53e4c27634017419a72d"
EXPECTED_PACKET_TEST_COUNT = 2729

FORBIDDEN_PRIVATE_FIELDS = {
    "private_key",
    "private_key_b64",
    "private_key_pem",
    "secret_key",
    "seed",
    "mnemonic",
}


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _run_git(repo: Path, *args: str) -> tuple[int, str]:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return proc.returncode, (proc.stdout or proc.stderr or "").strip()


def _contains_forbidden_private_field(value: Any) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).strip().casefold() in FORBIDDEN_PRIVATE_FIELDS:
                return True
            if _contains_forbidden_private_field(child):
                return True
    elif isinstance(value, list):
        return any(_contains_forbidden_private_field(item) for item in value)
    return False


def _validate_public_trust_root(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        return {"ok": False, "reason": f"{label}_NOT_FOUND", "path": str(path)}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"ok": False, "reason": f"{label}_JSON_INVALID:{type(exc).__name__}", "path": str(path)}
    if _contains_forbidden_private_field(payload):
        return {"ok": False, "reason": f"{label}_CONTAINS_PRIVATE_FIELD", "path": str(path)}
    try:
        registry = TrustRootRegistry.from_mapping(payload)
    except Exception as exc:
        return {"ok": False, "reason": f"{label}_INVALID:{type(exc).__name__}", "path": str(path)}
    return {
        "ok": True,
        "reason": "VALID_PUBLIC_TRUST_ROOT",
        "path": str(path.resolve()),
        "registry_type": type(registry).__name__,
        "private_material_observed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--packet",
        type=Path,
        default=Path("ops/aion-core-v1-formal-closure/unsigned_v220_evidence_packet.json"),
    )
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--nonce-registry", type=Path, required=True)
    parser.add_argument("--certification-trust-root", type=Path)
    parser.add_argument("--owner-trust-root", type=Path)
    parser.add_argument("--expected-runtime-sha", default=EXPECTED_RUNTIME_SHA)
    parser.add_argument("--check-runtime-read", action="store_true")
    parser.add_argument("--require-write-ready", action="store_true")
    parser.add_argument("--allow-non-windows-ci", action="store_true")
    args = parser.parse_args()

    blockers: list[str] = []
    checks: dict[str, Any] = {}
    repo = args.repo_root.resolve()
    packet_path = args.packet if args.packet.is_absolute() else repo / args.packet
    work_dir = args.work_dir.expanduser().resolve()
    nonce_registry = args.nonce_registry.expanduser().resolve()

    is_windows = platform.system().casefold() == "windows"
    checks["platform"] = {
        "ok": is_windows or args.allow_non_windows_ci,
        "system": platform.system(),
        "windows_required_in_real_ceremony": True,
    }
    if not checks["platform"]["ok"]:
        blockers.append("AUTHORIZED_WINDOWS_HOST_REQUIRED")

    python_ok = sys.version_info >= (3, 12)
    checks["python"] = {
        "ok": python_ok,
        "version": platform.python_version(),
        "minimum": "3.12",
    }
    if not python_ok:
        blockers.append("PYTHON_3_12_OR_NEWER_REQUIRED")

    try:
        import cryptography

        crypto_version = str(getattr(cryptography, "__version__", "unknown"))
        crypto_ok = True
    except Exception as exc:
        crypto_version = type(exc).__name__
        crypto_ok = False
    checks["cryptography"] = {"ok": crypto_ok, "version": crypto_version}
    if not crypto_ok:
        blockers.append("CRYPTOGRAPHY_DEPENDENCY_REQUIRED")

    repo_ok = (repo / ".git").exists() or _run_git(repo, "rev-parse", "--git-dir")[0] == 0
    checks["repository"] = {"ok": repo_ok, "root": str(repo)}
    if not repo_ok:
        blockers.append("GIT_REPOSITORY_REQUIRED")
    else:
        rc_target, target_result = _run_git(repo, "cat-file", "-e", f"{TARGET}^{{commit}}")
        target_ok = rc_target == 0
        rc_ancestor, _ = _run_git(repo, "merge-base", "--is-ancestor", TARGET, "HEAD")
        ancestor_ok = rc_ancestor == 0
        rc_dirty, dirty_out = _run_git(repo, "status", "--porcelain")
        clean_ok = rc_dirty == 0 and not dirty_out
        rc_head, head = _run_git(repo, "rev-parse", "HEAD")
        checks["git_target"] = {
            "ok": target_ok and ancestor_ok,
            "target_commit": TARGET,
            "target_object_present": target_ok,
            "target_is_ancestor_of_tooling_head": ancestor_ok,
            "tooling_head": head if rc_head == 0 else "",
        }
        checks["working_tree"] = {"ok": clean_ok, "clean": clean_ok}
        if not target_ok:
            blockers.append("FORMAL_TARGET_COMMIT_NOT_PRESENT")
        if target_ok and not ancestor_ok:
            blockers.append("TOOLING_HEAD_NOT_DESCENDED_FROM_FORMAL_TARGET")
        if not clean_ok:
            blockers.append("WORKING_TREE_MUST_BE_CLEAN")

    try:
        packet_result = validate_packet(read_json(packet_path))
    except Exception as exc:
        packet_result = {"state": "BLOCKED", "reason": type(exc).__name__}
    packet_ok = (
        packet_result.get("state") == "VALID_UNSIGNED_PACKET"
        and packet_result.get("packet_digest") == EXPECTED_PACKET_DIGEST
        and packet_result.get("contract_test_count_sum") == EXPECTED_PACKET_TEST_COUNT
        and packet_result.get("formal_target_commit_sha") == TARGET
    )
    checks["unsigned_v220_packet"] = {
        "ok": packet_ok,
        "state": packet_result.get("state"),
        "packet_digest": packet_result.get("packet_digest"),
        "contract_test_count_sum": packet_result.get("contract_test_count_sum"),
        "formal_target_commit_sha": packet_result.get("formal_target_commit_sha"),
        "private_key_present": False,
    }
    if not packet_ok:
        blockers.append("UNSIGNED_V220_PACKET_NOT_CANONICAL")

    work_outside = not _inside(work_dir, repo)
    nonce_outside = not _inside(nonce_registry, repo)
    checks["external_state_paths"] = {
        "ok": work_outside and nonce_outside,
        "work_dir": str(work_dir),
        "work_dir_outside_repo": work_outside,
        "nonce_registry": str(nonce_registry),
        "nonce_registry_outside_repo": nonce_outside,
    }
    if not work_outside:
        blockers.append("WORK_DIR_MUST_BE_OUTSIDE_REPOSITORY")
    if not nonce_outside:
        blockers.append("NONCE_REGISTRY_MUST_BE_OUTSIDE_REPOSITORY")

    if args.certification_trust_root:
        checks["certification_trust_root"] = _validate_public_trust_root(
            args.certification_trust_root.expanduser().resolve(),
            "CERTIFICATION_TRUST_ROOT",
        )
        if not checks["certification_trust_root"]["ok"]:
            blockers.append(str(checks["certification_trust_root"]["reason"]))
    else:
        checks["certification_trust_root"] = {
            "ok": False,
            "reason": "NOT_SUPPLIED_TO_PREFLIGHT",
            "required_before_real_v220": True,
        }

    if args.owner_trust_root:
        checks["owner_trust_root"] = _validate_public_trust_root(
            args.owner_trust_root.expanduser().resolve(),
            "OWNER_TRUST_ROOT",
        )
        if not checks["owner_trust_root"]["ok"]:
            blockers.append(str(checks["owner_trust_root"]["reason"]))
    else:
        checks["owner_trust_root"] = {
            "ok": False,
            "reason": "NOT_SUPPLIED_TO_PREFLIGHT",
            "required_before_real_v224": True,
        }

    runtime_cfg = runtime_configuration_status()
    checks["runtime_configuration"] = {
        "ok": runtime_cfg.get("read_ready") is True,
        "repo_configured": runtime_cfg.get("repo_configured"),
        "branch_configured": runtime_cfg.get("branch_configured"),
        "branch_safe": runtime_cfg.get("branch_safe"),
        "read_ready": runtime_cfg.get("read_ready"),
        "write_ready": runtime_cfg.get("write_ready"),
        "write_credential_configured": runtime_cfg.get("write_credential_configured"),
        "mode": runtime_cfg.get("mode"),
        "secret_exposed": False,
    }
    if args.require_write_ready and runtime_cfg.get("write_ready") is not True:
        blockers.append("RUNTIME_WRITE_CREDENTIAL_NOT_READY")

    if args.check_runtime_read:
        observed = load_runtime_checkpoint()
        runtime_ok = (
            observed.get("status") == "CONFIRMED"
            and observed.get("source") == EXPECTED_RUNTIME_SOURCE
            and observed.get("sha") == args.expected_runtime_sha
        )
        checks["runtime_read"] = {
            "ok": runtime_ok,
            "status": observed.get("status"),
            "source": observed.get("source"),
            "expected_sha": args.expected_runtime_sha,
            "observed_sha": observed.get("sha"),
            "checkpoint_loaded": isinstance(observed.get("checkpoint"), dict),
            "network_read_performed": True,
            "network_write_performed": False,
        }
        if not runtime_ok:
            blockers.append("OFFICIAL_RUNTIME_BASELINE_MISMATCH")
    else:
        checks["runtime_read"] = {
            "ok": None,
            "reason": "NOT_REQUESTED",
            "network_read_performed": False,
            "network_write_performed": False,
        }

    unique = sorted(set(blockers))
    real_authority_ready = (
        not unique
        and is_windows
        and checks["certification_trust_root"]["ok"] is True
        and checks["owner_trust_root"]["ok"] is True
        and runtime_cfg.get("write_ready") is True
        and args.check_runtime_read
        and checks["runtime_read"]["ok"] is True
    )

    result = {
        "schema": "AION_CORE_V1_WINDOWS_CLOSURE_READINESS_PREFLIGHT_V1",
        "state": (
            "READY_FOR_FORMAL_CLOSURE_CEREMONY"
            if real_authority_ready
            else "STRUCTURAL_PREFLIGHT_PASS"
            if not unique
            else "BLOCKED"
        ),
        "blockers": unique,
        "formal_target_commit_sha": TARGET,
        "expected_runtime_sha": args.expected_runtime_sha,
        "checks": checks,
        "real_authority_ready": real_authority_ready,
        "private_key_loaded": False,
        "signature_performed": False,
        "nonce_consumed": False,
        "runtime_write_performed": False,
        "merge_authorized": False,
        "deploy_authorized": False,
        "worker_armed": False,
        "executes_action": False,
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if not unique else 2


if __name__ == "__main__":
    raise SystemExit(main())
