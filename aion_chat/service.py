"""Persist conversations and task events, never execute instructions."""
from dataclasses import asdict
from .attachments import ingest_attachment
from .authorization import request_task
from .models import Message, TaskState
from .privacy import redact


class ChatService:
    def __init__(self, store, scope, attachment_root, policy=None):
        self.store, self.scope, self.attachment_root, self.policy = store, scope, attachment_root, policy

    def send(self, conversation_id, content, attachments=None, *, action=None):
        if not content.strip() and not attachments:
            raise ValueError("empty message")
        m = self.store.append_message(self.scope, Message(conversation_id, "user", content, attachments=attachments or []))
        if action:
            task = request_task(conversation_id, redact(content), action)
            text = ("Aguardando aprovação. Executor não conectado." if task.state == TaskState.WAITING_APPROVAL
                    else "Ação bloqueada." if task.state == TaskState.FAILED else "Tarefa registrada. Executor não conectado.")
            self.store.append_message(self.scope, Message(conversation_id, "task", text, task_metadata=asdict(task), truth_state="NOT_CONNECTED"))
        else:
            self.store.append_message(self.scope, Message(conversation_id, "system",
                "Mensagem salva. Modelo indisponível: nenhum provedor está conectado nesta fundação.", truth_state="NOT_CONNECTED"))
        return m

    def attach(self, conversation_id, name, data, declared_mime=""):
        return ingest_attachment(self.store, self.scope, conversation_id, self.attachment_root, name, data,
                                 declared_mime=declared_mime, policy=self.policy)

    def cancel(self, conversation_id, task_message_id):
        m = self.store.get_message(self.scope, conversation_id, task_message_id)
        if not m.task_metadata:
            raise ValueError("not a task")
        cursor = None
        while True:
            page = self.store.list_messages(self.scope, conversation_id, cursor=cursor, newest_first=True, page_size=200)
            for event in page.items:
                if event.task_metadata and event.task_metadata.get("id") == m.task_metadata["id"]:
                    if event.task_metadata["state"] not in {"PENDING", "RUNNING", "WAITING_APPROVAL"}:
                        raise ValueError("task is terminal")
                    return self.store.append_message(self.scope, Message(conversation_id, "task", "Tarefa cancelada.",
                        task_metadata=dict(m.task_metadata, state="CANCELLED")))
            if not page.next_cursor:
                raise LookupError("task unavailable")
            cursor = page.next_cursor

    def feedback(self, conversation_id, message_id, value):
        self.store.get_message(self.scope, conversation_id, message_id)
        if value not in {"useful", "needs_revision"}:
            raise ValueError("invalid feedback")
        return self.store.append_message(self.scope, Message(conversation_id, "system", "Feedback registrado.",
            metadata={"feedback": value, "message_id": message_id}))
