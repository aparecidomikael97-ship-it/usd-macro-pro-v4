"""Finite context assembled from immutable history and explicit memory events."""
from dataclasses import asdict
import json
from .models import ContextSummary, ConversationCheckpoint

FIELDS = ("pending", "open_tasks", "decisions", "preferences", "confirmed_facts", "files", "completed_tasks", "assumptions", "entities", "execution_state")


def compact_conversation(store, scope, conversation_id, *, through_sequence=None):
    c = store.get_conversation(scope, conversation_id)
    through = c.message_count if through_sequence is None else through_sequence
    if not isinstance(through, int) or not 0 < through <= c.message_count:
        raise ValueError("invalid coverage")
    prior = store.get_latest_checkpoint(scope, conversation_id)
    if prior and through <= prior.through_sequence:
        raise ValueError("coverage must advance")
    state = {k: dict(getattr(prior, k)) if prior else {} for k in FIELDS}
    provenance = list(prior.provenance) if prior else []
    cursor, excerpts, sources = None, [], []
    while True:
        page = store.list_messages(scope, conversation_id, cursor=cursor, page_size=200)
        for m in page.items:
            if m.sequence > through:
                break
            if prior and m.sequence <= prior.through_sequence:
                continue
            for aid in m.attachments:
                a = store.get_attachment(scope, conversation_id, aid)
                state["files"][aid] = {"name": a.name, "digest": a.digest, "source_message_id": m.id}
            if m.task_metadata:
                task = m.task_metadata
                task_id = task.get("id")
                task_state = task.get("state")
                if task_id:
                    entry = {"value": task, "source_message_id": m.id,
                             "truth_state": m.truth_state or "UNVERIFIED", "provenance": m.provenance}
                    state["execution_state"][task_id] = entry
                    if task_state == "COMPLETED":
                        state["completed_tasks"][task_id] = entry
                        state["open_tasks"].pop(task_id, None)
                        state["pending"].pop(task_id, None)
                    elif task_state in {"CANCELLED", "FAILED"}:
                        state["open_tasks"].pop(task_id, None)
                        state["pending"].pop(task_id, None)
                    else:
                        state["open_tasks"][task_id] = entry
                        if task_state == "WAITING_APPROVAL":
                            state["pending"][task_id] = entry
            for event in m.metadata.get("memory_events", []):
                kind, key = event.get("kind"), event.get("key")
                if kind not in FIELDS or not isinstance(key, str) or not key:
                    raise ValueError("invalid memory event")
                if kind == "confirmed_facts" and (event.get("confirmed") is not True or m.truth_state != "CONFIRMED"):
                    kind = "assumptions"
                state[kind][key] = {"value": event.get("value"), "source_message_id": m.id,
                                    "truth_state": m.truth_state or "UNVERIFIED", "provenance": m.provenance}
                if kind == "completed_tasks":
                    state["open_tasks"].pop(key, None)
                if kind == "confirmed_facts":
                    state["assumptions"].pop(key, None)
                if event.get("resolves"):
                    state["pending"].pop(str(event["resolves"]), None)
                provenance.append({"message_id": m.id, "kind": kind, "key": key, "sequence": m.sequence})
            excerpts.append({"message_id": m.id, "role": m.role, "excerpt": m.content[:240], "truth_state": m.truth_state or "UNVERIFIED"})
            sources.append(m.id)
            excerpts, sources = excerpts[-12:], sources[-12:]
        if not page.next_cursor or page.items[-1].sequence >= through:
            break
        cursor = page.next_cursor
    checkpoint = ConversationCheckpoint(conversation_id, through, **state, provenance=provenance)
    summary = ContextSummary(conversation_id, through, json.dumps({"checkpoint_id": checkpoint.id, "unverified_excerpts": excerpts}, ensure_ascii=False), sources)
    store.save_checkpoint(scope, checkpoint)
    store.save_context_summary(scope, summary)
    return checkpoint, summary


def build_conversation_context(store, scope, conversation_id, *, query="", budget_bytes=24000, recent_count=20, retrieval_count=8):
    """Byte budget bounds serialized context; a provider must additionally count tokens.

    Omitted memory is referenced by checkpoint id and requires rehydration before
    consequential decisions. Truncated prose retains its original message id.
    """
    if budget_bytes < 512:
        raise ValueError("budget too small")
    recent = store.list_messages(scope, conversation_id, page_size=recent_count, newest_first=True).items
    cp = store.get_latest_checkpoint(scope, conversation_id)
    summary = store.get_latest_summary(scope, conversation_id)
    older = store.retrieve_messages(scope, conversation_id, query, before_sequence=min((m.sequence for m in recent), default=1), limit=retrieval_count)
    out = {"conversation_id": conversation_id, "checkpoint_id": cp.id if cp else None, "summary_id": summary.id if summary else None,
           "checkpoint": {k: {} for k in FIELDS} if cp else {}, "summary": None, "recent": [], "retrieved": [], "requires_rehydration": False}
    def size():
        return len(json.dumps(out, ensure_ascii=False, separators=(",", ":")).encode())
    for m in recent:
        item = asdict(m)
        out["recent"].append(item)
        if size() > budget_bytes:
            out["recent"].pop()
            item["content"], item["truncated"] = item["content"][:budget_bytes // 8], True
            out["recent"].append(item)
            if size() > budget_bytes:
                out["recent"].pop()
            out["requires_rehydration"] = True
            break
    out["recent"].reverse()
    if cp:
        for kind in FIELDS:
            for key, value in getattr(cp, kind).items():
                out["checkpoint"][kind][key] = value
                if size() > budget_bytes:
                    del out["checkpoint"][kind][key]
                    out["requires_rehydration"] = True
    if summary:
        out["summary"] = summary.content
        if size() > budget_bytes:
            out["summary"] = None
            out["requires_rehydration"] = True
    for m in older:
        out["retrieved"].append(asdict(m))
        if size() > budget_bytes:
            out["retrieved"].pop()
            out["requires_rehydration"] = True
    if size() > budget_bytes:
        raise ValueError("references exceed context budget")
    return out
