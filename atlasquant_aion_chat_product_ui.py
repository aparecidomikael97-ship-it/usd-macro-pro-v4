"""Staged authenticated UI adapter for the durable AION Chat Product Bridge.

This adapter never creates a store, Scope, runtime checkpoint or provider.
Those values must be injected by the authenticated host. Without a complete
injection the durable UI path fails closed and the legacy session-only adapter
remains the default product behavior.
"""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Mapping

from aion_chat.models import Scope
from atlasquant_aion_chat_product_bridge import (
    continue_product_read_turn,
    create_product_conversation,
    read_product_history_page,
    validate_product_binding,
)

SCHEMA = "ATLASQUANT_AION_CHAT_PRODUCT_UI_STAGED_V1"
_REQUIRED_STORE_METHODS = (
    "create_conversation",
    "get_conversation",
    "list_messages",
    "get_message",
    "append_message",
    "get_attachment",
)


def _clean(value: Any, limit: int = 240) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def validate_product_ui_injection(
    access: Mapping[str, Any] | None,
    scope: Scope,
    store: Any,
    runtime_context: Mapping[str, Any],
) -> dict[str, Any]:
    """Require a complete trusted host composition; never infer missing pieces."""
    if not isinstance(scope, Scope):
        raise TypeError("trusted Scope required")
    if not isinstance(runtime_context, Mapping):
        raise TypeError("runtime_context mapping required")
    missing_methods = [
        name
        for name in _REQUIRED_STORE_METHODS
        if not callable(getattr(store, name, None))
    ]
    if missing_methods:
        raise TypeError(
            "injected chat store missing methods: " + ",".join(missing_methods)
        )
    binding = validate_product_binding(access, scope)
    if binding.get("bound") is not True:
        raise PermissionError(
            "AION staged product UI binding rejected: "
            + ",".join(binding.get("blockers") or [])
        )
    return {
        "schema": SCHEMA,
        "state": "BOUND_STAGED",
        "binding": binding,
        "scope_injected": True,
        "store_injected": True,
        "runtime_context_injected": True,
        "store_created_here": False,
        "scope_inferred": False,
        "runtime_context_inferred": False,
        "provider_called": False,
        "network_called": False,
        "external_action_executed": False,
        "production_store_activated": False,
        "grants_authority": False,
    }


def _state_key(access: Mapping[str, Any], scope: Scope) -> str:
    session = _mapping(access.get("session"))
    material = {
        "owner_id": scope.owner_id,
        "tenant_id": scope.tenant_id,
        "workspace_id": scope.workspace_id,
        "credential_fingerprint": _clean(
            session.get("credential_fingerprint"), 160
        ),
    }
    digest = sha256(
        json.dumps(material, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return "aq_aion_product_chat_" + digest


def staged_product_session(
    session: Any,
    access: Mapping[str, Any],
    scope: Scope,
) -> dict[str, Any]:
    """Return UI-only cursor/request state; durable messages stay in the store."""
    key = _state_key(access, scope)
    if key not in session:
        session[key] = {
            "conversation_id": "",
            "requests": set(),
            "cursor": None,
            "cursor_stack": [],
            "next_cursor": None,
            "ack": "",
            "notice": "",
        }
    state = session[key]
    if not isinstance(state.get("requests"), set):
        state["requests"] = set(state.get("requests") or [])
    if not isinstance(state.get("cursor_stack"), list):
        state["cursor_stack"] = []
    return state


def view_product_data(
    state: dict[str, Any],
    access: Mapping[str, Any],
    scope: Scope,
    store: Any,
    runtime_context: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the browser payload from scoped durable history only."""
    injection = validate_product_ui_injection(
        access,
        scope,
        store,
        runtime_context,
    )
    cid = _clean(state.get("conversation_id"), 120)
    if not cid:
        state["next_cursor"] = None
        return {
            "schema": SCHEMA,
            "conversation_id": "",
            "entries": [],
            "turns": {},
            "total": 0,
            "page": 0,
            "has_older": False,
            "has_newer": False,
            "ack": _clean(state.get("ack"), 100),
            "notice": _clean(state.get("notice"), 500),
            "product_mode": True,
            "durable_history": True,
            "history_source": "INJECTED_SCOPED_STORE",
            "injection": injection,
        }

    page = read_product_history_page(
        store,
        scope,
        access,
        cid,
        cursor=state.get("cursor"),
        page_size=40,
        newest_first=True,
    )
    state["next_cursor"] = page.get("next_cursor")
    return {
        "schema": SCHEMA,
        "conversation_id": cid,
        "entries": list(page.get("entries") or []),
        "turns": dict(page.get("turns") or {}),
        "total": int(page.get("total") or 0),
        "page": len(state.get("cursor_stack") or []),
        "has_older": bool(page.get("next_cursor")),
        "has_newer": bool(state.get("cursor_stack")),
        "ack": _clean(state.get("ack"), 100),
        "notice": _clean(state.get("notice"), 500),
        "product_mode": True,
        "durable_history": True,
        "history_source": "INJECTED_SCOPED_STORE",
        "injection": injection,
    }


def submit_product_turn(
    state: dict[str, Any],
    event: Mapping[str, Any],
    access: Mapping[str, Any],
    scope: Scope,
    store: Any,
    runtime_context: Mapping[str, Any],
) -> dict[str, Any]:
    """Persist one verified READ/SEARCH turn after an explicit browser send."""
    validate_product_ui_injection(access, scope, store, runtime_context)
    if not isinstance(event, Mapping):
        raise TypeError("chat event mapping required")

    request_id = event.get("request_id")
    if not isinstance(request_id, str) or not request_id or len(request_id) > 100:
        raise ValueError("Identificador de envio inválido.")
    if request_id in state["requests"]:
        return {
            "schema": SCHEMA,
            "state": "IDEMPOTENT_REQUEST",
            "request_id": request_id,
            "external_action_executed": False,
        }

    from atlasquant_aion_chat_surface import MAX_MESSAGE_CHARS

    text = event.get("message")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Mensagem vazia.")
    if len(text) > MAX_MESSAGE_CHARS:
        raise ValueError(
            "Mensagem excede o orçamento técnico de 8.000 caracteres."
        )

    # Browser file bodies are never accepted here. Durable attachment ingest is
    # a separate future adapter and cannot be smuggled through UI metadata.
    attachments = event.get("attachments")
    if isinstance(attachments, (list, tuple)) and attachments:
        raise ValueError(
            "Anexos duráveis ainda não estão ativos no modo staged."
        )

    current_cid = _clean(state.get("conversation_id"), 120)
    event_cid = _clean(event.get("conversation_id"), 120)
    if event_cid != current_cid:
        raise ValueError("Conversa durável da sessão não corresponde.")

    if not current_cid:
        created = create_product_conversation(
            store,
            scope,
            access,
            title="AION principal",
        )
        current_cid = _clean(created.get("conversation_id"), 120)
        state["conversation_id"] = current_cid

    result = continue_product_read_turn(
        store,
        scope,
        access,
        text,
        conversation_id=current_cid,
        runtime_context=runtime_context,
    )

    state["requests"].add(request_id)
    state["ack"] = request_id
    state["cursor"] = None
    state["cursor_stack"] = []
    state["next_cursor"] = None
    if result.get("state") == "CONFIRMED_AND_PERSISTED":
        state["notice"] = ""
    else:
        state["notice"] = (
            "Turno não persistido: somente leituras locais verificadas "
            "podem entrar no histórico durável."
        )
    return result


def change_product_page(state: dict[str, Any], direction: Any) -> bool:
    """Move across opaque durable-store cursors kept server-side."""
    value = _clean(direction, 20).lower()
    if value == "older":
        nxt = state.get("next_cursor")
        if not nxt:
            return False
        state["cursor_stack"].append(state.get("cursor"))
        state["cursor"] = nxt
        state["next_cursor"] = None
        return True
    if value == "newer":
        stack = state.get("cursor_stack") or []
        if not stack:
            return False
        state["cursor"] = stack.pop()
        state["next_cursor"] = None
        return True
    raise ValueError("unknown product history page direction")


def render_product_chat_workspace(
    st: Any,
    access: Mapping[str, Any],
    *,
    scope: Scope,
    store: Any,
    runtime_context: Mapping[str, Any],
    selected: str,
    navigation: list[tuple[str, str]] | tuple[tuple[str, str], ...],
    component: Any,
) -> bool:
    """Mount the staged durable product path using only injected host objects."""
    validate_product_ui_injection(access, scope, store, runtime_context)
    state = staged_product_session(st.session_state, access, scope)
    data = view_product_data(
        state,
        access,
        scope,
        store,
        runtime_context,
    )
    data.update(
        navigation=[
            {"route": key, "label": label}
            for key, label in navigation
        ],
        central=str(access.get("role") or "").upper() == "ADMIN",
        selected=selected,
    )
    result = component(
        data=data,
        key="aq_aion_chat_command",
        on_send_change=lambda: None,
        on_page_change=lambda: None,
        on_navigate_change=lambda: None,
    )

    if result.send:
        try:
            submit_product_turn(
                state,
                result.send,
                access,
                scope,
                store,
                runtime_context,
            )
        except (LookupError, PermissionError, ValueError, TypeError) as error:
            state["notice"] = str(error)
            state["ack"] = (
                str(result.send.get("request_id", ""))
                if isinstance(result.send, Mapping)
                else ""
            )
        st.rerun()

    if isinstance(result.page, str) and result.page in {"older", "newer"}:
        if change_product_page(state, result.page):
            st.rerun()

    if result.navigate:
        from atlasquant_reference_ui import apply_event

        apply_event(st.session_state, access, "aion", result.navigate)
        st.rerun()
    return True


__all__ = [
    "SCHEMA",
    "validate_product_ui_injection",
    "staged_product_session",
    "view_product_data",
    "submit_product_turn",
    "change_product_page",
    "render_product_chat_workspace",
]
