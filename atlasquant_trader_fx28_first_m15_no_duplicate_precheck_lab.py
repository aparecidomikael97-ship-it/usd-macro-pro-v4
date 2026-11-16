"""Read-only FX28 first M15 repeated-attempt archive preflight (LAB only).

This is a DETECTION guard, not an atomic lock. The frozen AM12 collector still
names archive directories using clock time and therefore permits another
archive for the same window if invoked again. NEVER interpret clean precheck
as permission for more than the ONE explicitly scheduled attempt.

No MT5, price access, filesystem changes, scheduler, trading or network.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import json
import os
from typing import Any

SCHEMA = "ATLASQUANT_FX28_FIRST_M15_SINGLE_ATTEMPT_PRECHECK_LAB_V1"
WINDOW = "CAMPAIGN_FIRST_M15_20261115"

def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_FX28_M15_REPEAT_ATTEMPT_PREFLIGHT_BLOCKED",
        "reason": reason,
        "window": WINDOW,
        "existing_candidate_count": None,
        "existing_candidate_names": [],
        "single_attempt_start_precheck_clear": False,
        "concurrency_safe_atomic_lock_verified": False,
        "precheck_does_not_reserve_or_lock_window": True,
        "source_first_seen_authenticated": False,
        "real_market_data_verified": False,
        "trading_authorized": False, "operational_bias": "AGUARDAR",
        "http_requests": 0, "mt5_calls": 0, "file_writes": 0,
        "research_only": True,
    }

def check_no_prior_attempt_lab(*, archive_root: Any, window: Any = WINDOW) -> dict[str, Any]:
    out = _base("INVALID_WINDOW_OR_ROOT")
    if (type(window) is not str or window != WINDOW
            or not isinstance(archive_root, Path) or not archive_root.is_absolute()):
        return out
    try:
        if archive_root.is_symlink():
            return _base("UNSAFE_ARCHIVE_ROOT_SYMLINK")
        if not archive_root.exists():
            out.update({
                "state": "LAB_FX28_M15_FIRST_ATTEMPT_ARCHIVE_NOT_SEEN_NO_GO",
                "reason": "ROOT_DOES_NOT_YET_EXIST_NO_LOCK_ATOMICITY",
                "existing_candidate_count": 0,
                "single_attempt_start_precheck_clear": True,
            })
            return out
        if not archive_root.is_dir():
            return _base("ROOT_NOT_A_DIRECTORY")
        # Case-insensitive comparison matches Windows directory semantics.
        prefix = window.casefold() + "_"
        existing = []
        with os.scandir(archive_root) as entries:
            for entry in entries:
                name = entry.name
                if name.casefold() == window.casefold() or name.casefold().startswith(prefix):
                    existing.append(name)
        existing.sort(key=str.casefold)
        out["existing_candidate_count"] = len(existing)
        out["existing_candidate_names"] = existing[:12]
        if existing:
            out["reason"] = "ONE_OR_MORE_PREVIOUS_ATTEMPT_ARTIFACTS_EXIST_NO_SECOND_RUN"
            return out
        out.update({
            "state": "LAB_FX28_M15_FIRST_ATTEMPT_ARCHIVE_NOT_SEEN_NO_GO",
            "reason": "NO_PRIOR_WINDOW_ARTIFACT_VISIBLE_AT_THIS_INSTANT_NO_LOCK_ATOMICITY",
            "single_attempt_start_precheck_clear": True,
        })
        return out
    except (OSError, ValueError, TypeError, PermissionError):
        return _base("ARCHIVE_ROOT_INSPECTION_FAILED_FAIL_CLOSED")

def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only no-duplicate M15 window precheck")
    parser.add_argument("--archive-root", type=Path)
    args = parser.parse_args()
    root = args.archive_root
    if root is None:
        localappdata = os.environ.get("LOCALAPPDATA")
        if not localappdata:
            print(json.dumps(_base("LOCALAPPDATA_MISSING_FAIL_CLOSED")))
            return 2
        root = Path(localappdata) / "AtlasQuant" / "LAB" / "FX28_NY17_M15"
    report = check_no_prior_attempt_lab(archive_root=root)
    print(json.dumps(report, sort_keys=True, indent=2, ensure_ascii=False))
    return 0 if report["single_attempt_start_precheck_clear"] else 2

if __name__ == "__main__":
    raise SystemExit(main())
