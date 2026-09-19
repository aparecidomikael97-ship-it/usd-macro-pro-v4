"""AtlasQuant source-parity contract.

Pure helpers for comparing source trees between the integration candidate and
runtime branch. Runtime evidence under dados/ is deliberately excluded. This
module never writes refs, merges branches, copies runtime data or changes
trading permissions.
"""
from __future__ import annotations

from pathlib import PurePosixPath
from typing import Mapping, Iterable, Any

SCHEMA="ATLASQUANT_SOURCE_PARITY_V1"
DEFAULT_IGNORED_PREFIXES=("dados/",)


def _normalize(path: object) -> str:
    raw=str(path or "").strip().replace("\\","/")
    while "//" in raw:
        raw=raw.replace("//","/")
    if raw.startswith("./"):
        raw=raw[2:]
    return raw


def is_runtime_data_path(path: object, ignored_prefixes: Iterable[str] = DEFAULT_IGNORED_PREFIXES) -> bool:
    p=_normalize(path)
    if not p:
        return False
    prefixes=tuple(_normalize(x) for x in ignored_prefixes if _normalize(x))
    return any(p.startswith(prefix) for prefix in prefixes)


def compare_source_trees(
    integration: Mapping[str,str] | None,
    runtime: Mapping[str,str] | None,
    *,
    ignored_prefixes: Iterable[str] = DEFAULT_IGNORED_PREFIXES,
) -> dict[str,Any]:
    left={_normalize(k):str(v or "").strip() for k,v in dict(integration or {}).items()}
    right={_normalize(k):str(v or "").strip() for k,v in dict(runtime or {}).items()}

    all_paths=sorted(set(left)|set(right))
    checked=[]
    only_integration=[]
    only_runtime=[]
    mismatched=[]

    for path in all_paths:
        if not path or is_runtime_data_path(path,ignored_prefixes):
            continue
        checked.append(path)
        l=left.get(path)
        r=right.get(path)
        if l is None:
            only_runtime.append(path)
        elif r is None:
            only_integration.append(path)
        elif not l or not r or l!=r:
            mismatched.append(path)

    parity=not only_integration and not only_runtime and not mismatched
    return {
        "schema":SCHEMA,
        "status":"SOURCE_PARITY_OK" if parity else "SOURCE_PARITY_MISMATCH",
        "checked_files":len(checked),
        "only_integration":only_integration,
        "only_runtime":only_runtime,
        "mismatched":mismatched,
        "runtime_data_ignored":True,
        "manual_reconciliation_required":not parity,
        "automatic_merge_allowed":False,
        "automatic_runtime_overwrite_allowed":False,
    }


def parse_ls_tree(text: str | None) -> dict[str,str]:
    out:dict[str,str]={}
    for raw in str(text or "").splitlines():
        line=raw.rstrip("\n")
        if not line:
            continue
        try:
            meta,path=line.split("\t",1)
            parts=meta.split()
            sha=parts[2]
        except Exception as exc:
            raise ValueError(f"invalid ls-tree line: {line!r}") from exc
        p=_normalize(path)
        if not p or PurePosixPath(p).is_absolute() or ".." in PurePosixPath(p).parts:
            raise ValueError(f"unsafe tree path: {path!r}")
        if len(sha)!=40 or any(ch not in "0123456789abcdefABCDEF" for ch in sha):
            raise ValueError(f"invalid blob sha for {p}")
        out[p]=sha.lower()
    return out
