# AION BUSINESS — Capacity Live Metrics V1

## Objetivo

Responder com evidência real: **quantos clientes adicionais cabem agora sem
estourar custo, suporte, infraestrutura ou estabilidade?**

## Fontes obrigatórias

- FINOPS
- SUPPORT
- INFRA
- INCIDENTS

Todas entram apenas em leitura e precisam de atestação.

## Métricas por tenant

- custo mensal atual;
- utilização máxima;
- incidentes de alta severidade ativos;
- digest do custo FinOps;
- observed_at.

## Métricas da plataforma

- custo compartilhado;
- horas de suporte disponíveis;
- headroom de infraestrutura;
- observed_at.

## Frescor

O limite padrão é 24 horas. Métrica stale bloqueia o snapshot.

## Reutilização do Capacity Manager

O binding não inventa um segundo motor.

Ele chama o `evaluate_capacity_scale()` existente com:
- usage rows reais;
- measurement_ref derivado do snapshot;
- budget cap;
- suporte;
- infraestrutura;
- custo e receita esperados do novo tenant.

## Saída

Quando tudo está saudável:
`LIVE_CAPACITY_REVIEW_READY`

Quando há incidente, custo, suporte, infraestrutura ou evidência insuficiente:
`LIVE_CAPACITY_REVIEW_BLOCKED`

## Autoridade

Mesmo em READY:
- customer_admission_authorized=false;
- automatic_customer_admission=false;
- automatic_budget_increase=false;
- automatic_quota_change=false;
- billing_authorized=false.
