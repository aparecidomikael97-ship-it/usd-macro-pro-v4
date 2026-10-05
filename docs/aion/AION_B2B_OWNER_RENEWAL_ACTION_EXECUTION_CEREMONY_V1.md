# AION B2B — Owner Renewal Action Execution Ceremony V1

Status: **staging / assinatura de intenção / persistência pendente / sem comando**.

## Objetivo

Receber uma confirmação criptográfica explícita do proprietário depois de um
Execution Preflight limpo.

Somente duas decisões são aceitas:

- `AUTHORIZE_BUSINESS_ACTION_EXECUTION`;
- `DENY_BUSINESS_ACTION_EXECUTION`.

Mensagens genéricas de chat, inclusive "vamos lá", não são autorização de
execução.

## Binding da assinatura

A assinatura Ed25519 vincula:

- owner / tenant / workspace;
- customer / pilot / package;
- review type;
- escolha comercial;
- action family;
- action-record digest;
- persistence-receipt digest;
- action checkpoint digest;
- writer-request digest;
- authorization-preflight digest;
- action-parameters digest;
- execution-environment digest;
- execution-preflight digest;
- ceremony ID;
- nonce;
- key ID/version/fingerprint;
- janela máxima de 120 segundos.

## Resultado máximo

Uma assinatura válida de autorização produz apenas:

`OWNER_BUSINESS_ACTION_EXECUTION_VERIFIED_AUTHORIZE_PENDING_PERSISTENCE`.

Uma assinatura válida de negação produz:

`OWNER_BUSINESS_ACTION_EXECUTION_VERIFIED_DENY_PENDING_PERSISTENCE`.

No caminho AUTHORIZE:

- execution_authorization_intent=true;
- requires_execution_record_persistence=true;
- eligible_for_command_planning_after_persistence=true.

Ainda permanecem falsos:

- execution_record_persisted;
- execution_command_generated;
- execution_command_executed;
- business_action_authorized;
- renovação;
- não renovação;
- remediação;
- pausa;
- encerramento;
- cobrança;
- repricing;
- mudanças de quota/pacote/papéis/integração;
- contato;
- provisionamento;
- CRM/provider;
- deploy;
- mutação de produção;
- execução externa.

Portanto, a assinatura final ainda não executa o negócio. O registro dessa
intenção precisa ser persistido e atestado antes que qualquer command planner
possa sequer ser considerado.
