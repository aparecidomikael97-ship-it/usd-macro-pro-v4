"""Explicit bridge to the existing checkpoint; no legacy writer/import side effects."""
from copy import deepcopy
from .context import Context
from .evidence import Origin, safe_text


CHECKPOINT_NAMESPACE = "aion_core_intelligence_v1"


def attach_checkpoint(legacy_checkpoint: dict, core_checkpoint: dict, context: Context) -> dict:
    """Return an export proposal. The caller's existing persistence gate owns saving.

    This deliberately cannot merge other task contexts or restore approval state.
    """
    if core_checkpoint.get("schema") != "AION_CORE_CHECKPOINT_V1":
        raise ValueError("invalid core checkpoint export")
    import json
    if core_checkpoint.get("scope") != json.loads(context.key):
        raise ValueError("checkpoint context mismatch")
    out = deepcopy(legacy_checkpoint)
    previous = out.get(CHECKPOINT_NAMESPACE)
    if previous is not None and previous.get("scope") != core_checkpoint["scope"]:
        raise ValueError("explicit cross-context checkpoint merge required")
    out[CHECKPOINT_NAMESPACE] = deepcopy(core_checkpoint)
    return out


def propose_legacy_memory(text: str, source_ref: str) -> dict:
    """Legacy CONFIRMED/approved flags cannot mint a human approval receipt."""
    return {"text": safe_text(text), "source_ref": safe_text(source_ref, 500),
            "origin": Origin.UNKNOWN.value, "approval_required": True,
            "persisted": False, "reason": "Legacy information needs explicit provenance review."}
