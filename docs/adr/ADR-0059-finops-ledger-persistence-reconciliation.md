# ADR-0059 — Persistência do ledger usa cadeia de versões e reconciliação de fatura read-only

Título: Persistência do ledger usa cadeia de versões e reconciliação de fatura read-only  
Data: 2026-09-30  
Status: ACCEPTED

## Contexto

O ledger FinOps já possui hash-chain interna para custos observados. Faltava uma
fronteira para versionar snapshots do ledger ao longo do tempo e reconciliar
faturas reais sem transformar revisão em pagamento.

## Problema

Salvar versões sem vínculo entre elas permite gaps/replay. Reconciliar faturas
sem atestação pode misturar valores, períodos ou providers incorretos.

## Alternativas consideradas

1. Persistir somente o arquivo mais recente.
2. Confiar apenas no digest interno do ledger.
3. Manifestos versionados encadeados + reconciliação de fatura atestada.

## Decisão

Adotar a alternativa 3.

Cada versão:
- possui número sequencial;
- aponta para o digest do manifesto anterior;
- a primeira versão aponta para genesis;
- possui storage_ref;
- registra creator e timestamp;
- liga ledger digest, tail digest e entry count;
- possui version_manifest_digest.

A cadeia rejeita:
- gap;
- reorder;
- replay;
- alteração retroativa;
- digest divergente.

A reconciliação de fatura exige:
- invoice attestation;
- provider/period iguais;
- ledger verificado;
- total dentro da tolerância administrativa.

## Consequências

O AION consegue demonstrar continuidade do ledger e conferir fatura x custo
observado antes de qualquer pagamento.

## Segurança

A camada não:
- grava storage;
- paga fatura;
- altera assinatura;
- muda preço;
- move dinheiro;
- chama provider;
- ativa runtime.

## Compatibilidade

Complementa ADR-0058 e o Budget Governor.

## Rollback/migração

Pure/read-only. Remoção não altera storage ou pagamentos reais.

## PR/commit relacionado

Draft PR AION FinOps Ledger Persistence & Reconciliation V1.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
