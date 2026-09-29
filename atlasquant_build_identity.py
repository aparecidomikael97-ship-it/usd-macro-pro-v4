"""Deterministic non-secret source-bundle identity for production observability.

The fingerprint represents the executable AtlasQuant Python bundle and runtime
configuration files shipped with the app. Runtime data, tests, docs and secrets
are intentionally excluded.

Runtime identity reports only values the host actually supplied. Missing git
metadata stays UNKNOWN. This module never reads or returns a deploy hook URL.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Iterable, Mapping
import os
import re
import subprocess

INCLUDE_TOP_LEVEL_SUFFIXES={".py"}
INCLUDE_EXACT={"requirements.txt","render.yaml","Dockerfile"}
EXCLUDE_PREFIXES=("test_",)
EXCLUDE_DIRS={".git","dados","docs","native","__pycache__"}


def _iter_identity_files(root:Path)->Iterable[Path]:
    for path in root.iterdir():
        if path.is_dir():
            continue
        name=path.name
        if any(name.startswith(prefix) for prefix in EXCLUDE_PREFIXES):
            continue
        if path.suffix in INCLUDE_TOP_LEVEL_SUFFIXES or name in INCLUDE_EXACT:
            yield path
    streamlit=root/".streamlit"/"config.toml"
    if streamlit.is_file():
        yield streamlit


def source_fingerprint(root:Path|str|None=None)->str:
    base=Path(root or Path(__file__).resolve().parent).resolve()
    digest=sha256()
    files=sorted(_iter_identity_files(base),key=lambda p:p.relative_to(base).as_posix())
    for path in files:
        rel=path.relative_to(base).as_posix().encode("utf-8")
        raw=path.read_bytes()
        digest.update(len(rel).to_bytes(4,"big"))
        digest.update(rel)
        digest.update(len(raw).to_bytes(8,"big"))
        digest.update(raw)
    return digest.hexdigest()


def short_source_fingerprint(root:Path|str|None=None,length:int=16)->str:
    n=max(8,min(64,int(length)))
    return source_fingerprint(root)[:n]


UNKNOWN="UNKNOWN"
_SHA_RE=re.compile(r"^[0-9a-fA-F]{40}$")
_REF_RE=re.compile(r"^[A-Za-z0-9._/-]{1,120}$")
_TOKEN_RE=re.compile(r"^[A-Za-z0-9._:+-]{1,80}$")
_RELEASE_RE=re.compile(r"^[A-Za-z0-9 ._+·—-]{1,160}$")
_STAMP_RE=re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]+)?(?:Z|[+-][0-9]{2}:[0-9]{2})$"
)
_LOCAL_HOSTS=("http://127.0.0.1","http://localhost","https://127.0.0.1","https://localhost")
_COMMIT_ENV=("RENDER_GIT_COMMIT","ATLASQUANT_DEPLOY_COMMIT","GIT_COMMIT")
_REF_ENV=("RENDER_GIT_BRANCH","ATLASQUANT_DEPLOY_REF","GITHUB_REF_NAME")


def _mapping(env:Mapping[str,str]|None)->Mapping[str,str]:
    if env is None:
        return os.environ
    return env


def normalize_commit_sha(value:object)->str:
    text=str(value or "").strip()
    if _SHA_RE.fullmatch(text):
        return text.lower()
    return UNKNOWN


def _present_sha(env:Mapping[str,str], key:str)->str|None:
    if key not in env:
        return None
    raw=env.get(key)
    if raw is None or str(raw).strip()=="":
        return None
    return normalize_commit_sha(raw)


def _present_token(env:Mapping[str,str], key:str, pattern:re.Pattern[str])->str|None:
    if key not in env:
        return None
    raw=env.get(key)
    if raw is None or str(raw).strip()=="":
        return None
    text=str(raw).strip()
    if pattern.fullmatch(text):
        return text
    return UNKNOWN


def _git_stdout(root:Path, args:list[str])->str:
    try:
        probe=subprocess.run(
            ["git",*args],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=1.5,
            check=False,
        )
    except Exception:
        return ""
    if probe.returncode!=0:
        return ""
    return str(probe.stdout or "").strip()


def _observed_commit(env:Mapping[str,str], root:Path)->str:
    for key in _COMMIT_ENV:
        found=_present_sha(env, key)
        if found is not None:
            return found
    candidate=_git_stdout(root, ["rev-parse","HEAD"])
    if candidate and re.fullmatch(r"[0-9a-fA-F]{40}", candidate):
        return candidate.lower()
    return UNKNOWN


def _observed_ref(env:Mapping[str,str], root:Path)->str:
    for key in _REF_ENV:
        found=_present_token(env, key, _REF_RE)
        if found is not None:
            return found
    branch=_git_stdout(root, ["rev-parse","--abbrev-ref","HEAD"])
    if branch and branch!="HEAD" and _REF_RE.fullmatch(branch):
        return branch
    return UNKNOWN


def _observed_environment(env:Mapping[str,str])->str:
    named=_present_token(env, "ATLASQUANT_ENVIRONMENT", _TOKEN_RE)
    if named is not None:
        return named
    render=str(env.get("RENDER","") or "").strip().lower()
    if render=="true":
        return "render"
    return UNKNOWN


def _observed_timestamp(env:Mapping[str,str])->str:
    named=_present_token(env, "ATLASQUANT_BUILD_TIMESTAMP", _STAMP_RE)
    if named is not None:
        return named
    if "SOURCE_DATE_EPOCH" not in env:
        return UNKNOWN
    raw=str(env.get("SOURCE_DATE_EPOCH") or "").strip()
    if raw=="":
        return UNKNOWN
    if not raw.isdigit():
        return UNKNOWN
    epoch=int(raw)
    if epoch<=0:
        return UNKNOWN
    return datetime.fromtimestamp(epoch, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _safe_release(value:object)->str:
    text=str(value or "").strip()
    if text and _RELEASE_RE.fullmatch(text):
        return text
    return UNKNOWN


def runtime_build_identity(
    *,
    env:Mapping[str,str]|None=None,
    root:Path|str|None=None,
    release_id:object="",
    source_build:object="",
)->dict[str,str|bool]:
    """Non-secret runtime identity. Absent facts stay UNKNOWN."""
    data=_mapping(env)
    base=Path(root or Path(__file__).resolve().parent).resolve()
    commit=_observed_commit(data, base)
    fingerprint=str(source_build or "").strip().lower()
    if not fingerprint:
        try:
            fingerprint=short_source_fingerprint(base, 16)
        except Exception:
            fingerprint=UNKNOWN
    if not re.fullmatch(r"[0-9a-f]{8,64}", fingerprint or ""):
        fingerprint=UNKNOWN
    if str(release_id or "").strip():
        release=_safe_release(release_id)
    else:
        found=_present_token(data, "ATLASQUANT_RELEASE_ID", _RELEASE_RE)
        release=UNKNOWN if found is None else found
    return {
        "schema":"ATLASQUANT_RUNTIME_BUILD_IDENTITY_V1",
        "commit_sha":commit,
        "branch":_observed_ref(data, base),
        "environment":_observed_environment(data),
        "build_timestamp":_observed_timestamp(data),
        "release_id":release if isinstance(release, str) else UNKNOWN,
        "source_build":fingerprint,
        "commit_observed":commit!=UNKNOWN,
    }


def compare_deploy_identity(
    expected_sha:object,
    observed_sha:object,
    *,
    target_url:object="",
)->dict[str,object]:
    """Compare expected and observed SHAs without treating localhost as production."""
    expected=normalize_commit_sha(expected_sha)
    observed=normalize_commit_sha(observed_sha)
    url=str(target_url or "").strip().lower()
    local=url=="" or url.startswith(_LOCAL_HOSTS)
    if local:
        state="LOCAL_OBSERVATION"
        match=expected!=UNKNOWN and expected==observed
        proves=False
    elif expected==UNKNOWN or observed==UNKNOWN:
        state="SHA_UNAVAILABLE"
        match=False
        proves=False
    elif expected!=observed:
        state="DEPLOY_IDENTITY_MISMATCH"
        match=False
        proves=False
    else:
        state="MATCH"
        match=True
        proves=True
    return {
        "schema":"ATLASQUANT_DEPLOY_IDENTITY_COMPARE_V1",
        "state":state,
        "code":state,
        "expected_sha":expected,
        "observed_sha":observed,
        "match":match,
        "proves_production":proves,
        "target_is_local":local,
    }


def _attr(value:object)->str:
    text=str(value or UNKNOWN)
    if text!=UNKNOWN and not (
        _SHA_RE.fullmatch(text)
        or _REF_RE.fullmatch(text)
        or _TOKEN_RE.fullmatch(text)
        or _RELEASE_RE.fullmatch(text)
        or _STAMP_RE.fullmatch(text)
        or re.fullmatch(r"[0-9a-f]{8,64}", text)
    ):
        text=UNKNOWN
    return text


def identity_marker_html(identity:Mapping[str,object])->str:
    """Hidden diagnostic marker. It never includes credentials or hook URLs."""
    commit=_attr(identity.get("commit_sha"))
    branch=_attr(identity.get("branch"))
    environment=_attr(identity.get("environment"))
    built_at=_attr(identity.get("build_timestamp"))
    release=_attr(identity.get("release_id"))
    proves="true" if commit!=UNKNOWN else "false"
    return (
        '<div id="atlasquant-runtime-identity" '
        f'data-commit="{commit}" '
        f'data-branch="{branch}" '
        f'data-environment="{environment}" '
        f'data-built-at="{built_at}" '
        f'data-release="{release}" '
        f'data-proves-sha="{proves}" '
        'aria-hidden="true" '
        'style="position:absolute;left:-10000px;top:auto;width:1px;height:1px;'
        'overflow:hidden;opacity:0;pointer-events:none;">'
        f'AQSHA:{commit}</div>'
    )


__all__=[
    "UNKNOWN",
    "source_fingerprint",
    "short_source_fingerprint",
    "normalize_commit_sha",
    "runtime_build_identity",
    "compare_deploy_identity",
    "identity_marker_html",
]
