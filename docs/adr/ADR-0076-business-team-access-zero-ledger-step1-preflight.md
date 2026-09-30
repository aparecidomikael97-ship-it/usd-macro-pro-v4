# ADR-0076 — Business Team Access Zero-Ledger Step 1 Preflight Package

- Status: ACCEPTED
- Data: 2026-09-30
- Escopo: AtlasQuant / AION Business / Equipe & Acessos

## Contexto

Após o lifecycle plan materializado e o Authorization Package válido, ainda não
deve existir execução automática do primeiro step.

Antes de qualquer decisão manual do Step 1 é necessário congelar:

- authorization package íntegro;
- materialization digest;
- empty ledger;
- genesis chain;
- baseline digest observado novamente;
- saúde do sandbox;
- OIDC;
- schema do registry;
- localização segura de secrets;
- ausência de target de produção;
- caminho de cleanup;
- observação recente.

## Decisão

Adicionar um pacote read-only específico para o Step 1.

O pacote:

1. revalida o materialization packet;
2. revalida o Authorization Package;
3. cria um ledger com zero receipts;
4. exige chain head igual ao GENESIS digest;
5. exige Step 1 como next expected;
6. exige observação read-only com no máximo 900 segundos;
7. chama o Step Gate somente quando todos os gates anteriores passam;
8. produz um packet digest para revisão;
9. permite recalcular esse digest antes de qualquer decisão futura.

## Observação Windows

Get-TeamAccessStep1ReadinessObservation.ps1 executa apenas:

- Docker status;
- OIDC discovery GET;
- PostgreSQL schema SELECT;
- verificações locais de path/compose/cleanup.

O script não inicia containers e não executa mutações de lifecycle.

## Estado máximo

READY_FOR_EXPLICIT_MANUAL_SANDBOX_STEP_1_DECISION_PACKET

Esse estado não registra a decisão do Step 1.

## Segurança

Mesmo no estado máximo:

- manual_decision_recorded = false;
- step_execution_authorized = false;
- automatic_execution_authorized = false;
- automatic_ledger_append = false;
- executor_enabled = false;
- production/deploy/runtime = false.

Se qualquer requisito anterior falhar, o Step Gate interno não é avaliado e não
é emitido token de decisão.

## Compatibilidade

Complementa ADR-0069, ADR-0070, ADR-0074 e ADR-0075.
