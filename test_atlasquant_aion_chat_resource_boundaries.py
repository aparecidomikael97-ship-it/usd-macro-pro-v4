from __future__ import annotations

import unittest

import atlasquant_aion_chat_workspace_ui as ui
from atlasquant_aion_chat_surface import (
    MAX_ATTACHMENT_NAME,
    MAX_ATTACHMENT_SIZE_BYTES,
    MAX_IN_MEMORY_HISTORY_ENTRIES,
    append_chat_history,
    build_chat_turn,
    normalize_attachment_metadata,
)


ADMIN_CONTEXT = {
    "role": "ADMIN",
    "persona": "admin",
    "experience_mode": "ADVANCED",
    "domain_hint": "admin",
    "tenant_id": "tenant:test",
    "workspace_id": "workspace:aion",
    "actor_id": "mikael",
}


class _HugeHistory:
    """Length is available, iteration must never happen after an over-budget check."""

    def __len__(self):
        return 10_000

    def __iter__(self):
        raise AssertionError("over-budget history was iterated/copied")


class AttachmentBudgetTests(unittest.TestCase):
    def test_metadata_truncation_and_clamping_are_explicit(self):
        rows = normalize_attachment_metadata([{
            "name": "n" * (MAX_ATTACHMENT_NAME + 50),
            "mime_type": "application/" + ("x" * 200),
            "kind": "K" * 80,
            "size_bytes": MAX_ATTACHMENT_SIZE_BYTES + 999,
            "sha256": "a" * 70,
            "content": "UNTRUSTED_BODY",
        }])
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(len(row["name"]), MAX_ATTACHMENT_NAME)
        self.assertTrue(row["name_truncated"])
        self.assertTrue(row["mime_type_truncated"])
        self.assertTrue(row["kind_truncated"])
        self.assertTrue(row["size_clamped"])
        self.assertTrue(row["sha256_invalid"])
        self.assertTrue(row["metadata_truncated"])
        self.assertEqual(row["sha256"], "")
        self.assertTrue(row["content_supplied_but_not_accepted"])
        self.assertFalse(row["content_accepted"])

    def test_bool_size_is_not_silently_coerced_to_one_byte(self):
        row = normalize_attachment_metadata([{"size_bytes": True}])[0]
        self.assertEqual(row["size_bytes"], 0)
        self.assertTrue(row["size_clamped"])

    def test_attachment_count_overflow_blocks_chat_turn(self):
        out = build_chat_turn(
            "status geral",
            context=ADMIN_CONTEXT,
            attachments=[
                {"name": f"file-{index}.txt", "size_bytes": 1}
                for index in range(17)
            ],
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertEqual(out["reason"], "ATTACHMENT_BUDGET_EXCEEDED")
        self.assertEqual(out["attachment_budget"]["received_count"], 17)
        self.assertEqual(out["attachment_budget"]["accepted_count"], 16)
        self.assertTrue(out["attachment_budget"]["overflow"])
        self.assertFalse(out["may_execute"])
        self.assertFalse(out["execution_authorized"])
        self.assertFalse(out["external_action_executed"])


class InMemoryHistoryBudgetTests(unittest.TestCase):
    def _turn(self):
        return build_chat_turn("status geral", context=ADMIN_CONTEXT)

    def test_oversized_history_fails_before_iteration_or_copy(self):
        with self.assertRaisesRegex(ValueError, "durable chat store required"):
            append_chat_history(_HugeHistory(), self._turn())

    def test_exact_budget_is_allowed_without_dropping_rows(self):
        existing = [
            {"role": "user", "content": f"row-{index}"}
            for index in range(MAX_IN_MEMORY_HISTORY_ENTRIES - 2)
        ]
        out = append_chat_history(
            existing,
            self._turn(),
            assistant_text="resposta",
        )
        self.assertEqual(
            out["entry_count"],
            MAX_IN_MEMORY_HISTORY_ENTRIES,
        )
        self.assertEqual(out["history_budget"]["rows_dropped"], 0)
        self.assertEqual(out["history_budget"]["remaining_entries"], 0)
        self.assertTrue(
            out["history_budget"]["durable_store_required_at_limit"]
        )
        self.assertEqual(existing[0]["content"], "row-0")
        self.assertEqual(
            existing[-1]["content"],
            f"row-{MAX_IN_MEMORY_HISTORY_ENTRIES - 3}",
        )

    def test_over_budget_append_fails_without_mutating_existing_history(self):
        existing = [
            {"role": "user", "content": f"row-{index}"}
            for index in range(MAX_IN_MEMORY_HISTORY_ENTRIES - 1)
        ]
        before = list(existing)
        with self.assertRaisesRegex(ValueError, "durable chat store required"):
            append_chat_history(
                existing,
                self._turn(),
                assistant_text="resposta",
            )
        self.assertEqual(existing, before)


class SessionFallbackBudgetTests(unittest.TestCase):
    def _chat(self):
        return ui.session_chat({}, ADMIN_CONTEXT)

    def _event(self, chat, **overrides):
        event = {
            "conversation_id": chat["conversation_id"],
            "request_id": "request-1",
            "message": "status geral",
            "attachments": [],
        }
        event.update(overrides)
        return event

    def test_session_fallback_fails_closed_at_memory_budget(self):
        chat = self._chat()
        chat["entries"] = [
            {"role": "user", "content": "existing"}
            for _ in range(MAX_IN_MEMORY_HISTORY_ENTRIES - 1)
        ]
        before_entries = list(chat["entries"])
        with self.assertRaisesRegex(ValueError, "histórico durável"):
            ui.submit_turn(chat, self._event(chat), ADMIN_CONTEXT)
        self.assertEqual(chat["entries"], before_entries)
        self.assertEqual(chat["turns"], {})
        self.assertEqual(chat["requests"], set())

    def test_session_view_exposes_budget_without_dropping_rows(self):
        chat = self._chat()
        for index in range(10):
            ui.submit_turn(
                chat,
                self._event(chat, request_id=f"request-{index}"),
                ADMIN_CONTEXT,
            )
        data = ui.view_data(chat)
        self.assertEqual(data["session_budget"]["used_entries"], 20)
        self.assertEqual(data["session_budget"]["rows_dropped"], 0)
        self.assertTrue(
            data["session_budget"]["durable_history_is_product_source"]
        )

    def test_ui_rejects_oversized_metadata_instead_of_silent_truncation(self):
        chat = self._chat()
        with self.assertRaisesRegex(ValueError, "Nome de anexo"):
            ui.submit_turn(
                chat,
                self._event(
                    chat,
                    attachments=[{
                        "filename": "x" * (MAX_ATTACHMENT_NAME + 1),
                        "mime_type": "text/plain",
                        "size_bytes": 1,
                    }],
                ),
                ADMIN_CONTEXT,
            )
        self.assertEqual(chat["entries"], [])

    def test_ui_rejects_oversized_file_size(self):
        chat = self._chat()
        with self.assertRaisesRegex(ValueError, "Tamanho de anexo"):
            ui.submit_turn(
                chat,
                self._event(
                    chat,
                    attachments=[{
                        "filename": "x.txt",
                        "mime_type": "text/plain",
                        "size_bytes": MAX_ATTACHMENT_SIZE_BYTES + 1,
                    }],
                ),
                ADMIN_CONTEXT,
            )
        self.assertEqual(chat["entries"], [])


if __name__ == "__main__":
    unittest.main()
