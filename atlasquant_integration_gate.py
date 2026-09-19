"""AtlasQuant source-integration release gate.

Pure, offline evaluation for the source-only integration branch. It never merges,
promotes, writes runtime evidence, changes trading gates or certifies production.
"""
from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any, Iterable, Mapping
import json
import re

SCHEMA="ATLASQUANT_INTEGRATION_GATE_V1"
_SHA40=re.compile(r"^[0-9a-f]{40}$")


def _actual_bool(value: object) -> bool:
    return isinstance(value,bool)


def _normalize_path(value: object) -> str:
    raw=str(value or "").strip().replace("\\","/")
    while "//" in raw:
        raw=raw.replace("//","/")
    if raw.startswith("./"):
        raw=raw[2:]
    return raw


def _unsafe_path(path: str) -> bool:
    p=_normalize_path(path)
    if not p or p.startswith("/"):
        return True
    parts=PurePosixPath(p).parts
    return any(part in ("","..") for part in parts)


def _secret_like_path(path: str) -> bool:
    p=_normalize_path(path).lower()
    name=PurePosixPath(p).name
    if p in {".env",".streamlit/secrets.toml","secrets.toml"}:
        return True
    if p.startswith(".env."):
        return p!=".env.example"
    if name.endswith((".pem",".key")):
        return True
    if name.startswith("credentials") and name.endswith(".json"):
        return True
    if name.startswith("service-account") and name.endswith(".json"):
        return True
    return False


def evaluate_integration_candidate(
    changed_paths: Iterable[object] | None,
    *,
    main_is_ancestor: bool,
    compile_ok: bool,
    preflight_ok: bool,
    candidate_sha: str,
    base_sha: str,
) -> dict[str,Any]:
    blockers:list[str]=[]
    normalized=[]
    for raw in changed_paths or ():
        p=_normalize_path(raw)
        if not p:
            continue
        normalized.append(p)
        if _unsafe_path(p):
            blockers.append(f"Unsafe path: {p}")

    for name,value in (
        ("main_is_ancestor",main_is_ancestor),
        ("compile_ok",compile_ok),
        ("preflight_ok",preflight_ok),
    ):
        if not _actual_bool(value):
            blockers.append(f"Invalid boolean evidence: {name}")

    candidate=str(candidate_sha or "").strip().lower()
    base=str(base_sha or "").strip().lower()
    if not _SHA40.fullmatch(candidate):
        blockers.append("Invalid candidate SHA")
    if not _SHA40.fullmatch(base):
        blockers.append("Invalid base SHA")
    if candidate and base and candidate==base:
        blockers.append("Candidate contains no source change")

    if _actual_bool(main_is_ancestor) and not main_is_ancestor:
        blockers.append("Candidate is behind/diverged from current main")
    if _actual_bool(compile_ok) and not compile_ok:
        blockers.append("Python compile check failed")
    if _actual_bool(preflight_ok) and not preflight_ok:
        blockers.append("DEV preflight failed")

    data_paths=sorted({p for p in normalized if p.startswith("dados/")})
    if data_paths:
        blockers.append("Source candidate contains runtime/data files")

    secret_paths=sorted({p for p in normalized if _secret_like_path(p)})
    if secret_paths:
        blockers.append("Source candidate contains secret-like file paths")

    unique=sorted(set(normalized))
    if not unique:
        blockers.append("Candidate contains no changed source files")
    reviewable=not blockers
    return {
        "schema":SCHEMA,
        "status":"REVIEWABLE_SOURCE_ONLY" if reviewable else "BLOCKED",
        "candidate_sha":candidate,
        "base_sha":base,
        "changed_files":len(unique),
        "runtime_or_data_files":data_paths,
        "secret_like_files":secret_paths,
        "main_is_ancestor":bool(main_is_ancestor) if _actual_bool(main_is_ancestor) else False,
        "compile_ok":bool(compile_ok) if _actual_bool(compile_ok) else False,
        "preflight_ok":bool(preflight_ok) if _actual_bool(preflight_ok) else False,
        "blockers":blockers,
        "quality_suite_external_required":True,
        "source_checkpoint_external_required":True,
        "manual_review_required":True,
        "automatic_merge_allowed":False,
        "automatic_promotion_allowed":False,
        "runtime_data_copy_allowed":False,
    }


def integration_manifest_json(result: Mapping[str,Any]) -> str:
    return json.dumps(dict(result),ensure_ascii=False,indent=2,sort_keys=True)
