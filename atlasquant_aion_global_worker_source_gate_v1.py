"""Production Global Worker checkpoint source trust boundary (#1178).

No independently enrolled source identity or monotonic witness is configured.
A runtime GitHub SHA, token, branch, session, cached content, role, and a
caller-supplied signed envelope do not establish trusted source ownership.

Until an independent trust provider is enrolled and physically reviewed this
boundary deliberately has NO permissive path, environment flag, self-enrollment,
or admin override. Do not connect the offline cryptographic reference as an
authority by accepting arbitrary caller-provided pins or floors.
"""
from __future__ import annotations

from typing import Any

SOURCE_GATE_SCHEMA = "AION_GLOBAL_WORKER_SOURCE_TRUST_GATE_V1"


def independent_worker_source_preflight(config: Any) -> dict[str, Any]:
    """Always deny before a checkpoint GET, CAS claim, or task execution."""
    return {
        "schema": SOURCE_GATE_SCHEMA,
        "status": "BLOCKED",
        "reason": "INDEPENDENT_CHECKPOINT_SOURCE_UNAVAILABLE",
        "source_verified": False,
        "worker_authorized": False,
        "network_called": False,
        "reconciliation_required": True,
        "safe_to_retry": False,
    }
