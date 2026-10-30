"""A260 LAB: assemble and inspect a minimal OFFLINE, NO-SEND Outbox candidate.

A deliberately tiny, explicitly allowlisted STUDY bundle. Not a deployable
AtlasQuant web app or a provider-enabled Worker. The current render.yaml
still builds from the repository; this builder does not change that workflow.

No execution of repo source while building, no network, no deployment, no
signature or independent trust attestation. No release authorization.
"""
from __future__ import annotations

import ast
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path, PurePosixPath
import stat
import zipfile


SCHEMA = "ATLASQUANT_AION_A260_OFFLINE_RUNTIME_CANDIDATE_V1"
MANIFEST_NAME = "AION_OFFLINE_CANDIDATE_MANIFEST.json"
RUNTIME_FILES = (
    "aion_chat/__init__.py",
    "aion_chat/attachments.py",
    "aion_chat/models.py",
    "aion_chat/privacy.py",
    "aion_chat/store.py",
    "atlasquant_aion_execution_outbox.py",
)
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_ARCHIVE_BYTES = 7 * 1024 * 1024
EXPECTED = frozenset((*RUNTIME_FILES, MANIFEST_NAME))


class OfflineBundleRejected(ValueError):
    """The artifact is not even structurally acceptable for offline review."""


def _path_ok(name: str) -> None:
    if (
        not isinstance(name, str)
        or name.startswith("/")
        or "\\" in name
        or name.startswith("./")
        or ":" in name
        or any(part in {"", ".", ".."} for part in name.split("/"))
        or PurePosixPath(name).is_absolute()
    ):
        raise OfflineBundleRejected("unsafe archive path")
    if (
        name.startswith(("labs/", "test_"))
        or "/labs/" in name
        or name.endswith((".pyc", ".pyo"))
        or "__pycache__" in name.split("/")
    ):
        raise OfflineBundleRejected("laboratory or compiled code forbidden")


def _check_python_source(name: str, data: bytes) -> None:
    try:
        tree = ast.parse(data.decode("utf-8"), filename=name)
    except (UnicodeDecodeError, SyntaxError) as exc:
        raise OfflineBundleRejected("invalid Python source") from exc
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name.split(".")[0] == "labs" for alias in node.names):
                raise OfflineBundleRejected("runtime imports LAB")
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[0] == "labs":
                raise OfflineBundleRejected("runtime imports LAB")
    if name == "atlasquant_aion_execution_outbox.py":
        classes = [n for n in tree.body if isinstance(n, ast.ClassDef)
                   and n.name == "ExecutionOutbox"]
        if len(classes) != 1:
            raise OfflineBundleRejected("ExecutionOutbox class missing or duplicated")
        klass = classes[0]
        init = [n for n in klass.body if isinstance(n, ast.FunctionDef)
                and n.name == "__init__"]
        guard = [n for n in klass.body if isinstance(n, ast.FunctionDef)
                 and n.name == "_reserved_first_attempt"]
        if len(init) != 1 or len(guard) != 1:
            raise OfflineBundleRejected("Outbox runtime contract missing")
        params = init[0].args
        if (
            [a.arg for a in (*params.posonlyargs, *params.args)]
            != ["self", "store", "scope"]
            or params.kwonlyargs or params.vararg or params.kwarg
        ):
            raise OfflineBundleRejected("caller-supplied first attempt callback")
        body = [n for n in guard[0].body if not isinstance(n, ast.Expr)
                or not isinstance(n.value, ast.Constant)
                or not isinstance(n.value.value, str)]
        # Reject any other operation, including branches or a synthetic
        # return True, in this deliberately no-send, no-authority build.
        if (
            len(body) != 1 or not isinstance(body[0], ast.Return)
            or not isinstance(body[0].value, ast.Constant)
            or body[0].value.value is not False
        ):
            raise OfflineBundleRejected("first-attempt gate must be literal False")

        # A274: a literal False in _reserved_first_attempt is insufficient
        # if dispatch/reconciliation reads a host adapter or calls a
        # forged authorizer elsewhere. This is a narrow AST negative guard,
        # NOT a proof against arbitrary Python/host mutation.
        forbidden_params = {
            "adapter", "authorize", "cumulative_authority_guard",
        }
        forbidden_builtins = {
            "eval", "exec", "getattr", "setattr", "locals", "globals",
            "__import__",
        }
        forbidden_methods = {
            "_authorization_gate", "_reserved_first_attempt",
            "_confirm", "send", "reconcile",
        }
        for method_name in ("dispatch_claimed", "reconcile"):
            methods = [
                node for node in klass.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == method_name
            ]
            if len(methods) != 1 or not isinstance(methods[0], ast.FunctionDef):
                raise OfflineBundleRejected("normal no-send method missing or duplicated")
            method = methods[0]
            for node in ast.walk(method):
                if isinstance(node, ast.Name) and node.id in forbidden_params:
                    raise OfflineBundleRejected("host callback or adapter used by runtime")
                if isinstance(node, ast.Call):
                    if (isinstance(node.func, ast.Name)
                            and node.func.id in forbidden_builtins):
                        raise OfflineBundleRejected("dynamic callback lookup in no-send method")
                    if (isinstance(node.func, ast.Attribute)
                            and node.func.attr in forbidden_methods):
                        raise OfflineBundleRejected("send or authorization method called")


def _canonical(value) -> bytes:
    return (json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ) + "\n").encode("utf-8")


def _entry(name: str, data: bytes, bundle: zipfile.ZipFile):
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.create_system = 3
    info.external_attr = (stat.S_IFREG | 0o644) << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    bundle.writestr(info, data)


def verify_offline_candidate(raw: bytes | Path) -> dict:
    """Verify exact file list, content hashes and no-send AST. NOT provenance."""
    if isinstance(raw, Path):
        if raw.is_symlink() or not raw.is_file():
            raise OfflineBundleRejected("unsafe or missing archive")
        raw = raw.read_bytes()
    if type(raw) is not bytes or len(raw) > MAX_ARCHIVE_BYTES:
        raise OfflineBundleRejected("invalid or oversized archive")
    try:
        with zipfile.ZipFile(BytesIO(raw)) as archive:
            entries = archive.infolist()
            names = [entry.filename for entry in entries]
            if len(names) != len(EXPECTED) or set(names) != EXPECTED:
                raise OfflineBundleRejected("extra, missing or duplicate entry")
            contents = {}
            for entry in entries:
                name = entry.filename
                _path_ok(name)
                mode = (entry.external_attr >> 16) & 0o170000  # POSIX S_IFMT mask, portable on Windows
                if entry.is_dir() or entry.flag_bits & 1 or (
                    entry.create_system == 3 and mode != stat.S_IFREG
                ):
                    raise OfflineBundleRejected("directory, link or encrypted entry")
                if entry.file_size > MAX_FILE_BYTES:
                    raise OfflineBundleRejected("oversized entry")
                data = archive.read(entry)
                if len(data) != entry.file_size:
                    raise OfflineBundleRejected("truncated archive entry")
                contents[name] = data
    except (zipfile.BadZipFile, RuntimeError, OSError) as exc:
        raise OfflineBundleRejected("corrupted archive") from exc

    try:
        manifest = json.loads(contents[MANIFEST_NAME])
    except (ValueError, UnicodeDecodeError, TypeError) as exc:
        raise OfflineBundleRejected("bad manifest") from exc
    if (
        type(manifest) is not dict
        or set(manifest) != {
            "schema", "mode", "p0_homologated", "authorizes_send",
            "permits_worker", "permits_deploy", "files",
        }
        or manifest["schema"] != SCHEMA
        or manifest["mode"] != "STUDY_ONLY_OFFLINE_NO_SEND"
        or type(manifest["p0_homologated"]) is not int
        or manifest["p0_homologated"] != 0
        or manifest["authorizes_send"] is not False
        or manifest["permits_worker"] is not False
        or manifest["permits_deploy"] is not False
        or type(manifest["files"]) is not dict
        or set(manifest["files"]) != set(RUNTIME_FILES)
    ):
        raise OfflineBundleRejected("candidate manifest claims authority or has wrong files")
    for name in RUNTIME_FILES:
        digest = sha256(contents[name]).hexdigest()
        if manifest["files"][name] != digest:
            raise OfflineBundleRejected("file/manifest digest mismatch")
        _check_python_source(name, contents[name])
    return {
        "status": "OFFLINE_STRUCTURE_VERIFIED_NOT_AUTHORIZED",
        "sha256": sha256(raw).hexdigest(),
        "files": list(RUNTIME_FILES),
        "p0_homologated": 0, "authorizes_send": False,
        "permits_worker": False, "permits_deploy": False,
        "independent_provenance": False,
    }


def build_offline_candidate(source_root: Path, target_zip: Path) -> dict:
    """Copy *only* six approved runtime files to a create-only study archive."""
    root = Path(source_root)
    target = Path(target_zip)
    if root.is_symlink() or not root.is_dir():
        raise OfflineBundleRejected("source root invalid")
    if target.is_symlink() or target.exists():
        raise OfflineBundleRejected("candidate already exists (create only)")
    if not target.parent.is_dir() or target.parent.is_symlink():
        raise OfflineBundleRejected("target parent must already exist")
    root_real = root.resolve()
    files = {}
    for name in RUNTIME_FILES:
        _path_ok(name)
        candidate = root / name
        if (
            not candidate.is_file() or candidate.is_symlink()
            or any((root / part).is_symlink()
                   for part in PurePosixPath(name).parents if str(part) != ".")
            or not candidate.resolve().is_relative_to(root_real)
        ):
            raise OfflineBundleRejected("unsafe or missing source file")
        data = candidate.read_bytes()
        if len(data) > MAX_FILE_BYTES:
            raise OfflineBundleRejected("oversized source")
        _check_python_source(name, data)
        files[name] = data

    manifest = {
        "schema": SCHEMA, "mode": "STUDY_ONLY_OFFLINE_NO_SEND",
        "p0_homologated": 0, "authorizes_send": False,
        "permits_worker": False, "permits_deploy": False,
        "files": {name: sha256(files[name]).hexdigest() for name in RUNTIME_FILES},
    }
    stream = BytesIO()
    with zipfile.ZipFile(stream, mode="w") as archive:
        for name in RUNTIME_FILES:
            _entry(name, files[name], archive)
        _entry(MANIFEST_NAME, _canonical(manifest), archive)
    candidate_bytes = stream.getvalue()
    verification = verify_offline_candidate(candidate_bytes)
    with target.open("xb") as handle:
        handle.write(candidate_bytes)
    return {**verification, "status": "OFFLINE_STUDY_CANDIDATE_CREATED_NO_AUTHORITY"}


__all__ = ["SCHEMA", "MANIFEST_NAME", "RUNTIME_FILES", "OfflineBundleRejected",
           "build_offline_candidate", "verify_offline_candidate"]
