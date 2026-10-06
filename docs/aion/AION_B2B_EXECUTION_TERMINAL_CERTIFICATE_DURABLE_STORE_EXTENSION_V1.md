# AION B2B — Execution Terminal Certificate Durable Store Extension V1

Status: **design-only / fail-closed / non-executable**.

## Objetivo

Resolver o gap físico identificado pelo Runtime Reader Store Adapter sem criar
uma segunda fonte de verdade.

Modo:

`ADDITIVE_SAME_DB_TERMINAL_EVIDENCE_EXTENSION`

## Estado máximo

`READY_FOR_EXECUTION_TERMINAL_CERTIFICATE_DURABLE_STORE_EXTENSION_DESIGN_REVIEW`

Próximo passo permitido:

`IMPLEMENT_EXECUTION_TERMINAL_CERTIFICATE_DURABLE_STORE_EXTENSION_OFFLINE_ONLY`

## O que existe hoje

O `DurableExecutionStore` já protege:

- execution id;
- idempotency key;
- effect key;
- lifecycle state;
- attempts/lease/deadline;
- result digest;
- reconciliation evidence digest;
- crash recovery.

Mas a base atual ainda não possui fisicamente:

- tenant/workspace binding durável;
- terminal revision durável;
- finalization record;
- audit seal record;
- terminal certificate record.

## Estratégia: mesma base, extensão aditiva

A solução futura deve usar **o mesmo banco** do
`DurableExecutionStore`.

Tabelas aditivas propostas:

1. `execution_scope_bindings`
2. `execution_terminal_finalizations`
3. `execution_audit_seals`
4. `execution_terminal_certificates`

A tabela `executions` continua sendo a fonte de identidade da execução.

Não haverá banco sidecar nem segunda verdade terminal.

## Scope binding

O vínculo owner/tenant/workspace deve ser:

- explícito;
- one-to-one por execution id;
- imutável;
- ligado por digest à evidência de origem.

Execuções legadas sem scope **não podem receber scope por adivinhação**.
Elas permanecem fail-closed até uma migração/autorização explícita futura.

## Revisão terminal

Timestamp não pode ser usado como revisão.

A extensão deve oferecer `terminal_revision` durável e verificável, para CAS,
replay e detecção de conflito.

## Cadeia física

A ordem durável é:

`execution -> finalization -> audit seal -> terminal certificate`

Cada etapa é append-only e imutável.

O certificado final liga por digest:

- scope;
- finalization;
- audit seal;
- terminal evidence;
- FinOps observado;
- observability trace;
- audit chain.

## APIs futuras

O mesmo store deverá oferecer APIs explícitas para:

- bind de scope uma vez;
- leitura do scope;
- persistência/leitura de finalization;
- persistência/leitura de audit seal;
- persistência/leitura de certificate;
- snapshot consistente para o Runtime Reader.

## Migração

A implementação futura será primeiro **offline-only** e deverá provar:

- schema version bump;
- preservação de todas as linhas existentes;
- foreign keys ativas;
- WAL e synchronous FULL preservados;
- transação de migração;
- reopen;
- crash antes do commit;
- crash depois do commit;
- legacy unscoped fail-closed;
- zero provider/rede;
- rollback/backup antes de qualquer migração fora de teste.

## Esta versão não migra

Nenhum banco é aberto.
Nenhuma tabela é criada.
Nenhuma linha é escrita.
Nenhuma produção é tocada.

## Autoridade

Persistência de evidência não cria autoridade de execução, retry, reopen,
reconciliação, rollback, compensação ou efeito externo.

## FinOps

Permanece o teto estrutural de **R$ 200/mês** (`20000` centavos).
