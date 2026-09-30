# AION BUSINESS Capacity & Quota Guardrail V1

Schema: ATLASQUANT_AION_BUSINESS_CAPACITY_QUOTA_GUARDRAIL_V1

## Objetivo

Vincular a capacidade operacional e econômica de cada tenant ao último estado
íntegro do ledger de expansão.

## Quotas obrigatórias por tenant

- max_ai_requests;
- max_integration_calls;
- max_workflow_runs;
- max_storage_mb;
- ai_cost_budget;
- integration_cost_budget;
- support_cost_budget;
- infra_cost_budget;
- expected_revenue.

O conjunto de tenants das quotas precisa ser exatamente igual ao conjunto de
tenants do ledger verificado.

## Política

A revisão exige duas decisões numéricas explícitas do administrador:

- minimum_margin_pct;
- reserve_capacity_pct.

A margem é recalculada depois da reserva de capacidade. Se qualquer tenant ficar
abaixo da margem mínima, o review é bloqueado.

## Estados

- CAPACITY_POLICY_REQUIRED;
- CAPACITY_QUOTA_REVIEW_READY;
- CAPACITY_QUOTA_REVIEW_BLOCKED;
- QUOTA_APPLICATION_DECISION_REQUIRED.

## Segurança

Mesmo um review verde mantém:

- quota_application_authorized=false;
- billing_authorized=false;
- automatic_expansion_allowed=false;
- client_actions_authorized=false;
- executes_action=false.

Este módulo não aplica quota, não cobra, não muda runtime e não chama serviços
externos.
