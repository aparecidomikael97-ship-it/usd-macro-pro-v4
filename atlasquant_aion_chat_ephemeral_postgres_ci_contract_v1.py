"""AION Chat ephemeral Postgres CI integration contract V1.

Design/CI-only. It defines the boundary for a future isolated PostgreSQL service
used only in CI. It opens no connection and executes no SQL.

Maximum state:
READY_FOR_EPHEMERAL_POSTGRES_CI_IMPLEMENTATION_REVIEW
"""
from __future__ import annotations

from typing import Any, Mapping

SCHEMA = "ATLASQUANT_AION_CHAT_EPHEMERAL_POSTGRES_CI_CONTRACT_V1"
READY = "READY_FOR_EPHEMERAL_POSTGRES_CI_IMPLEMENTATION_REVIEW"
NEXT_ALLOWED_STEP = "IMPLEMENT_EPHEMERAL_POSTGRES_CI_HARNESS"
BACKEND_KIND = "EPHEMERAL_POSTGRES_SERVICE"
ALLOWED_ENVIRONMENT = "CI"
ALLOWED_HOST_CLASSES = ("LOOPBACK", "CI_SERVICE")

FALSE_FIELDS = (
    "postgres_service_started",
    "credentials_loaded",
    "production_secret_loaded",
    "production_dsn_loaded",
    "network_called",
    "connection_opened",
    "sql_executed",
    "migration_executed",
    "persistent_volume_created",
    "production_database_touched",
    "provider_called",
    "billing_executed",
    "deploy_executed",
    "worker_armed",
    "external_action_executed",
    "core_checkpoint_write",
)

def _m(value: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}

def _result(state: str, blockers=(), **fields) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": state,
        "blockers": sorted(set(str(x) for x in blockers if str(x))),
        **fields,
        **{key: False for key in FALSE_FIELDS},
    }

def evaluate_ephemeral_postgres_ci_contract(
    *,
    environment: Mapping[str, Any] | None,
    database: Mapping[str, Any] | None,
    credential_policy: Mapping[str, Any] | None,
    evidence_policy: Mapping[str, Any] | None,
) -> dict[str, Any]:
    e = _m(environment)
    d = _m(database)
    c = _m(credential_policy)
    p = _m(evidence_policy)
    blockers: list[str] = []

    checks = {
        "CI_ENVIRONMENT_REQUIRED": str(e.get("name") or "").upper() == ALLOWED_ENVIRONMENT,
        "PULL_REQUEST_OR_DISPATCH_ONLY_REQUIRED": e.get("pr_or_dispatch_only") is True,
        "NO_PRODUCTION_ENV_INJECTION_REQUIRED": e.get("production_environment_injected") is False,
        "EPHEMERAL_BACKEND_REQUIRED": str(d.get("kind") or "") == BACKEND_KIND,
        "NO_PERSISTENT_VOLUME_REQUIRED": d.get("persistent_volume") is False,
        "DATABASE_RECREATED_PER_JOB_REQUIRED": d.get("recreated_per_job") is True,
        "HOST_CLASS_REQUIRED": str(d.get("host_class") or "").upper() in ALLOWED_HOST_CLASSES,
        "NO_RENDER_ENDPOINT_REQUIRED": d.get("render_endpoint_used") is False,
        "NO_PUBLIC_DATABASE_ENDPOINT_REQUIRED": d.get("public_endpoint_used") is False,
        "TEST_ONLY_CREDENTIALS_REQUIRED": c.get("test_only_credentials") is True,
        "NO_PLATFORM_SECRET_REQUIRED": c.get("platform_secret_used") is False,
        "NO_PRODUCTION_DSN_REQUIRED": c.get("production_dsn_used") is False,
        "CREDENTIALS_JOB_SCOPED_REQUIRED": c.get("job_scoped") is True,
        "NO_PRODUCTION_READINESS_INFERENCE_REQUIRED": p.get("may_infer_production_readiness") is False,
        "TEST_EVIDENCE_LABELED_NONPROD_REQUIRED": p.get("explicit_nonproduction_label") is True,
        "ISOLATED_DB_NAMES_REQUIRED": p.get("unique_test_database") is True,
        "CLEANUP_REQUIRED": p.get("cleanup_required") is True,
        "FAIL_CLOSED_ON_UNEXPECTED_HOST_REQUIRED": p.get("fail_closed_on_unexpected_host") is True,
    }
    blockers.extend(name for name, ok in checks.items() if not ok)

    if d.get("host_class") == "PRODUCTION":
        blockers.append("PRODUCTION_HOST_FORBIDDEN")
    if c.get("credential_value_from_repository") is True:
        blockers.append("REPOSITORY_STORED_DB_CREDENTIAL_FORBIDDEN")
    if p.get("attests_render_postgres") is True:
        blockers.append("CI_HARNESS_MUST_NOT_ATTEST_RENDER_PRODUCTION")

    common = dict(
        design_only=True,
        backend_kind=BACKEND_KIND,
        allowed_environment=ALLOWED_ENVIRONMENT,
        production_equivalence=False,
        may_prove_driver_connectivity=True,
        may_prove_transaction_semantics=True,
        may_prove_scope_and_idempotency_semantics=True,
        may_not_prove_production_network=True,
        may_not_prove_production_backup_restore=True,
        may_not_prove_production_tls=True,
        next_allowed_step=NEXT_ALLOWED_STEP,
    )
    if blockers:
        return _result("BLOCKED", blockers, **common)
    return _result(READY, [], **common)

__all__ = [
    "SCHEMA",
    "READY",
    "NEXT_ALLOWED_STEP",
    "BACKEND_KIND",
    "ALLOWED_ENVIRONMENT",
    "ALLOWED_HOST_CLASSES",
    "FALSE_FIELDS",
    "evaluate_ephemeral_postgres_ci_contract",
]
