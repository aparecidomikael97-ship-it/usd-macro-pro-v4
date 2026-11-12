# AtlasQuant Trader — guarda CPI mensal prévia × definitivo (LAB)

Data local de referência: 09/11/2026 (America/Cuiaba). Estado: investigação, sem viés ou operação.

## Falha detectada

O validador estrutural `atlasquant_trader_g8_macro_asof_lab.py` aceitava `observation_period=2026-10` com `published_at_utc=2026-10-01` para CPI mensal. O carimbo de captura podia estar antes da decisão e ainda assim a leitura representar uma suposta inflação *definitiva* de um mês sequer concluído.

Esse é um risco real de mistura de **prévia / flash** com **resultado final**. O Eurostat informa que publica uma estimativa *flash* perto do fim do mês de referência e divulga dados finais do mês anterior por volta da metade do mês seguinte. Fonte primária: https://ec.europa.eu/eurostat/web/hicp/information-data (seção *Data release*). O calendário do BLS dos EUA explicita, separadamente, mês de referência, data e hora da publicação: https://www.bls.gov/schedule/news_release/cpi.htm.

## Proteção implementada

- No esquema atual `CPI_YOY` mensal, o mês de referência deve ser **anterior** ao mês da alegada publicação. Assim, os lançamentos com referência no mesmo mês, inclusive no último dia, são recusados até existir um tipo de evento `FLASH`/`FINAL`, um emissor específico e uma fonte temporal comprovável.
- Esse veto é **conservador**: pode bloquear uma prévia genuína do Eurostat. Não é uma afirmação de que todo CPI necessariamente espere o mês seguinte; é uma limitação intencional do esquema atual, que ainda não distingue prévias e finais.
- Uma taxa de política monetária continua podendo ter período de referência igual ao mês da decisão (não é CPI de um mês completo).
- CPI trimestral mantém a regra anterior de trimestre completo; testes bilaterais de 28 pares e demais validadores continuam compatíveis.
- Um recibo com mês passado aceito estruturalmente **não** prova que aquela publicação existiu na hora alegada, que seus valores são os originais nem que a fonte é autêntica.

## Testes

- Casos adicionais: `CPI_YOY` do próprio mês recusado antes da conclusão e no último dia; CPI do mês anterior e juros do mês corrente continuam estruturalmente aceitos sem liberação de viés.
- Execução local: `python -m unittest -q test_atlasquant_trader_g8_macro_asof_lab test_atlasquant_trader_g8_macro_matrix_pit_lab test_atlasquant_trader_g8_event_relevance_lab test_atlasquant_trader_g8_issuer_custody_chain_lab` — **87/87 PASS** em dados sintéticos.
- Nenhum teste foi executado no AM12, MT5 ou pelo GitHub Actions nesta rodada. Nenhum dado econômico real foi autenticado ou usado em decisão.

## Próxima exigência P0

Adicionar procedência e tipagem por documento oficial (`FLASH`, `FINAL`, `REVISION`), a primeira divulgação com hora/fuso verificado, histórico de revisões, e prova *point-in-time* imutável. Até então: `AGUARDAR`, sem publicar radar, executar ordem, merge, deploy, worker, cobrança ou agendamento.
