from __future__ import annotations

import os
import unittest
from uuid import uuid4

import psycopg

from aion_chat.models import Attachment, ContextSummary, ConversationCheckpoint, Message, Scope
from aion_chat.store import StorageUnavailableError
import atlasquant_aion_chat_postgres_migration_rls_restore_ci_v1 as migration
import atlasquant_aion_chat_production_schema_binding_ci_v1 as binding
import atlasquant_aion_chat_storage_audit_receipts_ci_v1 as audit
import atlasquant_aion_chat_retention_controlled_delete_ci_v1 as retention


class RetentionControlledDeleteCiV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        dsn = str(os.environ.get("AION_CHAT_RETENTION_CI_PG_DSN") or "").strip()
        if not dsn:
            raise RuntimeError("AION_CHAT_RETENTION_CI_PG_DSN required")
        if "localhost" not in dsn and "127.0.0.1" not in dsn:
            raise RuntimeError("retention CI PostgreSQL must be loopback-only")
        cls._dsn = dsn

        def connect():
            return psycopg.connect(
                cls._dsn,
                autocommit=False,
                connect_timeout=5,
                application_name="atlasquant-aion-retention-ci",
            )

        cls.connect = staticmethod(connect)
        cls._reset_all()
        result = migration.apply_migration(cls.connect, environment="CI")
        if result["state"] != migration.APPLIED:
            raise RuntimeError(result)
        cls._create_roles()

    @classmethod
    def tearDownClass(cls):
        cls._reset_all()

    @classmethod
    def _reset_all(cls):
        conn = cls.connect()
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(f"DROP SCHEMA IF EXISTS {migration.SCHEMA} CASCADE")
                for role in (binding.CI_APP_ROLE, retention.RETENTION_ROLE):
                    cur.execute(
                        "SELECT 1 FROM pg_roles WHERE rolname=%s",
                        (role,),
                    )
                    if cur.fetchone():
                        cur.execute(f"DROP OWNED BY {role}")
                        cur.execute(f"DROP ROLE {role}")
        finally:
            conn.close()

    @classmethod
    def _create_roles(cls):
        conn = cls.connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"CREATE ROLE {binding.CI_APP_ROLE} "
                    "NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                    "NOINHERIT NOREPLICATION NOBYPASSRLS"
                )
                cur.execute(
                    f"GRANT USAGE ON SCHEMA {migration.SCHEMA} "
                    f"TO {binding.CI_APP_ROLE}"
                )
                cur.execute(
                    f"GRANT SELECT ON {migration.SCHEMA}.schema_meta "
                    f"TO {binding.CI_APP_ROLE}"
                )
                cur.execute(
                    f"GRANT SELECT,INSERT,UPDATE "
                    f"ON {migration.SCHEMA}.conversations "
                    f"TO {binding.CI_APP_ROLE}"
                )
                for table in binding.APPEND_ONLY_TABLES:
                    cur.execute(
                        f"GRANT SELECT,INSERT ON {migration.SCHEMA}.{table} "
                        f"TO {binding.CI_APP_ROLE}"
                    )

                cur.execute(
                    f"CREATE ROLE {retention.RETENTION_ROLE} "
                    "NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                    "NOINHERIT NOREPLICATION NOBYPASSRLS"
                )
                cur.execute(
                    f"GRANT USAGE ON SCHEMA {migration.SCHEMA} "
                    f"TO {retention.RETENTION_ROLE}"
                )
                cur.execute(
                    f"GRANT SELECT,DELETE ON {migration.SCHEMA}.conversations "
                    f"TO {retention.RETENTION_ROLE}"
                )
                for table in retention.CHILD_TABLES:
                    cur.execute(
                        f"GRANT SELECT ON {migration.SCHEMA}.{table} "
                        f"TO {retention.RETENTION_ROLE}"
                    )
                cur.execute(
                    f"GRANT SELECT,INSERT ON {migration.SCHEMA}.access_audit "
                    f"TO {retention.RETENTION_ROLE}"
                )
            conn.commit()
        finally:
            conn.close()

    def setUp(self):
        conn = self.connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"TRUNCATE TABLE "
                    f"{migration.SCHEMA}.access_audit,"
                    f"{migration.SCHEMA}.summaries,"
                    f"{migration.SCHEMA}.checkpoints,"
                    f"{migration.SCHEMA}.attachments,"
                    f"{migration.SCHEMA}.message_idempotency,"
                    f"{migration.SCHEMA}.messages,"
                    f"{migration.SCHEMA}.conversations CASCADE"
                )
            conn.commit()
        finally:
            conn.close()

        self.scope = Scope("mikael", "atlasquant-owner", "central")
        self.other_scope = Scope("other", "atlasquant-owner", "central")
        self.backend = audit.AuditedProductionSchemaPostgresBackendCiV1(
            self.connect,
            environment="CI",
        )
        self.store = audit.AuditedProductionSchemaPostgresChatStoreCiV1(
            self.backend,
            cursor_signing_key=b"atlasquant-retention-seed-store-cursor-key-v1",
        )
        self.retention = retention.ControlledRetentionExecutorCiV1(
            self.connect,
            environment="CI",
        )
        self.conversation = self.store.create_conversation(
            self.scope,
            title="retention target",
            metadata={"tags": ["retention-ci"]},
        )

    @staticmethod
    def approval_digest():
        return "sha256:" + ("a" * 64)

    def request(self, plan, *, request_id=None, conversation_id=None, actor=None):
        return retention.RetentionDeleteRequestV1(
            request_id=request_id or ("delete-" + uuid4().hex),
            conversation_id=conversation_id or self.conversation.id,
            authorized_by=actor or self.scope.owner_id,
            decision=retention.APPROVE_DELETE,
            approval_evidence_digest=self.approval_digest(),
            expected_plan_digest=plan["plan_digest"],
        )

    def archive(self):
        return self.store.archive_conversation(
            self.scope,
            self.conversation.id,
        )

    def seed_children(self):
        message = self.store.append_message(
            self.scope,
            Message(
                conversation_id=self.conversation.id,
                role="user",
                content="private retention body",
                metadata={"idempotency_key": "retention-message-1"},
            ),
        )
        self.store.add_attachment_metadata(
            self.scope,
            Attachment(
                conversation_id=self.conversation.id,
                name="private-retention-file.txt",
                mime_type="text/plain",
                size=10,
                digest="d" * 64,
                storage_reference=("d" * 64) + ".blob",
            ),
        )
        self.store.save_checkpoint(
            self.scope,
            ConversationCheckpoint(
                conversation_id=self.conversation.id,
                through_sequence=message.sequence,
            ),
        )
        self.store.save_context_summary(
            self.scope,
            ContextSummary(
                conversation_id=self.conversation.id,
                through_sequence=message.sequence,
                content="private retention summary",
                source_message_ids=[message.id],
            ),
        )
        return message

    def test_health_proves_separate_minimal_retention_role(self):
        report = self.retention.health_report()
        self.assertEqual(report["state"], retention.READY)
        self.assertTrue(report["least_privilege_role_healthy"])
        self.assertTrue(report["conversation_delete_only"])
        self.assertTrue(report["child_delete_denied"])
        self.assertTrue(report["audit_append_only"])
        self.assertTrue(report["schema_create_denied"])
        self.assertTrue(report["migration_history_denied"])
        self.assertFalse(report["automatic_deletion_enabled"])

    def test_unarchived_conversation_cannot_even_be_planned(self):
        with self.assertRaises(retention.RetentionBlockedError):
            self.retention.plan_delete(
                self.scope,
                self.conversation.id,
            )

    def test_plan_is_content_free_and_counts_scoped_children(self):
        self.seed_children()
        self.archive()
        plan = self.retention.plan_delete(
            self.scope,
            self.conversation.id,
        )
        self.assertEqual(plan["state"], retention.READY)
        self.assertRegex(plan["plan_digest"], r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(plan["counts"]["messages"], 1)
        self.assertEqual(plan["counts"]["message_idempotency"], 1)
        self.assertEqual(plan["counts"]["attachments"], 1)
        self.assertEqual(plan["counts"]["checkpoints"], 1)
        self.assertEqual(plan["counts"]["summaries"], 1)
        self.assertFalse(plan["delete_executed"])
        self.assertNotIn("private", repr(plan).lower())

    def test_stale_plan_fails_closed_and_preserves_conversation(self):
        self.archive()
        plan = self.retention.plan_delete(
            self.scope,
            self.conversation.id,
        )
        self.store.append_message(
            self.scope,
            Message(
                conversation_id=self.conversation.id,
                role="user",
                content="changed after approval plan",
                metadata={"idempotency_key": "stale-plan-message"},
            ),
        )
        with self.assertRaises(retention.StaleRetentionPlanError):
            self.retention.execute_delete(
                self.scope,
                self.request(plan),
            )
        self.assertEqual(
            self.store.get_conversation(
                self.scope,
                self.conversation.id,
            ).id,
            self.conversation.id,
        )

    def test_approval_actor_must_match_trusted_owner_scope(self):
        self.archive()
        plan = self.retention.plan_delete(
            self.scope,
            self.conversation.id,
        )
        with self.assertRaises(retention.RetentionBlockedError):
            self.retention.execute_delete(
                self.scope,
                self.request(plan, actor="delegated-not-yet-authorized"),
            )

    def test_successful_delete_cascades_children_and_preserves_audit_receipt(self):
        self.seed_children()
        self.archive()
        plan = self.retention.plan_delete(
            self.scope,
            self.conversation.id,
        )
        request = self.request(plan)
        result = self.retention.execute_delete(self.scope, request)
        self.assertEqual(result["state"], retention.COMMITTED)
        self.assertEqual(result["audit_receipt_id"], request.request_id)

        with self.assertRaises(LookupError):
            self.store.get_conversation(
                self.scope,
                self.conversation.id,
            )

        conn = self.connect()
        try:
            with conn.cursor() as cur:
                for table in retention.CHILD_TABLES:
                    cur.execute(
                        f"SELECT count(*) FROM {migration.SCHEMA}.{table} "
                        "WHERE owner_id=%s AND tenant_id=%s AND workspace_id=%s "
                        "AND conversation_id=%s",
                        (
                            self.scope.owner_id,
                            self.scope.tenant_id,
                            self.scope.workspace_id,
                            self.conversation.id,
                        ),
                    )
                    self.assertEqual(cur.fetchone()[0], 0, table)

                cur.execute(
                    f"SELECT operation,resource_type,resource_id,result "
                    f"FROM {migration.SCHEMA}.access_audit "
                    "WHERE owner_id=%s AND tenant_id=%s AND workspace_id=%s "
                    "AND id=%s",
                    (
                        self.scope.owner_id,
                        self.scope.tenant_id,
                        self.scope.workspace_id,
                        request.request_id,
                    ),
                )
                receipt = cur.fetchone()
            conn.rollback()
        finally:
            conn.close()

        self.assertEqual(
            receipt,
            (
                "CONVERSATION_DELETE",
                "conversation",
                self.conversation.id,
                retention.COMMITTED,
            ),
        )

    def test_unknown_commit_requires_receipt_reconciliation(self):
        self.archive()
        plan = self.retention.plan_delete(
            self.scope,
            self.conversation.id,
        )
        request = self.request(plan)
        self.retention.commit_outcome_unknown_once = True

        with self.assertRaises(
            retention.RetentionCommitOutcomeUnknownError
        ) as ctx:
            self.retention.execute_delete(self.scope, request)
        self.assertEqual(ctx.exception.request_id, request.request_id)

        reconciled = self.retention.reconcile_delete(
            self.scope,
            request_id=request.request_id,
            conversation_id=self.conversation.id,
        )
        self.assertEqual(reconciled["state"], retention.COMMITTED)
        self.assertTrue(reconciled["receipt_found"])
        self.assertFalse(reconciled["conversation_live"])

        repeated = self.retention.execute_delete(self.scope, request)
        self.assertEqual(repeated["state"], retention.ALREADY_COMMITTED)

    def test_delete_audit_and_delete_rollback_together_on_database_failure(self):
        self.archive()
        plan = self.retention.plan_delete(
            self.scope,
            self.conversation.id,
        )
        request = self.request(plan)

        conn = self.connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE OR REPLACE FUNCTION aion_chat_v1.reject_retention_delete()
                    RETURNS trigger LANGUAGE plpgsql AS $$
                    BEGIN
                      RAISE EXCEPTION 'synthetic retention delete failure';
                    END;
                    $$;
                    """
                )
                cur.execute(
                    f"CREATE TRIGGER reject_retention_delete_v1 "
                    f"BEFORE DELETE ON {migration.SCHEMA}.conversations "
                    "FOR EACH ROW EXECUTE FUNCTION "
                    "aion_chat_v1.reject_retention_delete()"
                )
            conn.commit()
        finally:
            conn.close()

        try:
            with self.assertRaises(StorageUnavailableError):
                self.retention.execute_delete(self.scope, request)
        finally:
            conn = self.connect()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        f"DROP TRIGGER IF EXISTS reject_retention_delete_v1 "
                        f"ON {migration.SCHEMA}.conversations"
                    )
                    cur.execute(
                        "DROP FUNCTION IF EXISTS "
                        "aion_chat_v1.reject_retention_delete()"
                    )
                conn.commit()
            finally:
                conn.close()

        self.assertEqual(
            self.store.get_conversation(
                self.scope,
                self.conversation.id,
            ).id,
            self.conversation.id,
        )

        conn = self.connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT count(*) FROM {migration.SCHEMA}.access_audit "
                    "WHERE owner_id=%s AND tenant_id=%s AND workspace_id=%s "
                    "AND id=%s",
                    (
                        self.scope.owner_id,
                        self.scope.tenant_id,
                        self.scope.workspace_id,
                        request.request_id,
                    ),
                )
                self.assertEqual(cur.fetchone()[0], 0)
            conn.rollback()
        finally:
            conn.close()

    def test_cross_scope_cannot_plan_or_delete_target(self):
        self.archive()
        with self.assertRaises(LookupError):
            self.retention.plan_delete(
                self.other_scope,
                self.conversation.id,
            )

    def test_normal_application_role_still_has_no_delete_privilege(self):
        conn = self.connect()
        try:
            with conn.cursor() as cur:
                cur.execute(f"SET ROLE {binding.CI_APP_ROLE}")
                cur.execute(
                    "SELECT has_table_privilege(current_user,%s,'DELETE')",
                    (f"{migration.SCHEMA}.conversations",),
                )
                self.assertEqual(cur.fetchone(), (False,))
            conn.rollback()
        finally:
            conn.close()

    def test_retention_request_requires_exact_decision_and_digests(self):
        self.archive()
        plan = self.retention.plan_delete(
            self.scope,
            self.conversation.id,
        )
        with self.assertRaises(ValueError):
            retention.RetentionDeleteRequestV1(
                request_id="short",
                conversation_id=self.conversation.id,
                authorized_by=self.scope.owner_id,
                decision=retention.APPROVE_DELETE,
                approval_evidence_digest=self.approval_digest(),
                expected_plan_digest=plan["plan_digest"],
            )
        with self.assertRaises(ValueError):
            retention.RetentionDeleteRequestV1(
                request_id="delete-" + uuid4().hex,
                conversation_id=self.conversation.id,
                authorized_by=self.scope.owner_id,
                decision="DELETE",
                approval_evidence_digest=self.approval_digest(),
                expected_plan_digest=plan["plan_digest"],
            )
        with self.assertRaises(ValueError):
            retention.RetentionDeleteRequestV1(
                request_id="delete-" + uuid4().hex,
                conversation_id=self.conversation.id,
                authorized_by=self.scope.owner_id,
                decision=retention.APPROVE_DELETE,
                approval_evidence_digest="not-a-digest",
                expected_plan_digest=plan["plan_digest"],
            )

    def test_policy_disables_automatic_and_batch_deletion(self):
        policy = retention.retention_policy()
        self.assertFalse(policy["automatic_ttl_enabled"])
        self.assertFalse(policy["batch_delete_enabled"])
        self.assertTrue(policy["single_conversation_only"])
        self.assertTrue(policy["archive_required"])
        self.assertTrue(policy["explicit_approval_required"])
        self.assertTrue(policy["stale_plan_fails_closed"])
        self.assertFalse(policy["normal_application_delete_allowed"])
        self.assertTrue(policy["unknown_commit_requires_reconciliation"])
        self.assertFalse(policy["production_allowed"])
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
