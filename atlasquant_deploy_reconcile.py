"""Deployment reconciliation token for AtlasQuant production.

This module has no runtime side effects and is intentionally not imported by the
application. Its presence changes the deterministic source-bundle fingerprint
and gives Render's checksPass auto-deploy flow a real Python-source change to
publish when production is known to be serving an older bundle.
"""

RECONCILIATION_ID = "2026-09-24-production-identity-v1"

__all__ = ["RECONCILIATION_ID"]
