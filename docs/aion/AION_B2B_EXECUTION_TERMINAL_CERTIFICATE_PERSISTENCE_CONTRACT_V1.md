# AION B2B — Execution Terminal Certificate Persistence Contract V1

Status: **design-only / fail-closed / non-executable**.

## Objetivo

Definir como um futuro runtime deverá persistir, de forma durável, o certificado terminal de uma execução já finalizada, selada e elegível para certificação.

Modo:

`APPEND_ONLY_CAS_TERMINAL_CERTIFICATE_COMMIT`

## Estado máximo

`READY_FOR_EXECUTION_TERMINAL_CERTIFICATE_PERSISTENCE_DESIGN_REVIEW`

Próximo passo permitido:

`DESIGN_EXECUTION_TERMINAL_CERTIFICATE_READ_MODEL_ONLY`

## Fonte de verdade

A persistência futura deve reutilizar:

- `atlasquant_aion_durable_execution_kernel.DurableExecutionStore`
- `atlasquant_aion_durable_execution_kernel.canonical_execution_id`

Não é permitido criar uma segunda verdade para o estado terminal ou para o certificado persistido.

## Pré-condições

O contrato exige, antes de qualquer persistência futura:

- execução terminal;
- finalização persistida;
- audit seal persistido e consistente após reopen;
- Terminal Certificate Contract em estado exato de design review;
- certificado somente de verificação;
- SHA256 + UTF8 canonical JSON;
- ausência total de autoridade operacional no certificado.

## Commit futuro

O futuro commit deve exigir:

- execution id canônico;
- terminal revision;
- expected pre-certificate revision;
- compare-and-set;
- apenas um vencedor por identidade terminal;
- certificate manifest digest;
- certificate digest;
- cadeia de finalização, audit seal, evidência, FinOps e observabilidade ligada por digest.

## Imutabilidade

Depois do commit futuro:

- registro append-only;
- certificado imutável;
- delete proibido;
- replace proibido;
- reopen da execução terminal proibido;
- mesmo digest = replay idempotente;
- digest diferente para a mesma identidade terminal = conflito fail-closed.

## Crash e reopen

Crash antes do commit não pode inferir certificado persistido.

Crash depois do commit deve reencontrar exatamente o mesmo registro.

Após reopen devem bater, no mínimo:

- execution id;
- terminal revision;
- final execution state;
- finalization record digest;
- audit seal manifest/persistence digests;
- certificate manifest digest;
- certificate digest;
- algoritmo e canonical encoding;
- ausência de duplicata;
- revision monotônica.

## Não cria autoridade

Persistir certificado não autoriza:

- nova execução;
- retry;
- reopen;
- reconciliação;
- rollback;
- compensação;
- efeito externo;
- cobrança;
- CRM;
- provisionamento;
- deploy;
- mutação de produção.

## Fora de escopo

Esta camada não:

- abre SQLite/store;
- inicia transação;
- faz CAS real;
- gera certificado real;
- assina certificado;
- carrega private key;
- escreve registro;
- consulta provider;
- abre rede;
- executa billing/CRM/deploy/produção.

## Limite FinOps

Permanece fixo em **R$ 200/mês** (`20000` centavos) enquanto este contrato estiver nesta fase de design.

## Regra fail-closed

Qualquer divergência de schema, estado, digest, revisão, cadeia terminal, canonicalização ou flag de autoridade bloqueia a progressão.
