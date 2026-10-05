# AION B2B — Owner Renewal Action Command Plan V1

Status: **staging / plano abstrato / não executável**.

## Objetivo

Congelar o significado da ação comercial recorrente depois de:

1. intenção final de execução assinada pelo proprietário;
2. registro persistido e atestado;
3. checkpoint writer criptograficamente atestado;
4. execution preflight original íntegro.

## O que o plano contém

- owner / tenant / workspace;
- customer / pilot / package;
- review type;
- escolha;
- action family;
- operation kind abstrato;
- action-parameters digest;
- execution-preflight digest;
- execution-record digest;
- writer-request digest.

Famílias suportadas: renovação, renovação com mudanças, não renovação,
remediação, rescope de capacidade, repricing, remediação de incidente, pausa e
encerramento.

## O que o plano proíbe

O plano não contém:

- endpoint ou URL de provedor;
- método HTTP;
- headers;
- token;
- senha ou credencial;
- payload executável;
- cURL / PowerShell / shell;
- comando de execução.

O estado máximo é:

`READY_FOR_BUSINESS_ACTION_COMMAND_ADAPTER_REVIEW`.

Mesmo nesse estado todas as autoridades comerciais, chamadas externas e
mutações continuam falsas. Um adaptador futuro deverá ser uma camada separada,
com binding explícito ao `command_plan_digest` e nova revalidação fresca.
