# AtlasQuant Trader — fatos BoE e NFP de 05–06/11/2026 (LAB)

## Contexto documental confirmado em páginas oficiais

1. **Banco da Inglaterra / GBP:** na página publicada em 05/11/2026, o MPC informou **Bank Rate de 4,00%**, após elevação de **0,25 ponto percentual** (portanto 3,75% antes). Fonte: https://www.bankofengland.co.uk/monetary-policy-summary-and-minutes/2026/november-2026 . A página fornece a **data** da publicação, mas o instante UTC original não foi atestado nesta pesquisa. O relógio do LAB só considera a divulgação cronologicamente anterior a partir de **06/11 00:00 UTC**, regra conservadora que não equivale a provar recebimento histórico nesse horário.
2. **BLS / USD:** o comunicado arquivado para o relatório de empregos de **outubro/2026** tem embargo até **06/11/2026 08:30 ET = 13:30 UTC** (EST). Informa acréscimo de **165 mil empregos não agrícolas** e desemprego de **4,1%**. Fonte: https://www.bls.gov/news.release/archives/empsit_11062026.htm . Esse relógio é a indicação de embargo na página, **não** um recibo independente de download no horário.

O arquivo `TRADER_G8_NOV6_POST_RELEASE_EVENTOS_LAB_20261106.json` preserva **transcrições manuais** desses fatos, sem fingir que recebeu HTML original ou que conhece o instante exato de disseminação. Não deve ser reaproveitado como vintage pré-evento do NFP, da decisão do BoE ou do CPI de 10/11.

## O que a nova verificação faz

`atlasquant_trader_g8_nov6_events_lab.py` valida o livro de casos contra valores, URL, período econômico, tipo de indicador e datas pré-fixadas. Não aceita modificar o NFP de 165 mil para outro número, fabricar consenso, adiantar o horário ou substituir a URL e manter o mesmo schema de evidência.

O relógio *as-of* é **simulação da cronologia permitida**, não prova que a página original foi realmente observada naquele instante. Antes de 06/11 00:00 UTC, nenhum dos dois eventos entra na cobertura documental. Entre 00:00 e 13:29:59 UTC, apenas GBP entra. Desde 13:30 UTC, GBP e USD entram, mas sempre com `historical_source_capture_time_independently_attested=false`.

Com os dois eventos após a divulgação, entre os **28 pares G8**:

| Cobertura desse recorte documental (não cobertura macro total) | Quantidade |
|---|---:|
| Dois lados com fatos publicados (somente GBP/USD) | 1 |
| Apenas um lado (pares com GBP ou USD, exceto GBP/USD) | 12 |
| Nenhum dos lados nesses dois eventos | 15 |

**Dois lados documentados NÃO significam duas surpresas comparáveis:** o evento GBP é política monetária e o evento USD é emprego. Falta comprovação independente de expectativas precificadas **antes** de cada evento, preços de reação, metodologia comparável e causalidade. Variação da taxa anunciada (0,25 pp) não deve ser denominada *surpresa*; um NFP positivo de 165 mil não informa se ficou acima ou abaixo do consenso.

As 28 linhas permanecem `D1=AGUARDAR`, `W1=AGUARDAR`, `fx_bias=null`, `market_surprise=null`, `validated_accuracy=null`, `trade_authorized=false`. Não há atualização de mercado em tempo real ou alteração do ranking da interface.

## Próximo passo para comparação fundamental de verdade

Continuar a verificação de expectativas pré-evento **publicamente disponíveis no horário correto** e de fontes G8 dos demais fatores. Quando houver consenso *antes* do release, seria possível calcular diferença realizada menos esperada **somente com mesmo indicador, período, unidade e ajuste**. Mesmo isso ainda não autoriza o sinal: a transmissão para câmbio depende da reprecificação relativa de política monetária, dos preços, do risco e de teste prospectivo OOS.

**DRAFT/HARD NO-GO:** sem merge, deploy, cron, Worker, execução, compra de fonte ou publicação. O estudo é somente documental e não altera a coorte de 56 vagas sem previsão.
