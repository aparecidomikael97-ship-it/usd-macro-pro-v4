# ADR-0019 — Core Certification é separada de Core Freeze

- Título: Core Certification é separada de Core Freeze
- Data: 2026-10-04
- Status: ACCEPTED

## Contexto

O AION Core passou por uma sequência de hardening estrutural até V2.19. O proprietário
determinou que o núcleo deve ser finalizado por completo, sem congelamento prematuro.

## Problema

Um CI verde ou uma bateria de testes bem-sucedida pode ser confundida com autorização
para congelar, mergear, fazer deploy ou ativar execução.

Também seria frágil declarar o núcleo completo sem evidência explícita de load, chaos,
recovery, concurrency, cost, isolation e audit replay.

## Alternativas consideradas

Foram rejeitados:
- freeze automático após CI verde;
- freeze automático após 6/6 gates;
- certificado baseado em booleano único;
- certificação sem binding ao commit exato;
- certificação sem load/chaos/recovery;
- certificação que arma worker;
- certificação que autoriza merge/deploy.

## Decisão

V2.20 cria um Core Certification contract e um workflow dedicado.

O estado positivo máximo produzido automaticamente é
`CERTIFICATION_CANDIDATE`.

A certificação exige evidência ligada ao commit para trust, durable execution,
isolation, resilience, multi-agent/memory, Constitution, provider independence,
E2E, load, chaos, recovery, backup/restore, concurrency, cost e audit replay.

Core Freeze permanece uma decisão separada e explícita do HUMAN_OWNER.

## Consequências

O AION pode ser completamente testado e certificado sem ativar produção.

O histórico preserva a diferença entre:
- código implementado;
- CI verde;
- certificação candidata;
- freeze autorizado;
- runtime ativado.

## Componentes afetados

Todo AION Core, CI, Checkpoint Mestre, Worker Readiness, Release process, ADR registry,
future deployment and execution ceremony.

## Segurança

- certification is not authority;
- certification does not arm worker;
- certification does not merge/deploy;
- certification cannot freeze the Core;
- evidence must bind to exact target commit;
- missing evidence blocks;
- caller boolean alone cannot certify a dimension;
- all real-world execution remains outside certification.

## Compatibilidade

Compõe V2.13–V2.19 e as suites anteriores sem alterar seus contratos.

## Rollback/migração

Alterar critérios de certificação ou permitir freeze automático exige ADR sucessor e
nova certificação.

## PR/commit relacionado

Branch `integration/aion-v220-core-certification-20261004`.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
