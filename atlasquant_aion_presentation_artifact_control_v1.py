"""AION Presentation Artifact + Control Contract V1.

Pure validation/planning layer between an evidence-valid AION meeting deck and a
future PPTX generator/presenter.

The meeting orchestrator remains the source of truth for meeting state and slide
position. This module never creates a PPTX file, renders a chart, opens
PowerPoint, starts slideshow mode, sends keyboard events, calls a provider, or
mutates meeting state.
"""
from __future__ import annotations

from hashlib import sha256
import json
import re
from typing import Any, Mapping

from atlasquant_aion_teaching_meeting_orchestrator_v1 import (
    MEETING_DECK_SCHEMA,
    MEETING_SESSION_SCHEMA,
)


SCHEMA = "ATLASQUANT_AION_PRESENTATION_ARTIFACT_CONTROL_V1"
REQUEST_SCHEMA = "ATLASQUANT_AION_PRESENTATION_ARTIFACT_REQUEST_V1"
ATTESTATION_SCHEMA = "ATLASQUANT_AION_PRESENTATION_ARTIFACT_ATTESTATION_V1"
CONTROL_SCHEMA = "ATLASQUANT_AION_PRESENTATION_CONTROL_INTENT_V1"
POLICY_SCHEMA = "ATLASQUANT_AION_PRESENTATION_POLICY_V1"

OUTPUT_FORMAT = "PPTX"
TARGET_APPLICATION = "MICROSOFT_POWERPOINT"
ASPECT_RATIO = "16:9"
THEME_ID = "ATLASQUANT_FUTURISTIC_V1"

CONTROL_ACTIONS = (
    "OPEN_ARTIFACT",
    "START_PRESENTATION",
    "SYNC_TO_MEETING_SLIDE",
    "END_PRESENTATION",
)

_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def _clean(value: Any, limit: int = 600) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _identity(value: Any, limit: int = 200) -> str:
    if type(value) is not str:
        return ""
    if not value or len(value) > limit or "\x00" in value:
        return ""
    if " ".join(value.split()) != value:
        return ""
    return value


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=str,
    )


def _digest(value: Any) -> str:
    return "sha256:" + sha256(_canonical(value).encode("utf-8")).hexdigest()


def _sha256(value: Any) -> str:
    token = _clean(value, 90)
    return token if _SHA256_RE.fullmatch(token) else ""


def _deck_material(deck: Mapping[str, Any]) -> dict[str, Any]:
    raw = dict(deck)
    raw.pop("deck_digest", None)
    return raw


def _request_material(request: Mapping[str, Any]) -> dict[str, Any]:
    raw = dict(request)
    raw.pop("request_digest", None)
    return raw


def _verify_deck(deck: Mapping[str, Any] | None) -> tuple[dict[str, Any], list[str]]:
    raw = dict(deck or {})
    blockers: list[str] = []
    if raw.get("schema") != MEETING_DECK_SCHEMA:
        blockers.append("MEETING_DECK_SCHEMA_MISMATCH")
    if raw.get("state") != "READY" or raw.get("blockers"):
        blockers.append("READY_MEETING_DECK_REQUIRED")

    supplied = _sha256(raw.get("deck_digest"))
    expected = _digest(_deck_material(raw))
    if not supplied or supplied != expected:
        blockers.append("MEETING_DECK_DIGEST_MISMATCH")

    manifest = raw.get("slide_manifest")
    if not isinstance(manifest, list) or not manifest:
        blockers.append("SLIDE_MANIFEST_REQUIRED")
    else:
        for index, slide in enumerate(manifest, start=1):
            if not isinstance(slide, Mapping):
                blockers.append(f"SLIDE_INVALID:{index}")
                continue
            kind = _clean(slide.get("kind"), 60).upper()
            if kind == "CHART":
                if not slide.get("evidence_refs"):
                    blockers.append(f"CHART_EVIDENCE_REQUIRED:{index}")
                if not slide.get("data_refs"):
                    blockers.append(f"CHART_DATA_REQUIRED:{index}")
                if not slide.get("validation_refs"):
                    blockers.append(f"CHART_VALIDATION_REQUIRED:{index}")
            if kind in {"ROI", "CASE"} and not slide.get("evidence_refs"):
                blockers.append(f"METRIC_EVIDENCE_REQUIRED:{index}")

    return raw, list(dict.fromkeys(blockers))


def _chart_manifest(deck: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for slide in list(deck.get("slide_manifest") or []):
        if _clean(slide.get("kind"), 60).upper() != "CHART":
            continue
        row = {
            "slide_id": _clean(slide.get("slide_id"), 120),
            "slide_order": slide.get("order"),
            "data_refs": list(slide.get("data_refs") or []),
            "validation_refs": list(slide.get("validation_refs") or []),
            "evidence_refs": list(slide.get("evidence_refs") or []),
        }
        row["chart_source_digest"] = _digest(row)
        rows.append(row)
    return rows


def build_presentation_artifact_request(
    deck: Mapping[str, Any] | None,
    *,
    artifact_id: Any,
    include_speaker_notes: bool = True,
    theme_id: Any = THEME_ID,
    aspect_ratio: Any = ASPECT_RATIO,
) -> dict[str, Any]:
    """Build a deterministic PPTX generation request; no file is generated."""
    raw, blockers = _verify_deck(deck)

    artifact = _identity(artifact_id, 160)
    if not artifact:
        blockers.append("ARTIFACT_ID_REQUIRED")

    theme = _identity(theme_id, 120)
    ratio = _clean(aspect_ratio, 20)
    if not theme:
        blockers.append("THEME_ID_REQUIRED")
    if ratio != ASPECT_RATIO:
        blockers.append("ASPECT_RATIO_16_9_REQUIRED")

    chart_manifest = _chart_manifest(raw)
    manifest = list(raw.get("slide_manifest") or [])

    blockers = list(dict.fromkeys(blockers))
    request: dict[str, Any] = {
        "schema": REQUEST_SCHEMA,
        "state": "READY" if not blockers else "BLOCKED",
        "blockers": blockers,
        "artifact_id": artifact,
        "deck_digest": _sha256(raw.get("deck_digest")),
        "output_format": OUTPUT_FORMAT,
        "target_application": TARGET_APPLICATION,
        "theme_id": theme,
        "aspect_ratio": ratio,
        "include_speaker_notes": bool(include_speaker_notes),
        "slide_count": len(manifest),
        "slide_order": [
            _clean(row.get("slide_id"), 120)
            for row in manifest
            if isinstance(row, Mapping)
        ],
        "chart_manifest": chart_manifest,
        "chart_count": len(chart_manifest),
        "chart_data_lineage_required": True,
        "chart_validation_lineage_required": True,
        "metric_evidence_lineage_required": True,
        "macros_allowed": False,
        "vba_allowed": False,
        "external_links_allowed": False,
        "external_relationships_allowed": False,
        "embedded_ole_objects_allowed": False,
        "remote_fetch_during_presentation_allowed": False,
        "credentials_allowed": False,
        "real_customer_data_allowed": False,
        "artifact_file_created": False,
        "charts_rendered": False,
        "powerpoint_opened": False,
        "presentation_started": False,
        "provider_called": False,
        "network_called": False,
        "external_action_executed": False,
        "executes_action": False,
        "request_digest": "",
    }
    request["request_digest"] = _digest(_request_material(request))
    return request


def verify_presentation_artifact_request(
    request: Mapping[str, Any] | None,
) -> dict[str, Any]:
    raw = dict(request or {})
    blockers: list[str] = []
    if raw.get("schema") != REQUEST_SCHEMA:
        blockers.append("REQUEST_SCHEMA_MISMATCH")

    supplied = _sha256(raw.get("request_digest"))
    expected = _digest(_request_material(raw))
    if not supplied or supplied != expected:
        blockers.append("REQUEST_DIGEST_MISMATCH")

    if raw.get("state") != "READY" or raw.get("blockers"):
        blockers.append("READY_REQUEST_REQUIRED")
    if raw.get("output_format") != OUTPUT_FORMAT:
        blockers.append("PPTX_REQUIRED")
    if raw.get("target_application") != TARGET_APPLICATION:
        blockers.append("POWERPOINT_TARGET_REQUIRED")
    if raw.get("aspect_ratio") != ASPECT_RATIO:
        blockers.append("ASPECT_RATIO_MISMATCH")

    for key in (
        "macros_allowed",
        "vba_allowed",
        "external_links_allowed",
        "external_relationships_allowed",
        "embedded_ole_objects_allowed",
        "remote_fetch_during_presentation_allowed",
        "credentials_allowed",
        "real_customer_data_allowed",
        "artifact_file_created",
        "charts_rendered",
        "powerpoint_opened",
        "presentation_started",
        "provider_called",
        "network_called",
        "external_action_executed",
        "executes_action",
    ):
        if raw.get(key) is not False:
            blockers.append("REQUEST_BOUNDARY_INVALID:" + key)

    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": SCHEMA,
        "state": "VALID" if not blockers else "INVALID",
        "valid": not blockers,
        "blockers": blockers,
        "request_digest": supplied,
        "executes_action": False,
    }


def evaluate_generated_artifact_attestation(
    request: Mapping[str, Any] | None,
    attestation: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Validate future generated-PPTX evidence; does not inspect/create a file."""
    req = dict(request or {})
    request_check = verify_presentation_artifact_request(req)
    evidence = dict(attestation or {})
    blockers: list[str] = []

    if request_check.get("valid") is not True:
        blockers.append("VALID_PRESENTATION_REQUEST_REQUIRED")
    if evidence.get("schema") != ATTESTATION_SCHEMA:
        blockers.append("ATTESTATION_SCHEMA_MISMATCH")
    if evidence.get("verified") is not True:
        blockers.append("ATTESTATION_NOT_VERIFIED")
    if _clean(evidence.get("request_digest"), 90) != _clean(
        req.get("request_digest"), 90
    ):
        blockers.append("ATTESTATION_REQUEST_DIGEST_MISMATCH")

    artifact_digest = _sha256(evidence.get("artifact_digest"))
    if not artifact_digest:
        blockers.append("ARTIFACT_DIGEST_REQUIRED")
    artifact_ref = _identity(evidence.get("artifact_ref"), 240)
    if not artifact_ref:
        blockers.append("ARTIFACT_REF_REQUIRED")
    if _clean(evidence.get("format"), 20).upper() != OUTPUT_FORMAT:
        blockers.append("ARTIFACT_FORMAT_MISMATCH")
    if evidence.get("slide_count") != req.get("slide_count"):
        blockers.append("SLIDE_COUNT_MISMATCH")
    if evidence.get("slide_order_verified") is not True:
        blockers.append("SLIDE_ORDER_NOT_VERIFIED")
    if evidence.get("chart_lineage_verified") is not True:
        blockers.append("CHART_LINEAGE_NOT_VERIFIED")
    if evidence.get("metric_evidence_verified") is not True:
        blockers.append("METRIC_EVIDENCE_NOT_VERIFIED")
    if req.get("include_speaker_notes") is True and (
        evidence.get("speaker_notes_policy_verified") is not True
    ):
        blockers.append("SPEAKER_NOTES_POLICY_NOT_VERIFIED")

    forbidden_true = (
        "macros_present",
        "vba_project_present",
        "external_links_present",
        "external_relationships_present",
        "embedded_ole_objects_present",
        "remote_fetch_required",
        "credentials_present",
        "real_customer_data_present",
    )
    for key in forbidden_true:
        if evidence.get(key) is not False:
            blockers.append("ARTIFACT_FORBIDDEN_OR_UNVERIFIED:" + key)

    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": ATTESTATION_SCHEMA,
        "state": "VALID" if not blockers else "BLOCKED",
        "valid": not blockers,
        "blockers": blockers,
        "request_digest": _clean(req.get("request_digest"), 90),
        "artifact_ref": artifact_ref,
        "artifact_digest": artifact_digest,
        "artifact_opened_by_this_module": False,
        "artifact_generated_by_this_module": False,
        "powerpoint_started_by_this_module": False,
        "external_action_executed_by_this_module": False,
        "executes_action": False,
    }


def build_presentation_control_intent(
    meeting_session: Mapping[str, Any] | None,
    deck: Mapping[str, Any] | None,
    artifact_attestation_result: Mapping[str, Any] | None,
    *,
    action: Any,
) -> dict[str, Any]:
    """Bind a future PowerPoint control action to orchestrator state."""
    session = dict(meeting_session or {})
    raw_deck, deck_blockers = _verify_deck(deck)
    artifact = dict(artifact_attestation_result or {})
    blockers = list(deck_blockers)

    requested = _clean(action, 80).upper()
    if requested not in CONTROL_ACTIONS:
        blockers.append("CONTROL_ACTION_INVALID")
    if session.get("schema") != MEETING_SESSION_SCHEMA:
        blockers.append("MEETING_SESSION_SCHEMA_MISMATCH")
    if _clean(session.get("deck_digest"), 90) != _clean(
        raw_deck.get("deck_digest"), 90
    ):
        blockers.append("MEETING_SESSION_DECK_MISMATCH")
    if not _sha256(session.get("session_digest")):
        blockers.append("MEETING_SESSION_DIGEST_REQUIRED")
    if artifact.get("schema") != ATTESTATION_SCHEMA or artifact.get("valid") is not True:
        blockers.append("VALID_ARTIFACT_ATTESTATION_REQUIRED")

    state = _clean(session.get("state"), 60).upper()
    slide_index = session.get("current_slide_index")
    slide_id = _clean(session.get("current_slide_id"), 120)
    manifest = list(raw_deck.get("slide_manifest") or [])
    if (
        isinstance(slide_index, bool)
        or not isinstance(slide_index, int)
        or not (0 <= slide_index < len(manifest))
        or manifest[slide_index].get("slide_id") != slide_id
    ):
        blockers.append("MEETING_SLIDE_BINDING_INVALID")

    if requested == "START_PRESENTATION" and state not in {"IDLE", "PRESENTING"}:
        blockers.append("START_PRESENTATION_STATE_INVALID")
    if requested == "SYNC_TO_MEETING_SLIDE" and state not in {
        "PRESENTING",
        "PAUSED_FOR_QA",
        "RESUME_PENDING",
        "DEMO_PENDING",
        "DEMO_ACTIVE",
    }:
        blockers.append("SYNC_PRESENTATION_STATE_INVALID")
    if requested == "END_PRESENTATION" and state not in {
        "PRESENTING",
        "COMPLETED",
        "IDLE",
    }:
        blockers.append("END_PRESENTATION_STATE_INVALID")

    blockers = list(dict.fromkeys(blockers))
    material = {
        "action": requested,
        "artifact_digest": _sha256(artifact.get("artifact_digest")),
        "artifact_ref": _identity(artifact.get("artifact_ref"), 240),
        "deck_digest": _sha256(raw_deck.get("deck_digest")),
        "meeting_session_digest": _sha256(session.get("session_digest")),
        "meeting_state": state,
        "slide_id": slide_id,
        "slide_index": slide_index,
    }

    return {
        "schema": CONTROL_SCHEMA,
        "state": "READY" if not blockers else "BLOCKED",
        "blockers": blockers,
        **material,
        "control_intent_digest": _digest(material) if not blockers else "",
        "uses_meeting_orchestrator_as_source_of_truth": True,
        "keyboard_event_sent": False,
        "mouse_event_sent": False,
        "powerpoint_opened": False,
        "slideshow_started": False,
        "slide_changed_physically": False,
        "slideshow_ended_physically": False,
        "subprocess_called": False,
        "network_called": False,
        "external_action_executed": False,
        "executes_action": False,
    }


def presentation_policy() -> dict[str, Any]:
    return {
        "schema": POLICY_SCHEMA,
        "output_format": OUTPUT_FORMAT,
        "target_application": TARGET_APPLICATION,
        "aspect_ratio": ASPECT_RATIO,
        "theme_id": THEME_ID,
        "meeting_orchestrator_is_slide_source_of_truth": True,
        "chart_data_lineage_required": True,
        "chart_validation_lineage_required": True,
        "metric_evidence_lineage_required": True,
        "macros_allowed": False,
        "vba_allowed": False,
        "external_links_allowed": False,
        "external_relationships_allowed": False,
        "embedded_ole_objects_allowed": False,
        "remote_fetch_during_presentation_allowed": False,
        "credentials_allowed": False,
        "real_customer_data_allowed": False,
        "artifact_file_created": False,
        "charts_rendered": False,
        "powerpoint_opened": False,
        "presentation_started": False,
        "keyboard_event_sent": False,
        "mouse_event_sent": False,
        "subprocess_called": False,
        "provider_called": False,
        "network_called": False,
        "worker_armed": False,
        "deploy_executed": False,
        "core_checkpoint_write": False,
        "external_action_executed": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "REQUEST_SCHEMA",
    "ATTESTATION_SCHEMA",
    "CONTROL_SCHEMA",
    "POLICY_SCHEMA",
    "OUTPUT_FORMAT",
    "TARGET_APPLICATION",
    "ASPECT_RATIO",
    "THEME_ID",
    "CONTROL_ACTIONS",
    "build_presentation_artifact_request",
    "verify_presentation_artifact_request",
    "evaluate_generated_artifact_attestation",
    "build_presentation_control_intent",
    "presentation_policy",
]
