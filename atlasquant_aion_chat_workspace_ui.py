"""Session-only presentation adapter for Chat Turn V1; no durable store or authority.

The trusted host supplies scope/access. Browser events contain text and file metadata,
never context, approval, flags, hashes or file bytes. Persistence is deliberately absent.
"""
from hashlib import sha256
import json
from pathlib import Path
from uuid import uuid4

ASSETS = Path(__file__).parent / "aion_chat" / "web"
PAGE_SIZE = 40  # Render budget only: logical session history is never truncated.
LABELS = {
    "PLANNED": ("Planejado", "Entendi o pedido e preparei um plano. Nenhuma ação foi executada; ainda não há resposta de um modelo conectado."),
    "WAITING_APPROVAL": ("Aguardando aprovação", "Este plano exige aprovação pelo fluxo autorizado. Mensagens como sim ou autorizo tudo não concedem permissão."),
    "BLOCKED": ("Bloqueado", "O contrato bloqueou este pedido. Nenhuma ação foi executada; os motivos estão abaixo."),
    "REJECTED": ("Não aceito", "O contrato não aceitou este turno. Revise a mensagem e tente novamente."),
}


def trusted_context(access, mode):
    session = access.get("session") or {}
    return {"role": str(access.get("role") or "USER"), "persona": "central", "experience_mode": mode,
            "tenant_id": str(access.get("tenant_id") or session.get("tenant_id") or ""),
            "workspace_id": str(access.get("workspace_id") or session.get("workspace_id") or "aion"),
            "actor_id": str(access.get("user_id") or session.get("user_id") or session.get("username") or access.get("username") or "")}


def session_chat(session, context):
    identity = {key: context.get(key) for key in ("tenant_id", "workspace_id", "actor_id", "role")}
    key = "aq_aion_chat_" + sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    if key not in session:
        session[key] = {"conversation_id": "AION-UI-" + uuid4().hex, "entries": [], "turns": {}, "requests": set(), "page": 0, "ack": "", "notice": ""}
    return session[key]


def attachment_metadata(items):
    """Whitelist metadata. Client hashes have no trusted ingest provenance; omit them."""
    from atlasquant_aion_chat_surface import MAX_ATTACHMENTS
    result = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict): continue
        if len(result) >= MAX_ATTACHMENTS: raise ValueError("Até 16 anexos por turno.")
        size = item.get("size_bytes", 0)
        if type(size) is not int or size < 0: raise ValueError("Tamanho de anexo inválido.")
        result.append({"filename": str(item.get("filename") or "arquivo")[:240], "mime_type": str(item.get("mime_type") or "application/octet-stream")[:120], "size_bytes": size, "kind": "IMAGE" if str(item.get("mime_type") or "").startswith("image/") else "FILE"})
    return result


def submit_turn(chat, event, context):
    """Only UI history mutation. All planning/policy decisions belong to #656."""
    from atlasquant_aion_chat_surface import build_chat_turn, append_chat_history, MAX_MESSAGE_CHARS
    if not isinstance(event, dict) or event.get("conversation_id") != chat["conversation_id"]:
        raise ValueError("Conversa da sessão não corresponde.")
    request_id = event.get("request_id")
    if not isinstance(request_id, str) or not request_id or len(request_id) > 100: raise ValueError("Identificador de envio inválido.")
    if request_id in chat["requests"]: return
    text = event.get("message")
    if not isinstance(text, str) or len(text) > MAX_MESSAGE_CHARS: raise ValueError("Mensagem excede o orçamento técnico de 8.000 caracteres.")
    files = attachment_metadata(event.get("attachments"))
    turn = build_chat_turn(text, context=context, attachments=files, conversation_id=chat["conversation_id"], turn_index=len(chat["turns"]))
    state = turn.get("state", "BLOCKED")
    _, answer = LABELS.get(state, LABELS["BLOCKED"])
    # Use the canonical append contract for each new pair; extend instead of copying
    # all prior logical history on every send. Raw multiline is UI-only display.
    appended = append_chat_history(None, turn, assistant_text=answer)["entries"]
    appended[0]["display_text"] = text
    appended[0]["attachments"] = turn.get("attachments", [])
    chat["entries"].extend(appended)
    chat["turns"][turn["turn_id"]] = turn
    chat["requests"].add(request_id)
    chat.update(page=0, ack=request_id, notice="")


def view_data(chat):
    end = max(0, len(chat["entries"]) - chat["page"] * PAGE_SIZE)
    start = max(0, end - PAGE_SIZE)
    entries = chat["entries"][start:end]
    # Never send the private Core result to the browser. Explicit public allowlist.
    public_turns = {}
    for row in entries:
        turn = chat["turns"].get(row["turn_id"], {})
        core = turn.get("core_preflight") or {}
        decision = core.get("decision") or {}
        local = turn.get("local_tool_preview") or {}
        public_turns[row["turn_id"]] = {
            "state": turn.get("state", "BLOCKED"), "reason": turn.get("reason", ""),
            "capability": (turn.get("selected_capability") or {}).get("capability_id", "Não selecionada"),
            "policy_state": decision.get("state", "UNKNOWN"),
            "blockers": list(decision.get("blockers") or []) + ([turn.get("reason")] if turn.get("state") == "BLOCKED" and local.get("state") == "BLOCKED_INTENT" else []),
            "approval": turn.get("approval") or {},
            "stages": [{"stage": item.get("stage"), "state": item.get("state")} for item in turn.get("golden_path", [])],
            "evidence": "Planejada · evidência ainda não coletada", "receipt": "Não criado · execução não iniciada",
        }
    return {"conversation_id": chat["conversation_id"], "entries": entries, "turns": public_turns, "total": len(chat["entries"]),
            "page": chat["page"], "has_older": start > 0, "has_newer": chat["page"] > 0, "ack": chat["ack"], "notice": chat["notice"]}


def render_aion_chat_workspace(st, access, *, mode, selected, navigation, component):
    from atlasquant_central_hub_ui import assert_area_access
    if not access or access.get("allowed") is not True: return False
    assert_area_access(access, "aion")
    # Semantic host marker stays outside the custom component so AppTest,
    # accessibility tooling and navigation contracts can identify the active
    # workspace without depending on component internals.
    st.markdown(
        '<span id="aq-aion-chat-workspace-host" data-workspace="aion" '
        'data-module="chat" aria-hidden="true"></span>',
        unsafe_allow_html=True,
    )
    context = trusted_context(access, mode)
    chat = session_chat(st.session_state, context)
    data = view_data(chat)
    data.update(navigation=[{"route": key, "label": label} for key, label in navigation], central=str(access.get("role")).upper() == "ADMIN", selected=selected)
    result = component(data=data, key="aq_aion_chat_command", on_send_change=lambda: None, on_page_change=lambda: None, on_navigate_change=lambda: None)
    if result.send:
        try: submit_turn(chat, result.send, context)
        except (ValueError, TypeError) as error:
            chat["notice"] = str(error)
            chat["ack"] = str(result.send.get("request_id", "")) if isinstance(result.send, dict) else ""
        st.rerun()
    if isinstance(result.page, str) and result.page in {"older", "newer"}:
        if result.page == "older" and data["has_older"]: chat["page"] += 1
        elif result.page == "newer": chat["page"] = max(0, chat["page"] - 1)
        st.rerun()
    if result.navigate:
        from atlasquant_reference_ui import apply_event
        apply_event(st.session_state, access, "aion", result.navigate)
        st.rerun()
    return True
