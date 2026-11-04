# AtlasQuant Trader — piloto de previsão PRÉ-CPI (Cleveland Fed), LAB 02/11/2026

## Primeiro dado prospectivo real pesquisado

A página oficial do **Federal Reserve Bank of Cleveland** exibe **nowcasts** (estimativas de modelo) para inflação mensal e anual. Na consulta documental de **02/11/2026**, a linha **outubro/2026** informava:

| Medida | Nowcast de outubro | Unidade |
| --- | ---: | --- |
| CPI geral (mês) | **0,24%** | mês a mês, sazonalmente ajustado (SA) |
| CPI núcleo (mês) | **0,21%** | mês a mês, SA |
| CPI geral (12 meses) | **3,74%** | ano a ano, não ajustado sazonalmente (NSA) |
| CPI núcleo (12 meses) | **2,48%** | ano a ano, NSA |

A própria página indicava **“Updated 11/02”**. É uma página **dinâmica**; esses números podem ser recalculados. Esta pesquisa **não** possui recibo imutável de captura, screenshot autenticada, horário de publicação independente ou direito de redistribuição confirmado. Logo, **não** é vintage histórica garantida nem ponto de partida válido para backtest antes do fim do dia de pesquisa.

Fontes:
- Cleveland Fed: https://www.clevelandfed.org/indicators-and-data/inflation-nowcasting
- BLS CPI schedule: https://www.bls.gov/schedule/news_release/cpi.htm
- Fed Research sobre política monetária **relativa** e câmbio: https://www.federalreserve.gov/econres/notes/feds-notes/monetary-policy-and-exchange-rates-during-the-global-tightening-20240510.html

O **CPI efetivo de outubro** está programado para **10/11/2026 às 08h30 Eastern Standard Time = 13h30 UTC**. O nowcast é **modelo pré-evento**, nunca o resultado oficial e **nunca** o consenso do mercado.

## Regras de comparação

O módulo `atlasquant_trader_us_cpi_cleveland_nowcast_lab.py` é somente leitura e não faz HTTP.

1. Protege o registro documental com `research_day_utc=2026-11-02`; antes de **03/11 00:00 UTC**, não permite sequer reapresentá-lo como dados conhecidos naquele instante.
2. Apresenta os quatro números como `LAB_PRE_EVENT_NOWCAST_MODEL_ONLY` se o **consenso público pré-divulgação** está ausente.
3. Permite teste com **consenso sintético explicitamente rotulado**, de mesma referência e unidade (CPI e núcleo, m/m SA). Calcula `modelo - consenso` em pontos percentuais; não compara 3,74% a/a NSA com 0,24% m/m SA.
4. Proíbe recibo depois do horário da hipótese, valores NaN, unidade errada, `actual` antes da divulgação e alegações de fonte ou benchmark autenticado.
5. Quando o horário da notícia passar sem publicação nova, responde `LAB_CPI_CALENDAR_PAST_DUE_REQUIRES_NEW_ACTUAL`; **não** converte nowcast em realizado.

## O que isso poderia significar (hipóteses condicionais)

**Cenário A — expectativa de inflação dos EUA mais alta que a do mercado.** Se o nowcast *relevante e corretamente comparado* estiver acima de um **consenso verdadeiro registrado antes da notícia**, isso sugere risco de surpresa inflacionária acima desse consenso. Mas não equivale ao CPI que sairá, nem automaticamente valoriza o USD. Precisamos examinar composição (núcleo/energia), como a curva de juros e o Fed reagiriam, BCE, dólar como refúgio e geopolítica. Um índice como NAS100 pode reagir em direção oposta ao USD — e não de forma constante.

**Cenário B — expectativa abaixo do consenso.** Sinaliza risco de surpresa baixista sob as mesmas ressalvas; em regime de desaceleração forte, juros menores podem não sustentar os índices. Ainda não atribuir seta.

**Cenário C — consenso não comprovado (estado atual).** Apresentar o nowcast e o próximo evento, mas **AGUARDAR** para EUR/USD, D1/W1/MN1 e índices. Taxa Fed de 3,75–4,00% e depósito BCE de 2,50% em documentos de outubro **não bastam** para inferir direção.

O objetivo de antecipação é verificar **diferenças de expectativas e mudança prospectiva de juros**, condicionadas ao regime. Estudos do Fed mostram importância de **surpresas relativas** de política; isso não valida qualquer coeficiente de acerto do AtlasQuant ou 90% de precisão.

## O que ainda falta

- Fonte de **consenso de mercado** com licença e carimbo pré-divulgação confiável para o CPI específico.
- Arquivo de **nowcasts diariamente versionados e custodiados** antes de cada lançamento, com possíveis revisões.
- CPI realizado com versão original, hora real de publicação, revisão, e histórico independente de preço dos 28 FX e dos índices.
- Regras de transmissão FX/índices por regime, ex-ante, validadas em walk-forward OOS.

**LAB / DRAFT / HARD NO-GO**: `directional_bias=AGUARDAR`, `probability_calibrated=null`, `accuracy_90_proven=false`, `market_consensus_verified=false`, `can_feed_live_radar=false`. Sem Worker, cron, APIs pagas, merge, deploy, operação ou alteração visual.
