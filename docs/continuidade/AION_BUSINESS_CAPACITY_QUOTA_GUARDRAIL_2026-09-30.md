# Continuidade — AION BUSINESS Capacity & Quota Guardrail V1

Data: 2026-09-30

## Ponto de partida

Empilhado sobre a Draft PR #431:
AION BUSINESS: expansion cycle audit ledger V1.

## Bloco

Criada a camada de capacidade e quotas por tenant:

- vínculo obrigatório ao ledger íntegro;
- conjunto de tenants precisa coincidir exatamente;
- quotas de IA, integrações, workflows e armazenamento;
- budgets de IA, integrações, suporte e infraestrutura;
- receita esperada por tenant;
- margem mínima explícita;
- reserva de capacidade explícita;
- margem recalculada após reserva;
- packet separado para futura decisão de aplicação;
- 21ª visão do Painel Business.

## Regra central

Nenhuma quota é aplicada por esta camada. Ela apenas verifica se o plano de
capacidade e economics está coerente e delimitado.

## Segurança

Billing, quotas reais, runtime, expansão e ações com clientes permanecem OFF.
