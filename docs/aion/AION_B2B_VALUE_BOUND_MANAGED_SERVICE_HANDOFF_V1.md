# AION B2B — Value-Bound Managed Service Handoff V1

## Objetivo

Levar uma conversão comercial já vinculada ao valor real do piloto até o
rascunho do serviço recorrente, preservando o mesmo cliente, piloto e escopo.

## Entrada obrigatória

O handoff aceita somente:

- schema de Value-Bound Conversion válido;
- estado `REVIEWABLE`;
- decisão de expansão ou continuidade para revisão comercial;
- escopo exato de owner/tenant/workspace;
- `customer_id` e `pilot_id` presentes;
- pacote recomendado válido;
- digest de evidência;
- flags de segurança intactas.

## Saída

Quando todas as condições comerciais e o approval do owner batem, o módulo
delega ao contrato existente de Managed Service e retorna apenas:

- `DRAFT_FOR_OWNER_ACTIVATION`;
- `BLOCKED_UNTIL_OWNER_ACTIVATION`.

Não existe ativação automática.

## Limite de autoridade

O handoff não executa ativação, contrato, cobrança, provisionamento, integração,
role grant, renovação, contato com cliente, provider, deploy, CRM ou mutação de
produção.
