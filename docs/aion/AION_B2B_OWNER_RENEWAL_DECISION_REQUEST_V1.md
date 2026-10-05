# AION B2B — Owner Renewal Decision Request V1

Status: **staging / request-only / no decision execution**.

## Objetivo

Preparar uma solicitação canônica para uma decisão explícita do proprietário
depois da revisão recorrente do serviço.

Este módulo não toma a decisão e não aceita uma mensagem genérica do chat como
decisão.

## Entrada

Exige um Owner Renewal Review Packet válido, sem blockers e com:

- owner/tenant/workspace;
- customer;
- pilot;
- pacote;
- tipo de revisão;
- alternativas exatas permitidas;
- digest do ciclo;
- digest do contrato;
- digest da conversão value-bound;
- digest do pacote de revisão.

## Escolha

`requested_choice` deve ser exatamente uma das alternativas presentes em
`allowed_owner_choices`.

Expressões genéricas como:

- "vamos lá";
- "ok";
- "sim";
- "aprovado";

não são aceitas como decisão.

## Saída

Uma solicitação válida produz apenas:

`READY_FOR_EXPLICIT_OWNER_SIGNATURE`

com um digest determinístico da solicitação.

Ainda ficam falsos:

- owner_signature_verified;
- owner_decision_verified;
- owner_decision_recorded;
- decision_persisted;
- renewal_authorized;
- expansion_authorized;
- pause_authorized;
- termination_authorized;
- billing_authorized;
- pricing_change_authorized;
- quota_change_authorized;
- role_change_authorized;
- integration_change_authorized;
- customer_contact_authorized;
- provisioning_authorized;
- deploy_authorized;
- production_mutation_authorized;
- executes_action.

## Próxima fronteira

A assinatura/verificação do proprietário deve ser uma etapa separada, ligada ao
digest exato desta solicitação. Persistência e qualquer execução também continuam
separadas.
