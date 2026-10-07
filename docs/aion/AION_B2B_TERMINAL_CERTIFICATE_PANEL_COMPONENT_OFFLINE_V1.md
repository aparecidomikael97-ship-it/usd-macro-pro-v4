# AION B2B — Terminal Certificate Panel Component Offline V1

Status: **offline-only / static / read-only / fail-closed / Draft**.

## Objetivo

Renderizar o primeiro componente HTML real do Terminal Execution Certificate a
partir do view-model já validado, sem integrar ainda à interface principal.

## Entrada

Somente:
`ATLASQUANT_AION_B2B_TERMINAL_CERTIFICATE_READ_MODEL_UI_RUNTIME_BINDING_OFFLINE_V1`

O componente não conhece store, runtime reader, provider ou banco.

## Saída

HTML estático e escapado com:

- cabeçalho;
- badge de estado;
- aviso explícito de evidência sem autoridade;
- 10 seções contratuais em ordem fixa.

## Estados

- VERIFIED — Evidência verificada;
- MISMATCH — Inconsistência detectada;
- UNAVAILABLE — Evidência indisponível;
- STALE — Evidência desatualizada.

Somente o texto visual muda. Nenhum estado cria autoridade.

## Zero interatividade

São proibidos no HTML:

- button;
- form;
- input;
- select;
- textarea;
- script;
- iframe;
- object/embed;
- links de ação;
- handlers JavaScript.

A coleção de controles do view-model precisa ser vazia.

## Segurança de conteúdo

Todo texto é passado por `html.escape`.

Conteúdo malicioso ou markup recebido como dado é exibido como texto, nunca
executado.

## Separação de autoridade

O componente não pode autorizar execução, retry, reopen, reconciliação,
rollback, compensação, efeito externo, cobrança, CRM, provisionamento, deploy ou
mutação de produção.

## Limite

O componente ainda não é montado em
`atlasquant_reference_ui.py` nem no Streamlit de produção.

Próximo passo permitido:
`INTEGRATE_TERMINAL_CERTIFICATE_PANEL_IN_REFERENCE_UI_DRAFT_ONLY`

Sem merge. Sem deploy.
