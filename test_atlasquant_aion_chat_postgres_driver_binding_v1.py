from __future__ import annotations

import inspect
import unittest

import psycopg

import atlasquant_aion_chat_postgres_driver_binding_v1 as binding


class PostgresDriverBindingV1Tests(unittest.TestCase):
    def config(self, **overrides):
        values = {
            "environment": "CI",
            "secret_reference": "AION_CHAT_POSTGRES_SECRET_REF",
        }
        values.update(overrides)
        return binding.DriverBindingConfig(**values)

    def test_pinned_driver_is_importable(self):
        self.assertEqual(psycopg.__version__, "3.3.6")
        meta = binding.PsycopgDriverBindingV1(self.config()).driver_metadata()
        self.assertEqual(meta["driver"], "psycopg")
        self.assertEqual(meta["driver_version"], "3.3.6")
        self.assertFalse(meta["network_enabled"])
        self.assertFalse(meta["production_credentials_allowed"])

    def test_production_environment_is_forbidden(self):
        with self.assertRaisesRegex(ValueError, "non-production environment required"):
            self.config(environment="PRODUCTION")

    def test_literal_dsn_or_credentials_are_forbidden(self):
        for bad in (
            "postgresql://user:pass@example/db",
            "user=atlas password=secret",
            "owner@example",
        ):
            with self.subTest(bad=bad):
                with self.assertRaisesRegex(ValueError, "credential material"):
                    self.config(secret_reference=bad)

    def test_tls_private_endpoint_and_timeouts_are_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "internal/private"):
            self.config(endpoint_class="PUBLIC")
        with self.assertRaisesRegex(ValueError, "TLS REQUIRE"):
            self.config(tls_mode="PREFER")
        with self.assertRaisesRegex(ValueError, "connect timeout"):
            self.config(connect_timeout_seconds=60)
        with self.assertRaisesRegex(ValueError, "statement timeout"):
            self.config(statement_timeout_ms=120_000)

    def test_descriptor_contains_reference_but_no_secret_material(self):
        descriptor = binding.PsycopgDriverBindingV1(self.config()).safe_descriptor()
        self.assertEqual(descriptor["secret_reference"], "AION_CHAT_POSTGRES_SECRET_REF")
        self.assertFalse(descriptor["credentials_loaded"])
        self.assertFalse(descriptor["dsn_materialized"])
        self.assertFalse(descriptor["connection_opened"])
        self.assertFalse(descriptor["network_called"])
        self.assertNotIn("password", descriptor)
        self.assertNotIn("dsn", {k for k in descriptor if k != "dsn_materialized"})

    def test_connection_kwargs_are_secret_free(self):
        kwargs = binding.PsycopgDriverBindingV1(self.config()).connection_kwargs_without_secret()
        self.assertEqual(kwargs["sslmode"], "require")
        self.assertEqual(kwargs["autocommit"], False)
        self.assertNotIn("host", kwargs)
        self.assertNotIn("user", kwargs)
        self.assertNotIn("password", kwargs)
        self.assertNotIn("dbname", kwargs)

    def test_connect_is_intentionally_disabled(self):
        driver = binding.PsycopgDriverBindingV1(self.config())
        with self.assertRaises(binding.NetworkDisabledError):
            driver.connect()

    def test_module_has_no_environment_reader_or_psycopg_connect_call(self):
        source = inspect.getsource(binding)
        self.assertNotIn("os.getenv(", source)
        self.assertNotIn("os.environ", source)
        self.assertNotIn("psycopg.connect(", source)
        self.assertNotIn("DATABASE_URL", source)

    def test_policy_is_zero_execution(self):
        policy = binding.binding_policy()
        self.assertEqual(policy["driver_dependency_expected"], "psycopg[binary]==3.3.6")
        for key in (
            "production_credentials_allowed",
            "environment_read",
            "dsn_materialized",
            "connection_opened",
            "sql_executed",
            "network_called",
            "provider_called",
            "billing_executed",
            "deploy_executed",
            "worker_armed",
            "external_action_executed",
            "core_checkpoint_write",
        ):
            self.assertIs(policy[key], False, key)


if __name__ == "__main__":
    unittest.main()
