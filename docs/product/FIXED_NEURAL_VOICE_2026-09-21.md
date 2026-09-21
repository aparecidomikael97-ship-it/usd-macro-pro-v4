# AtlasQuant — Voz Neural Oficial V2 · 21/09/2026

## Problema confirmado

A narração anterior ainda dependia de speechSynthesis do navegador/celular.

Na prática, Android/Chrome podia entregar uma voz genérica instalada pelo
Google, inclusive com timbre feminino/robotizado, mesmo quando a interface
dizia "voz AtlasQuant masculina/grave".

Isso não garantia identidade de voz.

## Nova arquitetura

A voz oficial passa a ser gerada no servidor por TTS neural.

Perfil:

- idioma: pt-BR;
- identidade: AtlasQuant;
- estilo: masculino, adulto, grave, natural e acolhedor;
- modelo padrão: gpt-4o-mini-tts;
- voz padrão: cedar;
- velocidade padrão: 0.96;
- reprodução automática: OFF;
- geração somente depois de ação explícita do usuário.

A instrução do TTS pede fala conversacional, sem tom de locutor e sem tom
robótico.

## Regra obrigatória de fallback

Browser/device TTS está desativado como fallback.

Se o provedor neural falhar ou não estiver configurado:

- o texto original continua visível;
- nenhuma voz do Google/aparelho é acionada;
- nenhuma outra voz é escolhida silenciosamente.

## Configuração de produção

Secret obrigatório para áudio:

- OPENAI_API_KEY

Opcionais, controlados pelo operador e não pelo usuário final:

- ATLASQUANT_TTS_MODEL
- ATLASQUANT_TTS_VOICE
- ATLASQUANT_TTS_SPEED

Não há seletor público Normal / Clear / Fancy / Deep / Crisp / Delicate.

O produto possui uma identidade oficial única.

## Custom voice futura

O contrato aceita posteriormente um voice ID aprovado no formato voice_* sem
mudar a interface. Isso permite substituir a voz integrada por uma identidade
customizada quando houver consentimento/elegibilidade apropriados.

## Áudio e cache de sessão

O player:

1. valida o texto;
2. gera um hash do transcript + perfil;
3. chama TTS somente após clique;
4. guarda o áudio na sessão do Streamlit;
5. reutiliza o mesmo áudio enquanto transcript/perfil não mudarem.

A chave do provedor não entra no hash, no transcript nem em logs da interface.

## Assistente contextual

Análise principal e respostas por texto passam pelo player neural.

O microfone do navegador continua opcional somente para reconhecimento da
pergunta. Ele não usa speechSynthesis para falar a resposta.

## Macro Briefing

O Macro Briefing também usa o mesmo player neural. O fluxo antigo de preparar
estilos cosméticos foi retirado.

## Transparência

A interface informa que o áudio é gerado por IA.

## Segurança operacional

A camada de voz:

- não altera score;
- não altera Gate;
- não altera viés;
- não cria sinal;
- não envia ordem;
- não habilita corretora;
- não modifica o texto do diagnóstico antes de enviá-lo ao TTS.

## Estado desta etapa

Código:

- atlasquant_neural_tts.py
- atlasquant_neural_voice_ui.py
- atlasquant_voice_profile.py
- atlasquant_voice_assistant.py
- atlasquant_home_radar.py
- atlasquant_macro_briefing_panel.py

Testes cobrem:

- identidade fixa;
- ausência de device fallback;
- ausência de speechSynthesis nos HTMLs ativos;
- transcript exato;
- request neural;
- erro sanitizado;
- segredo ausente = fail closed;
- estilos cosméticos rejeitados.
