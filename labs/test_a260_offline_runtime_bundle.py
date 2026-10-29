"""A260 CI: create real minimal candidate zip and reject LAB contamination.

No user artifact publication, release, network, Worker, or external send.
"""
from contextlib import closing
from hashlib import sha256
from io import BytesIO
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
import zipfile

from labs.a260_offline_runtime_bundle import (
    MANIFEST_NAME, RUNTIME_FILES, SCHEMA,
    OfflineBundleRejected, build_offline_candidate,
    verify_offline_candidate,
)


ROOT = Path(__file__).resolve().parent.parent


def _bundle(root=ROOT):
    tmp = TemporaryDirectory(prefix="a260-study-")
    zip_path = Path(tmp.name) / "study-no-send.zip"
    result = build_offline_candidate(root, zip_path)
    return tmp, zip_path, result


def _mutate_archive(original: bytes, name: str, altered: bytes) -> bytes:
    source = zipfile.ZipFile(BytesIO(original))
    stream = BytesIO()
    with source, zipfile.ZipFile(stream, "w") as output:
        for info in source.infolist():
            contents = altered if info.filename == name else source.read(info.filename)
            output.writestr(info, contents)
    return stream.getvalue()


class A260OfflineArtifactSeparationTests(unittest.TestCase):
    def test_01_actual_repository_builds_only_allowlisted_files(self):
        tmp, path, created = _bundle()
        try:
            self.assertEqual(created["status"], "OFFLINE_STUDY_CANDIDATE_CREATED_NO_AUTHORITY")
            verified = verify_offline_candidate(path)
            self.assertEqual(verified["status"], "OFFLINE_STRUCTURE_VERIFIED_NOT_AUTHORIZED")
            self.assertEqual(verified["sha256"], created["sha256"])
            self.assertEqual(tuple(verified["files"]), RUNTIME_FILES)
            self.assertEqual(verified["p0_homologated"], 0)
            self.assertFalse(verified["authorizes_send"])
            self.assertFalse(verified["permits_worker"])
            self.assertFalse(verified["permits_deploy"])
            self.assertFalse(verified["independent_provenance"])
            with zipfile.ZipFile(path) as zf:
                self.assertEqual(
                    set(zf.namelist()), set(RUNTIME_FILES) | {MANIFEST_NAME}
                )
                self.assertTrue(all(
                    not n.startswith("labs/") and "/labs/" not in n
                    for n in zf.namelist()
                ))
        finally:
            tmp.cleanup()

    def test_02_repeated_builds_are_byte_identical(self):
        with TemporaryDirectory(prefix="a260-determinism-") as raw:
            a, b = Path(raw) / "one.zip", Path(raw) / "two.zip"
            build_offline_candidate(ROOT, a)
            build_offline_candidate(ROOT, b)
            self.assertEqual(a.read_bytes(), b.read_bytes())
            self.assertEqual(sha256(a.read_bytes()).digest(), sha256(b.read_bytes()).digest())

    def test_03_create_only_refuses_overwriting_existing_candidate(self):
        tmp, archive, result = _bundle()
        try:
            snapshot = archive.read_bytes()
            with self.assertRaises(OfflineBundleRejected):
                build_offline_candidate(ROOT, archive)
            self.assertEqual(snapshot, archive.read_bytes())
        finally:
            tmp.cleanup()

    def test_04_contaminated_archive_with_labs_fixture_is_rejected(self):
        tmp, archive, result = _bundle()
        try:
            stream = BytesIO()
            with zipfile.ZipFile(archive) as old, zipfile.ZipFile(stream, "w") as out:
                for info in old.infolist():
                    out.writestr(info, old.read(info.filename))
                out.writestr("labs/a259_synthetic_outbox_fixture.py",
                             b"class FakeAllow: pass\n")
            with self.assertRaises(OfflineBundleRejected):
                verify_offline_candidate(stream.getvalue())
        finally:
            tmp.cleanup()

    def test_05_extra_or_duplicate_file_is_rejected(self):
        tmp, archive, result = _bundle()
        try:
            stream = BytesIO()
            with zipfile.ZipFile(archive) as old, zipfile.ZipFile(stream, "w") as out:
                for info in old.infolist():
                    out.writestr(info, old.read(info.filename))
                out.writestr("readme.txt", b"extra")
            with self.assertRaises(OfflineBundleRejected):
                verify_offline_candidate(stream.getvalue())
            stream = BytesIO()
            with zipfile.ZipFile(archive) as old, zipfile.ZipFile(stream, "w") as out:
                for info in old.infolist():
                    out.writestr(info, old.read(info.filename))
                out.writestr("atlasquant_aion_execution_outbox.py", b"pass\n")
            with self.assertRaises(OfflineBundleRejected):
                verify_offline_candidate(stream.getvalue())
        finally:
            tmp.cleanup()

    def test_06_tampered_outbox_body_or_new_true_gate_is_rejected(self):
        tmp, archive, result = _bundle()
        try:
            with zipfile.ZipFile(archive) as zf:
                outbox = zf.read("atlasquant_aion_execution_outbox.py")
            newline = b"\r\n" if b"\r\n" in outbox else b"\n"
            old = b"        return False" + newline + newline + b"    def _decision_row("
            new = b"        return True" + newline + newline + b"    def _decision_row("
            self.assertEqual(outbox.count(old), 1)
            modified = outbox.replace(old, new)
            with self.assertRaises(OfflineBundleRejected):
                verify_offline_candidate(_mutate_archive(
                    archive.read_bytes(), "atlasquant_aion_execution_outbox.py",
                    modified,
                ))
        finally:
            tmp.cleanup()

    def test_07_manipulated_manifest_or_positive_authority_claim_is_denied(self):
        tmp, archive, result = _bundle()
        try:
            with zipfile.ZipFile(archive) as zf:
                manifest = json.loads(zf.read(MANIFEST_NAME))
            self.assertEqual(manifest["schema"], SCHEMA)
            for variant in ("digest", "enable-worker", "enable-deploy", "fake-p0"):
                m = json.loads(json.dumps(manifest))
                if variant == "digest":
                    m["files"][RUNTIME_FILES[0]] = "0" * 64
                elif variant == "enable-worker":
                    m["permits_worker"] = True
                elif variant == "enable-deploy":
                    m["permits_deploy"] = True
                else:
                    m["p0_homologated"] = 6
                with self.subTest(case=variant), self.assertRaises(OfflineBundleRejected):
                    verify_offline_candidate(_mutate_archive(
                        archive.read_bytes(), MANIFEST_NAME,
                        json.dumps(m).encode("utf-8"),
                    ))
        finally:
            tmp.cleanup()

    def test_08_rejects_symlink_entry_even_if_file_name_is_allowed(self):
        tmp, archive, result = _bundle()
        try:
            stream = BytesIO()
            with zipfile.ZipFile(archive) as old, zipfile.ZipFile(stream, "w") as out:
                for info in old.infolist():
                    if info.filename == "aion_chat/privacy.py":
                        info.external_attr = (stat.S_IFLNK | 0o777) << 16
                    out.writestr(info, old.read(info.filename))
            with self.assertRaises(OfflineBundleRejected):
                verify_offline_candidate(stream.getvalue())
        finally:
            tmp.cleanup()

    def test_09_empty_repo_or_missing_source_fails_closed(self):
        with TemporaryDirectory(prefix="a260-missing-") as raw:
            root, dest = Path(raw) / "repo", Path(raw) / "candidate.zip"
            root.mkdir()
            with self.assertRaises(OfflineBundleRejected):
                build_offline_candidate(root, dest)
            self.assertFalse(dest.exists())

    def test_10_symlink_source_in_allowlist_is_rejected(self):
        with TemporaryDirectory(prefix="a260-symlink-") as raw:
            root, dest = Path(raw) / "fake_repo", Path(raw) / "candidate.zip"
            root.mkdir()
            for relative in RUNTIME_FILES:
                source = ROOT / relative
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
            target = root / "aion_chat/privacy.py"
            target.unlink()
            try:
                target.symlink_to(ROOT / "aion_chat/privacy.py")
            except (OSError, NotImplementedError):
                self.skipTest("host cannot create file symlink")
            with self.assertRaises(OfflineBundleRejected):
                build_offline_candidate(root, dest)
            self.assertFalse(dest.exists())

    def test_11_isolated_subprocess_can_import_no_send_code_without_labs(self):
        tmp, archive, result = _bundle()
        try:
            destination = Path(tmp.name) / "extracted"
            destination.mkdir()
            verify_offline_candidate(archive)
            with zipfile.ZipFile(archive) as zf:
                for name in RUNTIME_FILES:
                    target = destination / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(zf.read(name))
            script = """
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
from atlasquant_aion_execution_outbox import ExecutionOutbox
from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
assert importlib.util.find_spec("labs") is None, "LAB package leaked"
with TemporaryDirectory() as work:
    store = SQLiteChatStore(Path(work) / "offline.db")
    try:
        outbox = ExecutionOutbox(
            store, Scope("owner-a260", "tenant-a260", "workspace-a260")
        )
        assert outbox._reserved_first_attempt({}) is False
        try:
            ExecutionOutbox(store, outbox.scope, first_attempt_guard=lambda _: True)
        except TypeError:
            pass
        else:
            raise AssertionError("caller True callback was accepted")
        print("A260_OFFLINE_NO_SEND_OK")
    finally:
        store.close()
"""
            env = os.environ.copy()
            env["PYTHONPATH"] = str(destination)
            env["PYTHONNOUSERSITE"] = "1"
            completed = subprocess.run(
                [sys.executable, "-B", "-c", script],
                cwd=str(destination), env=env,
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(
                completed.returncode, 0, (completed.stdout, completed.stderr)
            )
            self.assertIn("A260_OFFLINE_NO_SEND_OK", completed.stdout)
        finally:
            tmp.cleanup()

    def test_12_source_importing_labs_is_rejected_even_with_same_paths(self):
        tmp, archive, result = _bundle()
        try:
            with zipfile.ZipFile(archive) as zf:
                source = zf.read("aion_chat/privacy.py")
            changed = source + b"\nimport labs.a259_synthetic_outbox_fixture\n"
            with self.assertRaises(OfflineBundleRejected):
                verify_offline_candidate(_mutate_archive(
                    archive.read_bytes(), "aion_chat/privacy.py", changed,
                ))
        finally:
            tmp.cleanup()

    @unittest.expectedFailure
    def test_13_red_current_render_source_build_has_no_artifact_enforcement(self):
        """Current Render source checkout is NOT constrained by this builder."""
        render = (ROOT / "render.yaml").read_text(encoding="utf-8")
        # Desired: release path would invoke the strict A260 preflight and
        # mount only its verified allowlisted output. Today it does not.
        self.assertIn("a260_offline_runtime_bundle", render)


if __name__ == "__main__":
    unittest.main()
