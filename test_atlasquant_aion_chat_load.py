"""Bounded local load smoke for AION chat persistence; no provider/network usage."""
import time

from aion_chat.context import compact_conversation
from aion_chat.models import Message, Scope
from aion_chat.store import SQLiteChatStore


def test_local_load_100_conversations_1000_messages_restart_and_pagination(tmp_path, capsys):
    db = tmp_path / "load.sqlite"
    scope = Scope("load-owner", "load-tenant", "load-workspace")
    start = time.perf_counter()
    store = SQLiteChatStore(db)

    conversations = [store.create_conversation(scope, f"Conversa {i}") for i in range(100)]
    target = conversations[0]
    for i in range(1000):
        store.append_message(scope, Message(target.id, "user", f"Mensagem de carga {i}"))

    write_seconds = time.perf_counter() - start
    assert len(store.list_conversations(scope, page_size=200).items) == 100
    assert store.get_conversation(scope, target.id).message_count == 1000

    ids = []
    cursor = None
    page_start = time.perf_counter()
    while True:
        page = store.list_messages(scope, target.id, cursor=cursor, page_size=73)
        ids.extend(m.id for m in page.items)
        if not page.next_cursor:
            break
        cursor = page.next_cursor
    pagination_seconds = time.perf_counter() - page_start
    assert len(ids) == len(set(ids)) == 1000

    checkpoint_start = time.perf_counter()
    checkpoint, summary = compact_conversation(store, scope, target.id, through_sequence=980)
    checkpoint_seconds = time.perf_counter() - checkpoint_start
    assert checkpoint.through_sequence == summary.through_sequence == 980
    store.close()

    reopen_start = time.perf_counter()
    reopened = SQLiteChatStore(db)
    reopen_seconds = time.perf_counter() - reopen_start
    assert reopened.get_conversation(scope, target.id).message_count == 1000
    assert reopened.get_message(scope, target.id, ids[0]).sequence == 1
    assert reopened.get_latest_checkpoint(scope, target.id).through_sequence == 980
    reopened.close()

    metrics = {
        "conversations": 100,
        "messages": 1000,
        "write_seconds": round(write_seconds, 4),
        "pagination_seconds": round(pagination_seconds, 4),
        "checkpoint_seconds": round(checkpoint_seconds, 4),
        "reopen_seconds": round(reopen_seconds, 4),
    }
    print("AION_CHAT_LOAD_METRICS", metrics)
    captured = capsys.readouterr()
    assert "AION_CHAT_LOAD_METRICS" in captured.out
