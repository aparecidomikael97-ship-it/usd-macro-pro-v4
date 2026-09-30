# AION BUSINESS Expansion Cycle Audit Ledger V1

Schema: ATLASQUANT_AION_BUSINESS_EXPANSION_CYCLE_AUDIT_LEDGER_V1

## Objetivo

Manter uma trilha encadeada, auditável e anti-replay de cada ciclo de expansão
já verificado e novamente congelado.

## Gênese

Antes do primeiro append, o ledger precisa ser vinculado a um `EXPLICIT_EXPANSION_DECISION_REQUIRED` válido. O boundary fornece o digest de verificação, o escopo e os tenants que formam a raiz da cadeia. Um ledger sem gênese pode ser auditado como vazio, mas não aceita entradas.

## Estrutura da entrada

Cada entrada contém:

- sequence;
- previous_entry_digest;
- expansion_verification_digest;
- authorization_digest;
- previous_scope;
- previous_tenant_ids;
- verified_scope;
- verified_tenant_ids;
- entry_digest.

O ledger_digest é sempre o digest da última entrada válida.

## Integridade

O auditor bloqueia:

- sequência quebrada;
- digest anterior incorreto;
- digest de entrada adulterado;
- replay de verification digest;
- remoção silenciosa de tenants;
- quebra de continuidade entre ciclos;
- salto ou downgrade de escopo;
- limite de tenants excedido;
- qualquer flag operacional indevidamente true.

## Estados

- EXPANSION_CYCLE_AUDIT_LEDGER_EMPTY
- EXPANSION_CYCLE_AUDIT_LEDGER_VERIFIED
- VERIFIED_EXPANSION_CYCLE_RECORDED
- EXPANSION_CYCLE_APPEND_BLOCKED
- LEDGER_INTEGRITY_VERIFIED
- LEDGER_INTEGRITY_BLOCKED

## Segurança

O ledger nunca executa expansão, runtime, feature flags, tráfego, deploy,
rollback, publicação, cobrança, comunicação externa ou ações com clientes.
