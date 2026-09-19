"""AtlasQuant Support Center — operational self-service guidance.

Presentation/support only. It never changes trading gates, accounts, secrets,
provider configuration, branch state, broker access or real-order permissions.
"""
from __future__ import annotations

from typing import Any
import streamlit as st

SCHEMA="ATLASQUANT_SUPPORT_CENTER_V1"

SUPPORT_TOPICS=(
    {
        "id":"app-access",
        "title":"Acesso ao aplicativo",
        "symptoms":"Login recusado, sessão expirada ou perfil sem acesso.",
        "actions":(
            "Confirme usuário e senha sem compartilhar a senha com terceiros.",
            "Se a sessão expirou, autentique novamente.",
            "Se a conta foi desativada ou alterada, procure o administrador responsável.",
        ),
    },
    {
        "id":"stale-data",
        "title":"Dados antigos / scanner bloqueado",
        "symptoms":"Scanner stale, MARKET_CLOSED ou entrada bloqueada por dados técnicos antigos.",
        "actions":(
            "Confirme se o mercado Forex está aberto.",
            "Aguarde a próxima coleta automática antes de avaliar um setup.",
            "Não trate dado stale como sinal operacional válido.",
        ),
    },
    {
        "id":"paper-trading",
        "title":"Paper Trading sem operações",
        "symptoms":"Trades simulados permanecem em zero.",
        "actions":(
            "Confira hard blocks e soft blocks do checklist.",
            "Verifique frescor M15/H1/H4 e estado do mercado.",
            "Zero trades pode ser comportamento correto quando os gates não liberam entrada.",
        ),
    },
    {
        "id":"pwa-install",
        "title":"Instalação da PWA",
        "symptoms":"Não encontrou um aplicativo nativo na loja.",
        "actions":(
            "Android/desktop: abra a PWA em navegador compatível e escolha Instalar aplicativo.",
            "iPhone/iPad: Safari → Compartilhar → Adicionar à Tela de Início.",
            "Play Store e App Store são canais separados e não devem ser confundidos com a PWA.",
        ),
    },
    {
        "id":"security",
        "title":"Segurança e trading real",
        "symptoms":"Dúvida sobre broker, ordens ou permissões.",
        "actions":(
            "Acesso USER/SALES/ADMIN não habilita trading real.",
            "Não informe senhas, tokens ou chaves de API em solicitações de suporte.",
            "O AtlasQuant deve permanecer fail-closed quando integridade ou dados não forem suficientes.",
        ),
    },
    {
        "id":"voice",
        "title":"Assistente de voz",
        "symptoms":"A narração não aparece ou o provedor TTS ainda não está configurado.",
        "actions":(
            "O texto do Macro Briefing continua disponível mesmo sem áudio.",
            "A infraestrutura de voz pode estar pronta enquanto o provedor TTS externo permanece pendente.",
            "Nunca envie token/chave do provedor por suporte; configure secrets somente no ambiente autorizado.",
        ),
    },
    {
        "id":"academy-media",
        "title":"Vídeos da Academy",
        "symptoms":"A aula possui conteúdo/roteiro, mas ainda não mostra vídeo final.",
        "actions":(
            "A trilha textual e os roteiros/storyboards podem estar prontos antes da renderização da mídia.",
            "Vídeo só deve ser marcado como pronto depois de existir arquivo/URL final revisado.",
            "Conteúdo da Academy é educacional e não substitui os controles de risco do AtlasQuant.",
        ),
    },
    {
        "id":"billing",
        "title":"Pagamento e assinatura",
        "symptoms":"Dúvida sobre cobrança, plano ou ativação comercial.",
        "actions":(
            "O contrato técnico de billing não significa que um provedor de pagamento já esteja integrado.",
            "Nenhuma cobrança automática deve ocorrer sem integração real, webhook validado e revisão humana.",
            "Nunca envie cartão, senha, token ou secret em solicitações de suporte.",
        ),
    },
    {
        "id":"public-launch",
        "title":"Lançamento público e lojas",
        "symptoms":"Dúvida sobre Play Store, App Store ou estado comercial do produto.",
        "actions":(
            "A PWA é a distribuição atual; preparação nativa não equivale a pacote assinado/publicado.",
            "Lançamento público depende de revisão jurídica, licenciamento de dados, billing, TTS/mídia e lojas quando aplicável.",
            "Use o Portal Comercial para separar preparação interna de dependências externas pendentes.",
        ),
    },
)

def support_catalog()->list[dict[str,Any]]:
    return [{"id":x["id"],"title":x["title"],"symptoms":x["symptoms"],"actions":tuple(x["actions"])} for x in SUPPORT_TOPICS]

def support_topic(topic_id:object)->dict[str,Any]|None:
    key=str(topic_id or "").strip().casefold()
    return next((dict(x) for x in SUPPORT_TOPICS if str(x["id"]).casefold()==key),None)

def support_minimum_ready()->bool:
    required={"app-access","stale-data","paper-trading","pwa-install","security","voice","academy-media","billing","public-launch"}
    ids={str(x["id"]) for x in SUPPORT_TOPICS}
    return required.issubset(ids) and all(bool(x.get("actions")) for x in SUPPORT_TOPICS)

def render_support_center()->dict[str,Any]:
    st.subheader("🛟 Central de Suporte")
    st.caption("Ajuda operacional e autoatendimento. Esta área não altera contas, gates, broker ou trading real.")
    labels={x["title"]:x for x in SUPPORT_TOPICS}
    chosen=st.selectbox("Assunto",list(labels),key="aq_support_topic")
    item=labels[chosen]
    st.markdown(f"**Quando usar:** {item['symptoms']}")
    for action in item["actions"]:
        st.markdown(f"- {action}")
    st.info("Nunca envie senha, token, secret ou chave de API em uma solicitação de suporte.")
    return {"schema":SCHEMA,"ready":support_minimum_ready(),"topic":item["id"],"real_orders_changed":False}

__all__=["SCHEMA","SUPPORT_TOPICS","support_catalog","support_topic","support_minimum_ready","render_support_center"]
