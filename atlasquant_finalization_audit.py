"""AtlasQuant final internal-completion audit.

This is a repository/product-preparation audit, not a public-launch approval.
External legal, licensing, billing, TTS, media-rendering and store-publication
evidence remain fail-closed until independently verified.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from atlasquant_public_launch_readiness import collect_public_launch_readiness
from atlasquant_native_packaging import native_packaging_audit
from atlasquant_commercial_prep import commercial_prep_audit

SCHEMA="ATLASQUANT_FINALIZATION_AUDIT_V1"
ROOT=Path(__file__).resolve().parent

_REQUIRED_HANDOFF_DOCS=(
    "README.md",
    "docs/release/ATLASQUANT_RELEASE_FINAL.md",
    "docs/release/SALES_ADMIN_OPERATIONS.md",
    "docs/release/EXTERNAL_DEPENDENCY_HANDOFF.md",
    "docs/release/STORE_METADATA_TEMPLATE.md",
    "docs/release/PROVIDER_SETUP_TEMPLATE.md",
    "docs/release/USER_QUICKSTART.md",
    "docs/release/BRANCH_POLICY.md",
    "docs/release/INCIDENT_ROLLBACK_RUNBOOK.md",
)

def finalization_audit(root:Path|None=None)->dict[str,Any]:
    base=Path(root) if root is not None else ROOT
    missing_docs=[p for p in _REQUIRED_HANDOFF_DOCS if not (base/p).is_file()]
    launch=collect_public_launch_readiness()
    native=native_packaging_audit(base)
    commercial=commercial_prep_audit(base)

    internal_complete=bool(
        launch.get("internal_preparation_complete")
        and native.get("preparation_ready")
        and commercial.get("internal_prep_ready")
        and not missing_docs
    )
    external_complete=bool(launch.get("external_dependencies_complete"))
    return {
        "schema":SCHEMA,
        "internal_release_preparation_complete":internal_complete,
        "handoff_docs_complete":not missing_docs,
        "missing_handoff_docs":missing_docs,
        "external_dependencies_complete":external_complete,
        "public_launch_ready":bool(internal_complete and external_complete),
        "real_orders_enabled":False,
        "broker_execution_enabled":False,
        "automatic_public_launch":False,
        "manual_external_completion_required":True,
    }

__all__=["SCHEMA","finalization_audit"]
