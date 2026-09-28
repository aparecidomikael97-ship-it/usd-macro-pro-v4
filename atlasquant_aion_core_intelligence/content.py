"""Local outline preparation, explicitly a draft with no publication capability."""
from .evidence import safe_text


def draft_outline(brief: str) -> dict:
    return {"status": "DRAFT", "kind": "SCRIPT_OUTLINE", "brief": safe_text(brief),
            "sections": [
                {"section": "OPENING", "instruction": "Apresentar a pergunta central do briefing."},
                {"section": "CONTEXT", "instruction": "Adicionar apenas contexto sustentado por fontes."},
                {"section": "MAIN_POINTS", "instruction": "Organizar argumentos e marcar inferências."},
                {"section": "CLOSING", "instruction": "Revisar fatos e preparar conclusão para aprovação."},
            ], "facts_verified": False, "provider_called": False,
            "published": False, "publication_approval_required": True}
