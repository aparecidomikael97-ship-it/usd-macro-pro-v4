"""AION Chat real Postgres driver binding contract V1.

Design/CI-only. No Postgres driver is installed/imported, no environment or
secret is read, no socket/DB connection is opened, and no SQL/provider/billing/
deploy/runtime action is executed.
"""
from __future__ import annotations
from typing import Any, Mapping

SCHEMA="ATLASQUANT_AION_CHAT_POSTGRES_DRIVER_BINDING_CONTRACT_V1"
READY="READY_FOR_REAL_POSTGRES_DRIVER_BINDING_IMPLEMENTATION_REVIEW"
NEXT_ALLOWED_STEP="IMPLEMENT_DRIVER_BINDING_WITH_NO_PRODUCTION_CREDENTIALS"
PLANNED_DRIVER="PSYCOPG3_SYNC"
ENDPOINT_CLASS="INTERNAL_PRIVATE"
TLS_MODE="REQUIRE"
CREDENTIAL_SOURCE="PLATFORM_SECRET_INJECTION"

FALSE_FIELDS=(
    "driver_installed","driver_imported","environment_read","credentials_loaded",
    "secrets_loaded","dsn_materialized","socket_opened","connection_opened",
    "sql_executed","migration_executed","database_created","network_called",
    "provider_called","billing_executed","deploy_executed","worker_armed",
    "worker_activated","external_action_executed","core_checkpoint_write",
)

def _m(value: Mapping[str, Any] | None)->dict[str,Any]:
    return dict(value) if isinstance(value, Mapping) else {}

def _result(state:str,blockers=(),**fields)->dict[str,Any]:
    return {
        "schema":SCHEMA,
        "state":state,
        "blockers":sorted(set(str(x) for x in blockers if str(x))),
        **fields,
        **{k:False for k in FALSE_FIELDS},
    }

def evaluate_driver_binding_contract(
    *,
    driver_plan: Mapping[str, Any] | None=None,
    secret_boundary: Mapping[str, Any] | None=None,
    connection_policy: Mapping[str, Any] | None=None,
    observability_policy: Mapping[str, Any] | None=None,
)->dict[str,Any]:
    d,s,c,o=_m(driver_plan),_m(secret_boundary),_m(connection_policy),_m(observability_policy)
    blockers=[]
    checks={
        "PSYCOPG3_SYNC_PLAN_REQUIRED":str(d.get("driver") or "")==PLANNED_DRIVER,
        "NO_DRIVER_IMPORT_IN_CONTRACT_REQUIRED":d.get("contract_imports_driver") is False,
        "STORE_LAYER_DRIVER_AGNOSTIC_REQUIRED":d.get("store_layer_driver_agnostic") is True,
        "COMPOSITION_ROOT_OWNS_BINDING_REQUIRED":d.get("composition_root_owns_binding") is True,
        "EXPLICIT_CONNECTION_FACTORY_REQUIRED":d.get("explicit_connection_factory") is True,
        "PLATFORM_SECRET_INJECTION_REQUIRED":str(s.get("credential_source") or "")==CREDENTIAL_SOURCE,
        "NO_SECRET_READ_AT_IMPORT_REQUIRED":s.get("no_secret_read_at_import") is True,
        "NO_ENV_READ_IN_STORE_REQUIRED":s.get("store_reads_environment") is False,
        "NO_DSN_IN_SOURCE_REQUIRED":s.get("dsn_in_source") is False,
        "NO_DSN_IN_LOGS_REQUIRED":s.get("dsn_logged") is False,
        "NO_PASSWORD_IN_LOGS_REQUIRED":s.get("password_logged") is False,
        "SECRET_REFERENCE_ONLY_REQUIRED":s.get("descriptor_contains_secret_reference_only") is True,
        "SECRET_ROTATION_WITHOUT_CODE_CHANGE_REQUIRED":s.get("rotation_without_code_change") is True,
        "INTERNAL_PRIVATE_ENDPOINT_REQUIRED":str(c.get("endpoint_class") or "")==ENDPOINT_CLASS,
        "EXTERNAL_ENDPOINT_DEFAULT_DENY_REQUIRED":c.get("external_endpoint_allowed") is False,
        "TLS_REQUIRED":str(c.get("tls_mode") or "").upper()==TLS_MODE,
        "AUTOCOMMIT_DISABLED_REQUIRED":c.get("autocommit") is False,
        "BOUNDED_CONNECT_TIMEOUT_REQUIRED":isinstance(c.get("connect_timeout_seconds"),int)
            and 1<=c.get("connect_timeout_seconds")<=10,
        "BOUNDED_STATEMENT_TIMEOUT_REQUIRED":isinstance(c.get("statement_timeout_ms"),int)
            and 100<=c.get("statement_timeout_ms")<=30000,
        "APPLICATION_NAME_REQUIRED":bool(str(c.get("application_name") or "").strip()),
        "LEAST_PRIVILEGE_ROLE_REQUIRED":c.get("least_privilege_role") is True,
        "SUPERUSER_FORBIDDEN":c.get("superuser") is False,
        "STARTUP_MIGRATION_FORBIDDEN":c.get("auto_migrate_on_connect") is False,
        "HEALTH_BEFORE_USE_REQUIRED":c.get("health_before_use") is True,
        "SCHEMA_COMPATIBILITY_BEFORE_USE_REQUIRED":c.get("schema_compatibility_before_use") is True,
        "SCOPE_POLICY_HEALTH_BEFORE_USE_REQUIRED":c.get("scope_policy_health_before_use") is True,
        "CONNECTION_STATE_LOGGING_REQUIRED":o.get("connection_state_logging") is True,
        "LATENCY_METRICS_REQUIRED":o.get("latency_metrics") is True,
        "ERROR_CLASS_METRICS_REQUIRED":o.get("error_class_metrics") is True,
        "NO_MESSAGE_CONTENT_IN_DB_LOGS_REQUIRED":o.get("message_content_logged") is False,
        "NO_SECRET_MATERIAL_IN_TELEMETRY_REQUIRED":o.get("secret_material_logged") is False,
        "SCOPE_IDENTIFIER_POLICY_REQUIRED":o.get("safe_scope_identifier_policy") is True,
    }
    blockers.extend(k for k,v in checks.items() if not v)
    if c.get("fallback_to_external_endpoint") is True:
        blockers.append("AUTOMATIC_EXTERNAL_ENDPOINT_FALLBACK_FORBIDDEN")
    if c.get("fallback_to_sqlite") is True:
        blockers.append("PRODUCTION_SQLITE_FALLBACK_FORBIDDEN")
    if s.get("plaintext_dsn_returned_to_ui") is True:
        blockers.append("PLAINTEXT_DSN_TO_UI_FORBIDDEN")

    common=dict(
        design_only=True,
        planned_driver=PLANNED_DRIVER,
        endpoint_class=ENDPOINT_CLASS,
        tls_mode=TLS_MODE,
        credential_source=CREDENTIAL_SOURCE,
        connection_descriptor_contains_no_plaintext_secret=True,
        driver_binding_separate_from_store_semantics=True,
        runtime_connection_requires_separate_attestation=True,
        next_allowed_step=NEXT_ALLOWED_STEP,
    )
    return _result("BLOCKED",blockers,**common) if blockers else _result(READY,[],**common)

__all__=[
    "SCHEMA","READY","NEXT_ALLOWED_STEP","PLANNED_DRIVER","ENDPOINT_CLASS",
    "TLS_MODE","CREDENTIAL_SOURCE","FALSE_FIELDS","evaluate_driver_binding_contract"
]
