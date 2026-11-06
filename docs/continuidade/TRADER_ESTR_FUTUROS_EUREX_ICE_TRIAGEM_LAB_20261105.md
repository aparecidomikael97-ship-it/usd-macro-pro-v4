# AtlasQuant Trader — triagem de futuros €STR (LAB, 05/11/2026)

**Escopo:** pesquisar expectativas de juros EUR utilizáveis em um estudo histórico
EUR/USD sem confundir fatos posteriores à decisão do BCE com previsões disponíveis
antes dela. Nenhum preço de mercado foi admitido como consenso; nenhum viés ou
operação foi habilitado.

## Evidência primária dos instrumentos

1. **Eurex Three-Month Euro STR Futures (FST3)**:
   <https://www.eurex.com/ex-en/markets/int/mon/3m-euro-str-futures/estr/Three-Month-Euro-STR-Futures-3402480>.
   O subjacente é a taxa €STR **composta por três meses**. A cotação do contrato
   é `100 - taxa negociada`, não uma previsão direta da taxa de depósito do BCE
   para uma reunião específica. O ajuste diário de vencimento corrente depende
   de operações perto das 17h15 CET, com regra própria para vencimentos seguintes.
   O instante efetivo de *publicação* do arquivo histórico não foi comprovado.
2. **Eurex estatísticas gratuitas e dados pagos**:
   <https://www.eurex.com/ex-en/data/statistics/trading-statistics> e
   <https://www.eurex.com/ex-en/data/trading-files>.
   O site diferencia `market statistics (online)` grátis de `market statistics
   (offline)` com tarifa. Grátis para acesso não significa licença comercial
   de uso de preços em produtos, nem prova de disponibilidade em cada data passada.
3. **ICE One/Three Month ESTR Futures**:
   <https://www.ice.com/products/37650328/One-Month-ESTR-Index-Futures> e
   <https://www.ice.com/report-center>.
   A ICE possui contratos de €STR e relatórios de ajuste; contudo, seu
   <https://www.ice.com/publicdocs/data/ICE_Report_Center_Click_Through_Agreement.pdf>
   exige aprovação prévia para criar produto baseado no conteúdo e proíbe
   disponibilizar dados a terceiros sem consentimento escrito. Os relatórios
   também são rotulados como preços não oficiais naquele documento. **Não houve
   aceite do portal, extração de cotação ICE ou contratação.**

## Captura exploratória real: Eurex Daily Statistics

- Arquivo público específico do dia **29/10/2026** (`dailystat_20261029.xls`):
  <https://www.eurex.com/resource/blob/5673476/043952812908322d6714be9f3d15aef3/data/dailystat_20261029.xls>.
- Baixado **manualmente em 05/11/2026 no AM12**, preservado em
  `C:\Users\apare\AtlasQuant_Trader_G8_LAB_20261104\evidence\eurex_daily_stats_20261029_research_only.xls`.
- Tamanho: **1.093.632 bytes**; SHA-256:
  `9f1599b6b32915091ea79cf0c5562b1c4deb917b6f081b9c1920e2e8485842ef`.
- Aberto **somente para leitura** via Excel instalado no AM12; abas `Cover`
  e `Eurex Daily Statistics`, esta última com 3.479 linhas e 19 colunas.
- Identificada linha **3351**, produto `Three-Month Euro STR Futures`, código
  `FST3`; linha 3358 refere opções `OST3`.
- Cabeçalho da linha **11** identifica *traded contracts*, suas acumulações,
  *open interest* anterior e volumes em EUR, **sem coluna de preço de ajuste,
  último negócio ou cotação**. Nenhum número dessa planilha deve ser convertido
  em taxa implícita ou previsão de juros.
- A data de negociação 29/10 **não prova** que o relatório estava disponível
  antes do anúncio do BCE daquele mesmo dia. Como a captura é posterior,
  ela também **não constitui vintage histórica autenticada**.
- O arquivo bruto fica somente no AM12. Este repositório contém unicamente
  metadados mínimos, o código de recusa e testes com bytes sintéticos.

## Decisões de engenharia

| Tipo de evidência | Bloqueio obrigatório | Por quê |
| --- | --- | --- |
| Eurex Daily Statistics/FST3 | `FST3_VOLUME_AND_OPEN_INTEREST_NOT_PRICE` | Não há preço na planilha examinada |
| Hipotético ajuste Eurex/FST3 | `ESTR_FUTURES_ACCRUAL_NOT_SINGLE_MEETING_DFR_CONSENSUS` | Taxa composta trimestral ≠ expectativa da DFR em reunião específica |
| ICE Report Center/€STR | `ICE_MARKET_DATA_PRODUCT_PERMISSION_NOT_VERIFIED` | Uso de dados em produto depende de autorização |

O módulo `atlasquant_trader_eurusd_consensus_pit_lab.py` aplica ainda os gates
temporais anteriores: documento divulgado após o evento ou no próprio dia,
sem testemunho do horário do anúncio, não passa. Os campos de preço histórico,
vencimento/acumulação do futuro, licença e disponibilidade pré-evento permanecem
sem comprovação. `pre_event_consensus_verified=false`, `fx_bias=null`,
`operational_bias=AGUARDAR`, `trade_authorized=false`.

## Próximo marco de investigação, sem custos

1. Buscar fonte **licitamente reutilizável** de ajustes históricos por contrato
   e vencimento, com hora de publicação atestável e licenciamento claro.
2. Testar o enquadramento de cada contrato à janela exata de acumulação €STR,
   verificando quais reuniões BCE ocorrem nela. Não assumir que taxa implícita
   de um vencimento equivale à surpresa de um evento.
3. Validar arquivo independente de anúncio/evento, versão do consenso antes
   dele e preços EUR/USD históricos independentes com timestamp. Sem isso,
   nenhum backtest direcional é admitido.

**HARD NO-GO:** sem merge, deploy, Worker, compra de dados, cobrança, ordens,
publicação ou ativação do Radar. PR #1815 permanece DRAFT; #1816 preservada.
