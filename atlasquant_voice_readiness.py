"""AtlasQuant voice integration readiness.

Defines the internal contract required before a real TTS provider can be connected.
No network call, credential handling or provider activation occurs in this module.
"""
from __future__ import annotations

from typing import Any

SCHEMA="ATLASQUANT_VOICE_READINESS_V1"

VOICE_REQUIREMENTS=(
    {"id":"explicit-provider","title":"Provedor explícito","detail":"A geração de áudio só pode ocorrer quando um provedor TTS for configurado explicitamente."},
    {"id":"exact-transcript","title":"Transcrição imutável","detail":"O áudio deve ler exatamente o speech_text validado pelo Macro Briefing; não pode alterar o diagnóstico."},
    {"id":"secrets","title":"Secrets protegidos","detail":"Tokens e chaves do provedor não podem ficar em código-fonte, commits, suporte ou logs."},
    {"id":"manual-action","title":"Ação explícita","detail":"Abrir a tela não deve chamar TTS automaticamente; a geração exige ação do usuário."},
    {"id":"fail-closed","title":"Falha segura","detail":"Sem provedor ou áudio válido, o sistema deve permanecer sem narração e preservar o texto original."},
    {"id":"no-trading-side-effect","title":"Sem efeito operacional","detail":"A camada de voz não pode liberar gate, criar sinal, enviar ordem ou alterar trading real."},
)

def voice_requirements()->list[dict[str,str]]:
    return [dict(x) for x in VOICE_REQUIREMENTS]

def voice_contract_ready()->bool:
    required={"explicit-provider","exact-transcript","secrets","manual-action","fail-closed","no-trading-side-effect"}
    ids={str(x["id"]) for x in VOICE_REQUIREMENTS}
    return required.issubset(ids) and all(bool(x.get("detail")) for x in VOICE_REQUIREMENTS)

def voice_readiness(provider_configured: bool=False)->dict[str,Any]:
    contract=voice_contract_ready()
    provider=bool(provider_configured)
    return {
        "schema":SCHEMA,
        "contract_ready":contract,
        "provider_configured":provider,
        "voice_ready":bool(contract and provider),
        "automatic_tts":False,
        "trading_side_effects":False,
        "real_orders_changed":False,
    }

__all__=["SCHEMA","VOICE_REQUIREMENTS","voice_requirements","voice_contract_ready","voice_readiness"]
