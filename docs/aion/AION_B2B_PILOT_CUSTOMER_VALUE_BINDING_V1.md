# AION B2B Pilot-to-Customer Value Binding V1

Status: **staging / explicit customer binding / read-only**.

## Objetivo

Permitir que o Portal do Cliente receba somente a projeção customer-safe do
valor de um piloto quando sessão, cliente, service tenant, workspace e pilot_id
estiverem explicitamente vinculados.

## Pré-condições

O binding exige três entradas independentes:

1. resultado ALLOW do Customer Portal Access;
2. binding Piloto ↔ Cliente com state CONFIRMED e enabled=true;
3. Pilot Value Read Model com view=CUSTOMER e state=READY.

## Continuidade de identidade

Devem coincidir exatamente:

- customer_id;
- service_tenant_id;
- workspace_id;
- pilot_id.

O binding administrativo exige pelo menos três evidence refs e um binding_ref.

## Projeção aceita

A projeção de valor deve ser customer-safe e manter:

- internal_economics_visible=false;
- provider_delivery_cost_exposed=false;
- provider_margin_exposed=false;
- retention_risk_exposed=false;
- internal_recommendation_exposed=false;
- renewal_control_exposed=false;
- expansion_control_exposed=false;
- billing_control_exposed=false;
- customer_contact_control_exposed=false;
- grants_authority=false;
- executes_action=false.

Campos internos como margem, custo de entrega, retention risk, recomendação
interna, review reasons ou evidence refs são rejeitados mesmo se forem
injetados em uma estrutura marcada como customer-safe.

## Portal

Quando o binding é válido e a seção value está autorizada, o portal pode mostrar:

- estado do valor do piloto;
- tendência;
- ROI observado;
- economia observada;
- quick wins;
- payback.

O portal não mostra margem AtlasQuant, custo interno, risco de retenção ou
recomendação de expansão/saída.

Sem a seção value, o bundle pode estar validado mas não é renderizado.

## Segurança

O binding não renova, expande, cobra, contata, provisiona, faz deploy ou altera
produção. Ele apenas produz e apresenta informação já validada.
