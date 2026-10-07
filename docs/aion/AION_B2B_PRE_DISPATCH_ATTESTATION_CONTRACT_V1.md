# AION B2B — Pre-Dispatch Attestation Contract V1

Status: **design-only / fail-closed / non-executable**.

## Objetivo

Definir a revalidação imediata antes de qualquer futuro efeito externo.

Modo:
`IMMEDIATE_PRE_EFFECT_REVALIDATION`

Idade máxima planejada da attestation:
**30 segundos**.

## Estado máximo

`READY_FOR_PRE_DISPATCH_ATTESTATION_DESIGN_REVIEW`

Próximo passo:
`DESIGN_DURABLE_DISPATCH_RECORD_CONTRACT_ONLY`

## Revalidações obrigatórias

Imediatamente antes do futuro dispatch:
- execution envelope digest deve reconstruir exatamente;
- envelope e autorização não podem estar expirados;
- autorização fresca continua válida e não consumida;
- single-use preservado;
- envelope nonce ainda não consumido;
- scope/action/operation invariantes;
- before-state ainda corresponde ao digest;
- expected postcondition continua bound;
- idempotency/effect-key reservation devem existir antes do dispatch;
- lease ownership válido e não expirado;
- provider adapter attestation ainda válida;
- provider capability binding ainda válido;
- capability intersection não mudou;
- provider identity ref não mudou;
- health evidence fresca;
- FinOps <= 20.000 cents;
- capacity reservation + quota;
- security/privacy/scope-breach clear;
- circuit breaker closed;
- kill switch available;
- rollback/compensation class ainda válida;
- irreversible boundary rechecado;
- observability trace reservado;
- audit context completo;
- durable dispatch record obrigatório antes de qualquer external effect.

## Material proibido

A attestation de design não carrega:
credencial, secret, senha, API key/token/private key, auth header, cookie,
endpoint/URL/webhook/callback, HTTP method/headers, payload/body,
command/shell/subprocess/PowerShell/curl/script.

## Esta camada NÃO faz

- attestation real;
- rebuild/consume de envelope;
- consumo de autorização;
- claim de nonce;
- reserva de idempotency/effect key;
- lease/capacity/quota;
- health check real;
- provider selection/binding;
- credential/endpoint/payload;
- dispatch record;
- network/provider call;
- billing/CRM/provisioning/deploy/produção.
