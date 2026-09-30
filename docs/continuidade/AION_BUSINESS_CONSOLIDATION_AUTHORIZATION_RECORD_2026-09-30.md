# BUSINESS Consolidation Explicit Authorization Record V1 — 2026-09-30

## Missão

Definir o contrato de uma futura autorização explícita sem executar merge.

## Token obrigatório

`AUTHORIZE_STACK_CONSOLIDATION_394_412`

Frases genéricas não são aceitas como autorização.

## Acknowledgements obrigatórios

- escopo somente #394–#412;
- deploy continua separado;
- piloto continua separado;
- runtime continua OFF;
- CI após cada etapa continua obrigatório;
- qualquer drift interrompe a autorização.

## Binding

O registro precisa apontar para o digest exato do pedido de decisão. Mudança de
request digest, revisor, escopo ou acknowledgement invalida o registro.

## Estado máximo

`EXPLICIT_AUTHORIZATION_RECORD_VERIFIED`.

Ainda não executa merge e não concede deploy, piloto ou runtime.
