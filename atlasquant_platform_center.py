"""AtlasQuant cross-platform installation/readiness center.

PWA readiness is distinct from native App Store/Play Store packaging.
This module reports what is actually present in the repository and does not
claim native-store publication before signed packages exist.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import streamlit as st

from atlasquant_native_packaging import native_packaging_audit

ROOT=Path(__file__).resolve().parent
DOCS=ROOT/"docs"
PWA_URL="https://aparecidomikael97-ship-it.github.io/usd-macro-pro-v4/"

def pwa_asset_audit(root:Path|None=None)->dict[str,Any]:
    base=Path(root) if root is not None else ROOT
    docs=base/"docs"
    required=(
        docs/"index.html",
        docs/"manifest.webmanifest",
        docs/"sw.js",
        docs/"icons"/"icon-192.png",
        docs/"icons"/"icon-512.png",
        docs/"icons"/"apple-touch-icon.png",
    )
    missing=[str(p.relative_to(base)) for p in required if not p.is_file()]
    manifest_ok=False
    try:
        manifest=json.loads((docs/"manifest.webmanifest").read_text(encoding="utf-8"))
        manifest_ok=bool(
            manifest.get("name")=="AtlasQuant"
            and manifest.get("display")=="standalone"
            and manifest.get("start_url")
            and manifest.get("id")
        )
    except Exception:
        manifest_ok=False
    sw_ok=False
    try:
        sw=(docs/"sw.js").read_text(encoding="utf-8")
        sw_ok='event.request.method === "GET"' in sw and "response.ok" in sw
    except Exception:
        sw_ok=False
    ready=bool(not missing and manifest_ok and sw_ok)
    return {
        "pwa_ready":ready,
        "missing":missing,
        "manifest_ok":manifest_ok,
        "service_worker_ok":sw_ok,
    }

def platform_matrix(audit:dict[str,Any]|None=None)->list[dict[str,str]]:
    a=dict(audit or pwa_asset_audit())
    pwa="PRONTO — PWA" if a.get("pwa_ready") else "BLOQUEADO — revisar PWA"
    return [
        {"Plataforma":"Android","Distribuição atual":pwa,"Tipo":"Instalação pelo navegador/PWA"},
        {"Plataforma":"iPhone / iPad","Distribuição atual":pwa,"Tipo":"Adicionar à Tela de Início/PWA"},
        {"Plataforma":"Windows","Distribuição atual":pwa,"Tipo":"Instalação pelo navegador/PWA"},
        {"Plataforma":"macOS","Distribuição atual":pwa,"Tipo":"Instalação pelo navegador/PWA"},
        {"Plataforma":"Linux","Distribuição atual":pwa,"Tipo":"Instalação pelo navegador/PWA"},
        {"Plataforma":"Google Play","Distribuição atual":"PENDENTE","Tipo":"Pacote nativo/store ainda não assinado/publicado"},
        {"Plataforma":"Apple App Store","Distribuição atual":"PENDENTE","Tipo":"Pacote nativo/store ainda não assinado/publicado"},
    ]


def platform_status(audit:dict[str,Any]|None=None)->dict[str,str]:
    a=dict(audit or {})
    if bool(a.get("pwa_ready",False)):
        return {"label":"PWA PRONTA","detail":"Android, iOS/iPadOS, Windows, macOS e Linux via navegador instalável"}
    missing=a.get("missing",[]) if isinstance(a.get("missing",[]),list) else []
    return {"label":"PWA BLOQUEADA","detail":f"{len(missing)} requisito(s) de instalação pendente(s)"}


def render_platform_center()->dict[str,Any]:
    audit=pwa_asset_audit()
    native=native_packaging_audit()
    st.subheader("📱 Instalação & Plataformas")
    st.caption(
        "A versão PWA cobre instalação pelo navegador em celular e desktop. "
        "Publicação nativa na Play Store/App Store é uma etapa separada e ainda não é marcada como concluída."
    )
    visual=platform_status(audit)
    st.markdown(
        f"""<div style="padding:11px 13px;border:1px solid rgba(137,170,210,.18);border-radius:12px;margin:4px 0 13px">
        <strong>PLATAFORMAS · {visual['label']}</strong><br>
        <span style="opacity:.74;font-size:.78rem">{visual['detail']}</span>
        <span style="float:right;opacity:.68;font-size:.72rem">Lojas nativas continuam separadas</span></div>""",
        unsafe_allow_html=True,
    )
    if audit["pwa_ready"]:
        st.success("PWA AtlasQuant: pronta no repositório para distribuição web instalável.")
        st.link_button("Abrir AtlasQuant PWA",PWA_URL,width="stretch")
    else:
        st.error("PWA bloqueada: faltam arquivos ou contratos de segurança.")
        if audit["missing"]:
            st.write("Arquivos ausentes: "+", ".join(audit["missing"]))
    st.dataframe(platform_matrix(audit),width="stretch",hide_index=True)
    st.markdown("### Preparação para lojas nativas")
    if native["preparation_ready"]:
        st.success("Metadados e checklists de empacotamento nativo: PRONTOS para a etapa externa de assinatura/build.")
    else:
        st.warning("Preparação de empacotamento nativo incompleta.")
    st.caption("Pacotes Android/iOS assinados e publicação nas lojas continuam pendentes e não são inferidos destes checklists.")

    st.markdown("### Como instalar hoje")
    st.markdown(
        "- **Android / Windows / macOS / Linux:** abra a PWA em navegador compatível e escolha Instalar/Adicionar aplicativo.\n"
        "- **iPhone / iPad:** abra no Safari → Compartilhar → Adicionar à Tela de Início.\n"
        "- **Play Store / App Store:** continuam pendentes de empacotamento, assinatura e publicação."
    )
    return {**audit,"native_packaging_preparation_ready":bool(native["preparation_ready"]),"native_store_publication_verified":False}
