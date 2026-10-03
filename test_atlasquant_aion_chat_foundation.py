import base64
from dataclasses import asdict
import io
import json
import re
import socket
import subprocess
import sys
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import zipfile

import pytest

from aion_chat.attachments import AttachmentPolicy, ingest_attachment, sanitize_name
from aion_chat.authorization import classify_action, request_task
from aion_chat.context import build_conversation_context, compact_conversation
from aion_chat.models import ActionClass, Attachment, ContextSummary, ConversationCheckpoint, Message, Scope, TaskState
from aion_chat.service import ChatService
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_chat_ui import ASSETS, render_chat_html


@pytest.fixture
def store(tmp_path):
    s = SQLiteChatStore(tmp_path / "chat.sqlite")
    yield s
    s.close()


@pytest.fixture
def scope():
    return Scope("alice", "tenant-a", "workspace-a")


def test_history_reopen(store, scope, tmp_path):
    c = store.create_conversation(scope, "Decisões", {"tags": ["macro"]})
    m = store.append_message(scope, Message(c.id, "user", "linha 1\nlinha 2"))
    assert store.get_message(scope, c.id, m.id) == m
    assert store.get_conversation(scope, c.id).message_count == 1
    reopened = SQLiteChatStore(tmp_path / "chat.sqlite")
    assert reopened.list_messages(scope, c.id).items == [m]
    reopened.close()


def test_conversations_pagination_search_archive(store, scope):
    cs = [store.create_conversation(scope, f"Título {i}", {"tags": ["macro"]}) for i in range(7)]
    store.append_message(scope, Message(cs[2].id, "user", "agulha histórica"))
    ids, cursor = [], None
    while True:
        p = store.list_conversations(scope, cursor=cursor, page_size=2)
        ids += [c.id for c in p.items]
        if not p.next_cursor:
            break
        cursor = p.next_cursor
    assert len(ids) == len(set(ids)) == 7
    assert store.search_conversations(scope, "agulha").items[0].id == cs[2].id
    assert len(store.search_conversations(scope, "macro").items) == 7
    assert len(store.list_conversations(scope, tag="macro", since="2000", until="9999").items) == 7
    assert store.list_conversations(scope, since="9999").items == []
    assert store.search_conversations(scope, "Título 3").items[0].id == cs[3].id
    store.archive_conversation(scope, cs[2].id)
    assert store.search_conversations(scope, "agulha").items == []
    assert store.list_conversations(scope, archived=True).items[0].id == cs[2].id
    assert store.list_messages(scope, cs[2].id).items[0].content == "agulha histórica"


@pytest.mark.parametrize("other", [Scope("bob", "tenant-a", "workspace-a"), Scope("alice", "tenant-b", "workspace-a"),
                                   Scope("alice", "tenant-a", "workspace-b")])
def test_all_operations_isolate_identity(store, scope, other, tmp_path):
    c = store.create_conversation(scope)
    m = store.append_message(scope, Message(c.id, "user", "private"))
    a = ingest_attachment(store, scope, c.id, tmp_path / "files", "a.txt", b"safe")
    store.save_checkpoint(scope, ConversationCheckpoint(c.id, 1))
    store.save_context_summary(scope, ContextSummary(c.id, 1, "summary"))
    assert store.list_conversations(other).items == []
    assert store.search_conversations(other, "private").items == []
    calls = [lambda: store.get_conversation(other, c.id), lambda: store.list_messages(other, c.id),
             lambda: store.get_message(other, c.id, m.id), lambda: store.archive_conversation(other, c.id),
             lambda: store.append_message(other, Message(c.id, "user", "attack")),
             lambda: store.get_attachment(other, c.id, a.id), lambda: store.add_attachment_metadata(other, a),
             lambda: store.get_latest_checkpoint(other, c.id), lambda: store.get_latest_summary(other, c.id),
             lambda: store.save_checkpoint(other, ConversationCheckpoint(c.id, 1)),
             lambda: store.save_context_summary(other, ContextSummary(c.id, 1, "attack")),
             lambda: store.retrieve_messages(other, c.id, "private", before_sequence=2),
             lambda: build_conversation_context(store, other, c.id)]
    for call in calls:
        with pytest.raises(LookupError):
            call()
    assert store.get_conversation(scope, c.id).message_count == 1


def test_cursor_scope_and_query(store, scope):
    for i in range(3):
        store.create_conversation(scope, str(i))
    cursor = store.list_conversations(scope, page_size=1).next_cursor
    for identity, query, cur in [(Scope("bob", "tenant-a", "workspace-a"), "", cursor),
                                  (scope, "different", cursor), (scope, "", "malformed")]:
        with pytest.raises(ValueError):
            store.list_conversations(identity, cursor=cur, query=query)


def test_thousand_messages_no_artificial_limit(store, scope):
    c = store.create_conversation(scope)
    for i in range(1000):
        store.append_message(scope, Message(c.id, "user", f"Mensagem {i}: histórico " * 8))
    ids, cursor = [], None
    while True:
        p = store.list_messages(scope, c.id, cursor=cursor, page_size=73)
        ids += [m.id for m in p.items]
        if not p.next_cursor:
            break
        cursor = p.next_cursor
    assert len(ids) == len(set(ids)) == 1000
    cp, summary = compact_conversation(store, scope, c.id, through_sequence=980)
    assert cp.through_sequence == summary.through_sequence == 980
    ctx = build_conversation_context(store, scope, c.id, query="Mensagem 7:", budget_bytes=16000)
    assert ctx["recent"][-1]["sequence"] == 1000
    assert ctx["retrieved"][0]["sequence"] == 8
    assert len(json.dumps(ctx, ensure_ascii=False, separators=(",", ":")).encode()) <= 16000
    assert store.db.execute("SELECT count(*) FROM messages WHERE cid=?", (c.id,)).fetchone()[0] == 1000
    assert store.get_message(scope, c.id, ids[0]).sequence == 1
    store.append_message(scope, Message(c.id, "user", "continuação"))
    assert store.get_conversation(scope, c.id).message_count == 1001


def test_more_than_fifty_conversations(store, scope):
    for i in range(65):
        store.create_conversation(scope, str(i))
    assert len(store.list_conversations(scope, page_size=200).items) == 65


def test_checkpoint_preserves_decisions_pending_corrections_files(store, scope, tmp_path):
    c = store.create_conversation(scope)
    a = ingest_attachment(store, scope, c.id, tmp_path / "files", "research.txt", b"research")
    events = [{"kind": "decisions", "key": "db", "value": "SQLite"},
              {"kind": "pending", "key": "review", "value": "revisar PDF"},
              {"kind": "preferences", "key": "language", "value": "English"},
              {"kind": "open_tasks", "key": "report", "value": "relatório"},
              {"kind": "confirmed_facts", "key": "claim", "value": "suposição"}]
    store.append_message(scope, Message(c.id, "user", "eventos", attachments=[a.id], metadata={"memory_events": events}))
    compact_conversation(store, scope, c.id)
    store.append_message(scope, Message(c.id, "user", "correção", metadata={"memory_events": [
        {"kind": "preferences", "key": "language", "value": "Português"},
        {"kind": "completed_tasks", "key": "report", "value": "feito"}]}))
    cp, summary = compact_conversation(store, scope, c.id)
    assert store.get_latest_checkpoint(scope, c.id) == cp
    assert store.get_latest_summary(scope, c.id) == summary
    assert cp.decisions["db"]["value"] == "SQLite"
    assert cp.pending["review"]["value"] == "revisar PDF"
    assert cp.preferences["language"]["value"] == "Português"
    assert cp.completed_tasks["report"]["value"] == "feito" and "report" not in cp.open_tasks
    assert cp.files[a.id]["digest"] == a.digest
    assert "claim" not in cp.confirmed_facts and "claim" in cp.assumptions
    assert len(store.list_messages(scope, c.id).items) == 2


def test_confirmation_resolution_and_checkpoint_validation(store, scope):
    c = store.create_conversation(scope)
    m = store.append_message(scope, Message(c.id, "user", "confirmed", truth_state="CONFIRMED", metadata={"memory_events": [
        {"kind": "confirmed_facts", "key": "fact", "value": "verified", "confirmed": True},
        {"kind": "pending", "key": "p", "value": "open"}]}))
    compact_conversation(store, scope, c.id)
    store.append_message(scope, Message(c.id, "user", "resolved", metadata={"memory_events": [
        {"kind": "completed_tasks", "key": "t", "value": "done", "resolves": "p"}]}))
    cp, _ = compact_conversation(store, scope, c.id)
    assert cp.confirmed_facts["fact"]["value"] == "verified" and not cp.pending
    with pytest.raises(ValueError):
        store.save_checkpoint(scope, ConversationCheckpoint(c.id, 3))
    with pytest.raises(ValueError):
        store.save_checkpoint(scope, ConversationCheckpoint(c.id, 2))
    with pytest.raises(ValueError):
        store.save_context_summary(scope, ContextSummary(c.id, 0, "wrong", [m.id]))


def test_context_budget_oversized_turn(store, scope):
    c = store.create_conversation(scope)
    store.append_message(scope, Message(c.id, "user", "文" * 50000))
    ctx = build_conversation_context(store, scope, c.id, budget_bytes=2048)
    assert ctx["requires_rehydration"] and ctx["recent"][0]["truncated"]
    assert len(json.dumps(ctx, ensure_ascii=False, separators=(",", ":")).encode()) <= 2048
    assert len(store.list_messages(scope, c.id).items[0].content) == 50000


@pytest.mark.parametrize("name", ["../secret.txt", "..\\secret.txt", "C:\\temp\\a.txt", "/tmp/a.txt", "CON.txt", "NUL", "..", "／etc.txt"])
def test_malicious_names(name):
    with pytest.raises(ValueError):
        sanitize_name(name)


def test_attachment_signatures_limits_metadata(store, scope, tmp_path):
    c = store.create_conversation(scope)
    a = ingest_attachment(store, scope, c.id, tmp_path / "files", "safe.txt", b"hello", declared_mime="image/png")
    assert a.mime_type == "text/plain" and a.declared_mime == "image/png"
    assert a.storage_reference == a.digest + ".blob"
    for name, data in [("fake.png", b"MZ"), ("evil.exe", b"MZ"), ("text.txt", b"\x00data")]:
        with pytest.raises(ValueError):
            ingest_attachment(store, scope, c.id, tmp_path, name, data)
    with pytest.raises(ValueError):
        ingest_attachment(store, scope, c.id, tmp_path, "huge.txt", b"1234", policy=AttachmentPolicy(max_bytes=3))
    with pytest.raises(ValueError):
        store.add_attachment_metadata(scope, Attachment(c.id, "safe.txt", "text/plain", 1, "a"*64, "../outside"))


@pytest.mark.parametrize("ext,marker", [(".docx", "word/document.xml"), (".xlsx", "xl/workbook.xml")])
def test_office_quarantine(store, scope, tmp_path, ext, marker):
    c = store.create_conversation(scope)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr(marker, "<document/>")
    a = ingest_attachment(store, scope, c.id, tmp_path, "file" + ext, buf.getvalue())
    assert a.status == "STORED_UNTRUSTED"


@pytest.mark.parametrize("action,kind", [("explain", ActionClass.READ_ONLY), ("query", ActionClass.READ_ONLY),
    ("draft", ActionClass.LOW_RISK), ("report", ActionClass.LOW_RISK), ("publish", ActionClass.REQUIRES_APPROVAL),
    ("email", ActionClass.REQUIRES_APPROVAL), ("merge", ActionClass.REQUIRES_APPROVAL), ("deploy", ActionClass.REQUIRES_APPROVAL),
    ("spend", ActionClass.REQUIRES_APPROVAL), ("credentials", ActionClass.REQUIRES_APPROVAL),
    ("trade_live", ActionClass.BLOCKED), ("unknown", ActionClass.BLOCKED)])
def test_authorization(action, kind):
    assert classify_action(action) == kind
    task = request_task("cid", "faça isso", action)
    if kind == ActionClass.REQUIRES_APPROVAL:
        assert task.state == TaskState.WAITING_APPROVAL
    if kind == ActionClass.BLOCKED:
        assert task.state == TaskState.FAILED


def test_service_tasks_feedback_no_fake_response(store, scope, tmp_path):
    c = store.create_conversation(scope)
    service = ChatService(store, scope, tmp_path)
    service.send(c.id, "oi")
    ms = store.list_messages(scope, c.id).items
    assert ms[-1].role == "system" and ms[-1].truth_state == "NOT_CONNECTED"
    assert not any(m.role == "assistant" for m in ms)
    service.send(c.id, "publique", action="publish")
    task = store.list_messages(scope, c.id).items[-1]
    assert task.task_metadata["state"] == "WAITING_APPROVAL"
    assert service.cancel(c.id, task.id).task_metadata["state"] == "CANCELLED"
    with pytest.raises(ValueError):
        service.cancel(c.id, task.id)
    assert service.feedback(c.id, task.id, "useful").metadata["message_id"] == task.id


def test_redaction(store, scope):
    c = store.create_conversation(scope, "api_key=secret-value", {"token": "secret"})
    m = store.append_message(scope, Message(c.id, "user", "senha=abc sk-abcdefghijk", metadata={"token": "secret"}))
    assert "secret-value" not in c.title and c.metadata["token"] == "[REDACTED]"
    assert "abc" not in m.content and "sk-" not in m.content and m.metadata["token"] == "[REDACTED]"


def test_ui_shell_css_accessibility():
    html = render_chat_html("test-token")
    for control in ["new", "search", "history", "message", "send", "image", "file", "more-messages", "drawer-toggle"]:
        assert f'id="{control}"' in html
    assert "NOT_CONNECTED" in html and "REQUIRES_PROVIDER" in html
    css = (ASSETS / "chat.css").read_text()
    assert "@media(max-width:700px)" in css and "prefers-reduced-motion:reduce" in css
    assert "100dvh" in css and "minmax(0,1fr)" in css
    js = (ASSETS / "chat.js").read_text()
    assert "textContent" in js and "innerHTML" not in js


@pytest.fixture
def preview(tmp_path):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    proc = subprocess.Popen([sys.executable, "atlasquant_aion_chat_ui.py", "--data-dir", str(tmp_path), "--port", str(port)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    root = f"http://127.0.0.1:{port}"
    try:
        html = None
        for _ in range(100):
            try:
                html = urlopen(root, timeout=.5).read().decode()
                break
            except OSError:
                if proc.poll() is not None:
                    pytest.fail(proc.stderr.read().decode())
                time.sleep(.05)
        assert html
        token = re.search(r'name="aion-token" content="([^"]+)"', html)[1]
        yield root, token
    finally:
        proc.terminate()
        proc.wait(timeout=5)
        proc.stderr.close()


def test_http_send_attach_context_csrf(preview):
    root, token = preview
    def call(path, body=None, headers=None):
        req = Request(root + path, json.dumps(body).encode() if body else None,
                      {"X-Aion-Token": token, "Content-Type": "application/json", **(headers or {})})
        return json.loads(urlopen(req).read())
    c = call("/api/create", {"title": "HTTP"})
    a = call("/api/attach", {"cid": c["id"], "name": "note.txt", "data": base64.b64encode(b"note").decode()})
    call("/api/send", {"cid": c["id"], "content": "olá", "attachments": [a["id"]]})
    assert call("/api/messages?cid=" + c["id"])["items"][-1]["attachments"] == [a["id"]]
    assert call("/api/conversations")["items"][0]["message_count"] == 2
    call("/api/compact", {"cid": c["id"]})
    assert call("/api/context?cid=" + c["id"])["checkpoint_id"]
    for headers in [{"X-Aion-Token": "wrong"}, {"Origin": "https://evil.example"}, {"Host": "evil.example"}]:
        with pytest.raises(HTTPError) as err:
            call("/api/create", {"title": "attack"}, headers)
        assert err.value.code == 403


def test_task_state_compaction_continuity(store, scope, tmp_path):
    c = store.create_conversation(scope)
    svc = ChatService(store, scope, tmp_path)
    svc.send(c.id, "publique", action="publish")
    task = store.list_messages(scope, c.id).items[-1]
    cp, _ = compact_conversation(store, scope, c.id)
    tid = task.task_metadata["id"]
    assert cp.open_tasks[tid]["value"]["state"] == "WAITING_APPROVAL"
    assert tid in cp.pending
    svc.cancel(c.id, task.id)
    cp, _ = compact_conversation(store, scope, c.id)
    assert tid not in cp.pending and tid not in cp.open_tasks
    assert cp.execution_state[tid]["value"]["state"] == "CANCELLED"


def test_cross_conversation_attachment_and_atomic_failure(store, scope, tmp_path):
    c = store.create_conversation(scope)
    other = store.create_conversation(scope)
    a = ingest_attachment(store, scope, c.id, tmp_path, "safe.txt", b"safe")
    with pytest.raises(LookupError):
        store.append_message(scope, Message(other.id, "user", "wrong", attachments=[a.id]))
    assert store.get_conversation(scope, other.id).message_count == 0
    m = store.append_message(scope, Message(c.id, "user", "first"))
    with pytest.raises(Exception):
        store.append_message(scope, m)
    assert store.get_conversation(scope, c.id).message_count == 1


def test_checkpoint_overflow_still_preserves_pending_in_storage(store, scope):
    c = store.create_conversation(scope)
    store.append_message(scope, Message(c.id, "user", "event", metadata={"memory_events": [
        {"kind": "pending", "key": f"p{i}", "value": "x"*1000} for i in range(20)]}))
    cp, _ = compact_conversation(store, scope, c.id)
    ctx = build_conversation_context(store, scope, c.id, budget_bytes=1024)
    assert ctx["requires_rehydration"] and ctx["checkpoint_id"] == cp.id
    assert len(store.get_latest_checkpoint(scope, c.id).pending) == 20
    assert len(json.dumps(ctx, ensure_ascii=False, separators=(",", ":")).encode()) <= 1024
