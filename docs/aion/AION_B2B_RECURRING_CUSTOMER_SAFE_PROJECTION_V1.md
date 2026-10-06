# AION B2B — Recurring Customer-Safe Projection V1

Status: **staging / read-only / customer-safe**.

## Objetivo

Criar a projeção recorrente segura que pode alimentar o Portal do Cliente depois
do Managed Service já estar vinculado ao valor real do piloto.

A projeção recebe:

1. acesso ao Portal do Cliente já autorizado;
2. ciclo recorrente value-bound;
3. read model operacional já validado.

Ela preserva customer, pilot, tenant, workspace e pacote, mas reduz a saída ao que
é seguro para o cliente.

## O que o cliente pode ver

- estado público do serviço;
- saúde;
- ROI observado;
- uso de capacidade;
- uso de chamadas;
- uso de tokens;
- uso de tickets;
- primeira resposta;
- resolução;
- indicadores de SLA;
- horário/evidência da atualização.

## O que nunca entra na projeção

- custo interno da AtlasQuant;
- custo de provider;
- margem;
- risco de retenção;
- recomendação interna;
- decisão de renovação;
- decisão de expansão;
- razões internas de revisão;
- escolhas disponíveis ao proprietário;
- lineage interno de expansão/continuidade.

Os estados internos são convertidos para rótulos customer-safe:

- HEALTHY → SAUDÁVEL;
- REMEDIATION → EM ACOMPANHAMENTO;
- CAPACITY_HOLD → CAPACIDADE EM REVISÃO;
- INCIDENT_REVIEW → EM ANÁLISE.

## Integração com o Portal

Quando a projeção recorrente é fornecida ao Portal do Cliente e passa todas as
validações, ela substitui os campos operacionais brutos da visualização.

Nesse modo:

- `service_decision=""`;
- `review_reasons=[]`;
- `incident_reasons=[]`;
- custo interno não é copiado;
- recommendation/renewal/expansion internals não são renderizados.

A integração é opcional para preservar compatibilidade com o Portal existente
enquanto a cadeia continua em Draft.

## Segurança

A projeção exige:

- acesso ao portal previamente ALLOW;
- exato customer/service tenant/workspace/package;
- ciclo value-bound sem blockers;
- customer_visible=false no ciclo interno;
- contains_internal_finops=true;
- requires_customer_safe_projection=true;
- read model READY/read-only;
- evidência presente;
- zero autoridade automática.

Permanecem falsos:

- cobrança automática;
- renovação automática;
- expansão automática;
- contato automático;
- deploy;
- mutação de produção;
- grants_authority;
- executes_action.
