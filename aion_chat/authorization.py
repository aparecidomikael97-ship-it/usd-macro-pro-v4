"""Classification never grants execution authority."""
from .models import ActionClass, TaskRequest, TaskState


def classify_action(action):
    if action in {"explain", "query", "verify", "analyze"}:
        return ActionClass.READ_ONLY
    if action in {"draft", "report", "create_task"}:
        return ActionClass.LOW_RISK
    if action in {"publish", "email", "merge", "deploy", "spend", "credentials", "open_trader"}:
        return ActionClass.REQUIRES_APPROVAL
    return ActionClass.BLOCKED


def request_task(conversation_id, instruction, action):
    kind = classify_action(action)
    state = (TaskState.WAITING_APPROVAL if kind == ActionClass.REQUIRES_APPROVAL
             else TaskState.FAILED if kind == ActionClass.BLOCKED else TaskState.PENDING)
    return TaskRequest(conversation_id, instruction, action, kind, state)
