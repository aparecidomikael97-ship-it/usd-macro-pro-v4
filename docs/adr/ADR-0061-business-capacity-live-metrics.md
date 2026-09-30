# ADR-0061 — Capacidade usa métricas reais atestadas em leitura antes de revisar novos clientes

Título: Capacidade usa métricas reais atestadas em leitura antes de revisar novos clientes  
Data: 2026-09-30  
Status: ACCEPTED

## Contexto

O Gestor de Capacidade & Escala já decide quantos tenants adicionais podem ser
revisados com base em custo, suporte, infraestrutura, margem e saúde dos tenants.
Faltava a ponte entre esses inputs e métricas reais de operação.

## Problema

Preencher capacidade com números manuais/stale pode liberar crescimento acima do
que o orçamento, suporte ou infraestrutura realmente comportam.

## Alternativas consideradas

1. Continuar com inputs manuais.
2. Permitir que cada provider escreva diretamente no Capacity Manager.
3. Normalizar métricas read-only atestadas e reutilizar o Capacity Manager atual.

## Decisão

Adotar a alternativa 3.

Fontes obrigatórias:
- FinOps;
- Suporte;
- Infraestrutura;
- Incidentes.

Cada fonte precisa:
- source_ref;
- autenticação verificada externamente;
- escopo read-only;
- ausência de write scope;
- timestamp válido.

Cada tenant precisa:
- tenant_id;
- custo mensal atual;
- utilização máxima;
- incidentes de alta severidade ativos;
- digest do custo FinOps;
- observed_at recente.

Métricas da plataforma:
- custo compartilhado;
- horas de suporte disponíveis;
- headroom de infraestrutura;
- observed_at recente.

O snapshot normalizado alimenta o `evaluate_capacity_scale()` existente.

## Consequências

A lógica de capacidade continua única, mas agora pode operar sobre evidência
real e recente sem duplicar o motor de decisão.

## Segurança

A camada não:
- consulta provider sozinha;
- aumenta orçamento;
- altera quota;
- admite cliente;
- cobra;
- provisiona tenant;
- faz deploy;
- ativa runtime.

## Compatibilidade

Complementa ADR-0049 e ADR-0058.

## Rollback/migração

Read-only. Remoção não muda clientes ou infraestrutura.

## PR/commit relacionado

Draft PR #449 — AION BUSINESS: live capacity metrics binding V1.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
