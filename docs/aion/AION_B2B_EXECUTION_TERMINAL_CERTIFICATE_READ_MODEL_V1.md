# AION B2B — Execution Terminal Certificate Read Model V1

Status: **design-only / fail-closed / read-only / non-executable**.

## Objetivo

Definir a projeção futura para consultar o certificado terminal de uma execução
B2B sem transformar evidência em autoridade.

Modo:

`READ_ONLY_TERMINAL_CERTIFICATE_PROJECTION`

## Estado máximo

`READY_FOR_EXECUTION_TERMINAL_CERTIFICATE_READ_MODEL_DESIGN_REVIEW`

Próximo passo permitido:

`DESIGN_EXECUTION_TERMINAL_CERTIFICATE_READ_MODEL_UI_ONLY`

## Pré-condição

A camada exige exatamente um
`Execution Terminal Certificate Persistence Contract V1` pronto para revisão,
mantendo:

- commit exatamente uma vez;
- compare-and-set;
- registro append-only e imutável;
- consistência após reopen;
- proibição de reabrir execução;
- ausência de autoridade de execução;
- SHA256 + JSON canônico UTF-8;
- teto FinOps de R$ 200/mês.

## Estados futuros da projeção

A projeção pode representar apenas:

- `VERIFIED`;
- `MISMATCH`;
- `UNAVAILABLE`;
- `STALE`.

Somente `VERIFIED` exige todos os digests vinculados consistentes. Qualquer
mismatch, ausência ou evidência stale deve permanecer fail-closed e nunca pode
ser convertido em VERIFIED por conveniência de UI.

## Escopo

O read model deve ser isolado por tenant/workspace e ligado ao execution id
canônico, revisão terminal, estado final e cadeia de digests.

## Evidência exibível

A projeção futura pode carregar metadados e digests como:

- execution id;
- estado final;
- revisão terminal;
- status do certificado;
- digest do manifesto e do certificado;
- digest do registro de persistência;
- digest da finalização;
- digest do audit seal;
- digest do evidence set;
- observabilidade e FinOps.

## Material proibido

Nunca expor:

- credenciais, secrets, tokens ou chaves privadas;
- signing keys;
- authorization headers;
- payload bruto;
- resposta bruta de provider;
- mensagem bruta de cliente;
- comando de shell.

## Sem autoridade

Nenhum status do read model autoriza:

- emissão/assinatura de certificado;
- retry;
- reopen;
- reconciliação;
- rollback/compensação;
- efeito externo;
- cobrança;
- CRM;
- provisionamento;
- deploy;
- mutação de produção.

## Limite desta versão

Esta versão não abre banco, não lê registro real, não verifica digest ao vivo,
não consulta provider e não produz UI. Ela define somente o contrato da projeção
read-only que uma camada futura poderá consumir.
