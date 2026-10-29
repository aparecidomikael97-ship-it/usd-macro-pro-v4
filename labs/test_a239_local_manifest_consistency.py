"""A239: local manifest must match backup bytes before staged restoration.

This detects accidental/local non-coherent changes, not hostile-host forgery.
"""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from aion_chat.store import SQLiteChatStore, StorageUnavailableError
from atlasquant_aion_chat_storage_resilience import (
    create_verified_staging_backup,
    restore_verified_staging_backup,
)


def _fixture(root, manifest_path=None):
    root = Path(root)
    source = SQLiteChatStore(root / "live.db")
    try:
        source.db.execute("CREATE TABLE proof (value INTEGER NOT NULL)")
        source.db.execute("INSERT INTO proof VALUES (23)")
        source.db.commit()
        backup = root / "snapshot.db"
        result = create_verified_staging_backup(
            source, backup, manifest_path=manifest_path
        )
    finally:
        source.close()
    return backup, Path(result["manifest_path"])


def _change_manifest(manifest, update):
    data = json.loads(manifest.read_text(encoding="utf-8"))
    update(data)
    manifest.write_text(json.dumps(data), encoding="utf-8")


def _assert_restore_denied(backup, target, manifest=None):
    with unittest.TestCase().assertRaises(StorageUnavailableError):
        restore_verified_staging_backup(
            backup, target, **({"manifest_path": manifest} if manifest else {})
        )
    if target.exists():
        raise AssertionError("a denied restore published a target unexpectedly")


class A239LocalManifestConsistencyTests(unittest.TestCase):
    def test_01_valid_manifest_and_snapshot_restore(self):
        with TemporaryDirectory(prefix="a239-") as raw:
            root = Path(raw)
            backup, manifest = _fixture(root)
            result = restore_verified_staging_backup(backup, root / "recovered.db")
            self.assertTrue(manifest.exists())
            self.assertTrue(result["local_manifest_sha256_match"])
            self.assertTrue(result["restore"]["manifest_sha256_verified"])
            self.assertFalse(result["independent_provenance_verified"])
            with closing(sqlite3.connect(str(root / "recovered.db"))) as db:
                self.assertEqual(db.execute("SELECT value FROM proof").fetchone()[0], 23)

    def test_02_missing_manifest_denies_before_target_creation(self):
        with TemporaryDirectory(prefix="a239-") as raw:
            root = Path(raw)
            backup, manifest = _fixture(root)
            manifest.unlink()
            _assert_restore_denied(backup, root / "recovered.db")

    def test_03_valid_sqlite_mutation_after_backup_is_denied(self):
        with TemporaryDirectory(prefix="a239-") as raw:
            root = Path(raw)
            backup, manifest = _fixture(root)
            with closing(sqlite3.connect(str(backup))) as db:
                db.execute("UPDATE proof SET value=99")
                db.commit()
            with closing(sqlite3.connect(str(backup))) as db:
                self.assertEqual(db.execute("PRAGMA quick_check").fetchone()[0], "ok")
            _assert_restore_denied(backup, root / "recovered.db")

    def test_04_mismatched_sha256_denied(self):
        with TemporaryDirectory(prefix="a239-") as raw:
            root = Path(raw)
            backup, manifest = _fixture(root)
            _change_manifest(manifest, lambda d: d["backup"].__setitem__("sha256", "a"*64))
            _assert_restore_denied(backup, root / "recovered.db")

    def test_05_wrong_size_and_bool_size_denied(self):
        for value in (True, 0, 100_000_000):
            with self.subTest(value=value), TemporaryDirectory(prefix="a239-") as raw:
                root = Path(raw)
                backup, manifest = _fixture(root)
                _change_manifest(manifest, lambda d: d["backup"].__setitem__("size_bytes", value))
                _assert_restore_denied(backup, root / "recovered.db")

    def test_06_changed_backup_path_denied(self):
        with TemporaryDirectory(prefix="a239-") as raw:
            root = Path(raw)
            backup, manifest = _fixture(root)
            _change_manifest(manifest, lambda d: d["backup"].__setitem__("backup_path", str(root / "other.db")))
            _assert_restore_denied(backup, root / "recovered.db")

    def test_07_production_ready_claim_denied(self):
        with TemporaryDirectory(prefix="a239-") as raw:
            root = Path(raw)
            backup, manifest = _fixture(root)
            _change_manifest(manifest, lambda d: d.__setitem__("production_ready", True))
            _assert_restore_denied(backup, root / "recovered.db")

    def test_08_duplicate_json_object_keys_denied(self):
        with TemporaryDirectory(prefix="a239-") as raw:
            root = Path(raw)
            backup, manifest = _fixture(root)
            content = manifest.read_text(encoding="utf-8")
            manifest.write_text(content.replace('"schema":', '"schema": "forged", "schema":', 1), encoding="utf-8")
            _assert_restore_denied(backup, root / "recovered.db")

    def test_09_invalid_json_denied(self):
        with TemporaryDirectory(prefix="a239-") as raw:
            root = Path(raw)
            backup, manifest = _fixture(root)
            manifest.write_text('{"backup":', encoding="utf-8")
            _assert_restore_denied(backup, root / "recovered.db")

    def test_10_explicit_custom_manifest_path_supported(self):
        with TemporaryDirectory(prefix="a239-") as raw:
            root = Path(raw)
            custom = root / "custom-manifest.json"
            backup, manifest = _fixture(root, custom)
            self.assertEqual(manifest, custom)
            with self.assertRaises(StorageUnavailableError):
                restore_verified_staging_backup(backup, root / "wrong.db")
            result = restore_verified_staging_backup(
                backup, root / "right.db", manifest_path=custom
            )
            self.assertTrue(result["local_manifest_sha256_match"])
            self.assertFalse((root / "wrong.db").exists())

    def test_11_preexisting_manifest_vetoes_new_snapshot(self):
        with TemporaryDirectory(prefix="a239-") as raw:
            root = Path(raw)
            source = SQLiteChatStore(root / "live.db")
            backup = root / "snapshot.db"
            manifest = Path(str(backup) + ".manifest.json")
            manifest.write_text("existing", encoding="utf-8")
            try:
                with self.assertRaises(StorageUnavailableError):
                    create_verified_staging_backup(source, backup)
                self.assertEqual(manifest.read_text(encoding="utf-8"), "existing")
                self.assertFalse(backup.exists())
            finally:
                source.close()

    def test_12_symlink_manifest_is_untrusted(self):
        with TemporaryDirectory(prefix="a239-") as raw:
            root = Path(raw)
            backup, manifest = _fixture(root)
            original = root / "original-manifest.json"
            manifest.rename(original)
            try:
                manifest.symlink_to(original)
            except (OSError, NotImplementedError) as exc:
                self.skipTest("symlink unavailable: " + str(exc))
            _assert_restore_denied(backup, root / "recovered.db")

    def test_13_low_level_expected_digest_gate_blocks_modified_copy(self):
        with TemporaryDirectory(prefix="a239-") as raw:
            root = Path(raw)
            backup, manifest = _fixture(root)
            expected = json.loads(manifest.read_text(encoding="utf-8"))["backup"]["sha256"]
            with closing(sqlite3.connect(str(backup))) as db:
                db.execute("UPDATE proof SET value=98")
                db.commit()
            with self.assertRaises(StorageUnavailableError):
                SQLiteChatStore.restore_from_backup(
                    backup, root / "recovered.db", expected_sha256=expected
                )
            self.assertFalse((root / "recovered.db").exists())

    def test_14_low_level_invalid_digest_rejected(self):
        with TemporaryDirectory(prefix="a239-") as raw:
            root = Path(raw)
            backup, manifest = _fixture(root)
            for value in (True, "abc", "Z"*64):
                with self.subTest(value=value):
                    with self.assertRaises(ValueError):
                        SQLiteChatStore.restore_from_backup(
                            backup, root / "recovered.db", expected_sha256=value
                        )
            self.assertFalse((root / "recovered.db").exists())
