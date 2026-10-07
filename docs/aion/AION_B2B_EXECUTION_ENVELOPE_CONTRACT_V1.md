# AION B2B — Execution Envelope Contract V1

Status: **design-only / immutable-binding / non-executable**.

## Objetivo

Definir a futura caixa selada de evidências que será revalidada antes de qualquer
dispatch externo.

O envelope carrega somente referências e digests. Não carrega material de
execução.

## Estado máximo

`READY_FOR_EXECUTION_ENVELOPE_DESIGN_REVIEW`

Próximo passo:

`DESIGN_PRE_DISPATCH_ATTESTATION_CONTRACT_ONLY`

## Modo

`SEALED_DIGEST_REFERENCES_ONLY`

Janela máxima: **120 segundos** e nunca maior que a autorização fresca do Owner.

## Bindings obrigatórios

O envelope futuro deve ligar:
- owner/tenant/workspace/domain/customer/pilot/package;
- action family/operation kind;
- execution request;
- fresh Owner authorization;
- authenticated receipt;
- command/adapter/dry-run/rollback plans;
- idempotency/effect key;
- rollback-compensation contract;
- runtime guards;
- provider adapter attestation;
- provider capability binding;
- effective capability digest;
- provider identity ref;
- FinOps ceiling;
- before state;
- expected postcondition;
- issued/expires;
- envelope nonce digest.

## Regras

- todos os digests upstream obrigatórios;
- exact scope/action binding;
- autorização ainda válida;
- single-use preservado;
- idempotency/effect binding preservado;
- capability/rollback/FinOps preservados;
- before-state evidence;
- expected postcondition bound;
- provider identity somente por referência;
- canonical serialization;
- digest e nonce do envelope;
- tamper/rebuild mismatch bloqueia.

## Material proibido

Nenhum valor real de:
credencial, secret, senha, API key, token, private key, auth header, cookie,
endpoint/URL/webhook/callback, HTTP method/headers, payload/body,
command/shell/subprocess/PowerShell/curl/script.

## Esta camada não faz

- construir/assinar/persistir envelope real;
- claim de nonce;
- consumir autorização;
- reservar idempotency/effect key;
- lease/dispatch;
- provider identity verification;
- credential/endpoint/payload;
- network/provider call;
- billing/CRM/provisioning/deploy/produção.
