"""AION Core adapters for AtlasQuant voice status and persisted scheduling.

Voice preparation is local-only: it validates the exact transcript and reports
the already-configured AtlasQuant neural voice identity. Audio generation still
belongs to the existing explicit UI button.

Scheduling is also local-only: schedules are stored inside the Checkpoint
Mestre and can be inspected for due state. No background worker, network call,
subprocess or physical action is performed here.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from typing import Any, Mapping
from uuid import uuid4
from zoneinfo import ZoneInfo

from atlasquant_aion_clock import DEFAULT_TIMEZONE, application_timezone
from atlasquant_aion_core_intelligence.context import Context
from atlasquant_aion_core_intelligence.evidence import digest, safe_text, utc
from atlasquant_neural_tts import validate_transcript


SCHEMA = "ATLASQUANT_AION_CORE_VOICE_SCHEDULER_V1"
SCHEDULER_NAMESPACE = "aion_core_scheduler_v1"
SCHEDULE_SCHEMA = "AION_CORE_SCHEDULER_CHECKPOINT_V1"
CADENCES = ("ONCE", "HOURLY", "DAILY", "WEEKLY")
SCHEDULE_STATES = ("ACTIVE", "PAUSED", "CANCELED")
MAX_SCHEDULES = 200
MAX_PROMPT_CHARS = 2400
MAX_TITLE_CHARS = 240
SCHEDULE_CAPABILITIES = (
    "ADMINISTRATION",
    "MEMORY",
    "RESEARCH",
    "VOICE",
    "CONTENT",
    "OBSERVABILITY",
)


def _scope_payload(context: Context) -> list[str]:
    return json.loads(context.key)


def _bundle_digest(bundle: Mapping[str, Any]) -> str:
    raw = dict(bundle or {})
    raw.pop("digest", None)
    return digest(raw)


def _parse_iso(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return None
        return parsed
    except Exception:
        return None


def _clean_timezone(value: Any) -> str:
    name = " ".join(str(value or "").split()) or DEFAULT_TIMEZONE
    try:
        ZoneInfo(name)
        return name
    except Exception:
        return DEFAULT_TIMEZONE


def _clock_parts(hour: Any, minute: Any) -> tuple[int, int]:
    if isinstance(hour, bool) or isinstance(minute, bool):
        raise ValueError("invalid schedule clock")
    try:
        h = int(hour)
        m = int(minute)
    except Exception as exc:
        raise ValueError("invalid schedule clock") from exc
    if not 0 <= h <= 23 or not 0 <= m <= 59:
        raise ValueError("invalid schedule clock")
    return h, m


def _normalize_schedule(raw: Mapping[str, Any]) -> dict[str, Any]:
    item = dict(raw or {})
    schedule_id = safe_text(item.get("schedule_id"), 100)
    title = safe_text(item.get("title"), MAX_TITLE_CHARS)
    prompt = safe_text(item.get("prompt"), MAX_PROMPT_CHARS)
    capability_raw = str(item.get("capability") or "").strip().upper()
    capability = capability_raw if capability_raw in SCHEDULE_CAPABILITIES else ""
    cadence = safe_text(item.get("cadence"), 20).upper()
    state = safe_text(item.get("state"), 20).upper()
    timezone_name = _clean_timezone(item.get("timezone"))
    if not schedule_id or not title or not prompt:
        raise ValueError("incomplete schedule")
    if cadence not in CADENCES or state not in SCHEDULE_STATES:
        raise ValueError("invalid schedule state")
    hour, minute = _clock_parts(item.get("hour", 0), item.get("minute", 0))
    weekday = item.get("weekday")
    if cadence == "WEEKLY":
        if isinstance(weekday, bool):
            raise ValueError("invalid schedule weekday")
        try:
            weekday = int(weekday)
        except Exception as exc:
            raise ValueError("invalid schedule weekday") from exc
        if not 0 <= weekday <= 6:
            raise ValueError("invalid schedule weekday")
    else:
        weekday = None
    run_at = str(item.get("run_at") or "").strip()
    if cadence == "ONCE":
        parsed = _parse_iso(run_at)
        if parsed is None:
            raise ValueError("aware run_at required for ONCE")
        run_at = parsed.isoformat()
    else:
        run_at = ""
    created_at = _parse_iso(item.get("created_at"))
    if created_at is None:
        raise ValueError("valid created_at required")
    actor = safe_text(item.get("created_by"), 120)
    if not actor:
        raise ValueError("created_by required")
    return {
        "schema": "AION_CORE_SCHEDULE_V1",
        "schedule_id": schedule_id,
        "title": title,
        "prompt": prompt,
        "capability": capability,
        "cadence": cadence,
        "state": state,
        "timezone": timezone_name,
        "hour": hour,
        "minute": minute,
        "weekday": weekday,
        "run_at": run_at,
        "created_at": created_at.isoformat(),
        "created_by": actor,
        "last_observed_at": str(item.get("last_observed_at") or ""),
        "last_due_at": str(item.get("last_due_at") or ""),
        "execution_adapter": "LOCAL_MANUAL_V1",
        "automatic_execution": False,
        "execution_authorized": False,
        "external_action_executed": False,
    }


def _next_run(schedule: Mapping[str, Any], now: datetime) -> datetime | None:
    item = _normalize_schedule(schedule)
    if item["state"] != "ACTIVE":
        return None
    current = utc(now)
    zone = application_timezone(item["timezone"])
    local_now = current.astimezone(zone)
    cadence = item["cadence"]
    if cadence == "ONCE":
        run_at = _parse_iso(item["run_at"])
        if run_at is None:
            return None
        return run_at.astimezone(timezone.utc) if run_at > current else None
    if cadence == "HOURLY":
        candidate = local_now.replace(
            minute=item["minute"], second=0, microsecond=0
        )
        if candidate <= local_now:
            candidate += timedelta(hours=1)
        return candidate.astimezone(timezone.utc)
    if cadence == "DAILY":
        candidate = local_now.replace(
            hour=item["hour"], minute=item["minute"], second=0, microsecond=0
        )
        if candidate <= local_now:
            candidate += timedelta(days=1)
        return candidate.astimezone(timezone.utc)
    days = (int(item["weekday"]) - local_now.weekday()) % 7
    candidate = (local_now + timedelta(days=days)).replace(
        hour=item["hour"], minute=item["minute"], second=0, microsecond=0
    )
    if candidate <= local_now:
        candidate += timedelta(days=7)
    return candidate.astimezone(timezone.utc)


def _previous_due(schedule: Mapping[str, Any], now: datetime) -> datetime | None:
    item = _normalize_schedule(schedule)
    if item["state"] != "ACTIVE":
        return None
    current = utc(now)
    zone = application_timezone(item["timezone"])
    local_now = current.astimezone(zone)
    cadence = item["cadence"]
    if cadence == "ONCE":
        run_at = _parse_iso(item["run_at"])
        return run_at.astimezone(timezone.utc) if run_at and run_at <= current else None
    if cadence == "HOURLY":
        candidate = local_now.replace(
            minute=item["minute"], second=0, microsecond=0
        )
        if candidate > local_now:
            candidate -= timedelta(hours=1)
        return candidate.astimezone(timezone.utc)
    if cadence == "DAILY":
        candidate = local_now.replace(
            hour=item["hour"], minute=item["minute"], second=0, microsecond=0
        )
        if candidate > local_now:
            candidate -= timedelta(days=1)
        return candidate.astimezone(timezone.utc)
    days_back = (local_now.weekday() - int(item["weekday"])) % 7
    candidate = (local_now - timedelta(days=days_back)).replace(
        hour=item["hour"], minute=item["minute"], second=0, microsecond=0
    )
    if candidate > local_now:
        candidate -= timedelta(days=7)
    return candidate.astimezone(timezone.utc)


def _schedule_due(schedule: Mapping[str, Any], now: datetime) -> bool:
    item = _normalize_schedule(schedule)
    if item["state"] != "ACTIVE":
        return False
    previous = _previous_due(item, now)
    if previous is None:
        return False
    created = _parse_iso(item.get("created_at"))
    if created is not None and previous < created.astimezone(timezone.utc):
        return False
    last_due = _parse_iso(item.get("last_due_at"))
    return last_due is None or last_due < previous


def scheduler_bundle(
    context: Context,
    schedules: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
    *,
    exported_at: datetime,
) -> dict[str, Any]:
    if not isinstance(context, Context):
        raise ValueError("typed context required")
    rows = [_normalize_schedule(x) for x in list(schedules or [])]
    if len(rows) > MAX_SCHEDULES:
        raise ValueError("schedule limit exceeded")
    ids = [x["schedule_id"] for x in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate schedule id")
    out = {
        "schema": SCHEDULE_SCHEMA,
        "scope": _scope_payload(context),
        "exported_at": utc(exported_at).isoformat(),
        "schedules": rows,
        "execution_adapter": "UNAVAILABLE",
        "automatic_execution": False,
    }
    out["digest"] = _bundle_digest(out)
    return out


def scheduler_integrity(raw: Mapping[str, Any] | None) -> dict[str, str]:
    if not isinstance(raw, Mapping):
        return {"state": "ABSENT", "stored": "", "expected": ""}
    if raw.get("schema") != SCHEDULE_SCHEMA:
        return {"state": "MISMATCH", "stored": "", "expected": SCHEDULE_SCHEMA}
    supplied = str(raw.get("digest") or "").strip()
    expected = _bundle_digest(raw)
    return {
        "state": "MATCH" if supplied and supplied == expected else "MISMATCH",
        "stored": supplied,
        "expected": expected,
    }


def load_schedules(
    context: Context,
    checkpoint: Mapping[str, Any] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not isinstance(context, Context):
        raise ValueError("typed context required")
    payload = dict(checkpoint or {})
    raw = payload.get(SCHEDULER_NAMESPACE)
    if raw is None:
        return [], {"state": "EMPTY", "reason": "SCHEDULER_NAMESPACE_ABSENT"}
    if not isinstance(raw, Mapping):
        raise ValueError("SCHEDULER_CHECKPOINT_MISMATCH")
    integrity = scheduler_integrity(raw)
    if integrity["state"] != "MATCH":
        raise ValueError("SCHEDULER_CHECKPOINT_MISMATCH")
    if raw.get("scope") != _scope_payload(context):
        return [], {"state": "CONTEXT_ISOLATED", "reason": "SCHEDULER_CONTEXT_MISMATCH"}
    rows_raw = raw.get("schedules", [])
    if not isinstance(rows_raw, list) or len(rows_raw) > MAX_SCHEDULES:
        raise ValueError("invalid schedules")
    rows = [_normalize_schedule(x) for x in rows_raw if isinstance(x, Mapping)]
    if len(rows) != len(rows_raw):
        raise ValueError("invalid schedules")
    return rows, {"state": "CONNECTED", "reason": "", "count": len(rows)}


def attach_schedules(
    checkpoint: Mapping[str, Any],
    context: Context,
    schedules: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
    *,
    now: datetime,
) -> dict[str, Any]:
    out = deepcopy(dict(checkpoint or {}))
    previous = out.get(SCHEDULER_NAMESPACE)
    if isinstance(previous, Mapping) and previous.get("scope") != _scope_payload(context):
        raise ValueError("SCHEDULER_CONTEXT_MISMATCH")
    out[SCHEDULER_NAMESPACE] = scheduler_bundle(context, schedules, exported_at=now)
    return out


def stage_schedule(
    checkpoint: Mapping[str, Any],
    context: Context,
    *,
    title: str,
    prompt: str,
    cadence: str,
    capability: str | None = None,
    timezone_name: str | None,
    hour: int = 0,
    minute: int = 0,
    weekday: int | None = None,
    run_at: datetime | None = None,
    confirmation: bool,
    now: datetime | None = None,
) -> dict[str, Any]:
    if not isinstance(context, Context) or context.role != "ADMIN":
        raise ValueError("ADMIN_REQUIRED")
    if confirmation is not True:
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "EXPLICIT_HUMAN_CONFIRMATION_REQUIRED",
            "checkpoint": dict(checkpoint or {}),
            "external_persisted": False,
            "automatic_execution": False,
        }
    current = utc(now or datetime.now(timezone.utc))
    rows, state = load_schedules(context, checkpoint)
    if state["state"] == "CONTEXT_ISOLATED":
        raise ValueError("SCHEDULER_CONTEXT_MISMATCH")
    cadence_clean = safe_text(cadence, 20).upper()
    if cadence_clean not in CADENCES:
        raise ValueError("invalid cadence")
    h, m = _clock_parts(hour, minute)
    zone_name = _clean_timezone(timezone_name)
    run_at_text = ""
    if cadence_clean == "ONCE":
        if not isinstance(run_at, datetime) or run_at.tzinfo is None:
            raise ValueError("aware run_at required for ONCE")
        if run_at.astimezone(timezone.utc) <= current:
            raise ValueError("future run_at required for ONCE")
        run_at_text = run_at.isoformat()
    schedule = _normalize_schedule({
        "schedule_id": "SCH-" + uuid4().hex[:16].upper(),
        "title": title,
        "prompt": prompt,
        "capability": str(capability or "").strip().upper(),
        "cadence": cadence_clean,
        "state": "ACTIVE",
        "timezone": zone_name,
        "hour": h,
        "minute": m,
        "weekday": weekday,
        "run_at": run_at_text,
        "created_at": current.isoformat(),
        "created_by": context.actor_id,
    })
    rows.append(schedule)
    staged = attach_schedules(checkpoint, context, rows, now=current)
    next_run = _next_run(schedule, current)
    return {
        "schema": SCHEMA,
        "status": "STAGED",
        "checkpoint": staged,
        "schedule": schedule,
        "next_run_at": next_run.isoformat() if next_run else "",
        "external_persisted": False,
        "requires_checkpoint_save": True,
        "execution_adapter": "LOCAL_MANUAL_V1",
        "automatic_execution": False,
        "execution_authorized": False,
        "external_action_executed": False,
    }


class CheckpointAutomationAdapter:
    """Read-only Core adapter over schedules already present in the checkpoint."""

    available = True

    def __init__(self, context: Context, checkpoint: Mapping[str, Any] | None):
        self.context = context
        self.checkpoint = dict(checkpoint or {})

    def snapshot(self, now: datetime) -> dict[str, Any]:
        rows, state = load_schedules(self.context, self.checkpoint)
        current = utc(now)
        details = []
        due_count = 0
        for row in rows:
            due = _schedule_due(row, current)
            if due:
                due_count += 1
            due_at = _previous_due(row, current) if due else None
            next_run = _next_run(row, current)
            details.append({
                **deepcopy(row),
                "due": due,
                "due_at": due_at.isoformat() if due_at else "",
                "next_run_at": next_run.isoformat() if next_run else "",
                "executes_action": False,
            })
        return {
            "schema": SCHEMA,
            "status": state["state"],
            "schedules": details,
            "count": len(details),
            "due_count": due_count,
            "execution_adapter": "LOCAL_MANUAL_V1",
            "local_manual_executor": "AVAILABLE",
            "autonomous_worker_connected": False,
            "automatic_execution": False,
            "execution_authorized": False,
            "external_action_executed": False,
            "reason": (
                "LOCAL_MANUAL_EXECUTOR_AVAILABLE_AUTONOMOUS_WORKER_NOT_CONNECTED"
            ),
        }


class AtlasQuantVoiceAdapter:
    """Core-visible state for the existing explicit AtlasQuant neural voice UI."""

    def __init__(self, status: Mapping[str, Any] | None):
        self.status = dict(status or {})
        self.available = bool(self.status.get("configured"))

    def snapshot(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "status": "READY" if self.available else "UNAVAILABLE",
            "profile_id": str(self.status.get("profile_id") or ""),
            "provider": str(self.status.get("provider") or "UNKNOWN"),
            "model": str(self.status.get("model") or "UNKNOWN"),
            "voice": str(self.status.get("voice") or "UNKNOWN"),
            "provider_configured": self.available,
            "audio_generation_surface": "EXPLICIT_UI_BUTTON",
            "provider_called": False,
            "automatic_playback": False,
            "execution_authorized": False,
            "external_action_executed": False,
            "real_trading_enabled": False,
        }

    def prepare(self, transcript: str) -> dict[str, Any]:
        text = validate_transcript(transcript)
        snapshot = self.snapshot()
        if not self.available:
            return {
                **snapshot,
                "status": "UNAVAILABLE",
                "reason": "VOICE_PROVIDER_NOT_CONFIGURED",
                "transcript": text,
                "cache_digest": "",
            }
        return {
            **snapshot,
            "status": "READY_TO_GENERATE_ON_EXPLICIT_CLICK",
            "reason": "NO_PROVIDER_CALL_IN_CORE",
            "transcript": text,
            "transcript_digest": digest({
                "text": text,
                "profile_id": snapshot["profile_id"],
                "provider": snapshot["provider"],
                "model": snapshot["model"],
                "voice": snapshot["voice"],
            }),
        }


__all__ = [
    "SCHEMA",
    "SCHEDULER_NAMESPACE",
    "SCHEDULE_SCHEMA",
    "CADENCES",
    "SCHEDULE_STATES",
    "SCHEDULE_CAPABILITIES",
    "scheduler_integrity",
    "load_schedules",
    "attach_schedules",
    "stage_schedule",
    "CheckpointAutomationAdapter",
    "AtlasQuantVoiceAdapter",
]
