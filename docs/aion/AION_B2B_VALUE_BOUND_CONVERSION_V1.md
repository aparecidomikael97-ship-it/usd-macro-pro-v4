# AION B2B — Value-Bound Conversion V1

## Objetivo

Amarrar a camada de **Pilot Value Realization** ao gate comercial de
**Conversion + Capacity** antes de qualquer decisão de continuidade ou expansão.

## Binding obrigatório

O gate exige, em conjunto:

- escopo confiável exato: `owner_id`, `tenant_id`, `workspace_id`;
- `customer_id` explícito;
- `pilot_id` explícito;
- pelo menos três referências de evidência do binding;
- Pilot Value Realization sem blockers e elegível;
- Conversion Capacity em estado `REVIEWABLE`;
- decisão comercial ainda limitada a revisão humana.

## Estados elegíveis

Somente dois caminhos podem chegar a revisão comercial:

- `STRONG_VALUE + EXPANSION_REVIEW_CANDIDATE`;
- `VALUE_CONFIRMED + CONTINUE_REVIEW_CANDIDATE`.

Piloto em remediação, saída, stop review, evidência incompleta, capacity hold ou
commercial hold falha fechado.

## Decisões emitidas

O módulo emite apenas candidatos:

- `EXPANSION_COMMERCIAL_REVIEW_CANDIDATE`;
- `CONTINUE_COMMERCIAL_REVIEW_CANDIDATE`;
- ou `BLOCKED`.

## Limite de autoridade

Este bloco não executa:

- conversão automática;
- expansão automática;
- mudança automática de pacote ou preço;
- contrato;
- cobrança;
- provisionamento;
- renovação;
- contato com cliente;
- escrita em CRM;
- chamada de provider;
- deploy;
- mutação de produção.

Toda decisão comercial continua exigindo revisão e aprovação humana do owner.
