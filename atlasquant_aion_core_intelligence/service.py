"""Application facade. Dispatches only local data processing, never physical tools."""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Callable

from . import administration, content, developer, research
from .approval import Action, ApprovalGate, HumanApprovalAdapter
from .context import Context, FUTURE_DOMAINS
from .evidence import Evidence, Origin, utc
from .registry import Registry
from .router import route, words
from .store import CoreStore


SENSITIVE_INTENTS = {
    Action.PUBLICATION: frozenset({"publique", "publicar", "publicacao", "publish"}),
    Action.EXTERNAL_CHANGE: frozenset({"external", "externamente"}),
    Action.PAYMENT: frozenset({"pague", "pagar", "pagamento", "pagamentos", "cobrar"}),
    Action.FINANCIAL_CHANGE: frozenset({"transfira", "transferir", "saque", "deposito"}),
    Action.DEPLOY: frozenset({"deploy", "implantar"}),
    Action.MARKET_OPERATION: frozenset({"opere", "negociar", "trade"}),
}


@dataclass(frozen=True)
class ScopedEvidence:
    context: Context
    records: tuple[Evidence, ...]

    def __post_init__(self):
        if not isinstance(self.context, Context) or not isinstance(self.records, tuple):
            raise ValueError("typed evidence scope required")
        if len(self.records) > 200 or any(not isinstance(x, Evidence) for x in self.records):
            raise ValueError("bounded typed evidence required")

    def for_context(self, context: Context) -> tuple[Evidence, ...]:
        if context.key != self.context.key:
            raise ValueError("EVIDENCE_CONTEXT_MISMATCH")
        return self.records


class AionCore:
    def __init__(self, store: CoreStore | None = None, *,
                 human_adapter: HumanApprovalAdapter | None = None,
                 clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)):
        self.store = store
        self.clock = clock
        self.registry = Registry(checkpoint_connected=store is not None and not store.closed)
        self.approvals = ApprovalGate(store, human_adapter) if store else None
        self._handlers = {
            "ADMINISTRATION": self._administration,
            "MEMORY": self._memory,
            "DEVELOPER": self._developer,
            "RESEARCH": self._research,
            "CONTENT": self._content,
            "OBSERVABILITY": self._observability,
        }

    def _event(self, context, kind, now, result=""):
        if self.store:
            self.store.event(context, kind, now, result)

    def handle(self, intent: str, context: Context, *, evidence: ScopedEvidence | None = None,
               capability: str | None = None, action: Action | None = None,
               source_code: str | None = None, before_code: str | None = None,
               branch: str | None = None, baseline_ref: str | None = None) -> dict:
        now = utc(self.clock())
        if not isinstance(context, Context):
            raise ValueError("authenticated application context required")
        try:
            self._event(context, "intent_received", now)
            records = evidence.for_context(context) if evidence else ()
            selection = route(intent, context, self.registry, capability=capability)
            result = {"route": asdict(selection), "status": selection.status,
                      "execution_authorized": False, "external_action_executed": False,
                      "real_trading_enabled": False, "provider_called": False,
                      "memory_auto_written": False, "payload": None}
            if selection.status in {"DENIED", "UNAVAILABLE", "CONTEXT_SWITCH_REQUIRED", "CLARIFICATION_REQUIRED"}:
                self._event(context, "capability_unavailable", now, "BLOCKED")
                return result
            if action is not None and not isinstance(action, Action):
                raise ValueError("typed approval action required")
            matched = {a for a, markers in SENSITIVE_INTENTS.items() if words(intent) & markers}
            if action:
                matched.add(action)
            if len(matched) > 1:
                result.update(status="CLARIFICATION_REQUIRED", reason="MULTIPLE_SENSITIVE_ACTIONS")
                return result
            if matched:
                chosen = next(iter(matched))
                if not self.approvals:
                    result.update(status="UNAVAILABLE", reason="APPROVAL_STORE_UNAVAILABLE")
                    return result
                # Approval hashes the bounded request; raw intent never enters the journal.
                request = self.approvals.request(context, chosen, {"intent": intent}, now)
                result.update(status="APPROVAL_REQUIRED", payload=request)
                return result
            if selection.status != "SELECTED":
                return result
            self._event(context, "module_selected", now)
            handler = self._handlers.get(selection.capability)
            if handler is None:
                self._event(context, "capability_unavailable", now, "UNAVAILABLE")
                result.update(status="UNAVAILABLE", reason="LOCAL_HANDLER_NOT_CONNECTED")
                return result
            result["payload"] = handler(context=context, intent=intent, records=records, now=now,
                source_code=source_code, before_code=before_code, branch=branch, baseline_ref=baseline_ref)
            result["status"] = "COMPLETED"
            self._event(context, "completed", now, "OK")
            return result
        except Exception:
            # Failure remains explicit; exception text can contain credentials/code.
            if self.store and not self.store.closed:
                self._event(context, "error", now, "ERROR")
            raise

    def remember(self, context: Context, *, kind: str, text: str, origin: Origin,
                 source: str, expected_revision: int, evidence_refs: tuple[str, ...] = (),
                 record_id: str | None = None, approval_id: str | None = None) -> dict:
        if context.domain in FUTURE_DOMAINS:
            raise ValueError("FUTURE_CONTEXT_DISABLED")
        if self.store is None:
            raise ValueError("CHECKPOINT_UNAVAILABLE")
        now = utc(self.clock())
        try:
            return self.store.append(context, kind=kind, text=text, origin=origin, source=source,
                now=now, expected_revision=expected_revision, evidence_refs=evidence_refs,
                record_id=record_id, approval_id=approval_id)
        except Exception:
            self._event(context, "error", now, "ERROR")
            raise

    def _administration(self, *, context, records, now, **_):
        observations = {name: tuple(x for x in records if x.claim == name) for name in administration.FIELDS}
        return administration.status(context, self.registry, self.store, observations, now)

    def _memory(self, *, context, now, **_):
        rows = self.store.read(context, now)
        return {"status": "SCOPED_MEMORY", "records": rows,
                "approved_decisions": [x for x in rows if x["kind"] == "DECISION" and x["origin"] == Origin.USER_APPROVED.value],
                "answer_truth": "UNKNOWN" if not rows else "RECORDED_PROVENANCE",
                "reason": "Records retain origin; inference is never an approved decision."}

    def _developer(self, *, context, intent, records, now, source_code, before_code,
                   branch, baseline_ref, **_):
        return {
            "analysis": developer.analyze(source_code) if source_code is not None else {"status": "UNKNOWN", "reason": "SOURCE_CODE_NOT_SUPPLIED"},
            "comparison": developer.compare(before_code, source_code, records, now) if before_code is not None and source_code is not None else {"status": "UNKNOWN", "reason": "BEFORE_AFTER_NOT_SUPPLIED"},
            "plan": developer.plan(context, intent, branch=branch, baseline_ref=baseline_ref, now=now) if branch and baseline_ref else {"status": "NEEDS_INPUT", "reason": "BRANCH_AND_BASELINE_REQUIRED"},
            "tests_executed": False, "security_chain_adapter": "UNAVAILABLE",
        }

    def _research(self, *, intent, records, now, **_):
        return research.synthesize(intent, records, now)

    def _content(self, *, intent, **_):
        return content.draft_outline(intent)

    def _observability(self, *, context, **_):
        return {"status": "LOCAL_SCOPED_EVENTS", "events": self.store.events(context)}
