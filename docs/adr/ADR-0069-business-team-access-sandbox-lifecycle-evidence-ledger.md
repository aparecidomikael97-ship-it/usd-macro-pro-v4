# ADR-0069 — Business Team Access Sandbox Lifecycle Evidence Ledger

- Status: ACCEPTED
- Data: 2026-09-30
- Escopo: AtlasQuant / AION Business / Equipe & Acessos

## Contexto

Uma autorização explícita ainda não é evidência de que o lifecycle foi
executado corretamente. Cada uma das dez etapas precisa de prova individual,
ordem estrita e cadeia auditável.

## Decisão

Criar um ledger append-only lógico com recibos sanitizados.

Cada recibo contém:
- step_order;
- step_id;
- plan digest;
- authorization record digest;
- evidence digest;
- observed_at;
- previous entry digest;
- mutation_observed;
- flags sandbox-only.

O ledger armazena apenas digests e metadados mínimos. Evidência bruta sensível
fica fora do ledger.

## Cadeia

- step 1 referencia GENESIS_DIGEST = 64 zeros;
- cada step seguinte referencia o receipt digest anterior;
- ordem diferente de 1→10 bloqueia;
- evidência duplicada bloqueia;
- receipt digest duplicado bloqueia;
- quebra da cadeia bloqueia;
- binding diferente de plano/autorização bloqueia.

## Estados

- READY_FOR_FIRST_SANDBOX_LIFECYCLE_STEP;
- READY_FOR_NEXT_SANDBOX_LIFECYCLE_STEP;
- SANDBOX_LIFECYCLE_EVIDENCE_COMPLETE_REVIEW_REQUIRED;
- SANDBOX_LIFECYCLE_EVIDENCE_LEDGER_BLOCKED.

Mesmo quando as dez etapas estão completas, ainda existe revisão humana final.

## Segurança

O ledger:
- não executa próximo passo automaticamente;
- não guarda raw evidence;
- não habilita executor;
- não autoriza produção;
- não autoriza deploy;
- não autoriza runtime.

## Compatibilidade

Complementa ADR-0068 e todo o fluxo de ADR-0048 até ADR-0067.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
