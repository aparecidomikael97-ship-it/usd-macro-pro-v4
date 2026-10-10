"""Autopilot evidence: fail closed until externally durable claim is verified.

No production verifier or shared claim ledger exists. An in-process lock cannot
protect writes across GitHub Actions runs, process restart, hosts, or rollback.
Deliberately never invoke writers: there is NO test flag or fallback override.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any


def guarded_autopilot_evidence_write(
    *,
    repo: str,
    branch: str,
    sink: str,
    write: Callable[[], Mapping[str, Any]],
) -> dict[str, Any]:
    """Reject all Shadow/Flight writes until a real external durable gate exists.

    This function MUST NOT infer an authorization from a session cache,
    ALREADY_PRESENT, HTTP 200/201, or the one-process predecessor guard.
    The previous write may be uncertain, so new calls remain blocked.
    """
    key = (str(repo).strip(), str(branch).strip(), str(sink).strip())
    valid = all(key) and key[2] in ("shadow", "flight")
    return {
        "ok": False,
        "state": "HARD_DENY",
        "sink": key[2] if key[2] in ("shadow", "flight") else "UNKNOWN",
        "execution_authorized": False,
        "reason": "DURABLE_CLAIM_REQUIRED" if valid else "INVALID_SINK_IDENTITY",
        "error": "",
        "write_outcome": "NOT_ATTEMPTED_BY_THIS_GUARD",
        "write_attempted": False,
        "reconciliation_required": True,
        "safe_to_retry": False,
        "verified": False,
        "remote_durability_certified": False,
        "durable_admission_verified": False,
        "external_writer_called": False,
    }


__all__ = ["guarded_autopilot_evidence_write"]
