"""AION intelligent onboarding V1.

Pure, offline contract. It builds a resumable trail from a role and from
evidence the caller already supplied. It does not create accounts, charge,
publish, deploy, write runtime, change feature flags, or authorize trading.

Limits:
- a role is not an entitlement and an entitlement is not a payment;
- a feature flag is not operational proof;
- missing evidence never becomes COMPLETED;
- an incompatible snapshot becomes STALE instead of staying COMPLETED;
- USER and SALES cannot complete an ADMIN step;
- BEGINNER and ADVANCED do not grant extra permissions.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

from atlasquant_access_control import has_permission, normalize_role
from atlasquant_aion_core import guardian_decision, is_admin, truth_record
from atlasquant_aion_entitlements import entitlement_effective, normalize_entitlements
from atlasquant_aion_tenant import PERSONAL_SCOPE

SCHEMA = "ATLASQUANT_AION_ONBOARDING_V1"
ONBOARDING_VERSION = 1
MAX_PAYLOAD_CHARS = 16_384
MAX_DEPTH = 8
MAX_COLLECTION = 80

NOT_STARTED = "NOT_STARTED"
IN_PROGRESS = "IN_PROGRESS"
BLOCKED = "BLOCKED"
COMPLETED = "COMPLETED"
STALE = "STALE"
STATES = (NOT_STARTED, IN_PROGRESS, BLOCKED, COMPLETED, STALE)

BEGINNER = "BEGINNER"
ADVANCED = "ADVANCED"
EXPERIENCE_MODES = (BEGINNER, ADVANCED)

CONFIRMED = "CONFIRMED"
UNKNOWN = "UNKNOWN"
EVIDENCE_STATES = (CONFIRMED, BLOCKED, UNKNOWN)

_SECRET_EXACT = frozenset({
    "secret",
    "token",
    "password",
    "credential",
    "credentials",
    "api_key",
    "apikey",
    "api_token",
    "access_token",
    "auth_token",
    "private_key",
})
_CONTEXT_KEYS = frozenset({
    "subject_ref",
    "role",
    "experience_mode",
    "entitlements",
    "feature_flags",
    "payment_confirmed",
    "operational_integration_confirmed",
    "acknowledged_step_ids",
    "updated_at",
})


@dataclass(frozen=True)
class _Step:
    step_id: str
    title: str
    description: str
    area: str
    prerequisites: tuple[str, ...]
    roles: frozenset[str]
    required_modes: frozenset[str]
    evidence: str
    permission: str
    version: int
    next_safe_action: str


_CATALOG: tuple[_Step, ...] = (
    _Step(
        "role_confirmed",
        "Confirmar papel",
        "O papel informado é normalizado pelo controle de acesso existente.",
        "access",
        (),
        frozenset({"ADMIN", "USER", "SALES"}),
        frozenset({BEGINNER, ADVANCED}),
        "ROLE",
        "app:read",
        1,
        "Conferir o papel já normalizado sem alterar permissões.",
    ),
    _Step(
        "experience_confirmed",
        "Confirmar experiência",
        "BEGINNER e ADVANCED mudam a trilha; um modo ausente não é presumido.",
        "access",
        ("role_confirmed",),
        frozenset({"ADMIN", "USER", "SALES"}),
        frozenset({BEGINNER, ADVANCED}),
        "EXPERIENCE",
        "app:read",
        1,
        "Registrar o modo de experiência informado, sem promover o papel.",
    ),
    _Step(
        "read_access_confirmed",
        "Confirmar leitura",
        "A permissão app:read vem da tabela de papéis existente.",
        "access",
        ("experience_confirmed",),
        frozenset({"ADMIN", "USER", "SALES"}),
        frozenset({BEGINNER, ADVANCED}),
        "PERMISSION",
        "app:read",
        1,
        "Seguir apenas com a permissão de leitura que o papel já possui.",
    ),
    _Step(
        "personal_entitlement_confirmed",
        "Entitlement pessoal",
        "USER só avança com AION_PERSONAL efetivo. O papel não concede isso.",
        "entitlements",
        ("read_access_confirmed",),
        frozenset({"USER"}),
        frozenset({BEGINNER, ADVANCED}),
        "ENTITLEMENT",
        "app:read",
        1,
        "Aguardar evidência efetiva de entitlement. Não criar cobrança nem direito.",
    ),
    _Step(
        "payment_evidence_confirmed",
        "Evidência de pagamento",
        "Pagamento é evidência própria. Entitlement não prova pagamento.",
        "entitlements",
        ("personal_entitlement_confirmed",),
        frozenset({"USER"}),
        frozenset({BEGINNER, ADVANCED}),
        "PAYMENT",
        "app:read",
        1,
        "Separar a evidência de pagamento do entitlement. Não cobrar.",
    ),
    _Step(
        "sales_orientation",
        "Orientação comercial",
        "Trilha de SALES. Não abre passo administrativo.",
        "sales",
        ("read_access_confirmed",),
        frozenset({"SALES"}),
        frozenset({BEGINNER}),
        "ACK",
        "sales:read",
        1,
        "Ler a orientação comercial sem conceder admin:read.",
    ),
    _Step(
        "admin_guardian_review",
        "Revisão do Guardian",
        "Passo exclusivo de ADMIN. USER e SALES não podem concluí-lo.",
        "admin",
        ("read_access_confirmed",),
        frozenset({"ADMIN"}),
        frozenset({BEGINNER, ADVANCED}),
        "ACK",
        "aion:admin",
        1,
        "Revisar a postura do Guardian em leitura. Não aprovar ação sensível.",
    ),
    _Step(
        "admin_beginner_orientation",
        "Orientação inicial de ADMIN",
        "Obrigatória só para BEGINNER. ADVANCED não amplia privilégio.",
        "admin",
        ("admin_guardian_review",),
        frozenset({"ADMIN"}),
        frozenset({BEGINNER}),
        "ACK",
        "aion:admin",
        1,
        "Percorrer a orientação inicial sem ativar flag nem deploy.",
    ),
    _Step(
        "operational_integration_review",
        "Integração operacional",
        "Flag ligada não prova integração. Sem evidência explícita permanece bloqueado.",
        "admin",
        ("admin_guardian_review",),
        frozenset({"ADMIN"}),
        frozenset({BEGINNER, ADVANCED}),
        "OPERATIONAL",
        "aion:admin",
        1,
        "Não tratar feature flag como prova operacional nem autorizar execução.",
    ),
)


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _version_map(value: Any) -> dict[str, int]:
    if not isinstance(value, Mapping):
        return {}
    out: dict[str, int] = {}
    for key, item in value.items():
        if isinstance(key, str) and type(item) is int and item >= 1:
            out[key] = item
    return out


def onboarding_digest(snapshot: Mapping[str, Any]) -> str:
    """Hash closed progress fields. The stored digest is not part of the input."""
    payload = {
        "schema": SCHEMA,
        "onboarding_version": snapshot.get("onboarding_version"),
        "subject_ref": snapshot.get("subject_ref") if isinstance(snapshot.get("subject_ref"), str) else "",
        "role": snapshot.get("role") if isinstance(snapshot.get("role"), str) else "",
        "experience_mode": snapshot.get("experience_mode") if isinstance(snapshot.get("experience_mode"), str) else "",
        "state": snapshot.get("state") if isinstance(snapshot.get("state"), str) else "",
        "completed_step_ids": _string_list(snapshot.get("completed_step_ids")),
        "completed_step_versions": _version_map(snapshot.get("completed_step_versions")),
        "blocked_step_ids": _string_list(snapshot.get("blocked_step_ids")),
        "stale_step_ids": _string_list(snapshot.get("stale_step_ids")),
        "acknowledged_step_ids": _string_list(snapshot.get("acknowledged_step_ids")),
        "last_seen_step_id": snapshot.get("last_seen_step_id") if isinstance(snapshot.get("last_seen_step_id"), str) else "",
        "updated_at": snapshot.get("updated_at") if isinstance(snapshot.get("updated_at"), str) else "",
    }
    return sha256(_canonical(payload).encode("utf-8")).hexdigest()


def validate_step_graph(steps: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
    """Return structural problems. The production catalog is checked with this."""
    problems: list[str] = []
    ids = [str(step.get("step_id") or "") for step in steps]
    if any(not step_id for step_id in ids) or len(ids) != len(set(ids)):
        problems.append("DUPLICATE_STEP_ID")
    known = set(ids)
    prerequisites: dict[str, list[str]] = {}
    missing = False
    for step in steps:
        step_id = str(step.get("step_id") or "")
        raw = step.get("prerequisites") or []
        required = [str(item) for item in raw] if isinstance(raw, (list, tuple)) else []
        prerequisites[step_id] = required
        if any(item not in known for item in required):
            missing = True
    if missing:
        problems.append("UNKNOWN_PREREQUISITE")
    color = {step_id: 0 for step_id in ids}
    cyclic = False

    def visit(step_id: str) -> None:
        nonlocal cyclic
        if step_id not in color or color[step_id] == 2:
            return
        if color[step_id] == 1:
            cyclic = True
            return
        color[step_id] = 1
        for item in prerequisites.get(step_id, []):
            visit(item)
        color[step_id] = 2

    for step_id in ids:
        visit(step_id)
    if cyclic:
        problems.append("CIRCULAR_DEPENDENCY")
    return tuple(dict.fromkeys(problems))


def onboarding_catalog_problems() -> tuple[str, ...]:
    return validate_step_graph([
        {"step_id": step.step_id, "prerequisites": list(step.prerequisites)}
        for step in _CATALOG
    ])


if onboarding_catalog_problems():
    raise RuntimeError("onboarding catalog is not a valid step graph")


def _secret_key(name: object) -> bool:
    token = str(name or "").casefold().replace("-", "_")
    if token in _SECRET_EXACT:
        return True
    parts = set(token.split("_"))
    if parts & {"secret", "password", "credential", "credentials"}:
        return True
    if "api" in parts and parts & {"key", "token"}:
        return True
    return token.endswith("_token") or token.endswith("_password") or token.endswith("_secret")


def _contains_secret(value: Any, depth: int = 0) -> bool:
    if depth > MAX_DEPTH:
        return False
    if isinstance(value, Mapping):
        for key, item in list(value.items())[:MAX_COLLECTION]:
            if _secret_key(key) or _contains_secret(item, depth + 1):
                return True
        return False
    if isinstance(value, (list, tuple)):
        return any(_contains_secret(item, depth + 1) for item in list(value)[:MAX_COLLECTION])
    return False


def _too_large(value: Any, depth: int = 0) -> bool:
    if depth > MAX_DEPTH:
        return True
    if isinstance(value, str):
        return len(value) > 4_000
    if isinstance(value, Mapping):
        if len(value) > MAX_COLLECTION:
            return True
        return any(_too_large(item, depth + 1) for item in value.values())
    if isinstance(value, (list, tuple)):
        if len(value) > MAX_COLLECTION:
            return True
        return any(_too_large(item, depth + 1) for item in value)
    try:
        return len(_canonical(value)) > MAX_PAYLOAD_CHARS
    except (TypeError, ValueError):
        return True


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _exact_bool(value: Any) -> bool | None:
    if type(value) is bool:
        return value
    return None


def _subject(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    text = " ".join(value.split())
    if not text or len(text) > 120 or any(ord(char) < 32 for char in text):
        return ""
    return text


def _experience(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    mode = value.strip().upper()
    return mode if mode in EXPERIENCE_MODES else ""


def _version_overrides(raw: Mapping[str, int] | None) -> dict[str, int] | None:
    if raw is None:
        return {}
    if not isinstance(raw, Mapping):
        return None
    overrides: dict[str, int] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or type(value) is not int or value < 1:
            return None
        overrides[key] = value
    return overrides


def _field_type_error(payload: Mapping[str, Any]) -> str | None:
    string_fields = ("role", "experience_mode", "subject_ref", "updated_at")
    for key in string_fields:
        if key in payload and payload.get(key) is not None and not isinstance(payload.get(key), str):
            return "TYPE_INVALID"
    for key in ("payment_confirmed", "operational_integration_confirmed"):
        if key in payload and payload.get(key) is not None and type(payload.get(key)) is not bool:
            return "TYPE_INVALID"
    if "entitlements" in payload and payload.get("entitlements") is not None and not isinstance(payload.get("entitlements"), list):
        return "TYPE_INVALID"
    if "feature_flags" in payload and payload.get("feature_flags") is not None and not isinstance(payload.get("feature_flags"), Mapping):
        return "TYPE_INVALID"
    if "acknowledged_step_ids" in payload and payload.get("acknowledged_step_ids") is not None and not isinstance(payload.get("acknowledged_step_ids"), list):
        return "TYPE_INVALID"
    return None


def _empty_report(code: str, *, updated_at: str = "") -> dict[str, Any]:
    report: dict[str, Any] = {
        "schema": SCHEMA,
        "onboarding_version": ONBOARDING_VERSION,
        "state": BLOCKED,
        "rejected": True,
        "rejection": {"code": code},
        "subject_ref": "",
        "role": "",
        "experience_mode": "",
        "admin": False,
        "steps": [],
        "completed_step_ids": [],
        "completed_step_versions": {},
        "blocked_step_ids": [],
        "stale_step_ids": [],
        "rejected_step_ids": [],
        "acknowledged_step_ids": [],
        "last_seen_step_id": "",
        "updated_at": updated_at,
        "recommendations": [],
        "review_required": False,
        "real_trading_enabled": False,
        "executes_action": False,
        "feature_flag_changed": False,
        "runtime_written": False,
        "payment_inferred_from_entitlement": False,
        "feature_flag_is_operational_proof": False,
        "guardian": guardian_decision("real_trade", None),
    }
    report["digest"] = onboarding_digest(report)
    return report


def _session(role: str) -> dict[str, str]:
    return {"role": role}


def _personal_entitlement_ids(subject: str, rows: Any, now: datetime | None) -> list[str]:
    if not subject or not isinstance(rows, list):
        return []
    found: list[str] = []
    for item in normalize_entitlements(rows):
        if str(item.get("subject_ref") or "").casefold() != subject.casefold():
            continue
        if str(item.get("scope") or "") != PERSONAL_SCOPE:
            continue
        effect = entitlement_effective(item, now=now)
        if effect.get("effective") is True:
            found.append(str(effect.get("entitlement_id") or ""))
    return found


def _evidence(
    step: _Step,
    *,
    role: str,
    mode: str,
    subject: str,
    context: Mapping[str, Any],
    acknowledged: set[str],
    now: datetime | None,
) -> tuple[str, dict[str, Any], str]:
    if step.evidence == "ROLE":
        confirmed = bool(role)
        return (
            CONFIRMED if confirmed else UNKNOWN,
            truth_record(role or None, source="normalize_role", confirmed=confirmed),
            "",
        )
    if step.evidence == "EXPERIENCE":
        confirmed = bool(mode)
        return (
            CONFIRMED if confirmed else UNKNOWN,
            truth_record(mode or None, source="experience_mode", confirmed=confirmed),
            "",
        )
    if step.evidence == "PERMISSION":
        confirmed = has_permission(_session(role), step.permission)
        return (
            CONFIRMED if confirmed else BLOCKED,
            truth_record(step.permission, source="has_permission", confirmed=confirmed),
            "",
        )
    if step.evidence == "ENTITLEMENT":
        ids = _personal_entitlement_ids(subject, context.get("entitlements"), now)
        if ids:
            return CONFIRMED, truth_record(ids, source="entitlement_effective", confirmed=True), ""
        if context.get("entitlements") in (None, []):
            return UNKNOWN, truth_record(None, source="entitlement_effective", confirmed=False), "ENTITLEMENT_ABSENT"
        return BLOCKED, truth_record(False, source="entitlement_effective", confirmed=False), "ENTITLEMENT_NOT_EFFECTIVE"
    if step.evidence == "PAYMENT":
        flag = _exact_bool(context.get("payment_confirmed")) if "payment_confirmed" in context else None
        if flag is True:
            return CONFIRMED, truth_record(True, source="payment_confirmed", confirmed=True), ""
        if flag is False:
            return BLOCKED, truth_record(False, source="payment_confirmed", confirmed=False), "PAYMENT_NOT_CONFIRMED"
        return UNKNOWN, truth_record(None, source="payment_confirmed", confirmed=False), "PAYMENT_ABSENT"
    if step.evidence == "OPERATIONAL":
        flag = (
            _exact_bool(context.get("operational_integration_confirmed"))
            if "operational_integration_confirmed" in context
            else None
        )
        if flag is True:
            return CONFIRMED, truth_record(True, source="operational_integration_confirmed", confirmed=True), ""
        reason = "FEATURE_FLAG_IS_NOT_OPERATIONAL_PROOF"
        if flag is False:
            return BLOCKED, truth_record(False, source="operational_integration_confirmed", confirmed=False), reason
        return UNKNOWN, truth_record(None, source="operational_integration_confirmed", confirmed=False), reason
    confirmed = step.step_id in acknowledged
    return (
        CONFIRMED if confirmed else UNKNOWN,
        truth_record(step.step_id if confirmed else None, source="acknowledgement", confirmed=confirmed),
        "",
    )


def _parse_completed(progress: Mapping[str, Any]) -> tuple[str, list[str], dict[str, int], str]:
    if "completed_step_ids" not in progress:
        ids: list[str] = []
    else:
        raw = progress.get("completed_step_ids")
        if not isinstance(raw, list) or any(not isinstance(item, str) or not item.strip() for item in raw):
            return "MALFORMED_PROGRESS", [], {}, ""
        ids = [item.strip() for item in raw]
        if len(ids) != len(set(ids)):
            return "DUPLICATE_STEP_ID", [], {}, ""
    if "completed_step_versions" in progress and not isinstance(progress.get("completed_step_versions"), Mapping):
        return "MALFORMED_PROGRESS", [], {}, ""
    versions = _version_map(progress.get("completed_step_versions"))
    last = progress.get("last_seen_step_id")
    if last is None:
        last = ""
    if not isinstance(last, str):
        return "MALFORMED_PROGRESS", [], {}, ""
    return "", ids, versions, last.strip()


def recommend_onboarding_actions(report: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return at most three safe next steps. None of them grants a permission."""
    if not isinstance(report, Mapping) or report.get("rejected") is True:
        return []
    role = normalize_role(report.get("role"))
    if not role:
        return []
    actions: list[dict[str, Any]] = []
    steps = report.get("steps") if isinstance(report.get("steps"), list) else []
    completed = set(_string_list(report.get("completed_step_ids")))
    required_open = [
        step for step in steps
        if isinstance(step, Mapping) and step.get("required") is True and step.get("state") != COMPLETED
    ]
    pool = required_open or [
        step for step in steps
        if isinstance(step, Mapping) and step.get("state") not in {COMPLETED, STALE}
    ]
    for step in pool:
        if not isinstance(step, Mapping) or step.get("state") in {COMPLETED, STALE}:
            continue
        prerequisites = step.get("prerequisites") if isinstance(step.get("prerequisites"), list) else []
        if any(item not in completed for item in prerequisites):
            continue
        status = step.get("evidence_status")
        if status not in EVIDENCE_STATES:
            status = UNKNOWN
        actions.append({
            "step_id": step.get("step_id"),
            "status": status,
            "next_safe_action": step.get("next_safe_action") or "",
            "widens_permission": False,
            "executes_action": False,
            "real_trading_enabled": False,
            "role": role,
        })
        if len(actions) == 3:
            break
    return actions


def _seal(report: dict[str, Any]) -> dict[str, Any]:
    report["recommendations"] = recommend_onboarding_actions(report)
    report["digest"] = onboarding_digest(report)
    report["real_trading_enabled"] = False
    report["executes_action"] = False
    report["feature_flag_changed"] = False
    report["runtime_written"] = False
    return report


def assess_onboarding(
    payload: Mapping[str, Any] | None,
    progress: Mapping[str, Any] | None = None,
    *,
    now: datetime | None = None,
    step_versions: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    """Classify the trail. This function does not write, charge, or execute."""
    if now is not None and (not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None):
        return _empty_report("INVALID_CLOCK")
    if _too_large(payload) or _too_large(progress) or _too_large(step_versions):
        return _empty_report("PAYLOAD_TOO_LARGE")
    if _contains_secret(payload) or _contains_secret(progress) or _contains_secret(step_versions):
        return _empty_report("SECRET_FIELD")
    if not isinstance(payload, Mapping):
        return _empty_report("PAYLOAD_INVALID")
    type_error = _field_type_error(payload)
    if type_error:
        return _empty_report(type_error)
    overrides = _version_overrides(step_versions)
    if overrides is None:
        return _empty_report("INVALID_STEP_VERSION")

    context = {key: payload.get(key) for key in _CONTEXT_KEYS if key in payload}
    updated_raw = context.get("updated_at")
    updated_at = updated_raw if isinstance(updated_raw, str) else ""
    if "updated_at" in context and updated_at != "":
        parsed_now = _parse_timestamp(updated_at)
        if parsed_now is None:
            return _empty_report("INVALID_TIMESTAMP")
        if now is not None and parsed_now > now.astimezone(timezone.utc):
            return _empty_report("FUTURE_TIMESTAMP")
    if "role" not in context or context.get("role") in (None, ""):
        return _empty_report("ROLE_ABSENT")
    role = normalize_role(context.get("role"))
    mode = _experience(context.get("experience_mode"))
    subject = _subject(context.get("subject_ref"))
    if not role:
        return _empty_report("ROLE_INVALID")
    if "experience_mode" not in context or context.get("experience_mode") in (None, ""):
        report = _empty_report("EXPERIENCE_MODE_ABSENT")
        report["role"] = role
        report["digest"] = onboarding_digest(report)
        return report
    if not mode:
        report = _empty_report("EXPERIENCE_MODE_INVALID")
        report["role"] = role
        report["digest"] = onboarding_digest(report)
        return report
    if not subject:
        report = _empty_report("SUBJECT_REF_INVALID")
        report["role"] = role
        report["experience_mode"] = mode
        report["digest"] = onboarding_digest(report)
        return report

    progress_error = ""
    completed_ids: list[str] = []
    completed_versions: dict[str, int] = {}
    last_seen = ""
    stored_version: int | None = ONBOARDING_VERSION
    acknowledged = set(_string_list(context.get("acknowledged_step_ids")))
    if progress is not None:
        if not isinstance(progress, Mapping):
            progress_error = "MALFORMED_PROGRESS"
        elif "digest" in progress and progress.get("digest") != onboarding_digest(progress):
            progress_error = "DIGEST_MISMATCH"
        else:
            stored_role = progress.get("role")
            if stored_role not in (None, "") and normalize_role(stored_role) != role:
                progress_error = "ROLE_CHANGED"
            stored_mode = progress.get("experience_mode")
            if not progress_error and stored_mode not in (None, "") and _experience(stored_mode) != mode:
                progress_error = "EXPERIENCE_CHANGED"
            snap_time = _parse_timestamp(progress.get("updated_at")) if "updated_at" in progress else None
            if "updated_at" in progress and progress.get("updated_at") not in (None, "") and snap_time is None:
                progress_error = progress_error or "INVALID_TIMESTAMP"
            payload_time = _parse_timestamp(updated_at) if updated_at else None
            if not progress_error and snap_time and payload_time and snap_time < payload_time:
                progress_error = "REPLAY_REJECTED"
            if not progress_error:
                progress_error, completed_ids, completed_versions, last_seen = _parse_completed(progress)
            if not progress_error:
                if "onboarding_version" not in progress and completed_ids:
                    stored_version = None
                else:
                    version = progress.get("onboarding_version", ONBOARDING_VERSION)
                    stored_version = version if type(version) is int else None
                acknowledged.update(_string_list(progress.get("acknowledged_step_ids")))

    if progress_error:
        report = assess_onboarding(payload, None, now=now, step_versions=overrides or None)
        report["rejection"] = {"code": progress_error}
        report["rejected"] = progress_error in {
            "DIGEST_MISMATCH",
            "MALFORMED_PROGRESS",
            "DUPLICATE_STEP_ID",
            "INVALID_TIMESTAMP",
        }
        report["completed_step_ids"] = []
        report["completed_step_versions"] = {}
        report["review_required"] = progress_error in {"ROLE_CHANGED", "EXPERIENCE_CHANGED", "REPLAY_REJECTED"}
        report["state"] = STALE if report["review_required"] else BLOCKED
        return _seal(report)

    catalog_mismatch = stored_version != ONBOARDING_VERSION
    flags = context.get("feature_flags") if isinstance(context.get("feature_flags"), Mapping) else None
    visible = [step for step in _CATALOG if role in step.roles]
    visible_ids = {step.step_id for step in visible}
    rejected_ids = [step_id for step_id in completed_ids if step_id not in visible_ids]
    catalog_ids = {step.step_id for step in _CATALOG}
    unknown_ids = [step_id for step_id in completed_ids if step_id not in catalog_ids]

    rows: list[dict[str, Any]] = []
    completed_now: list[str] = []
    versions_now: dict[str, int] = {}
    for step in visible:
        evidence_status, evidence_record, reason = _evidence(
            step,
            role=role,
            mode=mode,
            subject=subject,
            context=context,
            acknowledged=acknowledged,
            now=now,
        )
        current_version = int(overrides.get(step.step_id, step.version))
        stored = completed_versions.get(step.step_id)
        claimed = step.step_id in completed_ids
        version_stale = claimed and (catalog_mismatch or stored != current_version)
        prereqs_ok = all(item in completed_now for item in step.prerequisites)
        forged = claimed and evidence_status != CONFIRMED
        if version_stale or (claimed and not prereqs_ok) or forged:
            state = STALE
        elif claimed and evidence_status == CONFIRMED and prereqs_ok and stored == current_version:
            state = COMPLETED
            completed_now.append(step.step_id)
            versions_now[step.step_id] = current_version
        elif evidence_status != CONFIRMED and step.evidence != "ACK":
            state = BLOCKED
        elif step.step_id == last_seen:
            state = IN_PROGRESS
        else:
            state = NOT_STARTED
        required = mode in step.required_modes
        completable = (
            state in {NOT_STARTED, IN_PROGRESS}
            and prereqs_ok
            and (evidence_status == CONFIRMED or step.evidence == "ACK")
            and has_permission(_session(role), step.permission)
        )
        rows.append({
            "step_id": step.step_id,
            "title": step.title,
            "description": step.description,
            "area": step.area,
            "prerequisites": list(step.prerequisites),
            "state": state,
            "required": required,
            "evidence_required": step.evidence,
            "evidence_status": evidence_status,
            "evidence_record": evidence_record,
            "blocked_reason": reason,
            "next_safe_action": step.next_safe_action,
            "version": current_version,
            "executes_action": False,
            "completable": completable,
        })

    blocked_ids = [row["step_id"] for row in rows if row["state"] == BLOCKED]
    stale_ids = [row["step_id"] for row in rows if row["state"] == STALE]
    required_rows = [row for row in rows if row["required"]]
    if stale_ids:
        state = STALE
    elif any(row["state"] == BLOCKED for row in required_rows):
        state = BLOCKED
    elif required_rows and all(row["state"] == COMPLETED for row in required_rows):
        state = COMPLETED
    elif completed_now or (last_seen in visible_ids):
        state = IN_PROGRESS
    else:
        state = NOT_STARTED

    report = {
        "schema": SCHEMA,
        "onboarding_version": ONBOARDING_VERSION,
        "state": state,
        "rejected": False,
        "rejection": {"code": "UNKNOWN_STEP", "step_ids": unknown_ids} if unknown_ids else None,
        "subject_ref": subject,
        "role": role,
        "experience_mode": mode,
        "admin": is_admin(_session(role)),
        "steps": rows,
        "completed_step_ids": completed_now,
        "completed_step_versions": versions_now,
        "blocked_step_ids": blocked_ids,
        "stale_step_ids": stale_ids,
        "rejected_step_ids": rejected_ids,
        "acknowledged_step_ids": [step.step_id for step in visible if step.step_id in acknowledged],
        "last_seen_step_id": last_seen if last_seen in visible_ids else "",
        "updated_at": updated_at,
        "recommendations": [],
        "review_required": bool(stale_ids),
        "real_trading_enabled": False,
        "executes_action": False,
        "feature_flag_changed": False,
        "runtime_written": False,
        "payment_inferred_from_entitlement": False,
        "feature_flag_is_operational_proof": False,
        "guardian": guardian_decision("real_trade", _session(role), feature_flags=flags),
    }
    return _seal(report)


def complete_onboarding_step(
    payload: Mapping[str, Any] | None,
    progress: Mapping[str, Any] | None,
    step_id: object,
    *,
    now: datetime | None = None,
    step_versions: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    """Record one explicit step. Prerequisites and evidence are required."""
    current = assess_onboarding(payload, progress, now=now, step_versions=step_versions)
    if current.get("rejected") is True or current.get("rejection"):
        return current
    if not isinstance(step_id, str):
        current["rejection"] = {"code": "UNKNOWN_STEP"}
        current["state"] = BLOCKED
        return _seal(current)
    target = step_id.strip()
    catalog_ids = {step.step_id for step in _CATALOG}
    rows = {row["step_id"]: row for row in current["steps"]}
    if target not in catalog_ids:
        current["rejection"] = {"code": "UNKNOWN_STEP", "step_id": target}
        current["state"] = BLOCKED
        return _seal(current)
    if target not in rows:
        current["rejection"] = {"code": "PRIVILEGE_ESCALATION", "step_id": target}
        current["state"] = BLOCKED
        if target not in current["rejected_step_ids"]:
            current["rejected_step_ids"] = [*current["rejected_step_ids"], target]
        return _seal(current)
    row = rows[target]
    if row["state"] == COMPLETED:
        return current
    if any(item not in current["completed_step_ids"] for item in row["prerequisites"]):
        current["rejection"] = {"code": "SKIPPED_PREREQUISITE", "step_id": target}
        return _seal(current)
    if row["evidence_status"] != CONFIRMED and row["evidence_required"] != "ACK":
        current["rejection"] = {"code": "MISSING_EVIDENCE", "step_id": target}
        current["state"] = BLOCKED
        return _seal(current)
    if row["completable"] is not True:
        current["rejection"] = {"code": "MISSING_EVIDENCE", "step_id": target}
        return _seal(current)
    if current.get("rejection"):
        return current

    next_payload = dict(payload or {})
    acknowledged = _string_list(next_payload.get("acknowledged_step_ids"))
    if row["evidence_required"] == "ACK":
        acknowledged = [*acknowledged, target]
    next_payload["acknowledged_step_ids"] = acknowledged
    next_progress = {
        "completed_step_ids": [*current["completed_step_ids"], target],
        "completed_step_versions": {**current["completed_step_versions"], target: row["version"]},
        "acknowledged_step_ids": acknowledged,
        "last_seen_step_id": target,
        "onboarding_version": ONBOARDING_VERSION,
        "role": current["role"],
        "experience_mode": current["experience_mode"],
        "subject_ref": current["subject_ref"],
        "updated_at": current["updated_at"],
    }
    return assess_onboarding(next_payload, next_progress, now=now, step_versions=step_versions)


def resume_onboarding(
    payload: Mapping[str, Any] | None,
    snapshot: Mapping[str, Any] | None,
    *,
    now: datetime | None = None,
    step_versions: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    """Resume a snapshot. Incompatible or replayed state does not stay COMPLETED."""
    if isinstance(snapshot, Mapping) and isinstance(payload, Mapping):
        left = _subject(snapshot.get("subject_ref")) if isinstance(snapshot.get("subject_ref"), str) else ""
        right = _subject(payload.get("subject_ref")) if isinstance(payload.get("subject_ref"), str) else ""
        if left and right and left != right:
            report = assess_onboarding(payload, None, now=now, step_versions=step_versions)
            if report.get("rejected") is True:
                return report
            report["rejection"] = {"code": "SUBJECT_MISMATCH"}
            report["state"] = BLOCKED
            report["completed_step_ids"] = []
            report["completed_step_versions"] = {}
            report["review_required"] = True
            return _seal(report)
    return assess_onboarding(payload, snapshot, now=now, step_versions=step_versions)


__all__ = [
    "SCHEMA",
    "ONBOARDING_VERSION",
    "STATES",
    "EXPERIENCE_MODES",
    "NOT_STARTED",
    "IN_PROGRESS",
    "BLOCKED",
    "COMPLETED",
    "STALE",
    "assess_onboarding",
    "complete_onboarding_step",
    "resume_onboarding",
    "recommend_onboarding_actions",
    "onboarding_digest",
    "validate_step_graph",
    "onboarding_catalog_problems",
]
