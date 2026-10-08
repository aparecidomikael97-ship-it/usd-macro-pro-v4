"""AION Teaching + Meeting Orchestrator V1.

Pure orchestration contracts for:
- adaptive teaching sessions with slides, exercises and Q&A pause/resume;
- client/internal meetings with evidence-bound decks, Q&A and sandbox demos.

This module never creates a PowerPoint file, renders a chart, starts a
presentation, opens a browser, runs a demo, calls a provider, records a
microphone, writes memory, or performs an external action.

It reuses Owner Experience V1 as the interaction-mode foundation and keeps
"plan/transition ready" strictly separate from physical execution.
"""
from __future__ import annotations

from hashlib import sha256
import json
import re
from typing import Any, Mapping, Sequence

from atlasquant_aion_owner_experience_v1 import (
    interaction_mode_plan,
    meeting_transition,
)


SCHEMA = "ATLASQUANT_AION_TEACHING_MEETING_ORCHESTRATOR_V1"
TEACHING_PROGRAM_SCHEMA = "ATLASQUANT_AION_TEACHING_PROGRAM_V1"
TEACHING_SESSION_SCHEMA = "ATLASQUANT_AION_TEACHING_SESSION_V1"
MEETING_DECK_SCHEMA = "ATLASQUANT_AION_MEETING_DECK_V1"
MEETING_SESSION_SCHEMA = "ATLASQUANT_AION_MEETING_SESSION_V1"
DEMO_PLAN_SCHEMA = "ATLASQUANT_AION_MEETING_DEMO_PLAN_V1"
HANDOFF_SCHEMA = "ATLASQUANT_AION_ORCHESTRATOR_HANDOFF_V1"
POLICY_SCHEMA = "ATLASQUANT_AION_TEACHING_MEETING_POLICY_V1"

TEACHING_LEVELS = ("BEGINNER", "INTERMEDIATE", "ADVANCED")
TEACHING_STATES = (
    "TEACHING",
    "PAUSED_FOR_QA",
    "RESUME_PENDING",
    "EXERCISE",
    "FEEDBACK",
    "COMPLETED",
)
TEACHING_EVENTS = (
    "NEXT_SLIDE",
    "PREVIOUS_SLIDE",
    "QUESTION",
    "ANSWERED",
    "RESUME",
    "START_EXERCISE",
    "SUBMIT_EXERCISE",
    "FEEDBACK_DONE",
    "COMPLETE",
)

MEETING_STATES = (
    "IDLE",
    "PRESENTING",
    "PAUSED_FOR_QA",
    "RESUME_PENDING",
    "DEMO_PENDING",
    "DEMO_ACTIVE",
    "COMPLETED",
)
MEETING_EVENTS = (
    "START",
    "NEXT_SLIDE",
    "PREVIOUS_SLIDE",
    "QUESTION",
    "ANSWERED",
    "RESUME",
    "DEMO_REQUEST",
    "DEMO_START",
    "DEMO_END",
    "COMPLETE",
    "STOP",
)

TEACHING_SLIDE_KINDS = (
    "TITLE",
    "OBJECTIVES",
    "CONCEPT",
    "DIAGRAM",
    "EXAMPLE",
    "WORKED_EXAMPLE",
    "EXERCISE",
    "RECAP",
)
MEETING_SLIDE_KINDS = (
    "TITLE",
    "AGENDA",
    "CONTEXT",
    "PROBLEM",
    "SOLUTION",
    "ARCHITECTURE",
    "CHART",
    "ROI",
    "CASE",
    "DEMO",
    "ROADMAP",
    "Q_AND_A",
    "NEXT_STEPS",
)

EVIDENCE_REQUIRED_MEETING_KINDS = frozenset({"CHART", "ROI", "CASE"})
DEMO_ENVIRONMENT = "SYNTHETIC_SANDBOX"
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def _clean(value: Any, limit: int = 600) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _identity(value: Any, limit: int = 160) -> str:
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


def _text_digest(value: Any) -> str:
    return "sha256:" + sha256(_clean(value, 4000).encode("utf-8")).hexdigest()


def _refs(value: Any, *, limit: int = 20) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    out: list[str] = []
    for item in value:
        text = _identity(item, 240)
        if text and text not in out:
            out.append(text)
        if len(out) >= limit:
            break
    return out


def _owner_binding_digest(value: Any) -> str:
    token = _clean(value, 100)
    return token if _SHA256_RE.fullmatch(token) else ""


def _manifest_rows(
    rows: Sequence[Mapping[str, Any]] | None,
    *,
    allowed_kinds: Sequence[str],
    evidence_required_kinds: frozenset[str] = frozenset(),
) -> tuple[list[dict[str, Any]], list[str]]:
    blockers: list[str] = []
    manifest: list[dict[str, Any]] = []
    source = list(rows or [])
    if not source:
        return [], ["SLIDE_MANIFEST_REQUIRED"]

    seen_ids: set[str] = set()
    for index, raw in enumerate(source, start=1):
        if not isinstance(raw, Mapping):
            blockers.append(f"SLIDE_INVALID:{index}")
            continue
        slide_id = _identity(raw.get("slide_id"), 120)
        title = _clean(raw.get("title"), 240)
        kind = _clean(raw.get("kind"), 60).upper()
        objective = _clean(raw.get("objective"), 400)
        content_ref = _identity(raw.get("content_ref"), 300)
        evidence_refs = _refs(raw.get("evidence_refs"), limit=20)
        data_refs = _refs(raw.get("data_refs"), limit=20)
        validation_refs = _refs(raw.get("validation_refs"), limit=20)

        if not slide_id:
            blockers.append(f"SLIDE_ID_REQUIRED:{index}")
        elif slide_id in seen_ids:
            blockers.append(f"DUPLICATE_SLIDE_ID:{slide_id}")
        else:
            seen_ids.add(slide_id)
        if not title:
            blockers.append(f"SLIDE_TITLE_REQUIRED:{index}")
        if kind not in allowed_kinds:
            blockers.append(f"SLIDE_KIND_INVALID:{index}")
        if not objective:
            blockers.append(f"SLIDE_OBJECTIVE_REQUIRED:{index}")
        if kind in evidence_required_kinds and not evidence_refs:
            blockers.append(f"EVIDENCE_REQUIRED_FOR_SLIDE:{slide_id or index}")
        if kind == "CHART":
            if not data_refs:
                blockers.append(f"CHART_DATA_REF_REQUIRED:{slide_id or index}")
            if not validation_refs:
                blockers.append(
                    f"CHART_VALIDATION_REF_REQUIRED:{slide_id or index}"
                )

        manifest.append(
            {
                "order": index,
                "slide_id": slide_id,
                "title": title,
                "kind": kind,
                "objective": objective,
                "content_ref": content_ref,
                "evidence_refs": evidence_refs,
                "data_refs": data_refs,
                "validation_refs": validation_refs,
            }
        )
    return manifest, list(dict.fromkeys(blockers))


def _slide_index(manifest: Sequence[Mapping[str, Any]], slide_id: Any) -> int:
    wanted = _clean(slide_id, 120)
    for index, row in enumerate(manifest):
        if _clean(row.get("slide_id"), 120) == wanted:
            return index
    return -1


def _session_material(session: Mapping[str, Any]) -> dict[str, Any]:
    raw = dict(session)
    raw.pop("session_digest", None)
    return raw


def _finalize_session(session: dict[str, Any]) -> dict[str, Any]:
    session["session_digest"] = _digest(_session_material(session))
    return session


def _verify_session_digest(
    session: Mapping[str, Any],
    *,
    schema: str,
) -> list[str]:
    blockers: list[str] = []
    if session.get("schema") != schema:
        blockers.append("SESSION_SCHEMA_MISMATCH")
    supplied = _sha256(session.get("session_digest"))
    expected = _digest(_session_material(session))
    if not supplied or supplied != expected:
        blockers.append("SESSION_DIGEST_MISMATCH")
    return blockers


def build_teaching_program(
    *,
    topic: Any,
    level: Any,
    learning_objectives: Sequence[Any] | None,
    slides: Sequence[Mapping[str, Any]] | None,
    exercises: Sequence[Mapping[str, Any]] | None = None,
    learner_profile_ref: Any = "",
) -> dict[str, Any]:
    """Build an evidence-free educational program manifest; no content is rendered."""
    mode = interaction_mode_plan("TEACHING", topic=topic)
    blockers: list[str] = []

    topic_text = _clean(topic, 240)
    level_text = _clean(level, 40).upper()
    if not topic_text:
        blockers.append("TOPIC_REQUIRED")
    if level_text not in TEACHING_LEVELS:
        blockers.append("TEACHING_LEVEL_INVALID")

    objectives = []
    for item in list(learning_objectives or []):
        text = _clean(item, 400)
        if text and text not in objectives:
            objectives.append(text)
        if len(objectives) >= 12:
            break
    if not objectives:
        blockers.append("LEARNING_OBJECTIVES_REQUIRED")

    slide_manifest, slide_blockers = _manifest_rows(
        slides,
        allowed_kinds=TEACHING_SLIDE_KINDS,
    )
    blockers.extend(slide_blockers)
    slide_ids = {
        _clean(row.get("slide_id"), 120)
        for row in slide_manifest
        if _clean(row.get("slide_id"), 120)
    }

    exercise_manifest: list[dict[str, Any]] = []
    seen_exercises: set[str] = set()
    for index, raw in enumerate(list(exercises or []), start=1):
        if not isinstance(raw, Mapping):
            blockers.append(f"EXERCISE_INVALID:{index}")
            continue
        exercise_id = _identity(raw.get("exercise_id"), 120)
        slide_id = _identity(raw.get("slide_id"), 120)
        objective = _clean(raw.get("objective"), 400)
        prompt_ref = _identity(raw.get("prompt_ref"), 300)
        evaluation_ref = _identity(raw.get("evaluation_ref"), 300)
        if not exercise_id:
            blockers.append(f"EXERCISE_ID_REQUIRED:{index}")
        elif exercise_id in seen_exercises:
            blockers.append(f"DUPLICATE_EXERCISE_ID:{exercise_id}")
        else:
            seen_exercises.add(exercise_id)
        if slide_id not in slide_ids:
            blockers.append(f"EXERCISE_SLIDE_NOT_FOUND:{exercise_id or index}")
        if not objective:
            blockers.append(f"EXERCISE_OBJECTIVE_REQUIRED:{exercise_id or index}")
        if not prompt_ref:
            blockers.append(f"EXERCISE_PROMPT_REF_REQUIRED:{exercise_id or index}")
        exercise_manifest.append(
            {
                "exercise_id": exercise_id,
                "slide_id": slide_id,
                "objective": objective,
                "prompt_ref": prompt_ref,
                "evaluation_ref": evaluation_ref,
            }
        )

    blockers = list(dict.fromkeys(blockers))
    program: dict[str, Any] = {
        "schema": TEACHING_PROGRAM_SCHEMA,
        "state": "READY" if not blockers else "BLOCKED",
        "blockers": blockers,
        "mode": mode["mode"],
        "topic": topic_text,
        "level": level_text,
        "learning_objectives": objectives,
        "learner_profile_ref": _identity(learner_profile_ref, 240),
        "voice_style": mode.get("voice_style"),
        "adaptive_depth": mode.get("adaptive_depth") is True,
        "slides_enabled": mode.get("slides") is True,
        "drawings_enabled": mode.get("drawings") is True,
        "exercises_enabled": mode.get("exercises") is True,
        "slide_manifest": slide_manifest,
        "exercise_manifest": exercise_manifest,
        "slide_count": len(slide_manifest),
        "exercise_count": len(exercise_manifest),
        "raw_memory_written": False,
        "memory_promoted": False,
        "provider_called": False,
        "slides_rendered": False,
        "audio_played": False,
        "executes_action": False,
        "program_digest": "",
    }
    material = dict(program)
    material.pop("program_digest", None)
    program["program_digest"] = _digest(material)
    return program


def start_teaching_session(
    program: Mapping[str, Any] | None,
    *,
    session_id: Any,
    owner_binding_digest: Any,
) -> dict[str, Any]:
    raw = dict(program or {})
    blockers: list[str] = []
    if raw.get("schema") != TEACHING_PROGRAM_SCHEMA:
        blockers.append("TEACHING_PROGRAM_SCHEMA_MISMATCH")
    if raw.get("state") != "READY" or raw.get("blockers"):
        blockers.append("READY_TEACHING_PROGRAM_REQUIRED")

    session = _identity(session_id, 160)
    owner_digest = _owner_binding_digest(owner_binding_digest)
    if not session:
        blockers.append("SESSION_ID_REQUIRED")
    if not owner_digest:
        blockers.append("OWNER_BINDING_DIGEST_REQUIRED")

    manifest = list(raw.get("slide_manifest") or [])
    if not manifest:
        blockers.append("TEACHING_SLIDES_REQUIRED")
        first_slide = ""
    else:
        first_slide = _clean(manifest[0].get("slide_id"), 120)

    blockers = list(dict.fromkeys(blockers))
    result = {
        "schema": TEACHING_SESSION_SCHEMA,
        "state": "TEACHING" if not blockers else "BLOCKED",
        "blockers": blockers,
        "session_id": session,
        "owner_binding_digest": owner_digest,
        "program_digest": _clean(raw.get("program_digest"), 90),
        "current_slide_id": first_slide if not blockers else "",
        "current_slide_index": 0 if not blockers else -1,
        "return_slide_id": "",
        "return_slide_index": -1,
        "active_question_digest": "",
        "active_exercise_id": "",
        "last_answer_digest": "",
        "last_evaluation_digest": "",
        "slides_presented_physically": False,
        "provider_called": False,
        "memory_written": False,
        "checkpoint_written": False,
        "external_action_executed": False,
        "executes_action": False,
        "session_digest": "",
    }
    return _finalize_session(result)


def advance_teaching_session(
    session: Mapping[str, Any] | None,
    program: Mapping[str, Any] | None,
    *,
    event: Any,
    question: Any = "",
    exercise_id: Any = "",
    answer_digest: Any = "",
    evaluation: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    current = dict(session or {})
    raw_program = dict(program or {})
    blockers = _verify_session_digest(current, schema=TEACHING_SESSION_SCHEMA)

    if raw_program.get("schema") != TEACHING_PROGRAM_SCHEMA:
        blockers.append("TEACHING_PROGRAM_SCHEMA_MISMATCH")
    if _clean(current.get("program_digest"), 90) != _clean(
        raw_program.get("program_digest"), 90
    ):
        blockers.append("TEACHING_PROGRAM_DIGEST_MISMATCH")

    action = _clean(event, 60).upper()
    if action not in TEACHING_EVENTS:
        blockers.append("TEACHING_EVENT_INVALID")

    state = _clean(current.get("state"), 60).upper()
    if state not in TEACHING_STATES:
        blockers.append("TEACHING_STATE_INVALID")

    manifest = list(raw_program.get("slide_manifest") or [])
    index = int(current.get("current_slide_index", -1))
    if not (0 <= index < len(manifest)):
        blockers.append("CURRENT_SLIDE_INDEX_INVALID")

    if blockers:
        blocked = dict(current)
        blocked["blockers"] = list(dict.fromkeys(blockers))
        blocked["transition_state"] = "BLOCKED"
        blocked["session_digest"] = ""
        return _finalize_session(blocked)

    next_session = dict(current)
    next_session["blockers"] = []
    next_session["transition_state"] = "TRANSITIONED"

    if action == "NEXT_SLIDE":
        if state != "TEACHING":
            blockers.append("NEXT_SLIDE_REQUIRES_TEACHING_STATE")
        elif index + 1 >= len(manifest):
            next_session["state"] = "COMPLETED"
        else:
            index += 1
            next_session["current_slide_index"] = index
            next_session["current_slide_id"] = manifest[index]["slide_id"]

    elif action == "PREVIOUS_SLIDE":
        if state != "TEACHING":
            blockers.append("PREVIOUS_SLIDE_REQUIRES_TEACHING_STATE")
        elif index <= 0:
            blockers.append("ALREADY_AT_FIRST_SLIDE")
        else:
            index -= 1
            next_session["current_slide_index"] = index
            next_session["current_slide_id"] = manifest[index]["slide_id"]

    elif action == "QUESTION":
        if state != "TEACHING":
            blockers.append("QUESTION_REQUIRES_TEACHING_STATE")
        elif not _clean(question, 1200):
            blockers.append("QUESTION_REQUIRED")
        else:
            next_session["state"] = "PAUSED_FOR_QA"
            next_session["return_slide_id"] = current["current_slide_id"]
            next_session["return_slide_index"] = current["current_slide_index"]
            next_session["active_question_digest"] = _text_digest(question)

    elif action == "ANSWERED":
        if state != "PAUSED_FOR_QA":
            blockers.append("ANSWERED_REQUIRES_PAUSED_QA_STATE")
        else:
            next_session["state"] = "RESUME_PENDING"

    elif action == "RESUME":
        if state != "RESUME_PENDING":
            blockers.append("RESUME_REQUIRES_RESUME_PENDING_STATE")
        else:
            return_index = int(current.get("return_slide_index", -1))
            return_id = _clean(current.get("return_slide_id"), 120)
            if not (
                0 <= return_index < len(manifest)
                and manifest[return_index].get("slide_id") == return_id
            ):
                blockers.append("RETURN_SLIDE_BINDING_INVALID")
            else:
                next_session["state"] = "TEACHING"
                next_session["current_slide_index"] = return_index
                next_session["current_slide_id"] = return_id
                next_session["return_slide_id"] = ""
                next_session["return_slide_index"] = -1
                next_session["active_question_digest"] = ""

    elif action == "START_EXERCISE":
        if state != "TEACHING":
            blockers.append("EXERCISE_REQUIRES_TEACHING_STATE")
        else:
            wanted = _identity(exercise_id, 120)
            match = next(
                (
                    row
                    for row in list(raw_program.get("exercise_manifest") or [])
                    if row.get("exercise_id") == wanted
                ),
                None,
            )
            if match is None:
                blockers.append("EXERCISE_NOT_FOUND")
            elif match.get("slide_id") != current.get("current_slide_id"):
                blockers.append("EXERCISE_NOT_BOUND_TO_CURRENT_SLIDE")
            else:
                next_session["state"] = "EXERCISE"
                next_session["active_exercise_id"] = wanted

    elif action == "SUBMIT_EXERCISE":
        if state != "EXERCISE":
            blockers.append("SUBMIT_REQUIRES_EXERCISE_STATE")
        else:
            supplied_answer = _sha256(answer_digest)
            evaluation_raw = dict(evaluation or {})
            evaluation_digest = _sha256(evaluation_raw.get("evaluation_digest"))
            if not supplied_answer:
                blockers.append("ANSWER_DIGEST_REQUIRED")
            if evaluation_raw.get("verified") is not True:
                blockers.append("VERIFIED_EVALUATION_REQUIRED")
            if evaluation_raw.get("exercise_id") != current.get(
                "active_exercise_id"
            ):
                blockers.append("EVALUATION_EXERCISE_MISMATCH")
            if not evaluation_digest:
                blockers.append("EVALUATION_DIGEST_REQUIRED")
            if not blockers:
                next_session["state"] = "FEEDBACK"
                next_session["last_answer_digest"] = supplied_answer
                next_session["last_evaluation_digest"] = evaluation_digest

    elif action == "FEEDBACK_DONE":
        if state != "FEEDBACK":
            blockers.append("FEEDBACK_DONE_REQUIRES_FEEDBACK_STATE")
        else:
            next_session["state"] = "TEACHING"
            next_session["active_exercise_id"] = ""

    elif action == "COMPLETE":
        if state not in {"TEACHING", "FEEDBACK"}:
            blockers.append("COMPLETE_STATE_INVALID")
        else:
            next_session["state"] = "COMPLETED"

    if blockers:
        blocked = dict(current)
        blocked["blockers"] = list(dict.fromkeys(blockers))
        blocked["transition_state"] = "BLOCKED"
        blocked["session_digest"] = ""
        return _finalize_session(blocked)

    next_session["raw_question_persisted"] = False
    next_session["raw_answer_persisted"] = False
    next_session["slides_presented_physically"] = False
    next_session["provider_called"] = False
    next_session["memory_written"] = False
    next_session["checkpoint_written"] = False
    next_session["external_action_executed"] = False
    next_session["executes_action"] = False
    next_session["session_digest"] = ""
    return _finalize_session(next_session)


def build_meeting_deck(
    *,
    sector: Any,
    audience: Any,
    objective: Any,
    slides: Sequence[Mapping[str, Any]] | None,
    client_ref: Any = "",
) -> dict[str, Any]:
    """Build an evidence-bound meeting deck manifest without rendering slides."""
    mode = interaction_mode_plan("MEETING", sector=sector)
    blockers: list[str] = []

    sector_text = _clean(sector, 160)
    audience_text = _clean(audience, 240)
    objective_text = _clean(objective, 400)
    if not sector_text:
        blockers.append("SECTOR_REQUIRED")
    if not audience_text:
        blockers.append("AUDIENCE_REQUIRED")
    if not objective_text:
        blockers.append("MEETING_OBJECTIVE_REQUIRED")

    slide_manifest, slide_blockers = _manifest_rows(
        slides,
        allowed_kinds=MEETING_SLIDE_KINDS,
        evidence_required_kinds=EVIDENCE_REQUIRED_MEETING_KINDS,
    )
    blockers.extend(slide_blockers)

    blockers = list(dict.fromkeys(blockers))
    deck: dict[str, Any] = {
        "schema": MEETING_DECK_SCHEMA,
        "state": "READY" if not blockers else "BLOCKED",
        "blockers": blockers,
        "mode": mode["mode"],
        "sector": sector_text,
        "audience": audience_text,
        "objective": objective_text,
        "client_ref": _identity(client_ref, 240),
        "slide_manifest": slide_manifest,
        "slide_count": len(slide_manifest),
        "pause_for_questions": mode.get("pause_for_questions") is True,
        "resume_to_prior_slide": mode.get("resume_to_prior_slide") is True,
        "live_demo_supported": mode.get("live_demo_supported") is True,
        "evidence_required_for_metrics": True,
        "charts_require_data_and_validation_refs": True,
        "synthetic_sandbox_required_for_demo": True,
        "powerpoint_created": False,
        "charts_rendered": False,
        "presentation_started": False,
        "provider_called": False,
        "external_action_executed": False,
        "executes_action": False,
        "deck_digest": "",
    }
    material = dict(deck)
    material.pop("deck_digest", None)
    deck["deck_digest"] = _digest(material)
    return deck


def start_meeting_session(
    deck: Mapping[str, Any] | None,
    *,
    meeting_id: Any,
    owner_binding_digest: Any,
) -> dict[str, Any]:
    raw = dict(deck or {})
    blockers: list[str] = []
    if raw.get("schema") != MEETING_DECK_SCHEMA:
        blockers.append("MEETING_DECK_SCHEMA_MISMATCH")
    if raw.get("state") != "READY" or raw.get("blockers"):
        blockers.append("READY_MEETING_DECK_REQUIRED")

    meeting = _identity(meeting_id, 160)
    owner_digest = _owner_binding_digest(owner_binding_digest)
    if not meeting:
        blockers.append("MEETING_ID_REQUIRED")
    if not owner_digest:
        blockers.append("OWNER_BINDING_DIGEST_REQUIRED")

    manifest = list(raw.get("slide_manifest") or [])
    first_slide = _clean(manifest[0].get("slide_id"), 120) if manifest else ""
    if not first_slide:
        blockers.append("MEETING_SLIDES_REQUIRED")

    blockers = list(dict.fromkeys(blockers))
    result = {
        "schema": MEETING_SESSION_SCHEMA,
        "state": "IDLE" if not blockers else "BLOCKED",
        "blockers": blockers,
        "meeting_id": meeting,
        "owner_binding_digest": owner_digest,
        "deck_digest": _clean(raw.get("deck_digest"), 90),
        "current_slide_id": first_slide if not blockers else "",
        "current_slide_index": 0 if not blockers else -1,
        "return_slide_id": "",
        "return_slide_index": -1,
        "active_question_digest": "",
        "active_demo_plan_digest": "",
        "slides_presented_physically": False,
        "powerpoint_started": False,
        "demo_started_physically": False,
        "provider_called": False,
        "external_action_executed": False,
        "executes_action": False,
        "session_digest": "",
    }
    return _finalize_session(result)


def build_live_demo_plan(
    *,
    demo_script_ref: Any,
    sandbox_digest: Any,
    sandbox_attested: bool,
    production_tenant_access: bool,
    real_customer_data: bool,
    credentials_present: bool,
    external_side_effects_possible: bool,
    payments_enabled: bool,
    trading_enabled: bool,
    publication_enabled: bool,
    message_send_enabled: bool,
    environment: Any = DEMO_ENVIRONMENT,
) -> dict[str, Any]:
    blockers: list[str] = []
    env = _clean(environment, 80).upper()
    script_ref = _identity(demo_script_ref, 320)
    sandbox = _sha256(sandbox_digest)

    if env != DEMO_ENVIRONMENT:
        blockers.append("SYNTHETIC_SANDBOX_REQUIRED")
    if not script_ref:
        blockers.append("DEMO_SCRIPT_REF_REQUIRED")
    if not sandbox:
        blockers.append("SANDBOX_DIGEST_REQUIRED")
    if sandbox_attested is not True:
        blockers.append("SANDBOX_ATTESTATION_REQUIRED")

    forbidden_true = {
        "PRODUCTION_TENANT_ACCESS": production_tenant_access,
        "REAL_CUSTOMER_DATA": real_customer_data,
        "CREDENTIALS_PRESENT": credentials_present,
        "EXTERNAL_SIDE_EFFECTS_POSSIBLE": external_side_effects_possible,
        "PAYMENTS_ENABLED": payments_enabled,
        "TRADING_ENABLED": trading_enabled,
        "PUBLICATION_ENABLED": publication_enabled,
        "MESSAGE_SEND_ENABLED": message_send_enabled,
    }
    for label, value in forbidden_true.items():
        if value is True:
            blockers.append(label + "_FORBIDDEN")

    blockers = list(dict.fromkeys(blockers))
    plan = {
        "schema": DEMO_PLAN_SCHEMA,
        "state": "READY" if not blockers else "BLOCKED",
        "blockers": blockers,
        "environment": env,
        "demo_script_ref": script_ref,
        "sandbox_digest": sandbox,
        "sandbox_attested": bool(sandbox_attested),
        "production_tenant_access": bool(production_tenant_access),
        "real_customer_data": bool(real_customer_data),
        "credentials_present": bool(credentials_present),
        "external_side_effects_possible": bool(external_side_effects_possible),
        "payments_enabled": bool(payments_enabled),
        "trading_enabled": bool(trading_enabled),
        "publication_enabled": bool(publication_enabled),
        "message_send_enabled": bool(message_send_enabled),
        "physical_demo_started": False,
        "network_called": False,
        "external_action_executed": False,
        "executes_action": False,
        "demo_plan_digest": "",
    }
    material = dict(plan)
    material.pop("demo_plan_digest", None)
    plan["demo_plan_digest"] = _digest(material)
    return plan


def advance_meeting_session(
    session: Mapping[str, Any] | None,
    deck: Mapping[str, Any] | None,
    *,
    event: Any,
    question: Any = "",
    demo_plan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    current = dict(session or {})
    raw_deck = dict(deck or {})
    blockers = _verify_session_digest(current, schema=MEETING_SESSION_SCHEMA)

    if raw_deck.get("schema") != MEETING_DECK_SCHEMA:
        blockers.append("MEETING_DECK_SCHEMA_MISMATCH")
    if _clean(current.get("deck_digest"), 90) != _clean(
        raw_deck.get("deck_digest"), 90
    ):
        blockers.append("MEETING_DECK_DIGEST_MISMATCH")

    action = _clean(event, 60).upper()
    if action not in MEETING_EVENTS:
        blockers.append("MEETING_EVENT_INVALID")

    state = _clean(current.get("state"), 60).upper()
    if state not in MEETING_STATES:
        blockers.append("MEETING_STATE_INVALID")

    manifest = list(raw_deck.get("slide_manifest") or [])
    index = int(current.get("current_slide_index", -1))
    if not (0 <= index < len(manifest)):
        blockers.append("CURRENT_SLIDE_INDEX_INVALID")

    if blockers:
        blocked = dict(current)
        blocked["blockers"] = list(dict.fromkeys(blockers))
        blocked["transition_state"] = "BLOCKED"
        blocked["session_digest"] = ""
        return _finalize_session(blocked)

    next_session = dict(current)
    next_session["blockers"] = []
    next_session["transition_state"] = "TRANSITIONED"

    if action in {"START", "QUESTION", "ANSWERED", "RESUME", "STOP"}:
        if state not in {"IDLE", "PRESENTING", "PAUSED_FOR_QA", "RESUME_PENDING"}:
            blockers.append("OWNER_MEETING_TRANSITION_STATE_INVALID")
        else:
            owner_event = action
            transition = meeting_transition(
                state,
                owner_event,
                slide=index,
            )
            if transition.get("state") != "TRANSITION_PLANNED":
                blockers.append("OWNER_MEETING_TRANSITION_BLOCKED")
            else:
                next_state = transition.get("meeting_state")
                next_session["state"] = next_state
                if action == "QUESTION":
                    if not _clean(question, 1200):
                        blockers.append("QUESTION_REQUIRED")
                    else:
                        next_session["return_slide_id"] = current[
                            "current_slide_id"
                        ]
                        next_session["return_slide_index"] = index
                        next_session["active_question_digest"] = _text_digest(
                            question
                        )
                elif action == "RESUME":
                    return_index = int(current.get("return_slide_index", -1))
                    return_id = _clean(current.get("return_slide_id"), 120)
                    if not (
                        0 <= return_index < len(manifest)
                        and manifest[return_index].get("slide_id") == return_id
                    ):
                        blockers.append("RETURN_SLIDE_BINDING_INVALID")
                    else:
                        next_session["current_slide_index"] = return_index
                        next_session["current_slide_id"] = return_id
                        next_session["return_slide_index"] = -1
                        next_session["return_slide_id"] = ""
                        next_session["active_question_digest"] = ""
                elif action == "STOP":
                    next_session["return_slide_index"] = -1
                    next_session["return_slide_id"] = ""
                    next_session["active_question_digest"] = ""

    elif action == "NEXT_SLIDE":
        if state != "PRESENTING":
            blockers.append("NEXT_SLIDE_REQUIRES_PRESENTING_STATE")
        elif index + 1 >= len(manifest):
            blockers.append("ALREADY_AT_LAST_SLIDE")
        else:
            index += 1
            next_session["current_slide_index"] = index
            next_session["current_slide_id"] = manifest[index]["slide_id"]

    elif action == "PREVIOUS_SLIDE":
        if state != "PRESENTING":
            blockers.append("PREVIOUS_SLIDE_REQUIRES_PRESENTING_STATE")
        elif index <= 0:
            blockers.append("ALREADY_AT_FIRST_SLIDE")
        else:
            index -= 1
            next_session["current_slide_index"] = index
            next_session["current_slide_id"] = manifest[index]["slide_id"]

    elif action == "DEMO_REQUEST":
        if state != "PRESENTING":
            blockers.append("DEMO_REQUEST_REQUIRES_PRESENTING_STATE")
        elif manifest[index].get("kind") != "DEMO":
            blockers.append("CURRENT_SLIDE_IS_NOT_DEMO")
        else:
            next_session["state"] = "DEMO_PENDING"
            next_session["return_slide_id"] = current["current_slide_id"]
            next_session["return_slide_index"] = index

    elif action == "DEMO_START":
        if state != "DEMO_PENDING":
            blockers.append("DEMO_START_REQUIRES_DEMO_PENDING_STATE")
        else:
            demo = dict(demo_plan or {})
            if demo.get("schema") != DEMO_PLAN_SCHEMA:
                blockers.append("DEMO_PLAN_SCHEMA_MISMATCH")
            if demo.get("state") != "READY" or demo.get("blockers"):
                blockers.append("READY_DEMO_PLAN_REQUIRED")
            demo_digest = _sha256(demo.get("demo_plan_digest"))
            if not demo_digest:
                blockers.append("DEMO_PLAN_DIGEST_REQUIRED")
            if not blockers:
                next_session["state"] = "DEMO_ACTIVE"
                next_session["active_demo_plan_digest"] = demo_digest

    elif action == "DEMO_END":
        if state != "DEMO_ACTIVE":
            blockers.append("DEMO_END_REQUIRES_DEMO_ACTIVE_STATE")
        else:
            return_index = int(current.get("return_slide_index", -1))
            return_id = _clean(current.get("return_slide_id"), 120)
            if not (
                0 <= return_index < len(manifest)
                and manifest[return_index].get("slide_id") == return_id
            ):
                blockers.append("RETURN_SLIDE_BINDING_INVALID")
            else:
                next_session["state"] = "PRESENTING"
                next_session["current_slide_index"] = return_index
                next_session["current_slide_id"] = return_id
                next_session["return_slide_index"] = -1
                next_session["return_slide_id"] = ""
                next_session["active_demo_plan_digest"] = ""

    elif action == "COMPLETE":
        if state != "PRESENTING":
            blockers.append("COMPLETE_REQUIRES_PRESENTING_STATE")
        else:
            next_session["state"] = "COMPLETED"

    if blockers:
        blocked = dict(current)
        blocked["blockers"] = list(dict.fromkeys(blockers))
        blocked["transition_state"] = "BLOCKED"
        blocked["session_digest"] = ""
        return _finalize_session(blocked)

    next_session["raw_question_persisted"] = False
    next_session["slides_presented_physically"] = False
    next_session["powerpoint_started"] = False
    next_session["demo_started_physically"] = False
    next_session["provider_called"] = False
    next_session["external_action_executed"] = False
    next_session["executes_action"] = False
    next_session["session_digest"] = ""
    return _finalize_session(next_session)


def orchestrator_handoff_context(
    session: Mapping[str, Any] | None,
    *,
    mode: Any,
) -> dict[str, Any]:
    """Return digest-only state that cognitive continuity may carry cross-device."""
    raw = dict(session or {})
    mode_name = _clean(mode, 40).upper()
    if mode_name == "TEACHING":
        expected_schema = TEACHING_SESSION_SCHEMA
        artifact_digest_key = "program_digest"
    elif mode_name == "MEETING":
        expected_schema = MEETING_SESSION_SCHEMA
        artifact_digest_key = "deck_digest"
    else:
        return {
            "schema": HANDOFF_SCHEMA,
            "state": "BLOCKED",
            "blockers": ["SUPPORTED_MODE_REQUIRED"],
            "executes_action": False,
        }

    blockers = _verify_session_digest(raw, schema=expected_schema)
    artifact_digest = _sha256(raw.get(artifact_digest_key))
    if not artifact_digest:
        blockers.append("ARTIFACT_DIGEST_REQUIRED")

    context = {
        "mode": mode_name,
        "session_id": _clean(
            raw.get("session_id") or raw.get("meeting_id"),
            160,
        ),
        "session_state": _clean(raw.get("state"), 60).upper(),
        "artifact_digest": artifact_digest,
        "session_digest": _sha256(raw.get("session_digest")),
        "current_slide_id": _clean(raw.get("current_slide_id"), 120),
        "current_slide_index": raw.get("current_slide_index"),
        "return_slide_id": _clean(raw.get("return_slide_id"), 120),
        "return_slide_index": raw.get("return_slide_index"),
    }
    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": HANDOFF_SCHEMA,
        "state": "READY" if not blockers else "BLOCKED",
        "blockers": blockers,
        "context": context if not blockers else {},
        "handoff_context_digest": _digest(context) if not blockers else "",
        "raw_question_transferred": False,
        "raw_answer_transferred": False,
        "raw_slide_content_transferred": False,
        "authentication_transferred": False,
        "owner_authority_transferred": False,
        "requires_target_reauthentication": True,
        "memory_written": False,
        "executes_action": False,
    }


def teaching_meeting_policy() -> dict[str, Any]:
    return {
        "schema": POLICY_SCHEMA,
        "reuses_owner_experience_modes": True,
        "creates_second_memory_database": False,
        "teaching_levels": list(TEACHING_LEVELS),
        "teaching_question_pause_supported": True,
        "teaching_exact_slide_resume_required": True,
        "teaching_exercises_supported": True,
        "automatic_memory_promotion": False,
        "meeting_question_pause_supported": True,
        "meeting_exact_slide_resume_required": True,
        "meeting_charts_require_data_refs": True,
        "meeting_charts_require_validation_refs": True,
        "meeting_metrics_require_evidence_refs": True,
        "meeting_demo_requires_synthetic_sandbox": True,
        "production_demo_authority": False,
        "real_customer_data_in_demo": False,
        "payments_in_demo": False,
        "trading_in_demo": False,
        "publication_in_demo": False,
        "message_send_in_demo": False,
        "powerpoint_created": False,
        "presentation_started": False,
        "charts_rendered": False,
        "physical_demo_started": False,
        "provider_called": False,
        "network_called": False,
        "camera_started": False,
        "microphone_started": False,
        "worker_armed": False,
        "deploy_executed": False,
        "core_checkpoint_write": False,
        "external_action_executed": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "TEACHING_PROGRAM_SCHEMA",
    "TEACHING_SESSION_SCHEMA",
    "MEETING_DECK_SCHEMA",
    "MEETING_SESSION_SCHEMA",
    "DEMO_PLAN_SCHEMA",
    "HANDOFF_SCHEMA",
    "POLICY_SCHEMA",
    "TEACHING_LEVELS",
    "TEACHING_STATES",
    "TEACHING_EVENTS",
    "MEETING_STATES",
    "MEETING_EVENTS",
    "TEACHING_SLIDE_KINDS",
    "MEETING_SLIDE_KINDS",
    "build_teaching_program",
    "start_teaching_session",
    "advance_teaching_session",
    "build_meeting_deck",
    "start_meeting_session",
    "build_live_demo_plan",
    "advance_meeting_session",
    "orchestrator_handoff_context",
    "teaching_meeting_policy",
]
