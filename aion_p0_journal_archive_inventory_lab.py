"""Read-only evidence inventory for the original AION 12-Oct Journal P0 cases.

This utility NEVER runs recovered code, changes files, authenticates an issuer,
or changes the status of a P0. It inventories only known evidence basenames,
refuses ambiguous/symlinked inputs, and emits a content-hash report on stdout.

Usage (after authorized am12 access, without running historical tests):
 python -B aion_p0_journal_archive_inventory_lab.py --root "C:\\Users\\apare\\Downloads\\AQ_LAB_COMPAT_MIGRATE_20261012"
Optional: redirect stdout to a NEW file outside the evidence source directory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys

SOURCE = "https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/issues/1190#issuecomment-6132259470"
# Checkpoint's published digest is evidence of a historical CLAIM, not external authorship.
PUBLISHED_MANIFEST_SHA256 = "6ed98d799a8fbf6d985d72b15404463d8115e77b8904a60282fd4e0e1ad2a715"
# Exact names from 12-Oct checkpoint. The original two basenames are inferred
# from named test modules and MUST be manually compared with the source log.
REQUIRED = {
    "original_journal_a": "test_lab_journal.py",
    "original_journal_b": "test_conservative_journal.py",
    "migrated_journal_a": "test_lab_journal_migrated_v2.py",
    "migrated_journal_b": "test_conservative_journal_migrated_v2.py",
    "migration_report": "FINAL_COMPAT_MIGRATION.md",
    "migration_readout": "FINAL_COMPAT_MIGRATION_READOUT.json",
    "migrated_run_log": "MIGRATED_76_FINAL.log",
    "public_guard_log": "PUBLIC_GUARD_AND_V2.log",
    "rollback_counterexample_log": "ROLLBACK_COUNTEREXAMPLES.log",
    "manifest": "SHA256_MANIFEST.json",
}
MAX_BYTES_PER_FILE = 256 * 1024 * 1024
MAX_TREE_ENTRIES = 10000
MAX_TREE_DEPTH = 12


def _identity(info: os.stat_result) -> tuple[int, int, int, int, int]:
    """Best-effort stability fingerprint; not a cryptographic provenance proof."""
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _discover_evidence(root: Path) -> dict[str, list[Path]]:
    """Walk a bounded tree without following links or loading an unbounded glob."""
    found: dict[str, list[Path]] = {name: [] for name in REQUIRED.values()}
    stack: list[tuple[Path, int]] = [(root, 0)]
    visited = 0
    while stack:
        folder, depth = stack.pop()
        with os.scandir(folder) as entries:
            for entry in entries:
                visited += 1
                if visited > MAX_TREE_ENTRIES:
                    raise ValueError("EVIDENCE_TREE_ENTRY_LIMIT_EXCEEDED")
                # Windows junctions are separate from standard symlinks.
                if entry.is_symlink() or (hasattr(entry, "is_junction") and entry.is_junction()):
                    raise ValueError("EVIDENCE_TREE_LINK_OR_JUNCTION_UNTRUSTED")
                if entry.is_dir(follow_symlinks=False):
                    if depth >= MAX_TREE_DEPTH:
                        raise ValueError("EVIDENCE_TREE_DEPTH_LIMIT_EXCEEDED")
                    stack.append((Path(entry.path), depth + 1))
                elif entry.name in found and entry.is_file(follow_symlinks=False):
                    found[entry.name].append(Path(entry.path))
    return found


def sha256_regular_file(path: Path) -> str:
    """Bound an opened regular file, checking metadata before/after the read.

    O_NOFOLLOW is used where supported; Windows still needs isolated trusted
    recovery media and human review for reparse-point/race guarantees.
    """
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    with os.fdopen(fd, "rb") as stream:
        initial = os.fstat(stream.fileno())
        path_initial = path.lstat()
        if not stat.S_ISREG(initial.st_mode) or _identity(initial) != _identity(path_initial):
            raise ValueError("EVIDENCE_NOT_STABLE_REGULAR_FILE")
        if initial.st_size > MAX_BYTES_PER_FILE:
            raise ValueError("OVERSIZED_EVIDENCE_FILE")
        digest = hashlib.sha256()
        total = 0
        while block := stream.read(min(1024 * 1024, MAX_BYTES_PER_FILE - total + 1)):
            total += len(block)
            if total > MAX_BYTES_PER_FILE:
                raise ValueError("EVIDENCE_READ_LIMIT_EXCEEDED")
            digest.update(block)
        final = os.fstat(stream.fileno())
        path_final = path.lstat()
        if (total != initial.st_size or _identity(initial) != _identity(final)
                or _identity(initial) != _identity(path_final)):
            raise ValueError("EVIDENCE_CHANGED_DURING_READ")
        return digest.hexdigest()


def inspect(root: Path) -> dict:
    result = {
        "schema": "AION_JOURNAL_20261012_READONLY_INVENTORY_LAB_V1",
        "historical_reference": SOURCE,
        "published_manifest_sha256_claim": PUBLISHED_MANIFEST_SHA256,
        "status": "BLOCKED_EVIDENCE_INCOMPLETE",
        "case_homologation": "ZERO_OF_SIX",
        "worker_authorized": False,
        "automatic_retry_authorized": False,
        "production_allowed": False,
        "historical_tests_executed": False,
        "sources_authenticated": False,
        "historical_76_result_reproduced": False,
        "source_files_modified": False,
        "root_exists": False,
        "files": {},
        "gaps": [],
    }
    if not root.is_dir() or root.is_symlink():
        result["gaps"].append("EVIDENCE_ROOT_MISSING_OR_SYMLINK")
        return result
    root = root.resolve()
    result["root_exists"] = True
    # Single bounded walk; reject reparse points and ambiguous tree structure.
    # Never import, parse or execute historic Python.
    try:
        discovered = _discover_evidence(root)
    except (OSError, ValueError) as exc:
        result["gaps"].append(f"EVIDENCE_SCAN_BLOCKED:{type(exc).__name__}:{exc}")
        return result
    for label, basename in REQUIRED.items():
        matches = sorted(discovered[basename])
        if len(matches) != 1:
            code = "NOT_FOUND" if not matches else "AMBIGUOUS_MULTIPLE_COPIES"
            result["files"][label] = {"state": code, "copies_found": len(matches)}
            result["gaps"].append(f"{label}:{code}")
            continue
        p = matches[0]
        try:
            if p.is_symlink() or any(x.is_symlink() for x in p.parents if x != root and root in x.parents):
                raise ValueError("SYMLINKED_EVIDENCE_PATH")
            if not p.is_file() or not p.resolve().is_relative_to(root):
                raise ValueError("UNSAFE_OR_NON_REGULAR_FILE")
            before = p.lstat()
            size = before.st_size
            if size > MAX_BYTES_PER_FILE:
                raise ValueError("OVERSIZED_EVIDENCE_FILE")
            digest = sha256_regular_file(p)
            if _identity(before) != _identity(p.lstat()):
                raise ValueError("EVIDENCE_CHANGED_DURING_READ")
            item = {"state": "CAPTURED_UNAUTHENTICATED", "relative_path": p.relative_to(root).as_posix(), "bytes": size, "sha256": digest}
            if label == "manifest":
                item["matches_published_checkpoint_digest"] = (digest == PUBLISHED_MANIFEST_SHA256)
                if not item["matches_published_checkpoint_digest"]:
                    result["gaps"].append("MANIFEST_DIGEST_MISMATCH")
            result["files"][label] = item
        except (OSError, ValueError) as e:
            result["files"][label] = {"state": "UNSAFE_OR_UNREADABLE", "reason": str(e)}
            result["gaps"].append(f"{label}:UNSAFE_OR_UNREADABLE")
    if not result["gaps"]:
        result["status"] = "FILES_CAPTURED_REQUIRE_INDEPENDENT_COMPARISON_AND_REEXECUTION"
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Read-only original Journal P0 inventory; never verifies P0 closure")
    parser.add_argument("--root", type=Path, required=True, help="Path to an EXISTING, isolated 12-Oct evidence directory")
    args = parser.parse_args(argv)
    r = inspect(args.root)
    print(json.dumps(r, indent=2, ensure_ascii=False, sort_keys=True))
    # Even with every expected file present, archive capture is not P0 acceptance.
    # A nonzero exit prevents CI from silently turning the inventory into a GO.
    return 3 if r["status"].startswith("FILES_CAPTURED") else 2


if __name__ == "__main__":
    sys.exit(main())
