# AION B2B — External Effect Outcome Receipt Contract V1

Status: **design-only / fail-closed / non-executable**.

## Objetivo

Definir como um futuro executor deverá registrar o resultado observável de
**uma única chamada externa selada**, sem transformar ausência de erro,
timeout ou silêncio do provider em sucesso presumido.

Modo:
`IMMUTABLE_PROVIDER_OUTCOME_CLASSIFICATION`

## Estado máximo

`READY_FOR_EXTERNAL_EFFECT_OUTCOME_RECEIPT_DESIGN_REVIEW`

Próximo passo permitido:

`DESIGN_OUTCOME_RECONCILIATION_CONTRACT_ONLY`

## Estados de resultado permitidos

- `CONFIRMED_SUCCESS`
- `CONFIRMED_TERMINAL_FAILURE`
- `OUTCOME_UNKNOWN`

Não existe quarto estado implícito.

## Sucesso confirmado

Sucesso exige evidência positiva e correlacionada, incluindo identidade do
provider, adapter/capability, execution/trace, request correlation,
idempotency/effect identity, schema/autenticidade da resposta e evidência do
efeito/postcondition esperado.

**Ausência de erro não é prova de sucesso.**

## Falha terminal confirmada

Falha terminal exige resposta autoritativa correlacionada e evidência suficiente
de rejeição terminal ou de que o efeito não ocorreu.

**Ausência de resposta não é prova de falha.**

## OUTCOME_UNKNOWN

Timeout, reset de conexão, crash, ack ausente/malformado/ambíguo, mismatch de
correlação/identidade/schema/autenticidade, resposta duplicada conflitante,
resposta tardia fora de contexto ou evidência incompleta classificam o resultado
como `OUTCOME_UNKNOWN`.

Nesse estado:

- retry automático é proibido;
- o receipt original é imutável;
- reconciliação deve gerar outro registro;
- reconciliação exige evidência;
- reconciliação exige autorização separada;
- nova tentativa exige autorização fresca e novo durable dispatch.

## Bindings obrigatórios

O futuro receipt deverá estar ligado por referência/digest a:

- execution id e trace id;
- durable dispatch record e call boundary;
- execution envelope e pre-dispatch attestation;
- fresh owner authorization;
- provider adapter attestation e capability binding;
- provider identity/adapter;
- endpoint e credential references;
- payload digest;
- idempotency/effect digests;
- provider request correlation;
- provider response evidence;
- before state, expected postcondition e rollback plan;
- FinOps estimate/observation.

## Imutabilidade e segurança

O receipt é append-only, não pode ampliar capability, scope ou teto FinOps e
não pode carregar segredo, credencial, Authorization header, payload bruto ou
raw provider response body.

## Esta camada NÃO faz

- abrir socket/transporte;
- chamada de rede/provider;
- ler segredo/credencial;
- observar resposta real;
- classificar resultado real;
- persistir receipt;
- retry;
- reconciliação;
- billing;
- contato com cliente;
- CRM;
- provisioning;
- deploy;
- produção.
