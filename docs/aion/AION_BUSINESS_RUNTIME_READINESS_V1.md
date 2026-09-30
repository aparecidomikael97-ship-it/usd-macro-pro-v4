# AION BUSINESS Runtime Readiness V1

Schema: `ATLASQUANT_AION_BUSINESS_RUNTIME_READINESS_V1`

## Objetivo

Preparar o AION Business Expert certificado para uma futura decisão de runtime
sem ligar runtime neste bloco.

Certificação é condição necessária, mas não suficiente para execução.

## Estados

- `NOT_ELIGIBLE`: faltou certificação válida, vínculo de SHA/fingerprint ou
  algum gate de segurança.
- `SANDBOX_READY`: todos os gates de sandbox passaram.
- `RUNTIME_APPROVAL_REQUIRED`: existe um pacote preparado para revisão humana
  de runtime, mas runtime continua desligado.

## Sandbox

O plano de sandbox permite somente:

- read;
- analyze;
- draft.

Continuam negados:

- external_contact;
- sign_contract;
- charge/payment;
- spend;
- publish/publication;
- deploy;
- real_trade;
- move_money.

## Gates obrigatórios

Para `SANDBOX_READY`:

- decisão de certificação BUSINESS válida;
- SHA idêntico ao certificado;
- fingerprint idêntico ao certificado;
- sandbox isolado;
- rede externa desabilitada;
- pagamentos desabilitados;
- publicação desabilitada;
- deploy desabilitado;
- trading real desabilitado;
- auditoria habilitada;
- rollback pronto;
- kill switch pronto.

Booleanos semelhantes como `"true"` ou `1` não contam.

## Pacote de aprovação de runtime

`business_runtime_approval_packet()` apenas prepara uma solicitação futura.
Ele retorna `runtime_activation_approved=false` e não possui caminho de execução.

A aprovação futura terá escopo separado: `RUNTIME_ACTIVATION_ONLY`.

## Regra principal

Este módulo não ativa runtime. Ele não chama provider, não escreve externamente,
não envia contato, não assina contrato, não cobra, não publica, não faz deploy e
não opera trading real.
