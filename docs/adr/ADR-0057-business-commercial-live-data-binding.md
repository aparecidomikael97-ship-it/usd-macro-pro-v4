# ADR-0057 — Binding comercial real entra como leitura atestada, sem escrita externa

Título: Binding comercial real entra como leitura atestada, sem escrita externa  
Data: 2026-09-30  
Status: ACCEPTED

## Contexto

O pipeline B2B já existe internamente, mas ainda faltava uma fronteira para
consumir dados reais de CRM, formulários, e-mail, calendário, pagamentos e
analytics sem transformar leitura em automação de contato ou cobrança.

## Problema

Ligar dados externos diretamente ao pipeline pode introduzir PII bruta, segredos,
dados stale, duplicação de registros e escrita não autorizada em sistemas do
cliente.

## Alternativas consideradas

1. Conectar e escrever diretamente no CRM.
2. Copiar dados completos, incluindo contato, para o AION.
3. Ingerir somente snapshots read-only, atestados, bounded e referenciados.

## Decisão

Adotar a alternativa 3.

Cada fonte precisa de:
- integration permitida;
- connection reference;
- autenticação verificada por camada externa;
- escopo read-only verificado;
- ausência de write scope;
- ausência de valor de credencial;
- timestamp válido.

Cada registro precisa de:
- tenant;
- source;
- record_ref;
- subject_ref pseudônimo;
- source_ref;
- estágio canônico do pipeline;
- estado de permissão de contato;
- timestamp recente.

PII de contato bruta e segredos são rejeitados.

## Consequências

O AION pode produzir um estado observado do pipeline real com contagens, valores
estimados observados e DO_NOT_CONTACT, mas não altera o sistema externo.

O máximo automático é `READY_FOR_ADMIN_LIVE_READ_BINDING_REVIEW`.

## Segurança

A camada não autoriza:
- configuração física de connector;
- escrita no CRM;
- avanço de pipeline;
- envio de mensagem;
- proposta enviada;
- cobrança;
- onboarding;
- runtime;
- deploy.

## Compatibilidade

Complementa Integration Hub, B2B Revenue Offer e Commercial Acquisition.

## Rollback/migração

Read-only. Remoção não altera dados de sistemas externos.

## PR/commit relacionado

Draft PR AION BUSINESS Commercial Live Data Binding V1.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
