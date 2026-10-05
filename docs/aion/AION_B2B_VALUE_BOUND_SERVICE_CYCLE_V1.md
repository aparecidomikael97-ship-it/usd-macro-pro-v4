# AION B2B — Value-Bound Service Cycle V1

Status: **staging / review-only / no external authority**.

## Objetivo

Conectar o rascunho de serviço recorrente já vinculado ao valor real do piloto ao
ciclo operacional existente de Saúde do Cliente, SLA, quotas, FinOps e revisão de
renovação.

A cadeia preserva explicitamente:

- owner;
- tenant;
- workspace;
- customer;
- pilot;
- pacote;
- digest do contrato;
- digest da conversão value-bound;
- digest da evidência do ciclo.

## Estados do ciclo

O módulo reaproveita o avaliador de Managed Service já existente:

- `HEALTHY / RENEWAL_REVIEW_CANDIDATE`;
- `REMEDIATION / REMEDIATE_REVIEW`;
- `CAPACITY_HOLD / CAPACITY_REVIEW`;
- `INCIDENT_REVIEW`;
- `BLOCKED`.

Mesmo no estado saudável, renovação continua sendo apenas candidata à revisão do
proprietário.

## Fail-closed

O bridge bloqueia quando houver:

- schema de origem incorreto;
- rascunho ou boundary de ativação inválidos;
- blocker anterior;
- divergência de owner/tenant/workspace;
- divergência cliente ↔ contrato;
- ausência de pilot;
- divergência de pacote;
- ausência de digests;
- qualquer flag automática inesperada;
- evidência com customer_id ou pilot_id incompatível;
- ciclo recorrente com escopo, cliente ou pacote incompatível.

## Separação cliente x AtlasQuant

O ciclo contém FinOps interno e, por isso:

- `customer_visible=false`;
- `contains_internal_finops=true`;
- `requires_customer_safe_projection=true`.

O custo interno não deve ser enviado diretamente ao Portal do Cliente. Uma
projeção customer-safe separada deve filtrar qualquer informação interna.

## Limite de autoridade

O módulo não executa:

- renovação;
- expansão;
- troca de pacote;
- pausa;
- encerramento;
- cobrança;
- aumento de quota;
- mudança de role;
- mudança de integração;
- contato com cliente;
- provisionamento;
- deploy;
- provider call;
- mutação de produção.

Todas essas flags permanecem `false`.
