"""A190 G2 LAB — SQLite app history versus separate *local OS principal* floor.

This is a deliberately limited same-host experiment. A lower-privileged app
cannot write the custodian's filesystem object if OS ACLs enforce it, but
root/admin can restore BOTH objects. It is not an independent host, original
event authority, monotonic remote witness, provider receipt or H0 assurance.
"""
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
from uuid import uuid4

SCHEMA = "A190_G2_LOCAL_OS_PRINCIPAL_UNTRUSTED_V1"


class GateClosed(RuntimeError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def app_state(path):
    if not path.is_file():
        raise GateClosed("APP_DB_MISSING")
    with closing(sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)) as db:
        rows = db.execute("SELECT seq,event FROM intents ORDER BY seq").fetchall()
    return {"schema": SCHEMA, "seq": rows[-1][0] if rows else 0,
            "digest": hashlib.sha256(canonical(rows)).hexdigest()}


def app_init(path):
    if path.exists():
        raise GateClosed("NO_SILENT_REBOOTSTRAP")
    with closing(sqlite3.connect(path)) as db:
        db.execute("PRAGMA journal_mode=DELETE")
        db.execute("PRAGMA synchronous=FULL")
        db.execute("CREATE TABLE intents(seq INTEGER PRIMARY KEY, event TEXT UNIQUE NOT NULL)")
        db.execute("INSERT INTO intents VALUES(1,'synthetic-original-event')")
        db.commit()
    print("A190_G2_APP_INITIALIZED_SEQ1")


def app_advance(path):
    with closing(sqlite3.connect(path)) as db:
        db.execute("INSERT INTO intents VALUES(2,'synthetic-second-event')")
        db.commit()
    assert app_state(path)["seq"] == 2
    print("A190_G2_APP_ADVANCED_SEQ2")


def floor_read(path):
    try:
        value = json.loads(path.read_bytes())
    except (OSError, ValueError) as exc:
        raise GateClosed("FLOOR_UNAVAILABLE_OR_INVALID") from exc
    if not isinstance(value, dict) or set(value) != {"schema", "seq", "digest"}:
        raise GateClosed("FLOOR_INVALID_SHAPE")
    if value["schema"] != SCHEMA or type(value["seq"]) is not int or value["seq"] < 0:
        raise GateClosed("FLOOR_INVALID_SCHEMA")
    if not isinstance(value["digest"], str) or len(value["digest"]) != 64:
        raise GateClosed("FLOOR_INVALID_DIGEST")
    return value


def floor_publish(path, seq, digest):
    # This is called as a distinct OS user. The digest and seq remain SELF-CLAIMED:
    # no authenticated original event, nonce/challenge, key or real provider.
    if path.exists() and int(seq) <= floor_read(path)["seq"]:
        raise GateClosed("FLOOR_NONMONOTONIC_PUBLISH")
    value = {"schema": SCHEMA, "seq": int(seq), "digest": digest}
    temp = path.with_name(path.name + "." + uuid4().hex)
    try:
        with temp.open("xb") as f:
            f.write(canonical(value))
            f.flush()
            os.fsync(f.fileno())
        os.chmod(temp, 0o644)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)
    assert floor_read(path) == value
    print("A190_G2_CUSTODIAN_PUBLISHED_SEQ_" + str(seq))


def compare(db_path, floor_path):
    actual = app_state(db_path)
    claimed_floor = floor_read(floor_path)
    if actual != claimed_floor:
        raise GateClosed("A190_G2_STALE_OR_DIVERGENT_LOCAL_HISTORY")
    return actual


def expect_stale(db_path, floor_path):
    try:
        compare(db_path, floor_path)
    except GateClosed as exc:
        if str(exc) != "A190_G2_STALE_OR_DIVERGENT_LOCAL_HISTORY":
            raise
        print("A190_G2_APP_DB_ROLLBACK_VS_SEPARATE_UID_FLOOR=DENIED")
        return
    raise AssertionError("A190_G2_UNSAFE_READMISSION_AFTER_APP_ONLY_RESTORE")


def expect_current(db_path, floor_path, seq):
    current = compare(db_path, floor_path)
    assert current["seq"] == int(seq)
    print("A190_G2_MATCHED_LOCAL_STATE_SEQ_" + str(seq))


def attempt_floor_forge(path):
    # Both directory replacement and in-place mutation should be denied.
    checks = (
        ("INPLACE_WRITE", lambda: path.write_text('{"forged":true}', encoding="utf-8")),
        ("SIBLING_REPLACEMENT", lambda: path.with_name(path.name + ".forged").write_text("fake")),
    )
    for name, action in checks:
        try:
            action()
        except PermissionError:
            print("A190_G2_ATTACKER_" + name + "=OS_DENIED")
        else:
            raise AssertionError("A190_G2_UNSAFE_FLOOR_EDIT_" + name)


def main():
    if len(sys.argv) < 3:
        raise SystemExit("A190 G2 LAB CLI")
    op = sys.argv[1]
    raw = sys.argv[2:]
    if op == "app-init" and len(raw) == 1:
        app_init(Path(raw[0]))
    elif op == "app-advance" and len(raw) == 1:
        app_advance(Path(raw[0]))
    elif op == "state" and len(raw) == 1:
        state = app_state(Path(raw[0]))
        print(str(state["seq"]) + " " + state["digest"])
    elif op == "publish" and len(raw) == 3:
        floor_publish(Path(raw[0]), raw[1], raw[2])
    elif op == "expect-stale" and len(raw) == 2:
        expect_stale(Path(raw[0]), Path(raw[1]))
    elif op == "expect-current" and len(raw) == 3:
        expect_current(Path(raw[0]), Path(raw[1]), raw[2])
    elif op == "forge" and len(raw) == 1:
        attempt_floor_forge(Path(raw[0]))
    else:
        raise SystemExit("A190 G2 invalid command")


if __name__ == "__main__":
    main()
