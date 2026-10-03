from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4


def now():
    return datetime.now(timezone.utc).isoformat()


def uid():
    return uuid4().hex


class ActionClass(str, Enum):
    READ_ONLY = "READ_ONLY"
    LOW_RISK = "LOW_RISK"
    REQUIRES_APPROVAL = "REQUIRES_APPROVAL"
    BLOCKED = "BLOCKED"


class TaskState(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True)
class Scope:
    owner_id: str
    tenant_id: str
    workspace_id: str

    def __post_init__(self):
        if any(not isinstance(v, str) or not v.strip() for v in (self.owner_id, self.tenant_id, self.workspace_id)):
            raise ValueError("owner, tenant and workspace required")


@dataclass
class Conversation:
    owner_id: str
    tenant_id: str
    workspace_id: str
    title: str = "Nova conversa"
    id: str = field(default_factory=uid)
    created_at: str = field(default_factory=now)
    updated_at: str = field(default_factory=now)
    archived: bool = False
    message_count: int = 0
    latest_checkpoint: str | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class Message:
    conversation_id: str
    role: str
    content: str
    id: str = field(default_factory=uid)
    created_at: str = field(default_factory=now)
    attachments: list = field(default_factory=list)
    task_metadata: dict | None = None
    provenance: dict | None = None
    truth_state: str | None = None
    metadata: dict = field(default_factory=dict)
    sequence: int = 0


@dataclass
class Attachment:
    conversation_id: str
    name: str
    mime_type: str
    size: int
    digest: str
    storage_reference: str
    origin: str = "local_upload"
    status: str = "STORED_UNTRUSTED"
    declared_mime: str = ""
    id: str = field(default_factory=uid)
    created_at: str = field(default_factory=now)


@dataclass
class ConversationCheckpoint:
    conversation_id: str
    through_sequence: int
    decisions: dict = field(default_factory=dict)
    open_tasks: dict = field(default_factory=dict)
    completed_tasks: dict = field(default_factory=dict)
    preferences: dict = field(default_factory=dict)
    entities: dict = field(default_factory=dict)
    files: dict = field(default_factory=dict)
    pending: dict = field(default_factory=dict)
    confirmed_facts: dict = field(default_factory=dict)
    assumptions: dict = field(default_factory=dict)
    provenance: list = field(default_factory=list)
    execution_state: dict = field(default_factory=dict)
    id: str = field(default_factory=uid)
    created_at: str = field(default_factory=now)


@dataclass
class ContextSummary:
    conversation_id: str
    through_sequence: int
    content: str
    source_message_ids: list = field(default_factory=list)
    method: str = "structured_extractive_v1"
    id: str = field(default_factory=uid)
    created_at: str = field(default_factory=now)


@dataclass
class TaskRequest:
    conversation_id: str
    instruction: str
    action: str
    classification: ActionClass
    state: TaskState = TaskState.PENDING
    id: str = field(default_factory=uid)
    created_at: str = field(default_factory=now)


@dataclass
class TaskResult:
    task_id: str
    state: TaskState
    content: str
    provenance: dict = field(default_factory=dict)


@dataclass
class Page:
    items: list
    next_cursor: str | None = None
