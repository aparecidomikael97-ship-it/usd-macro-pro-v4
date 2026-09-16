# AtlasQuant — Backtest Operacional com TradingView

## Objetivo

Validar os operacionais do AtlasQuant com dados históricos sem inventar entrada,
stop ou alvo. O fluxo atual é offline e auditável: o usuário exporta OHLC do
TradingView e fornece uma planilha de sinais com níveis explícitos.

## Fluxo V1

1. No TradingView, exporte os candles do ativo/timeframe em CSV.
2. Na aba **Backtest** do AtlasQuant, envie o CSV de candles.
3. Envie a planilha de sinais/operacionais.
4. Rode o backtest.
5. Analise Gain, Loss, Break-even, Win Rate, resultado em R, expectativa,
   drawdown, sequências, setup e sessão.
6. Baixe o ledger completo em CSV para usar como planilha/diário.

Abrir a aba ou carregar o painel não faz chamadas a provedores.

## Colunas dos candles

O painel aceita os nomes do TradingView e aliases em português. O formato
canônico é:

\`datetime,open,high,low,close\`

## Colunas da planilha de sinais

Obrigatórias:

- \`signal_time\`
- \`side\` — BUY/SELL; também aceita COMPRA/VENDA e LONG/SHORT
- \`entry\`
- \`stop\`
- \`target\`

Opcionais/recomendadas:

- \`pair\`
- \`setup\`
- \`session\`
- \`source\`
- \`notes\`

O painel possui botões para baixar modelos vazios dos dois CSVs.

## Regras conservadoras do simulador

- Por padrão, a execução começa **depois** do candle do sinal, evitando
  look-ahead no candle que gerou a decisão.
- A entrada só existe se o OHLC tocar o preço de entrada dentro da janela
  configurada.
- BUY exige \`stop < entry < target\`.
- SELL exige \`target < entry < stop\`.
- Plano inválido vira \`NO_TRADE\`.
- Se stop e alvo forem tocados no mesmo candle OHLC, a ordem intrabar é
  desconhecida; por segurança o resultado é LOSS.
- Custos podem ser informados em R e são descontados do resultado.
- Após o limite de candles em posição, o simulador encerra pelo último close e
  marca \`TIME_EXIT\`.
- O motor registra MFE/MAE em R, barras de espera e barras em posição.

## Métricas e planilha

O resultado mostra e exporta:

- Trades
- Gain
- Loss
- Break-even
- No Trade
- Win Rate observado
- Resultado líquido em R
- Expectativa média em R
- Profit Factor
- Drawdown máximo em R
- Maior sequência de Gain
- Maior sequência de Loss
- Casos ambíguos de stop+alvo no mesmo candle
- Resultado por setup
- Resultado por sessão
- Ledger completo por operação

## TradingView e AtlasQuant

Esta primeira integração usa o TradingView como fonte de candles históricos e
visualização. Ela não afirma reproduzir automaticamente o contexto macro dentro
do Pine Script.

A etapa posterior será separar os operacionais que podem ser expressos de forma
100% objetiva em Pine Script e criar estratégias específicas para validação
visual no TradingView. Regras macro/institucionais que dependem do AtlasQuant
continuam sendo validadas pelo motor Python, a menos que exista uma forma
determinística de reproduzi-las no Pine.

## Estado de validação

O motor e o painel foram adicionados na branch \`atlasquant-dev\`. O checkpoint
de código testado que introduziu o painel é \`f7adc098249c09c3d544786a2f8a110bf5602d6b\`.

GitHub Actions Quality run \`35095699342\`:
**518 testes executados, 518 OK**, além do compile gate verde.

O Runtime não foi alterado por esta etapa.


## Modo automático — sem planilha de sinais

A aba Backtest também possui **Backtest automático — BOS/CHOCH + Order Block**.

Nesse modo:

1. envie apenas o CSV de candles exportado do TradingView;
2. informe o par/ativo;
3. escolha alvo em R, buffer do stop em ATR, entrada Midpoint/Proximal, eventos BOS/CHOCH e lados BUY/SELL;
4. o AtlasQuant faz replay candle a candle;
5. sinais só aparecem quando a estrutura está confirmada naquele ponto histórico;
6. o simulador começa a procurar a entrada depois do candle do sinal;
7. uma nova operação no mesmo par é bloqueada enquanto a anterior ainda estiver ativa;
8. baixe tanto a planilha de sinais gerados quanto o ledger final.

Esse replay é técnico. Ele não reconstrói automaticamente Fed, calendário macro ou força de moedas histórica.


## Operacional automático FVG

O FVG agora possui um replay e uma Pine Strategy independentes.

No AtlasQuant:

1. envie o CSV de candles;
2. abra **Backtest automático — FVG**;
3. configure alvo em R, buffer do stop em ATR, tamanho mínimo do gap em ATR e entrada Midpoint/Proximal;
4. escolha BUY, SELL ou ambos;
5. rode o backtest;
6. baixe os sinais FVG e o ledger separados.

Regra do replay:

- bullish FVG: o low do terceiro candle está acima do high de dois candles atrás;
- bearish FVG: o high do terceiro candle está abaixo do low de dois candles atrás;
- o sinal só existe depois que o terceiro candle está disponível;
- a execução do backtest começa depois do candle do sinal.

O arquivo \`tradingview/atlasquant_fvg_strategy_v1.pine\` serve para pesquisa visual no
Strategy Tester. A estatística FVG é mantida separada da estratégia BOS/CHOCH + Order Block.


## Paridade TradingView ↔ Python

A tela de Backtest possui um bloco de verificação de paridade estática.

Ele compara parâmetros e regras-chave das Pine Strategies com os replays Python para reduzir
drift acidental durante o desenvolvimento. Se um parâmetro central mudar de um lado e não do
outro, o Quality workflow deve falhar.

A verificação não substitui a compilação do Pine no TradingView e não promete equivalência
perfeita com o broker emulator. Diferenças de timezone, sessão e tick size ainda precisam ser
observadas durante validação no gráfico.


## Operacional automático OTE 62%-79%

O OTE possui replay Python e Pine Strategy próprios, separados de FVG e BOS/CHOCH + Order Block.

No AtlasQuant:

1. envie o CSV de candles;
2. abra **Backtest automático — OTE 62–79%**;
3. configure alvo em R, buffer do stop em ATR e filtro de impulso mínimo/ATR;
4. escolha entrada no sweet spot 70,5% ou midpoint da zona;
5. escolha BUY, SELL ou ambos;
6. rode o backtest;
7. baixe os sinais OTE e o ledger separados.

Regra do replay:

- usa lookback de 28 candles;
- procura o extremo mais recente dentro dos últimos 12 candles;
- BUY ancora low anterior -> high recente;
- SELL ancora high anterior -> low recente;
- a zona OTE é 62%-79% da retração;
- o sweet spot é 70,5%;
- um mesmo impulso só pode gerar um sinal;
- se BUY e SELL coincidirem no mesmo candle, o candidato mais próximo do 70,5% é escolhido de forma determinística;
- a execução começa após o candle do sinal, preservando a proteção anti-look-ahead.

O arquivo `tradingview/atlasquant_ote_strategy_v1.pine` permite pesquisa visual no Strategy Tester.
A estatística OTE permanece independente das demais estratégias.


### Proteção contra reancoragem do OTE

Para reduzir sinais repetidos no mesmo movimento, o OTE usa uma regra de nova perna:

- após um BUY, outro BUY só pode usar uma nova origem low que comece depois do terminal high anterior;
- após um SELL, outro SELL só pode usar uma nova origem high que comece depois do terminal low anterior;
- apenas estender o mesmo high/low não cria um novo setup;
- um segundo impulso próximo é permitido quando há uma nova origem real depois do terminal anterior.

Essa regra é aplicada no replay Python e na Pine Strategy e faz parte do contrato de paridade.


## Operacional automático CRT

O CRT possui replay Python e Pine Strategy próprios, separados de OTE, FVG e BOS/CHOCH + Order Block.

No AtlasQuant:

1. envie o CSV de candles;
2. abra **Backtest automático — CRT**;
3. configure buffer do stop em ATR e, se desejar, RR mínimo;
4. escolha BUY, SELL ou ambos;
5. rode o backtest;
6. baixe os sinais CRT e o ledger separados.

Regra do replay:

- candle 1 define o anchor range;
- BUY: candle 2 varre o low do anchor e fecha de volta acima; candle 3 entrega para cima, fechando acima do candle 2 e do midpoint do anchor;
- SELL: candle 2 varre o high do anchor e fecha de volta abaixo; candle 3 entrega para baixo, fechando abaixo do candle 2 e do midpoint;
- entrada de pesquisa usa o fechamento do candle de delivery;
- stop usa o extremo da varredura/anchor, com buffer ATR opcional;
- alvo usa a borda oposta do anchor range;
- a execução começa após o candle de confirmação, preservando a proteção anti-look-ahead.

O arquivo `tradingview/atlasquant_crt_strategy_v1.pine` permite pesquisa visual no Strategy Tester.
A estatística CRT permanece independente dos demais operacionais.


## Operacional automático AMD / Power of Three

O AMD/PO3 possui replay Python e Pine Strategy próprios, separados de CRT, OTE, FVG e BOS/CHOCH + Order Block.

No AtlasQuant:

1. envie o CSV de candles;
2. abra **Backtest automático — AMD / Power of Three**;
3. configure candles da acumulação, janela máxima até distribuição, buffer do stop em ATR e RR mínimo;
4. escolha BUY, SELL ou ambos;
5. rode o backtest;
6. baixe os sinais AMD e o ledger separados.

Regra do replay:

- primeiro o sistema congela uma faixa de acumulação usando apenas candles anteriores;
- BUY manipulation: varre abaixo do range e fecha de volta acima;
- SELL manipulation: varre acima do range e fecha de volta abaixo;
- a distribuição só pode ocorrer em candle posterior à manipulação;
- BUY distribution precisa fechar acima do midpoint da acumulação e acima do fechamento da manipulação;
- SELL usa a regra espelhada;
- o estado de manipulação expira após a janela configurada;
- entrada de pesquisa usa o fechamento da distribuição;
- stop usa o extremo da manipulação com buffer ATR opcional;
- alvo usa a borda oposta da acumulação;
- se o mesmo candle varrer os dois lados, apenas o sweep proporcionalmente mais profundo é mantido.

O arquivo `tradingview/atlasquant_amd_strategy_v1.pine` permite pesquisa visual no Strategy Tester.
A estatística AMD/PO3 permanece independente dos demais operacionais.


## Comparador dos 5 operacionais

A aba Backtest possui um bloco **Comparador dos 5 operacionais**.

Com o mesmo CSV de candles, o AtlasQuant roda separadamente:

- BOS/CHOCH + Order Block;
- FVG;
- OTE;
- CRT;
- AMD / Power of Three.

O sistema não mistura os sinais entre estratégias. Cada setup mantém seus próprios trades e métricas.

A comparação mostra:

- número de sinais e trades;
- Gain / Loss / Break-even;
- Win Rate observado;
- expectativa em R;
- resultado líquido em R;
- Profit Factor;
- Drawdown máximo;
- maior sequência de Loss;
- tamanho da amostra;
- ranking de expectativa observada apenas para estratégias com amostra mínima.

Por padrão, o ranking exige pelo menos **20 trades**. Esse valor pode ser ajustado na tela.

O ranking é somente uma ordenação descritiva do histórico usado no teste. Ele não é previsão,
probabilidade de lucro ou autorização para operar.

Também é possível baixar:

- a tabela geral de comparação em CSV;
- um ledger combinado em CSV, com a estratégia de origem identificada em cada linha.

A próxima camada de validação recomendada é verificar estabilidade por períodos do histórico,
para evitar favorecer um setup que funcionou apenas em um trecho específico.
