# AION P0 — lacuna real de cobertura Quality (21/10/2026)

**LAB isolado; nenhuma mudança na `main`, no Writer, no Worker, no deploy, na autoridade ou no fornecedor. HARD NO-GO.**

## Evidência de origem

Workflow canônico do commit `6dfbc54767fcbf7fc785dd1ffe56ccab9805083c`, [execução #39586235179](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39586235179), falhou com **6.562 métodos, 52 FAIL e 34 ERROR**. A Security A74 passou separadamente. Os 86 resultados Quality NÃO são dispensados.

A análise dos cabeçalhos completos de FAIL/ERROR do job (não apenas do resumo) identificou:

| Causa aparente / módulo | FAIL | ERROR |
| --- | ---: | ---: |
| Global Worker (módulo principal) | 21 | 0 |
| Cerimônia de ativação Global Worker | 15 | 0 |
| Worker local | 6 | 0 |
| Live verification Global Worker | 5 | 0 |
| Readiness Global Worker | 2 | 0 |
| Activation coverage A76 | 1 | 0 |
| Pós-incidente / reativação | 1 | 2 |
| `test_quality_workflow_coverage` | 1 | 0 |
| Execution Outbox | 0 | 23 |
| Execution Saga | 0 | 9 |
| **Total** | **52** | **34** |

Os bloqueios em Outbox/Saga e Worker fazem muitos testes históricos esperar autorizações ou confirmações hoje negadas intencionalmente. **Não afrouxar a barreira `_confirm`, `dispatch_claimed`, A53 ou a homologação para obter verde.** Diagnosticar/migrar suítes antigas por contrato e manter contraprovas negativas.

## Defeito de cobertura inequívoco

`test_quality_workflow_coverage.py::test_every_root_test_file_is_executed_by_quality_workflow` apontou **26 arquivos raiz `test_*.py`** ausentes do comando `python -m unittest -q` em `.github/workflows/quality-tests.yml`. Isso significa que a Quality **não vinha cobrindo todo o conjunto de testes-raiz**, embora o código de verificação exigisse cobertura integral.

Esta branch acrescenta os 26 nomes exatos ao comando real da Quality (sem exclusão, `skip`, `xfail`, filtro de erro, nem alteração da asserção existente). Cada nome foi retirado diretamente do log de execução; nenhum cenário foi inventado.

Um workflow novo `aion-p0-quality-root-coverage-lab.yml` roda no HEAD isolado em Ubuntu/Windows:
- guard existente `test_quality_workflow_coverage.py` sem dispensa;
- os 26 módulos adicionados, efetivamente executados — não apenas listados.

**Aprovação é condicionada à CI final nos dois SO, SHA exato e logs.** Um PASS aqui valida a cobertura e os novos módulos, NÃO repara os 85 FAIL/ERROR restantes nem aprova H0, P0, Worker ou produção.

## Critério de continuidade

1. Conferir logs do workflow de laboratório no commit final para detectar falhas introduzidas pelo aumento da cobertura.
2. Reexecutar Quality canônica completa no HEAD após a mudança. O total de testes deve aumentar (se todos os arquivos rodarem); comparar FAIL/ERROR individuais e sua causa, sem confundir uma alteração de contagem com segurança corrigida.
3. Tratar a separação entre contratos legados de execução e o atual HARD NO-GO com revisão humana explícita, mantendo veto a qualquer primeiro envio, retry ou terminalização sem evidência externa confiável.
4. Nenhum merge/deploy/Worker/custo novo. P0 homologados **0/6**.

**Veredito: cobertura incompleta demonstrada e remediação candidata, ainda não homologada.**

## Resultado da primeira bateria de backfill e correção de causas (sem waiver)

A primeira matriz Ubuntu iniciou 333 testes dos 26 módulos e reportou **1 FAIL + 1 ERROR**. A auditoria de enumeração canônica separada passou (9 testes).

- `test_aion_p0_quality_lab_coverage_governance_lab::test_no_unclassified_root_test_file`: o próprio teste LAB anterior exigia que os 26 fossem classificados como **omitidos**. A revisão da política neste Draft agora exige **zero omitidos**, sem enfraquecer a cobertura, e mantém os 26 na matriz LAB dedicada.
- `test_aion_p0_original_six_evidence_matrix_lab::test_07_original_m71_reactivation_sources_pinned_a118`: necessita ler o blob de `c62fab663c6349d7320f7843c8d09587c514426b`; o objeto histórico existe no GitHub, mas o checkout superficial não o trazia. A mudança `fetch-depth: 0` é **somente leitura** e permite verificar o hash histórico, sem trocar o pin, eliminar o teste ou alegar confiança externa.

O novo commit também habilita **execução real da Quality completa nesta branch LAB**. Mesmo se a cobertura ficar verde, toda a lista prévia de 85 problemas de Worker/Outbox/Saga segue ativa até reexecução e análise por causa raiz; nenhuma condição de operação está liberada.
