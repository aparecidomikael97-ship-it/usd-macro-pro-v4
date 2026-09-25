from __future__ import annotations

import unittest

from atlasquant_aion_vault import (
    default_vault,
    new_vault_entry,
    normalize_vault,
    upsert_vault_entry,
    vault_export_manifest,
    vault_summary,
)


class AtlasQuantAionVaultTests(unittest.TestCase):
    def test_vault_never_allows_plaintext_secret_metadata(self):
        with self.assertRaises(ValueError):
            new_vault_entry(
                "provider-secret",
                kind="SECRET_REF",
                backend="RENDER_SECRET",
                locator_ref="OPENAI_API_KEY",
                metadata={"api_key": "should-not-be-here"},
            )

    def test_vault_rejects_obvious_secret_value_as_reference(self):
        with self.assertRaises(ValueError):
            new_vault_entry(
                "bad-secret",
                kind="SECRET_REF",
                backend="ENVIRONMENT",
                locator_ref="sk-this-is-a-value-not-a-ref",
            )

    def test_secret_reference_is_metadata_only(self):
        entry = new_vault_entry(
            "openai-key-ref",
            kind="SECRET_REF",
            backend="RENDER_SECRET",
            locator_ref="OPENAI_API_KEY",
            label="OpenAI key slot",
        )
        self.assertFalse(entry["contains_plaintext_secret"])
        self.assertFalse(entry["mutable_by_aion_without_guardian"])

    def test_checkpoint_backup_reference_is_versioned(self):
        entry = new_vault_entry(
            "checkpoint-master-backup",
            kind="CHECKPOINT_BACKUP",
            backend="RUNTIME_DATA",
            locator_ref="dados/aion/checkpoint_master.json",
            content_digest="abcdef123456",
            version="v10",
        )
        vault = default_vault()
        vault["entries"] = upsert_vault_entry(vault["entries"], entry)
        summary = vault_summary(vault)
        self.assertEqual(summary["entries"], 1)
        self.assertEqual(summary["by_kind"]["CHECKPOINT_BACKUP"], 1)

    def test_export_contains_references_not_secret_values(self):
        entry = new_vault_entry(
            "github-token-ref",
            kind="SECRET_REF",
            backend="GITHUB_ACTIONS_SECRET",
            locator_ref="GITHUB_TOKEN_HISTORICO",
        )
        raw = default_vault()
        raw["entries"] = [entry]
        exported = vault_export_manifest(raw)
        self.assertFalse(exported["contains_secret_values"])
        self.assertEqual(exported["entries"][0]["locator_ref"], "GITHUB_TOKEN_HISTORICO")
        self.assertNotIn("secret_value", exported["entries"][0])

    def test_top_level_secret_like_field_marks_policy_violation(self):
        state = normalize_vault({
            "entries": [],
            "token": "should-not-be-here",
            "backend_connected": True,
        })
        self.assertTrue(state["plaintext_secrets_present"])
        self.assertFalse(state["backend_connected"])
        self.assertFalse(vault_summary(state)["policy_ok"])


if __name__ == "__main__":
    unittest.main()
