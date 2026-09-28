"""Exact task scope, supplied by an authenticated application boundary."""
from dataclasses import dataclass
from enum import Enum
import json
import re


class Domain(str, Enum):
    ADMIN = "ADMIN"
    DEVELOPER = "DEVELOPER"
    CONTENT = "CONTENT"
    RESEARCH = "RESEARCH"
    BUSINESS = "BUSINESS"
    TRADER = "TRADER"
    INVESTMENTS = "INVESTMENTS"


FUTURE_DOMAINS = frozenset({Domain.BUSINESS, Domain.TRADER, Domain.INVESTMENTS})


def identifier(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}", value):
        raise ValueError("invalid context identifier")
    return value


@dataclass(frozen=True)
class Context:
    tenant_id: str
    workspace_id: str
    actor_id: str
    task_id: str
    domain: Domain
    role: str = "USER"

    def __post_init__(self):
        for value in (self.tenant_id, self.workspace_id, self.actor_id, self.task_id):
            identifier(value)
        if not isinstance(self.domain, Domain) or self.role not in {"USER", "ADMIN"}:
            raise ValueError("invalid context domain or role")

    @property
    def key(self) -> str:
        # Role is not an identity; role changes cannot move memory to another user.
        return json.dumps([self.tenant_id, self.workspace_id, self.actor_id,
                           self.task_id, self.domain.value], separators=(",", ":"))

    def require_domain(self, domain: Domain) -> None:
        if self.domain != domain:
            raise ValueError("CONTEXT_SWITCH_REQUIRED")
