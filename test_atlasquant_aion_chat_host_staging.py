from __future__ import annotations

import os
from pathlib import Path
import socket
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from atlasquant_aion_chat_host_staging import (
    DIRECTORY_KEY,
    FLAG,
    SCHEMA,
    TENANT_KEY,
    WORKSPACE_KEY,
    build_staged_host_binding,
    close_staged_host_store,
)


def access():
    return {
        "allowed": True,
        "mode": "AUTHENTICATED",
        "reason": "OK",
        "role": "ADMIN",
        "session": {
            "username": "mikael",
            "role": "ADMIN",
            "permissions": [
                "app:read",
                "aion:admin",
                "aion:checkpoint",
            ],
            "credential_fingerprint": "host-staging-fingerprint",
            "authenticated_at": 1.0,
            "last_seen": 1.0,
        },
    }


def config(root, *, enabled=True):
    return {
        FLAG: "true" if enabled else "false",
        TENANT_KEY: "tenant-staging",
        WORKSPACE_KEY: "aion-staging",
        DIRECTORY_KEY: str(root),
    }


class StagedHostFeatureGateTests(unittest.TestCase):
    def test_flag_off_returns_none_without_constructing_runtime(self):
        with tempfile.TemporaryDirectory() as raw:
            with patch(
                "atlasquant_aion_chat_host_staging.build_staged_runtime_context",
                side_effect=AssertionError("runtime must not be built"),
            ):
                out = build_staged_host_binding(
                    {},
                    access(),
                    config=config(Path(raw), enabled=False),
                    environment="STAGING",
                )
            self.assertIsNone(out)

    def test_production_rejects_before_store_or_runtime(self):
        with tempfile.TemporaryDirectory() as raw:
            with (
                patch(
                    "atlasquant_aion_chat_host_staging.get_or_create_staged_store",
                    side_effect=AssertionError("store must not open"),
                ),
                patch(
                    "atlasquant_aion_chat_host_staging.build_staged_runtime_context",
                    side_effect=AssertionError("runtime must not build"),
                ),
            ):
                with self.assertRaisesRegex(
                    PermissionError,
                    "non-production",
                ):
                    build_staged_host_binding(
                        {},
                        access(),
                        config=config(Path(raw)),
                        environment="PRODUCTION",
                    )

    def test_open_preview_and_non_admin_access_cannot_activate_staged_host(self):
        with tempfile.TemporaryDirectory() as raw:
            for mutate in ("open", "preview", "user"):
                candidate = access()
                if mutate == "open":
                    candidate["mode"] = "OPEN"
                elif mutate == "preview":
                    candidate["mode"] = "PREVIEW"
                else:
                    candidate["role"] = "USER"
                    candidate["session"]["role"] = "USER"
                with self.subTest(mutate=mutate):
                    with self.assertRaises(PermissionError):
                        build_staged_host_binding(
                            {},
                            candidate,
                            config=config(Path(raw)),
                            environment="STAGING",
                        )

    def test_missing_explicit_scope_or_directory_fails_closed(self):
        with tempfile.TemporaryDirectory() as raw:
            base = config(Path(raw))
            for key in (TENANT_KEY, WORKSPACE_KEY, DIRECTORY_KEY):
                broken = dict(base)
                broken[key] = ""
                with self.subTest(key=key):
                    with self.assertRaises(ValueError):
                        build_staged_host_binding(
                            {},
                            access(),
                            config=broken,
                            environment="STAGING",
                        )

    def test_relative_or_url_directory_is_rejected(self):
        for value in ("relative/staging", "file:/tmp/chat", "https://host/chat"):
            cfg = config(Path("/tmp"))
            cfg[DIRECTORY_KEY] = value
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    build_staged_host_binding(
                        {},
                        access(),
                        config=cfg,
                        environment="STAGING",
                    )


class StagedHostLifecycleTests(unittest.TestCase):
    def test_complete_binding_is_scoped_local_and_reopens_same_sqlite(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            session = {}
            first = build_staged_host_binding(
                session,
                access(),
                config=config(root),
                environment="STAGING",
            )
            self.assertEqual(first["schema"], SCHEMA)
            self.assertEqual(first["state"], "STAGED_BOUND")
            self.assertEqual(first["scope"].owner_id, "mikael")
            self.assertEqual(first["scope"].tenant_id, "tenant-staging")
            self.assertEqual(first["scope"].workspace_id, "aion-staging")
            self.assertTrue(first["local_sqlite_only"])
            self.assertFalse(first["production_store_activated"])
            self.assertFalse(first["provider_called"])
            self.assertFalse(first["network_called"])
            self.assertFalse(first["external_action_executed"])
            self.assertFalse(first["grants_authority"])
            self.assertTrue(
                first["staging_store_path"].startswith(str(root))
            )
            self.assertTrue(
                first["staging_store_path"].endswith(".sqlite3")
            )

            store = first["store"]
            scope = first["scope"]
            conversation = store.create_conversation(scope, "Host staging")
            cid = conversation.id
            self.assertEqual(
                store.get_conversation(scope, cid).title,
                "Host staging",
            )

            self.assertTrue(close_staged_host_store(session, scope))
            second = build_staged_host_binding(
                session,
                access(),
                config=config(root),
                environment="STAGING",
            )
            self.assertIsNot(store, second["store"])
            self.assertEqual(
                second["store"].get_conversation(scope, cid).id,
                cid,
            )
            close_staged_host_store(session, scope)

    def test_same_session_reuses_exact_scoped_handle(self):
        with tempfile.TemporaryDirectory() as raw:
            session = {}
            first = build_staged_host_binding(
                session,
                access(),
                config=config(Path(raw)),
                environment="STAGING",
            )
            second = build_staged_host_binding(
                session,
                access(),
                config=config(Path(raw)),
                environment="STAGING",
            )
            self.assertIs(first["store"], second["store"])
            close_staged_host_store(session, first["scope"])

    def test_staging_binding_build_has_no_network_provider_or_subprocess(self):
        with tempfile.TemporaryDirectory() as raw:
            attempts = []

            def forbidden(*args, **kwargs):
                attempts.append((args, kwargs))
                raise AssertionError("external side effect attempted")

            with (
                patch("requests.sessions.Session.request", side_effect=forbidden),
                patch.object(socket, "socket", side_effect=forbidden),
                patch.object(subprocess, "Popen", side_effect=forbidden),
                patch.object(os, "system", side_effect=forbidden),
            ):
                session = {}
                out = build_staged_host_binding(
                    session,
                    access(),
                    config=config(Path(raw)),
                    environment="STAGING",
                )
            self.assertEqual(out["state"], "STAGED_BOUND")
            self.assertEqual(attempts, [])
            close_staged_host_store(session, out["scope"])


class HostWiringSourceTests(unittest.TestCase):
    def test_real_app_imports_staged_host_only_inside_aion_render_path(self):
        source = Path("usd_macro_pro_v4_cloud.py").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            'if str(requested or "").strip().casefold() == "aion":',
            source,
        )
        self.assertIn(
            "from atlasquant_aion_chat_host_staging import (",
            source,
        )
        self.assertIn(
            "build_streamlit_staged_binding(",
            source,
        )
        self.assertIn(
            "aion_chat_binding=_aion_chat_binding",
            source,
        )
        prefix = source[: source.index("def _render_atlasquant_central_hub")]
        self.assertNotIn(
            "from atlasquant_aion_chat_host_staging import",
            prefix,
        )

    def test_central_hub_threads_binding_only_to_aion_reference_workspace(self):
        source = Path("atlasquant_central_hub_ui.py").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            'if area == "aion" and aion_chat_binding is not None:',
            source,
        )
        self.assertIn(
            "aion_chat_binding=dict(aion_chat_binding)",
            source,
        )
        self.assertIn(
            "render_reference_workspace(st, access, area)",
            source,
        )


if __name__ == "__main__":
    unittest.main()
