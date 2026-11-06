# AtlasQuant Trader — leitor CSV nativo do MT5 M15 (LAB, 05/11/2026)

## Estado e decisão

O AM12 está online. Foi verificada a presença do executável `C:\Program Files\MetaTrader 5\terminal64.exe`, mas o terminal **não foi iniciado**. A biblioteca Python `MetaTrader5` não está instalada, e nenhuma exportação de preços EURUSD M15 foi encontrada nas pastas do LAB examinadas. Não houve contato com corretora, autenticação em conta, ordens ou downloads de mercado.

Já existe o contrato `atlasquant_trader_fx_m15_offline_price_window_lab.py` para *JSON sintético estilo copy_rates_range*, que **não** corresponde diretamente à exportação de Barras em CSV do terminal. O novo módulo `atlasquant_trader_mt5_m15_bars_csv_lab.py` recebe uma exportação de barras **CSV ou TSV**, com as nove colunas:

`<DATE> <TIME> <OPEN> <HIGH> <LOW> <CLOSE> <TICKVOL> <VOL> <SPREAD>`

Aceita separador por tabulação ou vírgula, datas `YYYY.MM.DD`, horas `HH:MM:SS` alinhadas a múltiplos de 15 minutos, preços decimais textuais, OHLC consistente e contadores inteiros. Exige símbolo declarado canônico dos 28 pares e período declarado M15. Rejeita intervalos fora da grade, duplicações, ordenação invertida, preços inválidos, volume impossível, cabeçalho trocado, codificação inválida ou arquivos superiores a 8 MB. Registra tamanho, hash SHA-256, quantidade, primeira/última barra **no horário do servidor**, quantidade de lacunas dentro da mesma data e barras com spread reportado zero.

**Não converte hora do servidor da corretora para UTC automaticamente**. O CSV sozinho não estabelece fuso, ajustes de horário de verão, identidade do broker, lado bid/ask, latência, spread real executável, direito de redistribuição ou vintage histórico anterior ao movimento. Portanto o leitor retorna `broker_server_timezone=UNKNOWN_UNATTESTED`, `usable_for_directional_backtest=false`, `fx_bias=null` e `operational_bias=AGUARDAR`; nenhum sinal é publicado.

## Como obter um arquivo M15 sem pagar

O procedimento documentado oficialmente pelo MetaTrader 5 é **Observação do Mercado → Símbolos → Barras (Bars) → selecionar o instrumento e o período → Pedir/Request → Exportar/Export**. A plataforma só fornece o histórico permitido pela corretora e pelo limite de barras da configuração. A ação pode consultar o servidor da corretora; não foi executada por esta revisão.

Documentação oficial: https://www.metatrader5.com/pt/terminal/help/trading/market_watch e formato de barras https://www.metatrader5.com/pt/terminal/help/trading_advanced/custom_instruments.

Após exportar o CSV do **EURUSD, M15**, guarde-o fora da pasta do aplicativo. Para analisar o arquivo sem modificá-lo, em um terminal PowerShell com Python 3.12:

```powershell
python atlasquant_trader_mt5_m15_bars_csv_lab.py --csv-file "C:\CAMINHO\PARA\EURUSD_M15.csv" --declared-symbol EURUSD
```

O script imprime somente resumo estrutural e recusas; retorna código de saída 2 se rejeitado. Ele **não inicia MetaTrader, não faz requisição HTTP, não abre conta, não envia operações e não grava alterações**. Apenas lê o arquivo indicado. Não mover dados de conta nem arquivos sensíveis para o GitHub.

## Validações

Na pasta isolada do AM12 `AtlasQuant_Trader_G8_LAB_20261104\evidence\verificacao_mt5_m15_csv_20261105`, o leitor e seus testes foram executados em 05/11/2026 com Python 3.12: **22 testes passaram**, com CSV simulados, sem preço de mercado real. Os testes incluem 28 símbolos, variação de separador, horários, barras repetidas, buracos, OHLC inválido, UTF-16, arquivo ausente e comando CLI somente leitura.

## Integração futura

1. Receber uma exportação M15 de dados reais e confirmar **o fuso de horário do servidor** e a convenção de fechamento de 17h de Nova York (e horário de verão).
2. Registrar URL/provedor, horário de coleta, hash original e direitos de uso; não extrapolar arquivos de hoje para provar disponibilidade histórica antes das decisões.
3. Cruzar M15 com os registros ex-ante D1/W1 e dados macro disponíveis no instante real; medir taxa de acerto fora de amostra com denominador explícito, abstenções, custo e intervalos de confiança.

**HARD NO-GO:** sem compra, merge, deploy, alterações à interface #1816, sinal negociável, Worker/Scheduler ou operação real. PR #1815 permanece isolada.
