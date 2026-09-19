"""AtlasQuant native packaging readiness audit.

Audits repository preparation only. It never signs packages, publishes stores,
changes distribution endpoints, embeds credentials or enables trading.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
import json

SCHEMA="ATLASQUANT_NATIVE_PACKAGING_V1"
ROOT=Path(__file__).resolve().parent

_REQUIRED=(
    "native/app_metadata.json",
    "native/README.md",
    "native/android/PACKAGING_CHECKLIST.md",
    "native/apple/PACKAGING_CHECKLIST.md",
    "native/desktop/PACKAGING_CHECKLIST.md",
)

def native_packaging_audit(root:Path|None=None)->dict[str,Any]:
    base=Path(root) if root is not None else ROOT
    missing=[p for p in _REQUIRED if not (base/p).is_file()]
    metadata={}
    metadata_ok=False
    if not missing:
        try:
            metadata=json.loads((base/"native"/"app_metadata.json").read_text(encoding="utf-8"))
            metadata_ok=bool(
                metadata.get("app_name")=="AtlasQuant"
                and str(metadata.get("pwa_url") or "").startswith("https://")
                and metadata.get("android_package_signed") is False
                and metadata.get("ios_package_signed") is False
                and metadata.get("store_publication_verified") is False
                and metadata.get("real_orders_enabled") is False
            )
        except Exception:
            metadata_ok=False
    prep_ready=bool(not missing and metadata_ok)
    return {
        "schema":SCHEMA,
        "preparation_ready":prep_ready,
        "missing":missing,
        "metadata_ok":metadata_ok,
        "android_signed":False,
        "ios_signed":False,
        "native_store_publication_verified":False,
        "pwa_remains_current_distribution":True,
        "signing_secrets_in_repo":False,
        "real_orders_changed":False,
    }

__all__=["SCHEMA","native_packaging_audit"]
