"""AION BUSINESS Team Access Physical Sandbox V1.

Read-only preflight contract for the isolated Keycloak/PostgreSQL sandbox.

This module does not invoke Docker, Keycloak, PostgreSQL, PowerShell, network
clients, secret stores, deploy hooks or runtime activation. It validates a
caller-supplied configuration snapshot and prepares an explicit manual command
plan for administrator review.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping
import json
import re

SCHEMA = "ATLASQUANT_AION_BUSINESS_TEAM_ACCESS_PHYSICAL_SANDBOX_V1"
VERSION = "1"

KEYCLOAK_IMAGE = "quay.io/keycloak/keycloak:26.7.5"
POSTGRES_IMAGE = "postgres:18.6"
KEYCLOAK_HOST = "127.0.0.1"
REGISTRY_HOST = "127.0.0.1"

_PLACEHOLDER = re.compile(r"CHANGE_ME|CHANGEME|EXAMPLE|PLACEHOLDER", re.I)


def _clean(value: Any, limit: int = 500) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _int_port(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        port = int(value)
    except (TypeError, ValueError):
        return None
    return port if 1024 <= port <= 65535 else None


def _digest(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return sha256(raw.encode("utf-8")).hexdigest()


def physical_sandbox_policy() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "TEAM_ACCESS_PHYSICAL_SANDBOX_POLICY_DEFINED",
        "keycloak_image": KEYCLOAK_IMAGE,
        "postgres_image": POSTGRES_IMAGE,
        "host_bindings": [KEYCLOAK_HOST, REGISTRY_HOST],
        "sandbox_only": True,
        "production_use_allowed": False,
        "secrets_in_repository_allowed": False,
        "automatic_start_allowed": False,
        "automatic_production_promotion": False,
        "executes_action": False,
    }


def sandbox_start_preflight(config: Mapping[str, Any] | None) -> dict[str, Any]:
    row = dict(config) if isinstance(config, Mapping) else {}

    keycloak_image = _clean(row.get("keycloak_image"), 200)
    postgres_image = _clean(row.get("postgres_image"), 200)
    keycloak_host = _clean(row.get("keycloak_host"), 80)
    registry_host = _clean(row.get("registry_host"), 80)
    keycloak_port = _int_port(row.get("keycloak_port"))
    registry_port = _int_port(row.get("registry_port"))

    admin_user = _clean(row.get("admin_username"), 120)
    admin_password = _clean(row.get("admin_password"), 500)
    keycloak_db_user = _clean(row.get("keycloak_db_username"), 120)
    keycloak_db_password = _clean(row.get("keycloak_db_password"), 500)
    registry_db_user = _clean(row.get("registry_db_username"), 120)
    registry_db_password = _clean(row.get("registry_db_password"), 500)

    secrets = [admin_password, keycloak_db_password, registry_db_password]
    secret_values_present = all(bool(item) for item in secrets)
    placeholders_absent = secret_values_present and not any(
        _PLACEHOLDER.search(item) for item in secrets
    )
    passwords_long_enough = secret_values_present and all(
        len(item) >= 20 for item in secrets
    )
    credentials_distinct = len(set(secrets)) == len(secrets) if secret_values_present else False

    gates = {
        "sandbox_only_true": row.get("sandbox_only") is True,
        "production_environment_false": row.get("production_environment") is False,
        "keycloak_image_pinned": keycloak_image == KEYCLOAK_IMAGE,
        "postgres_image_pinned": postgres_image == POSTGRES_IMAGE,
        "keycloak_localhost_only": keycloak_host == KEYCLOAK_HOST,
        "registry_localhost_only": registry_host == REGISTRY_HOST,
        "keycloak_port_valid": keycloak_port is not None,
        "registry_port_valid": registry_port is not None,
        "ports_distinct": bool(
            keycloak_port is not None
            and registry_port is not None
            and keycloak_port != registry_port
        ),
        "admin_username_present": bool(admin_user),
        "keycloak_db_username_present": bool(keycloak_db_user),
        "registry_db_username_present": bool(registry_db_user),
        "db_usernames_distinct": bool(
            keycloak_db_user
            and registry_db_user
            and keycloak_db_user != registry_db_user
        ),
        "secret_values_present_runtime_only": secret_values_present,
        "secret_placeholders_absent": placeholders_absent,
        "secret_minimum_length": passwords_long_enough,
        "secret_values_distinct": credentials_distinct,
        "env_file_is_gitignored": row.get("env_file_gitignored") is True,
        "compose_config_validated": row.get("compose_config_validated") is True,
        "docker_engine_observed": row.get("docker_engine_observed") is True,
        "automatic_start_requested": row.get("automatic_start_requested") is False,
    }
    blockers = [name for name, passed in gates.items() if not passed]
    ready = not blockers

    evidence = {
        "keycloak_image": keycloak_image,
        "postgres_image": postgres_image,
        "keycloak_host": keycloak_host,
        "registry_host": registry_host,
        "keycloak_port": keycloak_port,
        "registry_port": registry_port,
        "admin_username": admin_user,
        "keycloak_db_username": keycloak_db_user,
        "registry_db_username": registry_db_user,
        "secret_values_redacted": True,
    } if ready else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": (
            "READY_FOR_ADMIN_TEAM_ACCESS_PHYSICAL_SANDBOX_START_REVIEW"
            if ready
            else "TEAM_ACCESS_PHYSICAL_SANDBOX_START_BLOCKED"
        ),
        "gates": gates,
        "blockers": blockers,
        "evidence_digest": _digest(evidence) if ready else "",
        "secret_values_returned": False,
        "docker_started": False,
        "provider_called": False,
        "database_written": False,
        "production_authorized": False,
        "deploy_authorized": False,
        "runtime_authorized": False,
        "executes_action": False,
    }


def sandbox_command_plan(
    *,
    env_file: Any = "sandbox.env.local",
) -> dict[str, Any]:
    env_name = _clean(env_file, 160)
    safe_env = bool(
        env_name
        and env_name not in {".env", ".env.production", "production.env"}
        and "prod" not in env_name.lower()
    )

    compose = "deploy/sandbox/team-access/compose.yml"
    prefix = f"docker compose --env-file {env_name} -f {compose}"

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": (
            "TEAM_ACCESS_PHYSICAL_SANDBOX_COMMAND_PLAN_READY"
            if safe_env
            else "TEAM_ACCESS_PHYSICAL_SANDBOX_COMMAND_PLAN_BLOCKED"
        ),
        "env_file": env_name if safe_env else "",
        "commands": {
            "validate": f"{prefix} config --quiet" if safe_env else "",
            "start": f"{prefix} up -d" if safe_env else "",
            "status": f"{prefix} ps" if safe_env else "",
            "logs": f"{prefix} logs --tail 100" if safe_env else "",
            "stop": f"{prefix} down" if safe_env else "",
            "destroy_sandbox_data": f"{prefix} down -v" if safe_env else "",
        },
        "start_requires_explicit_admin_apply": True,
        "destroy_requires_explicit_admin_apply": True,
        "production_command_generated": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "KEYCLOAK_IMAGE",
    "POSTGRES_IMAGE",
    "physical_sandbox_policy",
    "sandbox_start_preflight",
    "sandbox_command_plan",
]
