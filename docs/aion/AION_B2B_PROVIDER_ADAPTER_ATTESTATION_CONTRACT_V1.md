# AION B2B — Provider Adapter Attestation Contract V1

Status: **design-only / provider-neutral / non-executable**.

## Objetivo

Definir as evidências mínimas que um futuro adapter concreto de provider deverá
apresentar antes de poder ser considerado para binding de runtime.

Esta camada NÃO escolhe provider, NÃO carrega adapter e NÃO aceita segredos,
tokens, endpoints executáveis ou payloads reais.

## Estado máximo

`READY_FOR_PROVIDER_ADAPTER_ATTESTATION_DESIGN_REVIEW`

Próximo passo permitido:

`DESIGN_PROVIDER_CAPABILITY_BINDING_CONTRACT_ONLY`

## Reuso obrigatório do núcleo

O contrato deve permanecer alinhado a:
- `ATLASQUANT_AION_MODEL_GATEWAY_V2`;
- `ATLASQUANT_AION_PROVIDER_NEUTRAL_MODEL_REGISTRY_V1`;
- `ATLASQUANT_AION_CAPABILITY_SCOPE_GRANT_V1`.

## Evidências obrigatórias do futuro adapter

- adapter_id estável;
- versão pinada;
- manifest digest;
- code digest;
- supply-chain evidence;
- provider identity reference;
- transport class;
- capability allowlist;
- forbidden capabilities;
- tenant/scope binding;
- action family/operation binding;
- request/response schema digests;
- error taxonomy;
- timeout/retry policy;
- idempotency/effect-key support;
- health evidence;
- cost model e custo máximo por ação;
- data classification;
- retention;
- log redaction;
- secret handling;
- credential source policy;
- audit receipt schema;
- rollback/compensation support;
- irreversible effects declaration;
- local fallback compatibility;
- no implicit authority.

## Material proibido nesta fase

Não pode existir valor real de:
- credencial;
- secret/API key/token/password/private key;
- Authorization header/cookie;
- provider endpoint/webhook/callback;
- request payload;
- shell command.

## FinOps

O teto global permanece em **20.000 centavos**. Esta camada não pode expandir
esse limite.

## Esta camada não faz

- provider selection;
- adapter loading;
- credential loading;
- endpoint resolution;
- payload construction;
- network/provider call;
- billing;
- customer contact;
- CRM write;
- provisioning;
- deploy;
- production mutation.
