# ADR-0045 — Capacidade e quotas por tenant são vinculadas ao ledger íntegro

- Título: Capacidade e quotas por tenant são vinculadas ao ledger íntegro
- Data: 2026-09-30
- Status: ACCEPTED

## Contexto

ADR-0044 cria o ledger auditável dos ciclos de expansão.

## Problema

Antes de qualquer crescimento operacional, cada tenant precisa ter limites de uso
e orçamento econômico coerentes com a capacidade disponível e com a margem
mínima definida pelo administrador.

## Decisão

Criar um guardrail administrativo de capacidade e quotas que exige:

1. ledger íntegro e com digest válido;
2. conjunto de quotas exatamente igual ao conjunto de tenants do último estado verificado;
3. limites positivos para IA, integrações, workflows e armazenamento;
4. orçamento explícito para IA, integrações, suporte e infraestrutura;
5. receita esperada positiva;
6. margem mínima explicitamente definida;
7. reserva de capacidade explicitamente definida;
8. margem reavaliada após reserva;
9. decisão de aplicação separada da análise.

O estado máximo automático é CAPACITY_QUOTA_REVIEW_READY.

## Consequências

Capacidade e rentabilidade deixam de ser verificações informais. Um tenant sem
quota completa, margem suficiente ou vínculo com o ledger bloqueia a revisão.

## Segurança

O módulo não aplica quotas, não altera billing, runtime, tenants, tráfego,
integrações, deploy ou sistemas externos.

## Compatibilidade

Consome apenas o resultado íntegro do ledger de ADR-0044.

## Rollback

Read-only/administrativo; sem efeito externo a compensar.
