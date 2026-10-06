# AION B2B — Execution Audit Seal Contract V1

Status: **design-only / fail-closed / non-executable**.

## Objetivo

Definir um selo determinístico de cadeia de custódia para uma execução B2B
terminal já finalizada e persistida.

Modo:
`DETERMINISTIC_TERMINAL_CHAIN_OF_CUSTODY_MANIFEST`

Digest:
`SHA256`

Encoding:
`UTF8_CANONICAL_JSON`

## Estado máximo

`READY_FOR_EXECUTION_AUDIT_SEAL_DESIGN_REVIEW`

Próximo passo permitido:

`DESIGN_EXECUTION_AUDIT_SEAL_PERSISTENCE_CONTRACT_ONLY`

## O que o selo liga

O manifest futuro deve ligar por referência/digest:

- execution id e terminal revision;
- estado terminal;
- finalization record;
- contratos de finalização/persistência;
- dispatch record;
- call boundary;
- outcome receipt;
- reconciliation quando aplicável;
- execution envelope e pre-dispatch attestation;
- owner/reconciliation authorizations;
- provider adapter/capability;
- idempotency/effect identity;
- provider request correlation;
- terminal evidence;
- before-state e expected postcondition;
- rollback/compensation settlement quando aplicável;
- FinOps estimate/observation;
- trace id;
- cadeia de auditoria pré-terminal.

## Determinismo

O mesmo manifest canônico deve produzir o mesmo digest.

Qualquer alteração em campo ligado deve alterar o digest.

A verificação futura deve recomputar o manifest e falhar fechado diante de
qualquer mismatch.

## Invalidadores

O selo não pode ser considerado válido se houver:

- execução não terminal;
- `OUTCOME_UNKNOWN` ou `STILL_OUTCOME_UNKNOWN`;
- binding ausente;
- schema/encoding/algoritmo divergente;
- mismatch de finalization/execution/revision;
- mismatch de idempotency/effect/provider correlation;
- mismatch de outcome/reconciliation;
- rollback/compensation não coerente;
- FinOps divergente;
- audit chain divergente;
- seal digest divergente.

## O selo não cria autoridade

O selo não autoriza:

- retry;
- reopen;
- reconciliação;
- rollback;
- compensação;
- efeito externo;
- billing/CRM/provisioning/deploy/produção.

## Esta camada NÃO faz

- geração real do selo;
- assinatura com chave real;
- leitura de private key;
- persistência;
- abertura de banco/store;
- network/provider query;
- retry/reopen;
- qualquer efeito externo.
