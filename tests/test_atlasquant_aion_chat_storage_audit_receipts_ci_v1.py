from __future__ import annotations

import os
import re
import unittest

import psycopg

from aion_chat.models import (
    Attachment,
    ContextSummary,
    ConversationCheckpoint,
    Message,
    Scope,
)
from aion_chat.store import StorageUnavailableError
from atlasquant_aion_chat_postgres_store_adapter_fake_v1 import (
    CommitOutcomeUnknownError,
)
import atlasquant_aion_chat_postgres_migration_rls_restore_ci_v1 as migration
import atlasquant_aion_chat_production_schema_binding_ci_v1 as binding
import atlasquant_aion_chat_storage_audit_receipts_ci_v1 as audit


class StorageAuditReceiptsCiV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        dsn = str(os.environ.get("AION_CHAT_AUDIT_CI_PG_DSN") or "").strip()
        if not dsn:
            raise RuntimeError("AION_CHAT_AUDIT_CI_PG_DSN required")
        if "localhost" not in dsn and "127.0.0.1" not in dsn:
            raise RuntimeError("audit CI PostgreSQL must be loopback-only")
        cls._dsn = dsn

        def connect():
            return psycopg.connect(
                cls._dsn,
                autocommit=False,
                connect_timeout=5,
                application_name="atlasquant-aion-storage-audit-ci",
            )

        cls.connect = staticmethod(connect)
        cls._reset_all()
        result = migration.apply_migration(cls.connect, environment="CI")
        if result["state"] != migration.APPLIED:
            raise RuntimeError(result)
        cls._create_app_role()

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
                cur.execute(
                    "SELECT 1 FROM pg_roles WHERE rolname=%s",
                    (binding.CI_APP_ROLE,),
                )
                if cur.fetchone():
                    cur.execute(f"DROP OWNED BY {binding.CI_APP_ROLE}")
                    cur.execute(f"DROP ROLE {binding.CI_APP_ROLE}")
        finally:
            conn.close()

    @classmethod
    def _create_app_role(cls):
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
                        f"GRANT SELECT,INSERT "
                        f"ON {migration.SCHEMA}.{table} "
                        f"TO {binding.CI_APP_ROLE}"
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

        self.backend = audit.AuditedProductionSchemaPostgresBackendCiV1(
            self.connect,
            environment="CI",
        )
        self.store = audit.AuditedProductionSchemaPostgresChatStoreCiV1(
            self.backend,
            cursor_signing_key=b"atlasquant-storage-audit-ci-cursor-key-v1",
        )
        self.scope = Scope("mikael", "atlasquant-owner", "central")
        self.other_scope = Scope("other", "atlasquant-owner", "central")
        self.conversation = self.store.create_conversation(
            self.scope,
            title="TOP SECRET TITLE MUST NEVER ENTER AUDIT",
            metadata={"tags": ["audit-ci"]},
        )

    def message(self, content="ULTRA SECRET BODY", key="audit-turn-1"):
        return Message(
            conversation_id=self.conversation.id,
            role="user",
            content=content,
            metadata={"idempotency_key": key},
        )

    def receipts(self):
        return self.backend.list_audit_receipts(self.scope, limit=200)

    def test_create_append_and_idempotent_replay_emit_atomic_receipts(self):
        first = self.store.append_message(
            self.scope,
            self.message("sensitive body one", "same-key"),
        )
        duplicate = self.store.append_message(
            self.scope,
            self.message("different sensitive body", "same-key"),
        )
        self.assertEqual(first.id, duplicate.id)

        receipts = self.receipts()
        operations = [row["operation"] for row in receipts]
        self.assertEqual(
            operations,
            [
                "CONVERSATION_CREATE",
                "MESSAGE_APPEND",
                "MESSAGE_APPEND_IDEMPOTENT",
            ],
        )
        self.assertEqual(receipts[-1]["result"], "ALREADY_COMMITTED")
        for row in receipts:
            self.assertRegex(row["evidence_digest"], r"^sha256:[0-9a-f]{64}$")
            self.assertEqual(row["actor_id"], self.scope.owner_id)

    def test_unknown_commit_has_committed_audit_receipt_and_reconciles(self):
        self.backend.commit_outcome_unknown_once = True
        with self.assertRaises(CommitOutcomeUnknownError):
            self.store.append_message(
                self.scope,
                self.message("unknown outcome secret", "unknown-key"),
            )

        receipts = self.receipts()
        self.assertEqual(
            [row["operation"] for row in receipts],
            ["CONVERSATION_CREATE", "MESSAGE_APPEND"],
        )
        reconciled = self.store.reconcile_message_idempotency(
            self.scope,
            self.conversation.id,
            "unknown-key",
        )
        self.assertIsNotNone(reconciled)
        self.assertEqual(reconciled.content, "unknown outcome secret")
        self.assertEqual(len(self.receipts()), 2)

    def test_mutation_and_audit_roll_back_together_when_audit_fails(self):
        class FailingAuditBackend(
            audit.AuditedProductionSchemaPostgresBackendCiV1
        ):
            def _audit_mutation(self, *args, **kwargs):
                super()._audit_mutation(*args, **kwargs)
                raise RuntimeError("synthetic audit failure")

        failing_backend = FailingAuditBackend(self.connect, environment="CI")
        failing_store = audit.AuditedProductionSchemaPostgresChatStoreCiV1(
            failing_backend,
            cursor_signing_key=b"atlasquant-failing-audit-ci-cursor-key-v1",
        )

        with self.assertRaises(StorageUnavailableError):
            failing_store.append_message(
                self.scope,
                self.message("must roll back", "rollback-key"),
            )

        page = self.store.list_messages(
            self.scope,
            self.conversation.id,
            page_size=10,
        )
        self.assertEqual(page.items, [])
        self.assertEqual(
            [row["operation"] for row in self.receipts()],
            ["CONVERSATION_CREATE"],
        )

    def test_all_supported_mutations_emit_expected_receipt_classes(self):
        archived = self.store.archive_conversation(
            self.scope,
            self.conversation.id,
        )
        self.assertTrue(archived.archived)

        message = self.store.append_message(
            self.scope,
            self.message("body not for audit", "all-ops-message"),
        )

        attachment = Attachment(
            conversation_id=self.conversation.id,
            name="private-client-contract.txt",
            mime_type="text/plain",
            size=7,
            digest="b" * 64,
            storage_reference=("b" * 64) + ".blob",
        )
        self.store.add_attachment_metadata(self.scope, attachment)

        checkpoint = ConversationCheckpoint(
            conversation_id=self.conversation.id,
            through_sequence=message.sequence,
        )
        self.store.save_checkpoint(self.scope, checkpoint)

        summary = ContextSummary(
            conversation_id=self.conversation.id,
            through_sequence=message.sequence,
            content="private summary text",
            source_message_ids=[message.id],
        )
        self.store.save_context_summary(self.scope, summary)

        operations = [row["operation"] for row in self.receipts()]
        self.assertEqual(
            operations,
            [
                "CONVERSATION_CREATE",
                "CONVERSATION_UPDATE",
                "MESSAGE_APPEND",
                "ATTACHMENT_METADATA_ADD",
                "CHECKPOINT_SAVE",
                "SUMMARY_SAVE",
            ],
        )

    def test_raw_audit_rows_do_not_contain_user_content_titles_or_attachment_names(self):
        message_secret = "MESSAGE-CONTENT-SHOULD-NOT-APPEAR-93741"
        title_secret = "TOP SECRET TITLE MUST NEVER ENTER AUDIT"
        attachment_secret = "CLIENT-PASSWORDS-DO-NOT-AUDIT.txt"

        self.store.append_message(
            self.scope,
            self.message(message_secret, "content-free-key"),
        )
        self.store.add_attachment_metadata(
            self.scope,
            Attachment(
                conversation_id=self.conversation.id,
                name=attachment_secret,
                mime_type="text/plain",
                size=9,
                digest="c" * 64,
                storage_reference=("c" * 64) + ".blob",
            ),
        )

        conn = self.connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT operation,actor_id,result,evidence_digest "
                    f"FROM {migration.SCHEMA}.access_audit "
                    "ORDER BY created_at,id"
                )
                raw = repr(cur.fetchall())
            conn.rollback()
        finally:
            conn.close()

        self.assertNotIn(message_secret, raw)
        self.assertNotIn(title_secret, raw)
        self.assertNotIn(attachment_secret, raw)
        self.assertNotIn("content-free-key", raw)

    def test_audit_receipts_are_scope_bound_by_rls(self):
        self.store.append_message(
            self.scope,
            self.message("owner only", "owner-only"),
        )
        self.assertEqual(
            self.backend.list_audit_receipts(self.other_scope),
            [],
        )

    def test_application_role_cannot_update_or_delete_audit_rows(self):
        receipt = self.receipts()[0]
        conn = self.backend._connection()
        try:
            self.backend._bind_scope(conn, self.scope)
            with conn.cursor() as cur:
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    cur.execute(
                        f"UPDATE {migration.SCHEMA}.access_audit "
                        "SET result='MUTATED' WHERE id=%s",
                        (receipt["id"],),
                    )
            conn.rollback()
        finally:
            conn.close()

        conn = self.backend._connection()
        try:
            self.backend._bind_scope(conn, self.scope)
            with conn.cursor() as cur:
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    cur.execute(
                        f"DELETE FROM {migration.SCHEMA}.access_audit "
                        "WHERE id=%s",
                        (receipt["id"],),
                    )
            conn.rollback()
        finally:
            conn.close()

    def test_audit_evidence_contract_rejects_content_bearing_or_extra_keys(self):
        with self.assertRaises(ValueError):
            audit._evidence_digest(
                operation="MESSAGE_APPEND",
                resource_type="message",
                resource_id="m-1",
                result="COMMITTED",
                evidence={
                    "conversation_id": "c-1",
                    "message_id": "m-1",
                    "sequence": 1,
                    "idempotency_key": "k-1",
                    "content": "must never be accepted",
                },
            )

        with self.assertRaises(ValueError):
            audit._evidence_digest(
                operation="UNKNOWN_OPERATION",
                resource_type="message",
                resource_id="m-1",
                result="COMMITTED",
                evidence={},
            )

    def test_receipt_limit_is_bounded(self):
        with self.assertRaises(ValueError):
            self.backend.list_audit_receipts(self.scope, limit=0)
        with self.assertRaises(ValueError):
            self.backend.list_audit_receipts(self.scope, limit=201)

    def test_policy_has_zero_production_authority(self):
        policy = audit.storage_audit_policy()
        self.assertTrue(policy["atomic_with_mutation"])
        self.assertTrue(policy["content_free"])
        self.assertFalse(policy["audit_update_allowed"])
        self.assertFalse(policy["audit_delete_allowed"])
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
