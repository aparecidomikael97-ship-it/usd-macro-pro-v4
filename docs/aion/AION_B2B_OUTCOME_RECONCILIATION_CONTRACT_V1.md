# AION B2B — Outcome Reconciliation Contract V1

Status: **design-only / fail-closed / non-executable**.

## Objetivo

Definir como um futuro runtime poderá reconciliar um receipt já registrado como
`OUTCOME_UNKNOWN` sem reescrever histórico e sem repetir o efeito externo.

Modo:
`SEPARATE_EVIDENCE_BOUND_UNKNOWN_RESOLUTION`

## Estado máximo

`READY_FOR_OUTCOME_RECONCILIATION_DESIGN_REVIEW`

Próximo passo permitido:

`DESIGN_EXECUTION_FINALIZATION_CONTRACT_ONLY`

## Resultados possíveis da reconciliação

- `RECONCILED_CONFIRMED_SUCCESS`
- `RECONCILED_CONFIRMED_TERMINAL_FAILURE`
- `STILL_OUTCOME_UNKNOWN`

A reconciliação nunca cria um quarto resultado implícito.

## Regra histórica

O receipt original de `OUTCOME_UNKNOWN` é **imutável**.

A reconciliação gera um registro separado, append-only, ligado por digest ao
receipt original e a toda cadeia de execução.

Ela não é retry e não é replay do efeito externo.

## Evidência

A futura reconciliação deve usar evidência autoritativa, autenticada, fresca,
correlacionada e ligada por digest.

Classes possíveis incluem:

- status autoritativo da operação no provider;
- lookup autoritativo do request no provider;
- evento/receipt assinado pelo provider;
- readback autoritativo no lado do efeito;
- registro downstream imutável.

Evidência faltante, incompleta, stale, não autenticada, conflitante ou com
mismatch de identidade/correlação mantém o estado
`STILL_OUTCOME_UNKNOWN`.

## Nova tentativa

Reconciliação **não autoriza** nova tentativa.

Quando a política permitir nova tentativa, ela exige cumulativamente:

- evidência confirmada de que o efeito não ocorreu;
- fresh owner authorization;
- novo durable dispatch record;
- nova call boundary.

Nenhum desses itens é executado nesta camada.

## Segurança

Reconciliação exige autorização separada. Autorização anterior não pode ser
reutilizada.

Capability scope e teto FinOps não podem ser expandidos durante reconciliação.

## Esta camada NÃO faz

- query em provider;
- leitura de secret/credential;
- abertura de rede/socket;
- leitura live de produção;
- mutação do receipt original;
- persistência real da reconciliação;
- retry;
- nova tentativa;
- efeito externo;
- billing;
- contato com cliente;
- CRM;
- provisioning;
- deploy;
- produção.
