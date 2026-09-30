# ADR-0075 — Business Team Access Materialized Lifecycle Authorization Package

- Status: ACCEPTED
- Data: 2026-09-30
- Escopo: AtlasQuant / AION Business / Equipe & Acessos

## Contexto

ADR-0068 valida a autorização humana contra o lifecycle plan. ADR-0074 adiciona
a materialização do plano a partir do baseline bruto e acceptance explícito.

A autorização não pode ignorar essa nova camada e se prender apenas ao
plan_digest.

## Decisão

Criar um Authorization Package que exige simultaneamente:

- materialization packet válido;
- materialization digest recalculado;
- plan digest idêntico ao plano aninhado;
- baseline digest idêntico;
- baseline acceptance record digest idêntico;
- operator session id válido;
- authorization record explícito da ADR-0068;
- materialization_digest explícito no authorization record.

O package digest é calculado sobre:

- materialization digest;
- plan digest;
- baseline digest;
- baseline acceptance record digest;
- operator session id;
- authorization record digest;
- approved_by;
- approved_at.

## Downstream

O evidence ledger e o Step Gate passam a exigir o binding materializado.

Receipts e ledger preservam:

- authorization record digest;
- authorization package digest;
- materialization digest.

## Estado máximo

EXPLICIT_SANDBOX_LIFECYCLE_AUTHORIZATION_RECORD_VERIFIED

Esse estado autoriza apenas o lifecycle manual step-by-step nos limites já
definidos. Não habilita executor e não executa nenhum step automaticamente.

## Segurança

O package não:
- cria conta;
- habilita MFA;
- grava registry;
- revoga sessão;
- inicia Docker;
- habilita executor;
- autoriza produção/deploy/runtime.

## Compatibilidade

Complementa ADR-0068, ADR-0069, ADR-0070 e ADR-0074.
