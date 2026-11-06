# AtlasQuant Trader — gráfico MT5 branco/laranja e primeira exportação M15 real, AM12 (LAB, 05/11/2026)

## Configuração do MetaTrader 5 realizada diretamente no AM12

O MetaTrader 5 já estava aberto em **uma conta de demonstração**. Foram configurados e verificados visualmente os dois gráficos abertos, mantendo seus períodos: **EURUSD M15** e **USDJPY M5**.

- Fundo **White** (#FFFFFF).
- Barra de alta **Black**, portanto pavio e contorno da vela de alta em preto.
- Barra de baixa **Black**, portanto pavio e contorno da vela de baixa em preto.
- Corpo de alta **White**.
- Corpo de baixa **DarkOrange** (#FF8C00, RGB 255/140/0).
- Demais configurações dos gráficos não foram uniformizadas nem o período foi alterado. Em especial, o USDJPY manteve a grade branca que já possuía, e o EURUSD manteve a grade prata.
- O modelo **AtlasQuant_Branco_Laranja.tpl** foi salvo sem sobrescrever modelos existentes em um diretório de dados MetaQuotes do perfil ativo, com **2.754 bytes**. Não foi aplicado automaticamente a outros gráficos, pois templates podem incluir outras configurações e indicadores.
- Apareceu um aviso de atualização do terminal. Foi selecionado **Depois**, sem autorizar instalação, reinicialização planejada ou compra. Nenhuma ordem foi enviada e o botão AlgoTrading não foi ativado.

## Teste real da exportação de barras M15

Na janela `Ativos -> Barras` do MetaTrader, foi escolhido **EURUSD, M15**.

1. A solicitação de **02 a 05/11/2026** retornou **0 barras** na sessão disponível. Não se pode supor que preços atualizados de novembro estejam carregados no terminal.
2. A solicitação de **16 a 18/04/2026** retornou **116 barras** (dados locais/fornecidos pelo terminal de demonstração). O primeiro horário do arquivo foi `2026.04.16 00:00:00` e o último `2026.04.17 04:45:00`, **horário do servidor não atestado**.
3. O CSV original foi exportado, sem sobrescrever dados anteriores, para `evidence/verificacao_mt5_m15_csv_20261105/EURUSD_M15_MT5_20260416_20260417.csv` no AM12. Tamanho **7.168 bytes**, SHA-256 **`7396f21a77d5290075eeb8b43e3c79c89a31aca0798afdc5144fe0ac60ad9676`**.
4. O leitor somente leitura `atlasquant_trader_mt5_m15_bars_csv_lab.py`, criado e testado anteriormente em PR #1815, analisou esse arquivo com **código de saída zero** e estado **`LAB_MT5_M15_CSV_STRUCTURE_VALID_SERVER_CLOCK_UNATTESTED`**.
5. O leitor registrou **116 linhas M15**, OHLC coerentes, **0 lacunas internas dentro da mesma data**, **0 registros de fim de semana** e **47 linhas com spread declarado zero**. Esses valores de spread exigem revisão da origem/preço bid-ask; não devem ser usados como custo real zero.

## O que o teste comprova e o que ainda não comprova

Os candles foram exportados pelo terminal de demonstração em funcionamento no AM12 e a estrutura do CSV passou no leitor offline. Essa é uma **prova prática do caminho de exportação e ingestão**, não da origem independente, qualidade comercial, carimbo histórico ou execução a preço disponível ao investidor.

O arquivo não se sobrepõe ao histórico BCE que obtivemos em **agosto a novembro**. Não há previsões ex-ante registradas para esses candles de abril. O terminal mostrou **0/0 KB** de transferência no canto inferior no momento da auditoria; a sessão de dados recentes precisa de checagem, sem tentar autenticar ou negociar em nome do usuário.

Permanecem `broker_server_timezone=UNKNOWN_UNATTESTED`, `bid_ask_price_side_verified=false`, `usable_for_directional_backtest=false`, `operational_bias=AGUARDAR`, `trade_authorized=false`, `historical_predictive_accuracy=null`.

**Próximo passo:** validar a conexão de dados do MT5 (somente leitura, sem senhas fornecidas ao chat), obter barras M15 de período que coincida com os dados oficiais BCE, conhecer o fuso do servidor e registrar os vieses D1/W1 **antes** do movimento para avaliação futura fora de amostra.

**HARD NO-GO:** sem Worker, Scheduler, operações, merge, deploy, cobrança, edição do app em produção ou alteração da PR #1816. Não enviar CSV bruto, screenshot com informações de conta ou detalhes pessoais ao GitHub.
