"""Local SQLite staging. All reads and writes require a trusted identity scope."""
import base64
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Protocol
from .models import Attachment, ContextSummary, Conversation, ConversationCheckpoint, Message, Page, Scope, now
from .privacy import redact


class AionChatStore(Protocol):
    def create_conversation(self, scope: Scope, title="Nova conversa", metadata=None) -> Conversation: ...
    def get_conversation(self, scope: Scope, conversation_id: str) -> Conversation: ...
    def list_conversations(self, scope: Scope, cursor=None, page_size=30, **filters) -> Page: ...
    def search_conversations(self, scope: Scope, query: str, **filters) -> Page: ...
    def archive_conversation(self, scope: Scope, conversation_id: str) -> Conversation: ...
    def append_message(self, scope: Scope, message: Message) -> Message: ...
    def list_messages(self, scope: Scope, conversation_id: str, cursor=None, page_size=50, **options) -> Page: ...
    def get_message(self, scope: Scope, conversation_id: str, message_id: str) -> Message: ...
    def add_attachment_metadata(self, scope: Scope, attachment: Attachment) -> Attachment: ...
    def get_attachment(self, scope: Scope, conversation_id: str, attachment_id: str) -> Attachment: ...
    def save_checkpoint(self, scope: Scope, checkpoint: ConversationCheckpoint): ...
    def get_latest_checkpoint(self, scope: Scope, conversation_id: str): ...
    def save_context_summary(self, scope: Scope, summary: ContextSummary): ...
    def get_latest_summary(self, scope: Scope, conversation_id: str): ...
    def retrieve_messages(self, scope: Scope, conversation_id: str, query: str, **options): ...


def dump(value):
    return json.dumps(redact(asdict(value)), ensure_ascii=False, separators=(",", ":"))


class SQLiteChatStore:
    def __init__(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path), timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
        PRAGMA foreign_keys=ON;
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS conversations(id TEXT PRIMARY KEY, owner TEXT NOT NULL,
            tenant TEXT NOT NULL, workspace TEXT NOT NULL, updated TEXT NOT NULL,
            archived INTEGER NOT NULL, title TEXT NOT NULL, data TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS scope_recency ON conversations(owner,tenant,workspace,archived,updated,id);
        CREATE TABLE IF NOT EXISTS messages(id TEXT PRIMARY KEY,cid TEXT NOT NULL REFERENCES conversations(id),
            seq INTEGER NOT NULL,content TEXT NOT NULL,data TEXT NOT NULL,UNIQUE(cid,seq));
        CREATE INDEX IF NOT EXISTS message_history ON messages(cid,seq);
        CREATE TABLE IF NOT EXISTS records(id TEXT PRIMARY KEY,cid TEXT NOT NULL REFERENCES conversations(id),
            kind TEXT NOT NULL,seq INTEGER NOT NULL,data TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS record_history ON records(cid,kind,seq,id);
        """)

    def close(self):
        self.db.close()

    def _scope(self, scope):
        if not isinstance(scope, Scope):
            raise TypeError("trusted Scope required")
        return scope.owner_id, scope.tenant_id, scope.workspace_id

    def get_conversation(self, scope, conversation_id):
        row = self.db.execute("SELECT data FROM conversations WHERE id=? AND owner=? AND tenant=? AND workspace=?",
                              (conversation_id, *self._scope(scope))).fetchone()
        if row is None:
            raise LookupError("conversation unavailable")
        return Conversation(**json.loads(row[0]))

    def _update(self, c):
        self.db.execute("UPDATE conversations SET updated=?,archived=?,title=?,data=? WHERE id=?",
                        (c.updated_at, c.archived, c.title, dump(c), c.id))

    def create_conversation(self, scope, title="Nova conversa", metadata=None):
        self._scope(scope)
        c = Conversation(**asdict(scope), title=redact(title), metadata=redact(metadata or {}))
        with self.db:
            self.db.execute("INSERT INTO conversations VALUES (?,?,?,?,?,?,?,?)",
                            (c.id, *self._scope(scope), c.updated_at, c.archived, c.title, dump(c)))
        return c

    def _cursor_key(self, scope, spec):
        return hashlib.sha256(json.dumps([self._scope(scope), spec], sort_keys=True).encode()).hexdigest()

    def _encode(self, scope, spec, boundary):
        return base64.urlsafe_b64encode(json.dumps([self._cursor_key(scope, spec), boundary]).encode()).decode()

    def _decode(self, scope, spec, cursor):
        try:
            key, boundary = json.loads(base64.urlsafe_b64decode(cursor))
            if key != self._cursor_key(scope, spec):
                raise ValueError()
            return boundary
        except Exception as exc:
            raise ValueError("invalid cursor for scope/query") from exc

    @staticmethod
    def _size(size):
        if not isinstance(size, int) or not 1 <= size <= 200:
            raise ValueError("page_size must be 1..200; this is not a history limit")
        return size

    def list_conversations(self, scope, cursor=None, page_size=30, *, query="", tag=None, since=None, until=None, archived=False):
        size = self._size(page_size)
        spec = ["conversations", query, tag, since, until, archived]
        sql = "SELECT c.* FROM conversations c WHERE owner=? AND tenant=? AND workspace=? AND archived=?"
        args = [*self._scope(scope), archived]
        if query:
            sql += " AND (instr(lower(title),lower(?))>0 OR EXISTS(SELECT 1 FROM messages m WHERE m.cid=c.id AND instr(lower(m.content),lower(?))>0) OR EXISTS(SELECT 1 FROM json_each(c.data,'$.metadata.tags') WHERE instr(lower(value),lower(?))>0))"
            args += [query, query, query]
        if tag:
            sql += " AND EXISTS(SELECT 1 FROM json_each(c.data,'$.metadata.tags') WHERE value=?)"
            args.append(tag)
        for value, op in ((since, ">="), (until, "<=")):
            if value:
                sql += f" AND updated{op}?"
                args.append(value)
        if cursor:
            updated, cid = self._decode(scope, spec, cursor)
            sql += " AND (updated,id)<(?,?)"
            args += [updated, cid]
        rows = self.db.execute(sql + " ORDER BY updated DESC,id DESC LIMIT ?", [*args, size+1]).fetchall()
        items = [Conversation(**json.loads(r["data"])) for r in rows[:size]]
        nxt = self._encode(scope, spec, [rows[size-1]["updated"], rows[size-1]["id"]]) if len(rows) > size else None
        return Page(items, nxt)

    def search_conversations(self, scope, query, **filters):
        return self.list_conversations(scope, query=query, **filters)

    def archive_conversation(self, scope, conversation_id):
        with self.db:
            c = self.get_conversation(scope, conversation_id)
            c.archived, c.updated_at = True, now()
            self._update(c)
        return c

    def append_message(self, scope, message):
        if message.role not in {"user", "assistant", "system", "task"}:
            raise ValueError("invalid role")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            c = self.get_conversation(scope, message.conversation_id)
            for aid in message.attachments:
                self.get_attachment(scope, c.id, aid)
            message = Message(**redact(asdict(message)))
            message.sequence = c.message_count + 1
            self.db.execute("INSERT INTO messages VALUES (?,?,?,?,?)", (message.id, c.id, message.sequence, message.content, dump(message)))
            c.message_count, c.updated_at = message.sequence, now()
            self._update(c)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return message

    def list_messages(self, scope, conversation_id, cursor=None, page_size=50, *, newest_first=False):
        self.get_conversation(scope, conversation_id)
        size = self._size(page_size)
        spec = ["messages", conversation_id, newest_first]
        sql, args = "SELECT * FROM messages WHERE cid=?", [conversation_id]
        if cursor:
            sql += " AND seq" + ("<?" if newest_first else ">?")
            args.append(self._decode(scope, spec, cursor))
        order = "DESC" if newest_first else "ASC"
        rows = self.db.execute(sql + f" ORDER BY seq {order} LIMIT ?", [*args, size+1]).fetchall()
        items = [Message(**json.loads(r["data"])) for r in rows[:size]]
        return Page(items, self._encode(scope, spec, items[-1].sequence) if len(rows) > size else None)

    def get_message(self, scope, conversation_id, message_id):
        self.get_conversation(scope, conversation_id)
        row = self.db.execute("SELECT data FROM messages WHERE cid=? AND id=?", (conversation_id, message_id)).fetchone()
        if not row:
            raise LookupError("message unavailable")
        return Message(**json.loads(row[0]))

    def _save_record(self, scope, kind, value, seq=0):
        c = self.get_conversation(scope, value.conversation_id)
        if not isinstance(seq, int) or not 0 <= seq <= c.message_count:
            raise ValueError("invalid coverage sequence")
        self.db.execute("INSERT INTO records VALUES (?,?,?,?,?)", (value.id, c.id, kind, seq, dump(value)))

    def add_attachment_metadata(self, scope, attachment):
        from .attachments import validate_metadata
        validate_metadata(attachment)
        with self.db:
            self._save_record(scope, "attachment", attachment)
        return attachment

    def get_attachment(self, scope, conversation_id, attachment_id):
        self.get_conversation(scope, conversation_id)
        row = self.db.execute("SELECT data FROM records WHERE cid=? AND id=? AND kind='attachment'", (conversation_id, attachment_id)).fetchone()
        if not row:
            raise LookupError("attachment unavailable")
        return Attachment(**json.loads(row[0]))

    def _latest(self, scope, cid, kind, model):
        self.get_conversation(scope, cid)
        row = self.db.execute("SELECT data FROM records WHERE cid=? AND kind=? ORDER BY seq DESC,id DESC LIMIT 1", (cid, kind)).fetchone()
        return model(**json.loads(row[0])) if row else None

    def get_latest_checkpoint(self, scope, conversation_id):
        return self._latest(scope, conversation_id, "checkpoint", ConversationCheckpoint)

    def save_checkpoint(self, scope, checkpoint):
        with self.db:
            prior = self.get_latest_checkpoint(scope, checkpoint.conversation_id)
            if prior and checkpoint.through_sequence <= prior.through_sequence:
                raise ValueError("coverage must advance")
            self._save_record(scope, "checkpoint", checkpoint, checkpoint.through_sequence)
            c = self.get_conversation(scope, checkpoint.conversation_id)
            c.latest_checkpoint = checkpoint.id
            self._update(c)

    def save_context_summary(self, scope, summary):
        with self.db:
            for mid in summary.source_message_ids:
                if self.get_message(scope, summary.conversation_id, mid).sequence > summary.through_sequence:
                    raise ValueError("source beyond coverage")
            self._save_record(scope, "summary", summary, summary.through_sequence)

    def get_latest_summary(self, scope, conversation_id):
        return self._latest(scope, conversation_id, "summary", ContextSummary)

    def retrieve_messages(self, scope, conversation_id, query, *, before_sequence, limit=10):
        self.get_conversation(scope, conversation_id)
        self._size(limit)
        rows = self.db.execute("SELECT data FROM messages WHERE cid=? AND seq<? AND instr(lower(content),lower(?))>0 ORDER BY seq DESC LIMIT ?",
                               (conversation_id, before_sequence, query, limit)).fetchall() if query.strip() else []
        return [Message(**json.loads(r[0])) for r in rows]
