"""Deterministic non-secret source-bundle identity for production observability.

The fingerprint represents the executable AtlasQuant Python bundle and runtime
configuration files shipped with the app. Runtime data, tests, docs and secrets
are intentionally excluded.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Iterable

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


__all__=["source_fingerprint","short_source_fingerprint"]
