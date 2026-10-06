# AION B2B — Execution Terminal Certificate Contract V1

Status: **design-only / fail-closed / non-executable**.

## Objetivo

Definir um certificado terminal verificável para uma execução cuja finalização
e audit seal já foram persistidos.

Modo:
`VERIFICATION_ONLY_TERMINAL_CHAIN_CERTIFICATE`

## Estado máximo

`READY_FOR_EXECUTION_TERMINAL_CERTIFICATE_DESIGN_REVIEW`

Próximo passo permitido:

`DESIGN_EXECUTION_TERMINAL_CERTIFICATE_PERSISTENCE_CONTRACT_ONLY`

## Significado

O certificado atesta somente a integridade verificável da cadeia terminal.

Ele **não** é:

- autorização de execução;
- token de retry;
- permissão de reopen;
- provider acknowledgement;
- assinatura jurídica;
- assinatura criptográfica com chave privada.

## Pré-condições

A futura emissão exige:

- execução terminal;
- finalization record persistido;
- audit seal persistido;
- reopen verification do seal;
- recomputação do manifest;
- digest recomputado igual ao persistido;
- ausência de OUTCOME_UNKNOWN/STILL_OUTCOME_UNKNOWN;
- ausência de reconciliação/rollback/compensação pendente.

## Bindings

O certificate manifest deve ligar execution id, terminal state/revision,
finalization record, seal manifest/persistence record, idempotency/effect,
provider correlation, terminal evidence, rollback/compensation settlement,
FinOps, trace e audit chain.

## Verificação

A verificação futura recomputa o certificate manifest digest e falha fechado
diante de qualquer mismatch em identidade, estado terminal, revision,
finalization, seal, correlation, evidence, FinOps ou audit chain.

## Sem autoridade

O certificado nunca autoriza:

- retry;
- reopen;
- nova execução;
- efeito externo;
- billing;
- CRM;
- provisioning;
- deploy;
- produção.

## Esta camada NÃO faz

- geração real de certificado;
- assinatura;
- carga de private key;
- persistência;
- abertura de banco/store;
- query em provider;
- rede;
- qualquer ação externa.
