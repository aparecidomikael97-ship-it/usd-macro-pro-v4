"""AION external-platform intent parser and approval policy."""
from __future__ import annotations
from typing import Any,Mapping
from atlasquant_aion_connectors import connector_action_policy

PROVIDER_TERMS={
    "youtube":("youtube","youtube music"),
    "spotify":("spotify",),
    "google_calendar":("calendar","calendário","calendario","agenda","compromisso"),
    "gmail":("gmail","e-mail","email","mensagem"),
    "google_drive":("drive","google drive","arquivo","documento"),
}
WRITE_TERMS=("adicione","adicionar","crie","criar","salve","salvar","publique","publicar","envie","enviar","remova","remover","delete","deletar","altere","alterar","toque","tocar","pause","pausar")

def detect_platform_intent(question:str)->dict[str,Any]:
    q=" ".join(str(question or "").strip().lower().split())
    provider=None
    for name,terms in PROVIDER_TERMS.items():
        if any(term in q for term in terms):
            provider=name
            break
    if provider is None:
        return {"matched":False,"provider":None,"action_class":None,"requires_confirmation":False}
    action_class="WRITE" if any(term in q for term in WRITE_TERMS) else "READ"
    return {
        "matched":True,
        "provider":provider,
        "action_class":action_class,
        "requires_confirmation":action_class!="READ",
    }

def evaluate_platform_intent(question:str,connections:Mapping[str,Any]|None=None)->dict[str,Any]:
    intent=detect_platform_intent(question)
    if not intent["matched"]:
        return {**intent,"allowed":False,"reason":"NO_PLATFORM_INTENT"}
    connected=bool(dict(connections or {}).get(intent["provider"],False))
    policy=connector_action_policy(intent["provider"],intent["action_class"],connected=connected)
    return {**intent,**policy}
