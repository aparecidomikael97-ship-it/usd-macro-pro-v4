# AION — Reconciliação da cobertura Quality e inventário RED da composição

Data de auditoria: 2026-10-11 UTC

**NÃO É ACEITE FINAL. NÃO MERGEAR, NÃO DEPLOYAR, NÃO INSTALAR.**

## Proveniência da árvore isolada

- Fonte UI/Owner #1203 (GREEN isolado): `6637638283b39a8cc751da32b9f95347b7560d66`
- Fonte Source/Worker privada #1191 (Worker operacional BLOCKED): `7d4af5e45b8e80ca43e65171d28255510b76b3b1`
- Composição CI da Draft #1204: `97fe31a7d18a260dfc20ad204478c969d43dcb5f`
- Este conjunto de correções é um **ramo filho isolado da #1204**, com nenhuma mudança na `main`, no Core V1 congelado ou nas Drafts originais.

## Falha determinística fechada nesta etapa: 17 testes raiz omitidos do Quality

O CI original da #1204 falhou no teste `test_quality_workflow_coverage.py::test_every_root_test_file_is_executed_by_quality_workflow`. Identificou exatamente **17** arquivos `test_*.py` acrescentados pela cadeia de segurança, mas ausentes da lista explícita do workflow `.github/workflows/quality-tests.yml`.

Nesta branch, os **17 módulos foram ADICIONADOS à execução global** `python -m unittest -q ...`, sem exclusão/skip/xfail, sem mudar nenhuma expectativa e sem esconder resultado. Inspeção estática da árvore: **569 arquivos `test_*.py` da raiz e 0 não listados**. Testes em `tests/` são controlados separadamente, não estão incluídos na contagem dos 569.

CI exclusiva desta correção `.github/workflows/aion-composite-quality-negative-coverage.yml` roda o próprio contrato de cobertura e os 17 módulos íntegros em Windows e Linux, com checkout no HEAD exato e sem GitHub write credentials. Também atesta que `independent_worker_source_preflight` CONTINUA `BLOCKED` para requerente que afirme `owner_verified` ou `worker_authorized`.

**Importante:** Adicionar os testes à suíte pode revelar outras falhas reais. Nesse caso, o resultado deve continuar vermelho; a correção aqui é de cobertura e NÃO promete Quality geral verde.

## Inventário exato das outras falhas da composição #1204 (não alteradas aqui)

Quality [run 38098161999](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/38098161999) mostrou 6.172 testes, **25 FAIL + 3 ERROR**, distribuídos por 11 módulos:

| Família de testes | Qtde FAIL | Qtde ERROR | Contrato/cenário a revisar |
| --- | ---: | ---: | --- |
| `test_autopilot_v107` | 7 | 0 | Shadow/Flight e retry de GitHub sob novo fence e outcome UNKNOWN; não reabrir writer/retry |
| `test_atlasquant_setup_journal` | 3 | 0 | leituras CSV/ledger dependentes de antiga fonte runtime; preservar SOURCE_UNBOUND |
| `test_atlasquant_shadow_store` | 6 | 0 | remoto de shadow, duplicate/conflict/404, novas negações e ausência de GET |
| `test_atlasquant_shadow_persistence` | 2 | 0 | persistência Shadow e código de erro, esperado HARD_DENIED hoje |
| `test_calendar` | 0 | 2 | loader de notícias runtime: erro real a classificar pelo traceback |
| `test_atlasquant_voice_profile` | 1 | 1 | voz neural paga bloqueada sem FinOps/trust; não executar provider pago |
| `test_atlasquant_aion_global_worker_activation` | 2 | 0 | fixture de readiness/write antiga espera PASS/WRITE_ACCEPTED, atual BLOCKED |
| `test_atlasquant_access_panel` | 1 | 0 | expectativa estática de gate AUTH em interface após containment privado |
| `test_atlasquant_admin_event_foundation` | 1 | 0 | expectativa estática de painel de histórico pós-containment |
| `test_atlasquant_research_intelligence_foundation` | 1 | 0 | razão UNSAFE_BRANCH antiga versus HARD_DENIED atual |
| `test_quality_workflow_coverage` | 1 | 0 | **escopo resolvido neste patch: 17 módulos omitidos, adicionados** |

A classificação acima é **triagem por famílias** e logs, não prova de que cada falha é teste obsoleto. Antes de resolver qualquer uma é necessário: confirmar fluxo de dados, efeitos, valores de falha, razões de erro; criar teste negativo para bloqueio e, onde válido, teste positivo em fixture isolada **sem alterar política produtiva**. Não trocar `BLOCKED` por `PASS` e não aplicar `skip` aos testes antigos. Fixes futuros devem ser separados por família, com evidência antes/depois e aprovação dentro dos limites.

Além dessas falhas:
- [Global Worker Activation Readiness run 38098161799](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/38098161799): `BLOCKED` por source trust indisponível e pulsos ausentes, **falha operacional correta que deve permanecer**.
- [Browser Request Reconciliation run 38098161724](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/38098161724): 155 testes, falhou apenas no mesmo contrato de cobertura omitida em Windows e Linux no HEAD original #1204. Esta correção é a primeira etapa, rerun obrigatório.
- [AtlasQuant Reference UI run 38098162119](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/38098162119): falhas de asserts de contrato antigo de Autopilot/Access UI, **não considerar regressão resolvida**.

## Bloqueios de liberação inalterados

- Sem matrícula real HUMAN_OWNER/collector, membership real tenant/workspace, source pin e witness independentes, geração monotônica, antirollback físico, Windows AppContainer, chaves de signatário e pacote nativo assinado.
- `main`, frozen Core V1 e estados do Worker não alterados; `no secret read`, `no deploy`, `no production write`, `no auto retry of UNKNOWN`, `no spend`, `no first install`.

**Estado do projeto:** COMPOSITE INTEGRATION RED; FIRST INSTALL HARD NO-GO.