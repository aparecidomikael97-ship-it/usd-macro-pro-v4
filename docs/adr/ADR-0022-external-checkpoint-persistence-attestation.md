# ADR-0022 — Persistência externa precisa de binding explícito entre Checkpoint lógico e runtime

- Título: Persistência externa precisa de binding explícito entre Checkpoint lógico e runtime
- Data: 2026-10-04
- Status: ACCEPTED

## Contexto

O AION possui dois contratos legítimos e diferentes:

- `atlasquant_aion_checkpoint_master`: envelope lógico, journal, revision e state digest;
- `atlasquant_aion_memory`: checkpoint operacional persistido em branch runtime com
  escrita condicional, receipt e read-after-write.

V2.22 identificou que um objeto lógico válido não prova, sozinho, persistência externa.

## Problema

Sem uma ponte explícita, um sistema poderia:

- revisar um Checkpoint lógico;
- persistir outro conteúdo;
- reaproveitar um receipt sem binding ao review;
- usar conteúdo coincidente sem provar atribuição da escrita;
- preparar assinatura sobre um estado diferente do estado persistido.

## Alternativas rejeitadas

- considerar a presença do review em memória como persistência;
- guardar o Checkpoint lógico inteiro dentro do runtime sem necessidade;
- aceitar apenas igualdade de conteúdo sem write attribution;
- aceitar runtime stale;
- aceitar receipt para `main`;
- reutilizar diretamente o digest V2.22 como digest assinável;
- executar save automaticamente na camada de attestation.

## Decisão

V2.23 cria um binding compacto e determinístico no namespace:

`aion_core_checkpoint_master_v1`

O binding contém:

- target SHA;
- checkpoint master digest;
- checkpoint state digest;
- checkpoint revision;
- V2.21 review digest;
- V2.22 challenge digest;
- flags críticas seguras;
- binding digest.

O binding não afirma persistência por conta própria.

A attestation positiva exige:

- runtime CONFIRMED;
- observação fresca;
- repo/branch/path exatamente iguais ao runtime oficial;
- branch runtime permitida;
- source/target consistentes;
- binding exato;
- receipt válido;
- `reconcile_runtime_write=CONFIRMED`;
- `write_attributed=true`;
- SHA/digest coerentes.

## Consequências

A cadeia crítica passa a ser:

1. V2.20 certificação;
2. V2.21 review;
3. V2.22 preflight lógico;
4. staging do binding V2.23;
5. persistência explícita futura;
6. read-after-write + receipt;
7. V2.23 attestation;
8. preparação da cerimônia de assinatura;
9. assinatura explícita do HUMAN_OWNER;
10. decisão explícita;
11. Core Freeze separado;
12. merge/deploy separados;
13. runtime activation separada.

Nenhuma etapa implica automaticamente a próxima.

## Segurança

V2.23:

- não usa rede;
- não salva;
- não assina;
- não decide;
- não congela;
- não mergeia;
- não deploya;
- não arma worker;
- rejeita branch de código como destino runtime;
- rejeita observação stale;
- rejeita conteúdo coincidente sem write attribution;
- rejeita SHA/digest divergentes.

## Compatibilidade

Compõe ADR-0002, ADR-0007, ADR-0009, ADR-0011, ADR-0012, ADR-0019, ADR-0020 e ADR-0021.

## Rollback/migração

O namespace V2.23 é aditivo. Runtime sem esse namespace permanece válido para operação
existente, mas não pode obter attestation V2.23.

## PR/commit relacionado

Branch `integration/aion-v223-external-checkpoint-persistence-attestation-20261004`.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
