"""TLS-enforced direct PostgreSQL application-role binding for disposable CI.

This stage strengthens the direct least-privilege PostgreSQL binding by
requiring a verified TLS transport and by proving the live backend connection
is encrypted. It remains CI/TEST-only and consumes only an injected connection
factory. No provider, production secret, deployment, Worker or Core authority
is present.
"""
from __future__ import annotations

from typing import Any

import psycopg
from psycopg.conninfo import conninfo_to_dict

from aion_chat.store import StorageUnavailableError
from atlasquant_aion_chat_direct_app_role_connection_ci_v1 import (
    CI_DIRECT_APP_ROLE,
    DirectLoginAuditedPostgresBackendCiV1,
    DirectLoginAuditedPostgresChatStoreCiV1,
    HEALTHY,
    FAILED,
)


class TlsDirectLoginAuditedPostgresBackendCiV1(
    DirectLoginAuditedPostgresBackendCiV1
):
    """Direct app-role backend that rejects any non-TLS PostgreSQL session."""

    def _connection(self) -> psycopg.Connection:
        conn = super()._connection()
        try:
            params = conninfo_to_dict(conn.info.dsn)
            if (
                str(params.get("sslmode") or "").strip().lower()
                != "verify-full"
                or not str(params.get("sslrootcert") or "").strip()
            ):
                raise StorageUnavailableError(
                    "verify-full PostgreSQL TLS client policy is not proven"
                )
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT s.ssl,s.version,s.cipher,"
                    "inet_client_addr() IS NOT NULL "
                    "FROM pg_stat_ssl s WHERE s.pid=pg_backend_pid()"
                )
                row = cur.fetchone()
            if (
                row is None
                or row[0] is not True
                or not str(row[1] or "").strip()
                or not str(row[2] or "").strip()
                or row[3] is not True
            ):
                raise StorageUnavailableError(
                    "verified PostgreSQL TLS transport is not proven"
                )
            return conn
        except Exception as exc:
            try:
                conn.rollback()
            except Exception:
                pass
            try:
                conn.close()
            except Exception:
                pass
            if isinstance(exc, StorageUnavailableError):
                raise
            raise StorageUnavailableError(
                "PostgreSQL TLS transport attestation unavailable"
            ) from exc

    def health_report(self) -> dict[str, Any]:
        report = super().health_report()
        report.update(
            tls_required=True,
            tls_verified=False,
            tls_version="",
            tls_cipher="",
            tcp_transport=False,
            plaintext_connection_allowed=False,
            certificate_hostname_verification_required=True,
            client_sslmode_required="verify-full",
            sslrootcert_required=True,
        )
        if report["state"] != HEALTHY:
            return report

        conn = None
        try:
            conn = self._connection()
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT s.ssl,s.version,s.cipher,"
                    "inet_client_addr() IS NOT NULL "
                    "FROM pg_stat_ssl s WHERE s.pid=pg_backend_pid()"
                )
                row = cur.fetchone()
            conn.rollback()

            tls_ok = bool(
                row
                and row[0] is True
                and str(row[1] or "").strip()
                and str(row[2] or "").strip()
                and row[3] is True
            )
            report.update(
                state=HEALTHY if tls_ok else FAILED,
                tls_verified=tls_ok,
                tls_version=str(row[1]) if row else "",
                tls_cipher=str(row[2]) if row else "",
                tcp_transport=bool(row and row[3]),
            )
            return report
        except Exception:
            report["state"] = FAILED
            return report
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass


class TlsDirectLoginAuditedPostgresChatStoreCiV1(
    DirectLoginAuditedPostgresChatStoreCiV1
):
    """AionChatStore over a directly authenticated TLS-only CI connection."""

    def __init__(
        self,
        backend: TlsDirectLoginAuditedPostgresBackendCiV1,
        *,
        cursor_signing_key: bytes,
    ):
        if not isinstance(
            backend,
            TlsDirectLoginAuditedPostgresBackendCiV1,
        ):
            raise TypeError("TlsDirectLoginAuditedPostgresBackendCiV1 required")
        super().__init__(
            backend,
            cursor_signing_key=cursor_signing_key,
        )


def tls_direct_connection_policy() -> dict[str, Any]:
    return {
        "schema": "ATLASQUANT_AION_CHAT_TLS_DIRECT_APP_ROLE_CI_V1",
        "direct_login_role": CI_DIRECT_APP_ROLE,
        "environment_allowed": ["CI", "TEST"],
        "production_allowed": False,
        "production_connection_allowed": False,
        "connection_factory_injected": True,
        "dsn_read_by_store": False,
        "password_read_by_store": False,
        "environment_read_by_store": False,
        "provider_secret_read_by_store": False,
        "tls_required": True,
        "certificate_verification_required": True,
        "hostname_verification_required": True,
        "plaintext_allowed": False,
        "tcp_transport_required": True,
        "set_role_used": False,
        "direct_login_identity_required": True,
        "forced_rls_required": True,
        "provider_called": False,
        "billing_executed": False,
        "deploy_executed": False,
        "worker_armed": False,
        "external_action_executed": False,
        "core_checkpoint_write": False,
    }


__all__ = [
    "TlsDirectLoginAuditedPostgresBackendCiV1",
    "TlsDirectLoginAuditedPostgresChatStoreCiV1",
    "tls_direct_connection_policy",
]
