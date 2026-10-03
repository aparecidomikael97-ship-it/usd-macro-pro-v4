"""Adapter contracts only. No production imports or physical execution."""
from typing import Protocol
from .models import Scope, TaskRequest, TaskResult


class ModelAdapter(Protocol):
    def respond(self, scope: Scope, context: dict) -> str: ...


class CheckpointMasterAdapter(Protocol):
    def prepare_export(self, scope: Scope, checkpoint: dict) -> dict: ...
    def save_approved(self, scope: Scope, export: dict, approval_receipt: str) -> dict: ...


class TaskAdapter(Protocol):
    def prepare(self, scope: Scope, request: TaskRequest) -> TaskResult: ...


class VoiceAdapter(Protocol):
    def transcribe(self, scope: Scope, audio: bytes) -> str: ...
    def speak(self, scope: Scope, text: str) -> bytes: ...


class RetrievalAdapter(Protocol):
    def retrieve(self, scope: Scope, query: str) -> list[dict]: ...
