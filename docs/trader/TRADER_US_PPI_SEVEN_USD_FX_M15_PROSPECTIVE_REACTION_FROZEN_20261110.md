# AtlasQuant Trader — coorte prospectiva de reação ao PPI nos 7 pares USD — congelada ANTES da divulgação

**Data:** 10/11/2026 à noite em Mato Grosso (11/11 UTC). **LAB / NÃO É sinal / NÃO É previsão validada / nenhum acesso à corretora feito pelo módulo**.

## Objetivo concreto

O AtlasQuant Trader deve avaliar se a informação macro **realizada − consenso capturado antes do evento** tem relação verificável com o comportamento posterior dos preços. Isso não pode ser inferido sem medir a resposta real. Para o PPI EUA de outubro/2026 de **13/11/2026, 13h30 UTC (9h30 MT / 8h30 ET)**, congelamos **antes do evento** a metodologia **de observação**, em vez de escolher pares e janelas depois de ver os resultados.

**Grupo fixo, 7 pares com USD:** EURUSD, GBPUSD, AUDUSD, NZDUSD, USDJPY, USDCHF, USDCAD. Os outros 21 cruzamentos G8 não são tratados como sete oportunidades independentes nem automaticamente afetados por essa notícia. XAUUSD, índices EUA, WIN/WDO exigem estudos distintos. O script Flow PRO v1.1 permanece preservado e fora de escopo.

**Tempo de referência e janelas de estudo, UTC:**
- Antes da divulgação: **preço de fechamento da vela M15 aberta às 13h15 e encerrada às 13h30 UTC**. Esse fechamento é apenas uma referência retrospectiva, não entrada executável nem prova de preço disponível no exato microssegundo da divulgação.
- **15 minutos após o evento:** vela M15 que fecha às **13h45 UTC**.
- **1 hora após:** vela M15 que fecha às **14h30 UTC**.
- **4 horas após:** vela M15 que fecha às **17h30 UTC**.
- Exigir **17 velas consecutivas de 15 minutos por par**: 13h15, 13h30, ... 17h15 UTC de abertura. Se faltar um arquivo, vela, hora, volume positivo ou integridade hash, não há classificação consolidada.
- **Sem janela de 24 horas**: a notícia ocorre numa sexta-feira, e +24h cai no sábado com Forex normalmente fechado. Não extrapolar retorno atravessando o fim de semana.

**Orientação USD rigorosa:** para USDJPY, USDCHF e USDCAD, usar mudança de preço na direção direta do dólar (P final / P anterior - 1); para EURUSD, GBPUSD, AUDUSD e NZDUSD, inverter a razão (P anterior / P final - 1) para medir a **valorização matemática do USD relativamente à outra moeda**. Resultados expostos em bps, sem confundir movimentos spot com lucro executável. Não atribuir probabilidade ou direção futura a um evento isolado.

## Evidência pré-evento já preservada no AM12

- Consenso **TD Economics** (10/11 20h58 MT): headline PPI MoM **0,4%**, núcleo sem alimentos e energia **0,3%**, HTML SHA256 `5f9d9eb128e5a3763ec6a3081bee7ba8c248a665a9d50e0ee132e9cbe037a42a`.
- Consenso **Trading Economics** (10/11 21h15 MT): headline PPI MoM **0,4%**, núcleo **0,3%**, HTML SHA256 `175c163514590db8e2ddd651f0c9865bd2eed298211f92072549233f670e23c0`. **Forecast próprio** do provedor (headline 0,3%) não substitui consenso.
- Relatórios originais: `docs/trader/TRADER_US_PPI_20261113_TWO_PRE_EVENT_PUBLISHERS_AM12_20261110.md` e `docs/trader/TRADER_US_PPI_20261113_ACTUAL_TABLE_FIRST_PRINT_GUARD_READY_20261110.md`.
- O módulo de PPI realizado está pronto mas **nenhum realizado foi observado até o checkpoint**. O calendário BLS confirma o evento futuro.
- No AM12, o MT5 Pepperstone foi verificado como **processo terminal64 aberto**, mas **MetaTrader5 não está instalado no Python 3.12**. Nenhum pacote foi instalado, nenhuma ligação Python à corretora foi feita e nenhuma ordem/conta foi acessada.
- O arquivo local antigo `%LOCALAPPDATA%/AtlasQuant/LAB/MT5_Snapshots/20261107_AM12` contém **28 arquivos M15** (um por par), porém o último candle do manifesto examinado é **06/11/2026 23h30 UTC**, e a captura foi registrada em 08/11 UTC. **Esses arquivos NÃO contêm o evento do dia 13/11**. Não reutilizar como se o PPI futuro tivesse sido capturado.

## Coorte congelada no AM12

Em `C:\Users\apare\Documents\AtlasQuant\Trader\PPI_US_20261113_PRE_EVENT_LAB\`:

- `AM12_PPI_USD_FX_SEVEN_PAIR_PRE_EVENT_COHORT_FROZEN_20261110.json` criado via arquivo novo exclusivo (`xb`), **sem sobrescrever versão anterior**.
- Horário UTC reportado pelo relógio local no instante do freeze: **2026-11-11T01:47:50.369208+00:00**.
- SHA256 dos bytes da coorte: **`82c7c452f5ca76c813067dc66a2cdf0d513ac5d7991d6efedd0aad58b2245358`**.
- Coorte fixa 7 símbolos, 3 janelas, baseline e 17 candles por par, sem hashes futuros e sem previsões já preenchidas.
- Relógio local + hash **não certificam independentemente a captura**, mas o checkpoint GitHub também foi registrado antes do evento e preserva regras auditáveis.

## Entrega técnica e status

- `atlasquant_trader_ppi_usd_fx_forward_reaction_lab.py` e `test_atlasquant_trader_ppi_usd_fx_forward_reaction_lab.py` na PR em rascunho; código offline apenas.
- **21 testes sintéticos PASS** no ambiente de criação e **21 testes PASS no AM12/Python 3.12**, inclusive: ausência de arquivo, vela faltante, timestamp duplicado, OHLC inválido, hash alterado, preço malformado, spread/volume inválido, janela futura e seleção incompleta.
- Avaliação de **hoje**, antes de 13/11: `state=LAB_WAIT_PPI_FX_FORWARD_WINDOW` e `operational_bias=AGUARDAR`.
- A inclusão na CI `.github/workflows/atlasquant-trader-d1w1-offline-lab.yml` cobre Python 3.11/3.12. As fixtures são **sintéticas**, não preços de mercado.
- Os 7 pares reagem ao **mesmo evento econômico**: se completos, o estudo conta **um choque/evento**, não 7 previsões estatisticamente independentes.
- Sem bid/ask executável, slippage, causalidade controlada, amostra de muitos eventos, previsão congelada por par, probabilidade calibrada ou backtest fora da amostra: **nenhuma assertividade ou performance de trading** pode ser reivindicada.

## Próximos passos depois da divulgação

1. A conferência do consenso **12/11 às 19h MT** e a conferência do PPI realizado **13/11 às 11h MT** já estão agendadas; **não duplicar tarefas**.
2. Para medir os preços depois de **13/11 17h30 UTC (13h30 MT)**, coletar **novos** candles M15 dos sete símbolos, somente leitura, em arquivos CSV separados; os snapshots existentes de 07/11 são insuficientes.
3. Verificar horas UTC reais, integridade de todas as velas, condições de spread e horário de corretora; **não supor acesso à API MetaTrader5 porque o terminal gráfico está aberto**. Se instalação de biblioteca ou outra permissão for necessária, avisar antes; não operar nem tocar em credenciais.
4. Comparar a reação dos preços somente após existir o PPI oficial e a coorte completa. Reportar também períodos sem dados e qualidade de cobertura, jamais selecionar só pares que confirmam a hipótese.
5. Repetir prospectivamente muitos eventos antes de inferir efeito incremental sobre viés diário/semanal ou de comercializar qualquer probabilidade.

**Status:** GO-LAB sem custo novo. NO-GO sinais operacionais, implantação ou operação real. PR #1851 permanece em rascunho.
