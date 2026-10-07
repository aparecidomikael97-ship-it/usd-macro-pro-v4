"""Psycopg driver binding V1 with no production credentials and no network.

This implementation proves dependency pinning and configuration boundaries.
It intentionally cannot open a database connection.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import psycopg

SCHEMA = "ATLASQUANT_AION_CHAT_POSTGRES_DRIVER_BINDING_V1"
ALLOWED_ENVIRONMENTS = frozenset({"LOCAL", "TEST", "CI"})
ENDPOINT_CLASS = "INTERNAL_PRIVATE"
TLS_MODE = "REQUIRE"
NEXT_ALLOWED_STEP = "DESIGN_NONPRODUCTION_POSTGRES_INTEGRATION_TEST_CONTRACT"


class NetworkDisabledError(RuntimeError):
    """Raised because this V1 binding intentionally cannot open connections."""


@dataclass(frozen=True)
class DriverBindingConfig:
    environment: str
    secret_reference: str
    endpoint_class: str = ENDPOINT_CLASS
    tls_mode: str = TLS_MODE
    connect_timeout_seconds: int = 5
    statement_timeout_ms: int = 10_000
    application_name: str = "atlasquant-aion-chat"
    autocommit: bool = False

    def __post_init__(self) -> None:
        environment = str(self.environment or "").strip().upper()
        secret_reference = str(self.secret_reference or "").strip()
        endpoint_class = str(self.endpoint_class or "").strip().upper()
        tls_mode = str(self.tls_mode or "").strip().upper()

        if environment not in ALLOWED_ENVIRONMENTS:
            raise ValueError("non-production environment required")
        if not secret_reference:
            raise ValueError("secret reference required")
        if any(marker in secret_reference for marker in ("://", "@", "password=", "user=")):
            raise ValueError("secret reference must not contain credential material")
        if endpoint_class != ENDPOINT_CLASS:
            raise ValueError("internal/private endpoint class required")
        if tls_mode != TLS_MODE:
            raise ValueError("TLS REQUIRE required")
        if not isinstance(self.connect_timeout_seconds, int) or not 1 <= self.connect_timeout_seconds <= 10:
            raise ValueError("connect timeout must be 1..10 seconds")
        if not isinstance(self.statement_timeout_ms, int) or not 100 <= self.statement_timeout_ms <= 30_000:
            raise ValueError("statement timeout must be 100..30000 ms")
        if not str(self.application_name or "").strip():
            raise ValueError("application name required")
        if self.autocommit is not False:
            raise ValueError("autocommit must remain disabled")

        object.__setattr__(self, "environment", environment)
        object.__setattr__(self, "secret_reference", secret_reference)
        object.__setattr__(self, "endpoint_class", endpoint_class)
        object.__setattr__(self, "tls_mode", tls_mode)


class PsycopgDriverBindingV1:
    """Non-network binding facade. It exposes policy but cannot connect."""

    def __init__(self, config: DriverBindingConfig):
        if not isinstance(config, DriverBindingConfig):
            raise TypeError("DriverBindingConfig required")
        self.config = config

    def driver_metadata(self) -> dict[str, Any]:
        return {
            "driver": "psycopg",
            "driver_version": str(psycopg.__version__),
            "driver_imported": True,
            "binary_extra_expected": True,
            "network_enabled": False,
            "production_credentials_allowed": False,
        }

    def safe_descriptor(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "environment": self.config.environment,
            "secret_reference": self.config.secret_reference,
            "endpoint_class": self.config.endpoint_class,
            "tls_mode": self.config.tls_mode,
            "connect_timeout_seconds": self.config.connect_timeout_seconds,
            "statement_timeout_ms": self.config.statement_timeout_ms,
            "application_name": self.config.application_name,
            "autocommit": self.config.autocommit,
            "dsn_materialized": False,
            "credentials_loaded": False,
            "connection_opened": False,
            "sql_executed": False,
            "network_called": False,
            "provider_called": False,
            "billing_executed": False,
            "deploy_executed": False,
            "worker_armed": False,
            "external_action_executed": False,
            "core_checkpoint_write": False,
            "next_allowed_step": NEXT_ALLOWED_STEP,
        }

    def connection_kwargs_without_secret(self) -> dict[str, Any]:
        return {
            "connect_timeout": self.config.connect_timeout_seconds,
            "application_name": self.config.application_name,
            "autocommit": False,
            "options": f"-c statement_timeout={self.config.statement_timeout_ms}",
            "sslmode": "require",
        }

    def connect(self, *_args: Any, **_kwargs: Any) -> None:
        raise NetworkDisabledError(
            "real Postgres connections are disabled in driver binding V1"
        )


def binding_policy() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "driver_dependency_expected": "psycopg[binary]==3.3.6",
        "production_credentials_allowed": False,
        "environment_read": False,
        "dsn_materialized": False,
        "connection_opened": False,
        "sql_executed": False,
        "network_called": False,
        "provider_called": False,
        "billing_executed": False,
        "deploy_executed": False,
        "worker_armed": False,
        "external_action_executed": False,
        "core_checkpoint_write": False,
        "next_allowed_step": NEXT_ALLOWED_STEP,
    }


__all__ = [
    "SCHEMA",
    "ALLOWED_ENVIRONMENTS",
    "ENDPOINT_CLASS",
    "TLS_MODE",
    "NEXT_ALLOWED_STEP",
    "NetworkDisabledError",
    "DriverBindingConfig",
    "PsycopgDriverBindingV1",
    "binding_policy",
]
