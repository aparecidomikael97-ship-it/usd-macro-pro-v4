"""Fail-closed quarantine for GitHub runtime files with no proven tenant owner.

Phase B of #1169. A valid ADMIN session and workspace membership authorizes
the *session context* only; it cannot establish which tenant owns a shared
legacy file at dados/*. There is no durable tenant namespace, independently
verified origin, CAS receipt, or anti-rollback witness for these files.

This module deliberately offers NO environment override, admin bypass,
fallback branch, token-based permit, or auto-discovery path. Existing bytes
remain unchanged in their legacy locations until a separately reviewed,
tenant-bound migration explicitly authorizes a particular resource.
"""
from __future__ import annotations

LEGACY_SHARED_PATHS = frozenset({
    "dados/atlasquant_shadow_samples.jsonl",
    "dados/atlasquant_operational_evidence_v1.jsonl",
    "dados/atlasquant_flight_recorder.jsonl",
    "dados/sinais_v84.csv",
    "dados/configuracoes_completas_v937.csv",
    "dados/scanner_tecnico_v934.json",
    "dados/autopilot_status_v107.json",
    "dados/news_nowcast_predictions_v1.csv",
    "dados/paper_trading_summary_v112.json",
    "dados/paper_setup_summary_v114.json",
    "dados/atlasquant_quota_shadow_v1.json",
    # Paper runtime paths are read through the generic _load_runtime_csv.
    # This default deny covers both current constants and future paths.
})


def legacy_private_remote_resource_allowed(resource_path: object) -> bool:
    """Never authorize unscoped legacy files; no source-to-tenant proof exists.

    A new durable resource-binding system must be specified, built, witnessed,
    and reviewed independently. Do not turn this into a policy env toggle.
    """
    return False


def require_legacy_private_remote_resource(resource_path: object) -> None:
    """Deny before token lookup, remote request, cached response or decode."""
    if not legacy_private_remote_resource_allowed(resource_path):
        raise PermissionError("TENANT_SOURCE_UNBOUND")
