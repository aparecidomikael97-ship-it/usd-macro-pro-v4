from __future__ import annotations

import os
from pathlib import Path
import unittest
from unittest.mock import patch

from aion_chat.models import Scope
import atlasquant_aion_chat_render_production_host_v1 as host
import atlasquant_aion_chat_render_production_composition_v1 as production


class _Secrets(dict):
    def get(self, key, default=None):
        return super().get(key, default)


class _FakeStreamlit:
    def __init__(self, secrets=None):
        self.secrets = _Secrets(secrets or {})


class RenderProductionHostV1Tests(unittest.TestCase):
    def access(self, *, role="ADMIN"):
        return {
            "allowed": True,
            "mode": "AUTHENTICATED",
            "role": role,
            "session": {
                "username": "mikael",
                "role": role,
                "permissions": [
                    "app:read",
                    "admin:read",
                    "aion:admin",
                    "aion:checkpoint",
                ],
                "credential_fingerprint": "owner-fingerprint-v1",
            },
        }

    def config(self, **updates):
        values = {
            production.ENABLED_KEY: "true",
            production.HOST_KEY: "dpg-private-render-host",
            production.PORT_KEY: "5432",
            production.DATABASE_KEY: production.EXPECTED_DATABASE,
            production.USER_KEY: production.EXPECTED_USER,
            production.PASSWORD_KEY: "x" * 48,
            production.SSLMODE_KEY: "require",
            production.CURSOR_KEY: "c" * 48,
            host.TENANT_KEY: "atlasquant-owner",
            host.WORKSPACE_KEY: "central",
        }
        values.update(updates)
        return values

    def test_flag_off_returns_none_without_touching_store(self):
        with patch.object(host, "build_production_chat_store") as builder:
            result = host.build_production_host_binding(
                self.access(),
                config={production.ENABLED_KEY: "false"},
                environment="RUNTIME",
            )
        self.assertIsNone(result)
        builder.assert_not_called()

    def test_wrong_environment_fails_closed_before_store(self):
        with patch.object(host, "build_production_chat_store") as builder:
            with self.assertRaises(PermissionError):
                host.build_production_host_binding(
                    self.access(),
                    config=self.config(),
                    environment="LOCAL",
                )
        builder.assert_not_called()

    def test_authenticated_owner_scope_binds_production_store(self):
        sentinel_store = object()
        storage_binding = {
            "state": "PRODUCTION_STORE_BOUND",
            "health": {"state": "healthy"},
        }
        with patch.object(
            host,
            "build_production_chat_store",
            return_value=(sentinel_store, storage_binding),
        ) as builder:
            result = host.build_production_host_binding(
                self.access(),
                config=self.config(),
                environment="RUNTIME",
            )

        self.assertEqual(result["state"], "PRODUCTION_BOUND")
        self.assertIs(result["store"], sentinel_store)
        self.assertEqual(
            result["scope"],
            Scope("mikael", "atlasquant-owner", "central"),
        )
        self.assertTrue(result["production_store_activated"])
        self.assertFalse(result["provider_called"])
        self.assertFalse(result["worker_armed"])
        self.assertFalse(result["external_action_executed"])
        self.assertFalse(result["core_checkpoint_write"])
        self.assertEqual(
            result["runtime_context"]["host_mode"],
            "RENDER_PRODUCTION_PERSISTENCE",
        )
        self.assertFalse(result["runtime_context"]["provider_enabled"])
        self.assertFalse(result["runtime_context"]["worker_enabled"])
        builder.assert_called_once()

        result_text = repr(result)
        self.assertNotIn(self.config()[production.PASSWORD_KEY], result_text)
        self.assertNotIn(self.config()[production.CURSOR_KEY], result_text)

    def test_non_admin_or_missing_scope_config_fails_closed(self):
        with patch.object(host, "build_production_chat_store") as builder:
            with self.assertRaises(PermissionError):
                host.build_production_host_binding(
                    self.access(role="USER"),
                    config=self.config(),
                    environment="RUNTIME",
                )
            with self.assertRaises(ValueError):
                host.build_production_host_binding(
                    self.access(),
                    config=self.config(**{host.TENANT_KEY: ""}),
                    environment="RUNTIME",
                )
        builder.assert_not_called()

    def test_streamlit_reader_reads_only_approved_keys(self):
        values = self.config()
        values["UNRELATED_SECRET"] = "must-not-be-read"
        st = _FakeStreamlit(values)

        with patch.dict(os.environ, {}, clear=True):
            result = host.streamlit_production_config(st)

        expected = {
            production.ENABLED_KEY,
            production.HOST_KEY,
            production.PORT_KEY,
            production.DATABASE_KEY,
            production.USER_KEY,
            production.PASSWORD_KEY,
            production.SSLMODE_KEY,
            production.CURSOR_KEY,
            host.TENANT_KEY,
            host.WORKSPACE_KEY,
        }
        self.assertEqual(set(result), expected)
        self.assertNotIn("UNRELATED_SECRET", result)

    def test_streamlit_flag_off_never_builds_store(self):
        st = _FakeStreamlit({production.ENABLED_KEY: "false"})
        with patch.object(host, "build_production_chat_store") as builder:
            result = host.build_streamlit_production_binding(
                st,
                self.access(),
                environment="RUNTIME",
            )
        self.assertIsNone(result)
        builder.assert_not_called()

    def test_real_shell_prefers_production_then_staging_then_default(self):
        source = Path("usd_macro_pro_v4_cloud.py").read_text(encoding="utf-8")
        production_marker = "build_streamlit_production_binding"
        staging_marker = "build_streamlit_staged_binding"
        default_marker = "Preserve the canonical default path byte-for-byte"

        self.assertIn(production_marker, source)
        self.assertIn(staging_marker, source)
        self.assertIn(default_marker, source)
        self.assertLess(
            source.index(production_marker),
            source.index(staging_marker),
        )
        self.assertLess(
            source.index(staging_marker),
            source.index(default_marker),
        )


if __name__ == "__main__":
    unittest.main()
