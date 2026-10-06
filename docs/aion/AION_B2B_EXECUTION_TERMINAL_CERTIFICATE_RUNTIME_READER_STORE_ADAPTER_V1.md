# AION B2B — Execution Terminal Certificate Runtime Reader Store Adapter V1

Status: **design-only / fail-closed / read-only / non-executable**.

## Objetivo

Definir o adapter entre o futuro Runtime Reader e o store durável existente,
sem criar uma segunda fonte de verdade.

Modo:

`READ_ONLY_FAIL_CLOSED_CORE_DURABLE_STORE_ADAPTER`

## Estado máximo

`READY_FOR_EXECUTION_TERMINAL_CERTIFICATE_RUNTIME_READER_STORE_ADAPTER_DESIGN_REVIEW`

Próximo passo permitido:

`DESIGN_EXECUTION_TERMINAL_CERTIFICATE_DURABLE_STORE_EXTENSION_ONLY`

## Achado arquitetural obrigatório

O `atlasquant_aion_durable_execution_kernel.DurableExecutionStore` atual
persiste a execução e já oferece identidade canônica, idempotência, effect key,
estado durável, result digest e reconciliation evidence digest.

Porém, **nesta base ele ainda não oferece**:

- API de leitura de certificado terminal;
- digest/revisão do certificado terminal;
- vínculo tenant;
- vínculo workspace;
- foreign key explícita certificado → execução;
- armazenamento append-only do certificado;
- leitura de consistência do certificado após reopen.

Portanto:

**live binding = false** nesta camada.

O adapter não pode fingir disponibilidade nem reconstruir certificado de outras
fontes.

## Uma única fonte física

É obrigatório reutilizar o mesmo store durável.

É proibido:

- banco sidecar;
- segundo SQLite para “resolver rápido”;
- cache tratado como fonte de verdade;
- terminal truth duplicada;
- fallback para provider;
- fallback para rede.

## Extensão futura necessária

A próxima camada deverá desenhar a extensão durável do mesmo store com pelo
menos:

- execution id;
- tenant id;
- workspace id;
- terminal revision;
- final execution state;
- certificate manifest digest;
- certificate digest;
- persistence record digest;
- finalization record digest;
- audit seal digests;
- terminal evidence digest;
- FinOps observation digest;
- observability trace;
- pre-terminal audit chain digest;
- digest algorithm;
- canonical encoding;
- persisted at.

O registro precisa estar ligado à execução canônica e manter semântica
append-only/imutável.

## Fail-closed

Se faltar API, schema, escopo, digest, revisão ou consistência:

- nunca inferir VERIFIED;
- nunca procurar outro tenant/workspace;
- nunca buscar provider;
- nunca buscar rede;
- nunca criar autoridade;
- retornar estado fail-closed apropriado.

## Separação evidência x autoridade

O adapter read-only não pode autorizar execução, retry, reopen, reconciliação,
rollback, compensação ou efeito externo.

Também não pode cobrar, escrever CRM, provisionar, fazer deploy ou mutar
produção.

## Limite desta versão

Esta PR futura não abrirá banco/store e não realizará query real. Ela fixa o
contrato e torna explícito o gap físico que precisa ser resolvido pela próxima
**Durable Store Extension**.

## FinOps

Permanece o teto estrutural de **R$ 200/mês** (`20000` centavos).
