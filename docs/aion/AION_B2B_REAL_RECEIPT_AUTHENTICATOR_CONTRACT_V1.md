# AION B2B — Real Receipt Authenticator Contract V1

Status: **design-only / provider-neutral / non-executable / fail-closed**.

## Objetivo

Definir o contrato de segurança que um futuro verificador de receipt real deverá
cumprir antes que qualquer receipt de execução possa ser aceito como autêntico.

Esta camada NÃO autentica receipt real, NÃO lê chave, NÃO resolve trust root,
NÃO registra nonce, NÃO grava replay registry e NÃO cria executor.

## Entrada obrigatória

A entrada deve ser o capability/readiness contract previamente aprovado:

`READY_FOR_FUTURE_EXECUTOR_CAPABILITY_DESIGN_REVIEW`

com:

`DESIGN_REAL_RECEIPT_AUTHENTICATOR_CONTRACT_ONLY`

Qualquer authority/effect flag ligada bloqueia o avanço.

## Estado máximo

`READY_FOR_REAL_RECEIPT_AUTHENTICATOR_DESIGN_REVIEW`

O próximo passo permitido é somente:

`DESIGN_IDEMPOTENCY_REPLAY_CONTRACT_ONLY`

## Criptografia e confiança exigidas futuramente

O verificador real deverá provar, em contrato separado e posteriormente
implementado/red-teamed:

- assinatura Ed25519 válida;
- digest SHA-256 canônico;
- resolução em trust root aprovado;
- key_id e key_version vinculados;
- status da chave ACTIVE;
- not_before / not_after válidos;
- receipt dentro da janela de freshness;
- nonce válido e ainda não consumido;
- replay rejeitado;
- binding exato de owner/tenant/workspace;
- binding de customer/pilot/package;
- binding da família/operação;
- binding de todos os digests da cadeia;
- binding de provider_identity_ref e writer_identity_ref;
- before/after state binding;
- idempotency binding.

## Campos que deverão fazer parte do material assinado

Entre outros:

- owner_id
- tenant_id
- workspace_id
- customer_id
- pilot_id
- package
- action_family
- operation_kind
- execution_request_digest
- execution_record_digest
- execution_intent_writer_request_digest
- command_plan_digest
- adapter_plan_digest
- dry_run_digest
- rollback_plan_digest
- idempotency_key_digest
- before_state_digest
- after_state_digest
- provider_identity_ref
- writer_identity_ref
- issued_at
- expires_at
- nonce
- key_id
- key_version

## Materiais proibidos nesta fase

Esta camada não pode conter:

- private key;
- secret key;
- credential;
- token;
- provider endpoint;
- HTTP method;
- headers;
- payload;
- shell command;
- executable command;
- production target.

## Autoridade

Mesmo com estado READY:

- real_receipt_verified = false
- signature_verified = false
- nonce_claimed = false
- replay_registry_written = false
- executor_implementation_allowed = false
- provider_selected = false
- billing_authorized = false
- customer_contact_authorized = false
- crm_write_authorized = false
- deploy_authorized = false
- production_mutation_authorized = false

Autorização histórica nunca pode ser reutilizada como autorização nova.

Qualquer implementação real futura exige novo contrato, testes, red-team e nova
autorização explícita do Owner.
