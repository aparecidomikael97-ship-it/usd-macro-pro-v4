# AION B2B — Provider Capability Binding Contract V1

Status: **design-only / least-privilege / non-executable**.

## Objetivo

Garantir que um futuro provider adapter receba somente a interseção exata entre
todas as fontes de autoridade já aprovadas.

Nenhuma capability nova pode nascer nesta camada.

## Estado máximo

`READY_FOR_PROVIDER_CAPABILITY_BINDING_DESIGN_REVIEW`

Próximo passo:

`DESIGN_EXECUTION_ENVELOPE_CONTRACT_ONLY`

## Regra central

Modo:

`EXACT_INTERSECTION_FAIL_CLOSED`

A capability efetiva futura deve ser a interseção de:
- Fresh Owner Authorization Scope;
- Runtime Guard Allowlist;
- Adapter Attested Allowlist;
- Tenant/Workspace/Domain Scope;
- Action Family/Operation Scope.

## Fail-closed obrigatório

Bloquear quando:
- a interseção estiver vazia;
- existir capability pedida além do permitido;
- existir wildcard;
- houver expansão de permissão;
- houver cross-tenant/workspace/domain;
- houver cross-action-family/operation;
- o adapter tentar transformar allowlist em autoridade;
- capability estiver na forbidden list do adapter;
- custo exceder o ceiling já aprovado.

## Precedência

- Owner scope vence;
- Runtime guard vence;
- forbidden capability vence;
- adapter allowlist é somente teto, nunca fonte de autoridade.

## Binding mínimo

O futuro binding deve ligar:
owner/tenant/workspace/domain/customer/pilot/action/operation,
authorization digest, runtime guards digest, adapter attestation/manifest digest,
provider identity ref, capability scope digest, requested/effective/forbidden
capability digests, FinOps ceiling e janela de validade.

## FinOps

Teto global permanece **20.000 centavos**.

## Esta camada não faz

- carregar capability scope;
- materializar capability efetiva;
- selecionar/bindar provider;
- carregar credencial;
- resolver endpoint;
- construir payload;
- network/provider call;
- billing/CRM/provisioning/deploy/produção.
