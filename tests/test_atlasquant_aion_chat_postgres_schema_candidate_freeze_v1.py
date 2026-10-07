from __future__ import annotations

import os
import unittest

import psycopg

import atlasquant_aion_chat_postgres_migration_rls_restore_ci_v1 as migration
import atlasquant_aion_chat_postgres_schema_candidate_freeze_v1 as freeze


class PostgresSchemaCandidateFreezeV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        dsn = str(os.environ.get("AION_CHAT_SCHEMA_FREEZE_CI_PG_DSN") or "").strip()
        if not dsn:
            raise RuntimeError("AION_CHAT_SCHEMA_FREEZE_CI_PG_DSN required")
        if "localhost" not in dsn and "127.0.0.1" not in dsn:
            raise RuntimeError("schema-freeze CI PostgreSQL must be loopback-only")
        cls._dsn = dsn

        def connect():
            return psycopg.connect(
                cls._dsn,
                autocommit=False,
                connect_timeout=5,
                application_name="atlasquant-aion-schema-freeze-ci",
            )

        cls.connect = staticmethod(connect)

    def setUp(self):
        conn = self.connect()
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(f"DROP SCHEMA IF EXISTS {migration.SCHEMA} CASCADE")
        finally:
            conn.close()
        applied = migration.apply_migration(self.connect, environment="CI")
        self.assertEqual(applied["state"], migration.APPLIED)

    def tearDown(self):
        conn = self.connect()
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(f"DROP SCHEMA IF EXISTS {migration.SCHEMA} CASCADE")
        finally:
            conn.close()

    def test_candidate_artifact_and_runner_hash_are_identical(self):
        report = freeze.candidate_artifact_report()
        self.assertEqual(report["state"], freeze.CANDIDATE_STATE)
        self.assertEqual(
            report["actual_sha256"],
            freeze.CANDIDATE_SHA256,
        )
        self.assertTrue(report["runner_hash_matches_candidate"])
        self.assertTrue(report["immutable_after_candidate_freeze"])
        self.assertTrue(
            report["future_schema_changes_require_new_numbered_migration"]
        )

    def test_exact_migrated_schema_reaches_candidate_freeze_state(self):
        report = freeze.schema_candidate_report(
            self.connect,
            environment="CI",
        )
        self.assertEqual(report["state"], freeze.CANDIDATE_STATE)
        self.assertTrue(report["migration_sha256_verified"])
        self.assertEqual(report["migration_health"], migration.HEALTHY)
        self.assertTrue(report["tables_exact"])
        self.assertTrue(report["access_audit_columns_exact"])
        self.assertTrue(report["required_indexes_present"])
        self.assertEqual(report["missing_tables"], [])
        self.assertEqual(report["extra_tables"], [])
        self.assertEqual(report["missing_indexes"], [])

    def test_missing_resource_audit_index_fails_candidate_closed(self):
        conn = self.connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"DROP INDEX {migration.SCHEMA}.access_audit_scope_resource_v1"
                )
            conn.commit()
        finally:
            conn.close()

        report = freeze.schema_candidate_report(
            self.connect,
            environment="CI",
        )
        self.assertEqual(report["state"], freeze.FAILED)
        self.assertFalse(report["required_indexes_present"])
        self.assertIn(
            "access_audit_scope_resource_v1",
            report["missing_indexes"],
        )

    def test_unexpected_table_fails_exact_schema_closed(self):
        conn = self.connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"CREATE TABLE {migration.SCHEMA}.unreviewed_table("
                    "id TEXT PRIMARY KEY)"
                )
            conn.commit()
        finally:
            conn.close()

        report = freeze.schema_candidate_report(
            self.connect,
            environment="CI",
        )
        self.assertEqual(report["state"], freeze.FAILED)
        self.assertFalse(report["tables_exact"])
        self.assertEqual(report["extra_tables"], ["unreviewed_table"])

    def test_access_audit_column_drift_fails_exact_schema_closed(self):
        conn = self.connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"ALTER TABLE {migration.SCHEMA}.access_audit "
                    "ADD COLUMN unreviewed_payload TEXT"
                )
            conn.commit()
        finally:
            conn.close()

        report = freeze.schema_candidate_report(
            self.connect,
            environment="CI",
        )
        self.assertEqual(report["state"], freeze.FAILED)
        self.assertFalse(report["access_audit_columns_exact"])

    def test_schema_version_or_checksum_drift_fails_closed(self):
        conn = self.connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE {migration.SCHEMA}.schema_migrations "
                    "SET checksum=%s WHERE version=%s",
                    ("0" * 64, migration.MIGRATION_VERSION),
                )
            conn.commit()
        finally:
            conn.close()

        report = freeze.schema_candidate_report(
            self.connect,
            environment="CI",
        )
        self.assertEqual(report["state"], freeze.FAILED)
        self.assertFalse(report["migration_sha256_verified"])

    def test_non_ci_environment_is_rejected(self):
        with self.assertRaises(ValueError):
            freeze.schema_candidate_report(
                self.connect,
                environment="PRODUCTION",
            )

    def test_freeze_policy_has_zero_runtime_authority(self):
        policy = freeze.schema_candidate_freeze_policy()
        self.assertTrue(policy["initial_migration_immutable_after_freeze"])
        self.assertTrue(policy["future_changes_require_new_numbered_migration"])
        self.assertFalse(policy["production_allowed"])
        self.assertFalse(policy["production_migration_executed"])
        for key in (
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
