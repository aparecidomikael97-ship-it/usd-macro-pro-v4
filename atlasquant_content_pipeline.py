"""Provider-neutral, approval-only content and voice pipeline contracts."""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

SCHEMA = "ATLASQUANT_CONTENT_PIPELINE_V1"
STAGES = (
    "AUTHORIZED_INPUT", "TRANSCRIPTION", "CLIP_DETECTION", "SCRIPT",
    "CAPTIONS", "REFORMAT", "THUMBNAIL", "METADATA", "HUMAN_APPROVAL",
    "PUBLICATION",
)
PLATFORM_VARIANTS = (
    ("YouTube", "16:9", "horizontal"),
    ("Instagram", "9:16", "vertical"),
    ("TikTok", "9:16", "vertical"),
    ("Shorts/Reels", "9:16", "vertical"),
)
RIGHTS_STATES = ("VERIFIED", "REVIEW_REQUIRED", "UNKNOWN", "BLOCKED")


def provider_readiness(
    *,
    transcription: bool = False,
    video_render: bool = False,
    image: bool = False,
    aion_voice: bool = False,
    mikael_voice: bool = False,
    mikael_consent: bool = False,
) -> dict[str, Any]:
    rows = {
        "transcription": bool(transcription),
        "video_render": bool(video_render),
        "image": bool(image),
        "aion_voice": bool(aion_voice),
        "mikael_voice": bool(mikael_voice and mikael_consent),
    }
    return {
        "schema": SCHEMA,
        "providers": {
            name: {"state": "CONFIGURED" if ready else "NOT_CONFIGURED"}
            for name, ready in rows.items()
        },
        "mikael_voice_consent_confirmed": bool(mikael_consent),
        "publishing_configured": False,
        "executes_external_call": False,
    }


def content_job(
    title: object,
    *,
    source_reference: object = "",
    rights_state: object = "UNKNOWN",
    formats: Sequence[str] | None = None,
) -> dict[str, Any]:
    name = str(title or "").strip()[:200]
    if not name:
        raise ValueError("title is required")
    rights = str(rights_state or "UNKNOWN").strip().upper()
    if rights not in RIGHTS_STATES:
        rights = "UNKNOWN"
    selected = set(str(x) for x in list(formats or []))
    variants = [{
        "platform": platform,
        "ratio": ratio,
        "orientation": orientation,
        "state": "DRAFT_NOT_RENDERED",
    } for platform, ratio, orientation in PLATFORM_VARIANTS if not selected or platform in selected]
    identity = json.dumps([name, str(source_reference), rights, variants], sort_keys=True)
    rights_ok = rights == "VERIFIED"
    return {
        "schema": SCHEMA,
        "job_id": "CONTENT-" + sha256(identity.encode("utf-8")).hexdigest()[:12],
        "title": name,
        "source_reference": str(source_reference or "").strip()[:500],
        "rights_state": rights,
        "rights_review_required": not rights_ok,
        "stages": [{
            "stage": stage,
            "state": (
                "READY_FOR_PROVIDER" if stage in {"TRANSCRIPTION", "CLIP_DETECTION", "SCRIPT", "CAPTIONS", "REFORMAT", "THUMBNAIL", "METADATA"} and rights_ok
                else "WAITING_HUMAN" if stage == "HUMAN_APPROVAL"
                else "BLOCKED" if stage == "PUBLICATION" or not rights_ok
                else "CONFIRMED"
            ),
        } for stage in STAGES],
        "variants": variants,
        "automatic_download": False,
        "automatic_publication": False,
        "paid_action": False,
    }


def approval_preflight(
    job: Mapping[str, Any] | None,
    *,
    human_approved: bool = False,
) -> dict[str, Any]:
    item = dict(job or {})
    if item.get("rights_state") != "VERIFIED":
        return {"allowed": False, "reason": "Direitos de uso não verificados.", "publishes": False}
    if not human_approved:
        return {"allowed": False, "reason": "Aprovação humana obrigatória.", "publishes": False}
    return {
        "allowed": True,
        "reason": "Conteúdo pode entrar na fila de conector; publicação não ocorre aqui.",
        "publishes": False,
    }


__all__ = [
    "PLATFORM_VARIANTS",
    "RIGHTS_STATES",
    "SCHEMA",
    "STAGES",
    "approval_preflight",
    "content_job",
    "provider_readiness",
]
