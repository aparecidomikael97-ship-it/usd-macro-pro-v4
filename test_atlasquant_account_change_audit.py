import unittest

from atlasquant_account_change_audit import (
    account_change_audit_json,
    build_account_change_audit,
)

class AtlasQuantAccountChangeAuditTests(unittest.TestCase):
    def test_manifest_contains_digest_not_credentials(self):
        registry='{"users":{"user.01":{"password_hash":"secret-hash"}}}'
        diff={
            "added":["user.01"],
            "changed":[],
            "destructive_removal_detected":False,
        }
        manifest=build_account_change_audit(
            actor="admin.01",
            diff=diff,
            registry_json=registry,
            generated_at="2026-09-19T01:00:00Z",
        )
        raw=account_change_audit_json(manifest)
        self.assertNotIn("secret-hash",raw)
        self.assertFalse(manifest["contains_password"])
        self.assertFalse(manifest["contains_password_hash"])
        self.assertFalse(manifest["automatic_apply"])
        self.assertEqual(len(manifest["registry_sha256"]),64)

    def test_destructive_change_is_rejected(self):
        with self.assertRaises(ValueError):
            build_account_change_audit(
                actor="admin.01",
                diff={"added":[],"changed":[],"destructive_removal_detected":True},
                registry_json='{"users":{}}',
                generated_at="2026-09-19T01:00:00Z",
            )

    def test_invalid_actor_or_change_item_fails_closed(self):
        with self.assertRaises(ValueError):
            build_account_change_audit(
                actor="../root",
                diff={"added":[],"changed":[],"destructive_removal_detected":False},
                registry_json='{"users":{}}',
                generated_at="2026-09-19T01:00:00Z",
            )
        with self.assertRaises(ValueError):
            build_account_change_audit(
                actor="admin.01",
                diff={"added":[],"changed":[{"username":"x","fields":[]}],"destructive_removal_detected":False},
                registry_json='{"users":{}}',
                generated_at="2026-09-19T01:00:00Z",
            )

if __name__=="__main__":
    unittest.main()
