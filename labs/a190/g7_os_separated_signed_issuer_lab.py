"""A190 G7 LAB — Ed25519 signer, SQLite reservation owned by a REAL OS principal.

All keys are ephemeral and synthetic. OS ACL can isolate custodian from the
lower-privileged application, but admin/root on the SAME host can roll back
the signer/DB and substitute pins. This proves NO remote custody, vendor
receipt, original-event authenticity, H0 survival or P0 homologation.
"""
from __future__ import annotations

import base64
from contextlib import closing
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey, Ed25519PublicKey,
)


SCHEMA = "A190_G7_REAL_OS_PRINCIPAL_SYNTHETIC_ED25519_V1"
DOMAIN = b"ATLASQUANT:A190:G7:LOCAL_OS_NOT_EXTERNAL\0"
INTENT_SHA = sha256(b"ONE-SYNTHETIC-ECONOMIC-INTENT-NO-EFFECT").hexdigest()
TOKEN = re.compile(r"^[a-z0-9_-]{1,48}$")
ISSUER = "SYNTHETIC_LOCAL_OS_CUSTODIAN_NOT_EXTERNAL"


class Denied(Exception):
    pass


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode("ascii")


def key_path(secret_dir):
    return secret_dir / "issuer-private.raw"


def database_path(secret_dir):
    return secret_dir / "issuer-reservations.sqlite"


def public_key_path(public_dir):
    return public_dir / "issuer-public.hex"


def token(value):
    if not TOKEN.fullmatch(value):
        raise Denied("G7_INVALID_SYNTHETIC_ID")
    return value


def init_custodian(secret_dir, public_dir):
    if any(path.exists() for path in (
        key_path(secret_dir), database_path(secret_dir), public_key_path(public_dir),
    )):
        raise Denied("G7_NO_AUTO_REENROLLMENT")
    private = Ed25519PrivateKey.generate()
    raw = private.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    with key_path(secret_dir).open("xb") as file:
        file.write(raw)
        file.flush()
        os.fsync(file.fileno())
    os.chmod(key_path(secret_dir), 0o600)
    pub = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    public_key_path(public_dir).write_text(pub.hex(), encoding="ascii")
    with closing(sqlite3.connect(database_path(secret_dir))) as connection:
        connection.execute("PRAGMA journal_mode=DELETE")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute(
            "CREATE TABLE reservations("
            "seq INTEGER PRIMARY KEY,"
            "original_event TEXT NOT NULL UNIQUE,"
            "intent_sha TEXT NOT NULL,"
            "request_id TEXT NOT NULL UNIQUE)"
        )
        connection.commit()
    print("A190_G7_CUSTODIAN_KEY_GENERATED_BY_SEPARATE_OS_ACCOUNT")
    print("A190_G7_CUSTODIAN_SQLITE_INITIALIZED_UNDER_PRIVATE_ACL")


def issue(secret_dir, public_dir, original, request):
    original, request = token(original), token(request)
    output = public_dir / (request + ".json")
    if output.exists():
        raise Denied("G7_DUPLICATE_RECEIPT_FILENAME_DENIED")
    with closing(sqlite3.connect(database_path(secret_dir), timeout=0.5)) as db:
        db.execute("BEGIN IMMEDIATE")
        if db.execute(
            "SELECT 1 FROM reservations WHERE original_event=?", (original,),
        ).fetchone():
            db.rollback()
            raise Denied("G7_DUPLICATE_ORIGINAL_EVENT_DENIED")
        seq = int(db.execute(
            "SELECT COALESCE(MAX(seq),0)+1 FROM reservations",
        ).fetchone()[0])
        db.execute(
            "INSERT INTO reservations VALUES (?,?,?,?)",
            (seq, original, INTENT_SHA, request),
        )
        db.commit()
    payload = {
        "schema": SCHEMA,
        "issuer": ISSUER,
        "sequence": seq,
        "original_event_id": original,
        "request_id": request,
        "original_sha256": INTENT_SHA,
        "tenant": "synthetic-tenant",
        "workspace": "lab",
        "action": "NO_EXTERNAL_EFFECT",
        "state": "RESERVED_OS_LOCAL_ONLY",
        "authority_epoch": 1,
    }
    private = Ed25519PrivateKey.from_private_bytes(
        key_path(secret_dir).read_bytes()
    )
    signature = private.sign(DOMAIN + canonical(payload))
    response = {
        "payload": payload,
        "signature_b64": base64.b64encode(signature).decode("ascii"),
    }
    with output.open("xb") as file:
        file.write(canonical(response))
        file.flush()
        os.fsync(file.fileno())
    print(f"A190_G7_CUSTODIAN_SIGNED_REQUEST={request}_SEQ={seq}")
    print("A190_G7_AION_NO_EFFECT_PROVIDER_OR_SEND=ATTESTED")


def verify(pin, receipt, expect):
    if expect not in {"valid", "invalid"}:
        raise Denied("G7_VERIFICATION_MODE_INVALID")
    response = json.loads(receipt.read_text(encoding="utf-8"))
    payload = response["payload"]
    if (
        set(payload) != {
            "schema", "issuer", "sequence", "original_event_id",
            "request_id", "original_sha256", "tenant", "workspace",
            "action", "state", "authority_epoch",
        }
        or payload["schema"] != SCHEMA
        or payload["issuer"] != ISSUER
        or payload["original_sha256"] != INTENT_SHA
        or payload["state"] != "RESERVED_OS_LOCAL_ONLY"
        or payload["action"] != "NO_EXTERNAL_EFFECT"
        or type(payload["sequence"]) is not int
        or payload["sequence"] <= 0
        or type(payload["authority_epoch"]) is not int
        or payload["authority_epoch"] != 1
    ):
        raise Denied("G7_INVALID_SIGNED_PAYLOAD")
    try:
        pub = Ed25519PublicKey.from_public_bytes(
            bytes.fromhex(pin.read_text(encoding="ascii").strip())
        )
        pub.verify(
            base64.b64decode(response["signature_b64"], validate=True),
            DOMAIN + canonical(payload),
        )
        valid = True
    except (InvalidSignature, ValueError):
        valid = False
    if valid != (expect == "valid"):
        raise AssertionError("G7_SIGNATURE_EXPECTATION_NOT_MET")
    if valid:
        print("A190_G7_SIGNATURE_MATH_VERIFIED_WITH_SUPPLIED_PUBLIC_KEY")
    else:
        print("A190_G7_ATTEMPTED_FORGERY_REJECTED_BY_RETAINED_PIN")
    # The accepted signature mathematically verifies under the supplied pin.
    # It *never* grants effect permission, root independence, or resend.
    print("A190_G7_PERMITS_SEND=False_EXTERNAL_HOMOLOGATION=False")


def forge(app_dir, honest_receipt):
    response = json.loads(honest_receipt.read_text(encoding="utf-8"))
    private = Ed25519PrivateKey.generate()
    pub = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    forged = {
        "payload": response["payload"],
        "signature_b64": base64.b64encode(
            private.sign(DOMAIN + canonical(response["payload"]))
        ).decode("ascii"),
    }
    (app_dir / "forged-pub.hex").write_text(pub.hex(), encoding="ascii")
    (app_dir / "forged-receipt.json").write_bytes(canonical(forged))
    print("A190_G7_APP_SELF_SIGNED_FAKE_RECEIPT_CREATED")


def read_hostile(secret_dir):
    attempts = (
        ("PRIVATE_KEY", lambda: key_path(secret_dir).read_bytes()),
        ("RESERVATION_DB", lambda: sqlite3.connect(
            database_path(secret_dir).as_uri() + "?mode=rw", uri=True, timeout=0.2,
        )),
    )
    for name, operation in attempts:
        try:
            value = operation()
        except (PermissionError, sqlite3.Error, OSError):
            print("A190_G7_LOWER_PRIV_APP_" + name + "=OS_DENIED")
        else:
            if isinstance(value, sqlite3.Connection):
                value.close()
            raise AssertionError("G7_UNSAFE_LOWER_PRIV_APP_READ_" + name)


def expect_duplicate(secret_dir, public_dir, original, request):
    try:
        issue(secret_dir, public_dir, original, request)
    except Denied as error:
        if str(error) != "G7_DUPLICATE_ORIGINAL_EVENT_DENIED":
            raise
        print("A190_G7_CUSTODIAN_SAME_EVENT_NEW_REQUEST=DENIED")
    else:
        raise AssertionError("G7_CUSTODIAN_DUPLICATE_ACCEPTED")


def compare(public_dir, req1, req2):
    first = json.loads((public_dir / (req1 + ".json")).read_bytes())["payload"]
    second = json.loads((public_dir / (req2 + ".json")).read_bytes())["payload"]
    if first["original_sha256"] != second["original_sha256"]:
        raise AssertionError("G7_ORIGINAL_SHA_DIFFERENT")
    if first["original_event_id"] == second["original_event_id"]:
        raise AssertionError("G7_ORIGINAL_IDS_EQUAL")
    print("A190_G7_DIFFERENT_SELF_CLAIMED_ORIGINAL_IDS_SAME_SEMANTIC_SHA=ADMITTED_RED")


def main(argv):
    if os.name == "nt":
        identity = subprocess.run(
            ["whoami", "/user"], capture_output=True, text=True, check=True,
        ).stdout
        match = re.search(r"S-1-\\d+(?:-\\d+)+", identity)
        if match is None:
            raise AssertionError("G7_REAL_WINDOWS_SID_NOT_FOUND")
        print("A190_G7_REAL_PROCESS_PRINCIPAL=" + match.group(0))
    else:
        print("A190_G7_REAL_PROCESS_PRINCIPAL=" + str(os.geteuid()))
    if len(argv) < 2:
        raise SystemExit("G7 LAB usage")
    op = argv[1]
    args = [Path(arg) if index in (0, 1) else arg
            for index, arg in enumerate(argv[2:])]
    if op == "init" and len(args) == 2:
        init_custodian(*args)
    elif op == "issue" and len(args) == 4:
        issue(args[0], args[1], args[2], args[3])
    elif op == "verify" and len(args) == 3:
        verify(Path(argv[2]), Path(argv[3]), argv[4])
    elif op == "forge" and len(args) == 2:
        forge(Path(argv[2]), Path(argv[3]))
    elif op == "try-read" and len(args) == 1:
        read_hostile(Path(argv[2]))
    elif op == "expect-duplicate" and len(args) == 4:
        expect_duplicate(args[0], args[1], args[2], args[3])
    elif op == "compare" and len(args) == 3:
        compare(Path(argv[2]), argv[3], argv[4])
    else:
        raise SystemExit("G7_INVALID_ARGS")


if __name__ == "__main__":
    main(sys.argv)
