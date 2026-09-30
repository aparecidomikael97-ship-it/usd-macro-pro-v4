# ADR-0049 — Admissão de novos clientes depende de capacidade medida

Título: Admissão de novos clientes depende de capacidade medida  
Data: 2026-09-30  
Status: ACCEPTED

## Contexto

O Business precisa crescer sem ultrapassar orçamento, suporte, infraestrutura,
margem ou o limite inicial de tenants.

## Problema

Aceitar novos clientes apenas porque existe demanda pode comprometer
estabilidade, suporte, margem e o teto financeiro atual.

## Alternativas consideradas

1. Aceitar clientes enquanto houver demanda.
2. Usar apenas um limite fixo de quantidade.
3. Calcular capacidade segura com múltiplos recursos e exigir decisão separada.

## Decisão

Adotar a alternativa 3.

O Capacity & Scale Manager combina:
- plano de quotas íntegro;
- conjunto atual de tenants;
- uso e saúde atuais;
- custo dos tenants;
- custo compartilhado da plataforma;
- teto mensal aprovado;
- capacidade de suporte;
- headroom de infraestrutura;
- custo e receita estimados por novo tenant;
- margem mínima.

A capacidade segura é o menor limite entre slots de tenant, orçamento, suporte e
infraestrutura, desde que todos os gates estejam verdes.

## Consequências

O sistema pode informar quantos novos clientes cabem com segurança, mas nunca
admiti-los automaticamente.

## Componentes afetados

- Business;
- Central Financeira;
- FinOps;
- Customer Success;
- observabilidade;
- quotas;
- onboarding.

## Segurança

O teto inicial é limitado a R$200 nesta versão. Aumentar orçamento exige decisão
separada. Incidente de alta severidade, tenant sobrecarregado, margem insuficiente
ou falta de evidência bloqueiam crescimento.

## Compatibilidade

Consome o capacity/quota review já definido no Business e valida seu digest
antes de confiar nele.

## Rollback/migração

Módulo read-only. Remoção não altera tenants ou runtime existentes.

## PR/commit relacionado

Draft PR Capacity & Scale Manager V1.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
