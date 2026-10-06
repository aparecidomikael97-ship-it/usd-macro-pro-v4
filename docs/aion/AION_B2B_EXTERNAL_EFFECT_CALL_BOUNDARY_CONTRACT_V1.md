# AION B2B — External Effect Call Boundary Contract V1

Status: **design-only / fail-closed / non-executable**.

## Objetivo

Definir a fronteira exata em torno de uma futura chamada externa.

Modo:
`SEALED_SINGLE_CALL_AFTER_DURABLE_DISPATCH`

A regra é:
1. todo material mutável é resolvido/validado antes do dispatch record;
2. `DISPATCH_RECORDED` é persistido de forma durável;
3. depois disso nada pode mudar;
4. um futuro executor teria no máximo uma tentativa selada;
5. qualquer ambiguidade pós-record vira `OUTCOME_UNKNOWN`.

## Estado máximo

`READY_FOR_EXTERNAL_EFFECT_CALL_BOUNDARY_DESIGN_REVIEW`

Próximo passo:
`DESIGN_EXTERNAL_EFFECT_OUTCOME_RECEIPT_CONTRACT_ONLY`

## Antes do dispatch record

Devem estar resolvidos e congelados por referência/digest:
- provider identity;
- adapter version/digest;
- capability binding;
- endpoint de trusted provider configuration;
- credential reference de approved secret source;
- credential scope/expiry;
- payload schema + digest;
- headers policy;
- transport/TLS policy;
- timeout policy;
- redirect policy;
- FinOps <= 20.000 cents;
- observability correlation.

## Depois do dispatch record

É proibido:
- trocar provider/endpoint;
- trocar credencial;
- alterar payload;
- expandir capability/scope;
- aumentar FinOps ceiling.

A tentativa futura deve preservar execution id, trace id, idempotency/effect
identity e produzir response-or-ambiguity receipt.

Timeout, connection reset, process crash ou provider ack ambíguo depois do
record => `OUTCOME_UNKNOWN`.

Retry automático nesse estado é proibido.

## Esta camada NÃO faz

- provider selection/binding;
- adapter load;
- endpoint resolution;
- credential/secret load;
- payload/header construction;
- socket/transport open;
- network/provider call;
- billing/CRM/provisioning/deploy/produção.
