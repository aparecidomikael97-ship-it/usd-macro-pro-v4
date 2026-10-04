"""Byte ingestion into scoped quarantine; no parsing or execution of attachments."""
from dataclasses import dataclass
import hashlib
import io
from pathlib import Path
import re
import unicodedata
import zipfile
from .models import Attachment


@dataclass(frozen=True)
class AttachmentPolicy:
    max_bytes: int = 20 * 1024 * 1024
    allowed_extensions: tuple = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".txt", ".csv", ".docx", ".xlsx")


def sanitize_name(name):
    name = unicodedata.normalize("NFKC", str(name))
    if any(v in name for v in ("/", "\\", ":", "..")):
        raise ValueError("unsafe name/path traversal")
    name = re.sub(r"[^\w. -]", "_", name).strip(" .")[:180]
    if not name or name.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *[f"COM{i}" for i in range(1,10)], *[f"LPT{i}" for i in range(1,10)]}:
        raise ValueError("unsafe filename")
    return name


def validate_metadata(a):
    if a.name != sanitize_name(a.name) or a.size < 0 or not re.fullmatch(r"[a-f0-9]{64}", a.digest):
        raise ValueError("invalid metadata")
    if a.storage_reference != a.digest + ".blob":
        raise ValueError("invalid content-addressed reference")


def detect_mime(data, extension):
    for magic, extensions, mime in ((b"\x89PNG\r\n\x1a\n", {".png"}, "image/png"),
        (b"\xff\xd8\xff", {".jpg", ".jpeg"}, "image/jpeg"), (b"GIF8", {".gif"}, "image/gif"),
        (b"%PDF-", {".pdf"}, "application/pdf")):
        if data.startswith(magic) and extension in extensions:
            return mime
    if extension == ".webp" and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if extension in {".txt", ".csv"}:
        try:
            text = data.decode("utf-8-sig")
            if any(ord(c) < 32 and c not in "\t\r\n" for c in text):
                raise ValueError()
        except (UnicodeError, ValueError) as exc:
            raise ValueError("not UTF-8 text") from exc
        return "text/csv" if extension == ".csv" else "text/plain"
    if extension in {".docx", ".xlsx"}:
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                names = z.namelist()
                marker = "word/document.xml" if extension == ".docx" else "xl/workbook.xml"
                if len(names) > 10000 or marker not in names or "[Content_Types].xml" not in names:
                    raise ValueError("invalid Office container")
                if any("vbaProject" in n or ".." in n.split("/") or n.startswith("/") for n in names):
                    raise ValueError("unsafe Office container")
                if sum(i.file_size for i in z.infolist()) > 100 * 1024 * 1024:
                    raise ValueError("expanded archive exceeds technical bound")
        except zipfile.BadZipFile as exc:
            raise ValueError("invalid Office container") from exc
        suffix = "wordprocessingml.document" if extension == ".docx" else "spreadsheetml.sheet"
        return "application/vnd.openxmlformats-officedocument." + suffix
    raise ValueError("signature/extension mismatch")


def ingest_attachment(store, scope, conversation_id, root, name, data, *, declared_mime="", policy=None):
    store.get_conversation(scope, conversation_id)
    policy = policy or AttachmentPolicy()
    if policy.max_bytes <= 0 or len(data) > policy.max_bytes:
        raise ValueError("attachment exceeds configured byte budget")
    name = sanitize_name(name)
    extension = Path(name).suffix.lower()
    if extension not in policy.allowed_extensions:
        raise ValueError("extension not permitted")
    mime = detect_mime(data, extension)
    digest = hashlib.sha256(data).hexdigest()
    base = Path(root).resolve()
    folder = base / hashlib.sha256(repr(scope).encode()).hexdigest()
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / (digest + ".blob")
    if not folder.resolve().is_relative_to(base) or target.resolve().parent != folder.resolve() or target.is_symlink():
        raise ValueError("attachment escaped quarantine")
    try:
        with target.open("xb") as f:
            f.write(data)
    except FileExistsError:
        if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise ValueError("stored attachment integrity mismatch")
    a = Attachment(conversation_id, name, mime, len(data), digest, target.name, declared_mime=declared_mime)
    return store.add_attachment_metadata(scope, a)
