"""AtlasQuant commercial preparation pack.

Audits internal launch-preparation documents only. It never certifies legal
compliance, grants data licences, enables billing, publishes to stores, changes
trading permissions or marks public launch ready automatically.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

SCHEMA="ATLASQUANT_COMMERCIAL_PREP_V1"
ROOT=Path(__file__).resolve().parent
COMMERCIAL_DIR=ROOT/"docs"/"commercial"

DOCUMENTS=(
    ("terms_draft","TERMS_DRAFT.md"),
    ("privacy_draft","PRIVACY_DRAFT.md"),
    ("risk_draft","RISK_DISCLOSURE_DRAFT.md"),
    ("data_licensing_checklist","DATA_LICENSING_CHECKLIST.md"),
    ("billing_checklist","BILLING_INTEGRATION_CHECKLIST.md"),
    ("store_checklist","STORE_PUBLICATION_CHECKLIST.md"),
)

def commercial_prep_audit(root: Path | None=None)->dict[str,Any]:
    base=Path(root) if root is not None else ROOT
    folder=base/"docs"/"commercial"
    files={}
    missing=[]
    unsafe=[]
    for key,name in DOCUMENTS:
        path=folder/name
        exists=path.is_file()
        files[key]={"path":str(path.relative_to(base)) if exists else str(Path("docs")/"commercial"/name),"exists":exists}
        if not exists:
            missing.append(name)
            continue
        text=path.read_text(encoding="utf-8",errors="replace")
        upper=text.upper()
        if "RASCUNHO" not in upper and "PREPARAÇÃO INTERNA" not in upper:
            unsafe.append(name)
    internal_ready=not missing and not unsafe
    return {
        "schema":SCHEMA,
        "files":files,
        "missing":missing,
        "unsafe":unsafe,
        "internal_prep_ready":internal_ready,
        "legal_drafts_ready":all(files[k]["exists"] for k in ("terms_draft","privacy_draft","risk_draft")) and not any(x in unsafe for x in ("TERMS_DRAFT.md","PRIVACY_DRAFT.md","RISK_DISCLOSURE_DRAFT.md")),
        "data_licensing_checklist_ready":files["data_licensing_checklist"]["exists"],
        "billing_checklist_ready":files["billing_checklist"]["exists"],
        "store_checklist_ready":files["store_checklist"]["exists"],
        "legal_review_verified":False,
        "data_licensing_verified":False,
        "billing_integrated":False,
        "native_store_published":False,
        "public_launch_ready":False,
        "automatic_launch":False,
        "trading_permission_changed":False,
    }

def commercial_external_blockers()->tuple[str,...]:
    return (
        "Revisão jurídica/privacidade dos documentos finais",
        "Licenciamento comercial dos provedores de dados",
        "Integração real e verificada de pagamento/assinatura",
        "Pacotes assinados e publicação/revisão nas lojas nativas",
        "Renderização/publicação dos vídeos da Academy",
        "Configuração de provedor TTS para narração",
    )

__all__=["SCHEMA","DOCUMENTS","commercial_prep_audit","commercial_external_blockers"]
