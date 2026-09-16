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


## Estabilidade temporal dos 5 operacionais

Depois de rodar o comparador, o AtlasQuant também pode dividir o histórico de cada estratégia
em blocos cronológicos para verificar se o resultado observado foi consistente ao longo da
amostra.

Você pode escolher:

- 3 blocos;
- 4 blocos;
- 5 blocos.

Também pode definir o mínimo de trades exigido em cada bloco.

Para cada operacional e bloco, são mostrados:

- Trades;
- Gain / Loss / Break-even;
- Win Rate observado;
- Expectativa em R;
- Resultado líquido em R;
- Drawdown máximo;
- Maior sequência de Loss.

O resumo temporal usa quatro estados descritivos:

- **POSITIVE_ACROSS_FOLDS** — expectativa positiva em todos os blocos;
- **NEGATIVE_ACROSS_FOLDS** — expectativa negativa em todos os blocos;
- **MIXED_ACROSS_FOLDS** — o sinal da expectativa muda entre os blocos;
- **INSUFFICIENT** — não há amostra mínima suficiente em todos os blocos.

Isso ajuda a enxergar quando um setup ficou positivo apenas em uma parte do histórico.
O diagnóstico é histórico e descritivo; ele não é previsão, probabilidade de lucro ou
autorização para operar.

A tabela detalhada dos blocos também pode ser baixada em CSV.


## Walk-forward — treino anterior × teste futuro

Depois do comparador e da estabilidade temporal, o AtlasQuant também pode executar um
diagnóstico walk-forward dos cinco operacionais.

O fluxo é cronológico:

1. uma parte inicial do histórico vira treino;
2. o bloco seguinte vira teste OOS;
3. depois o treino é expandido para incluir o que já passou;
4. o próximo bloco futuro vira novo teste;
5. as regras dos operacionais permanecem iguais durante todo o processo.

Não existe otimização automática nessa etapa.

Na tela é possível escolher:

- treino inicial de 50%, 60% ou 70%;
- 2, 3 ou 4 janelas OOS;
- mínimo de trades exigido no treino;
- mínimo de trades exigido em cada teste.

Para cada janela são mostrados:

- trades de treino e teste;
- expectativa em R de treino e teste;
- diferença entre expectativa de teste e treino;
- net R;
- win rate;
- drawdown do teste;
- maior sequência de Loss do teste.

O resumo usa quatro estados descritivos:

- **POSITIVE_ALL_OOS_WINDOWS** — expectativa OOS positiva em todas as janelas válidas;
- **NEGATIVE_ALL_OOS_WINDOWS** — expectativa OOS negativa em todas;
- **MIXED_OOS_WINDOWS** — comportamento OOS misto;
- **INSUFFICIENT** — amostra mínima não atendida.

A tabela detalhada pode ser baixada em CSV.

Esse walk-forward é apenas uma validação histórica fora da amostra. Ele não é previsão,
probabilidade de lucro ou autorização de operação e não altera automaticamente parâmetros,
pesos ou o Gate do AtlasQuant.


## Custos e slippage em R

O Backtest agora permite informar separadamente:

- **Custos totais por trade (R)**;
- **Slippage adverso por trade (R)**.

A conta usada no resultado histórico é:

`Net R = Gross R - Custos R - Slippage R`.

Exemplo:

- trade bruto: +2,00R;
- custo: 0,05R;
- slippage: 0,03R;
- resultado líquido: +1,92R.

Valores negativos de custo/slippage são rejeitados.

### Sensibilidade a custos e slippage

No **Comparador dos 5 operacionais**, o AtlasQuant também pode reprecificar os mesmos trades
sob diferentes níveis de atrito.

O teste sempre mantém iguais:

- sinais;
- entradas;
- stops;
- alvos;
- candles usados;
- horários de entrada/saída.

Somente o drag em R é alterado.

A tabela mostra, por setup e cenário:

- custo;
- slippage;
- fricção total;
- trades;
- Gain/Loss/BE;
- expectativa em R;
- Net R;
- Profit Factor;
- Drawdown.

O resumo usa estados descritivos:

- **POSITIVE_ALL_TESTED_FRICTION** — expectativa positiva em todos os níveis testados;
- **BREAKS_UNDER_TESTED_FRICTION** — expectativa positiva sem/baixo atrito, mas não positiva em algum stress;
- **NONPOSITIVE_BASELINE** — expectativa já não positiva no cenário sem fricção;
- **INSUFFICIENT** — amostra mínima não atendida.

Também é mostrado o primeiro nível testado de fricção em que a expectativa deixa de ser positiva.

Importante: o slippage desta etapa é modelado como um **drag fixo em R por trade**. Não é uma
simulação tick a tick de preenchimento de ordens. O objetivo é testar sensibilidade do histórico,
não reproduzir perfeitamente microestrutura de execução.

A tabela detalhada pode ser baixada em CSV.


## Stress por sessão/par e robustez de parâmetros

### Custos/slippage por sessão e par

Além do resumo geral, o AtlasQuant agora pode mostrar o efeito da fricção separado por:

- sessão;
- par/ativo;
- operacional;
- cenário de custo/slippage.

Isso ajuda a enxergar, por exemplo, quando a mesma estratégia perde expectativa sob atrito em
uma sessão específica.

A tabela segmentada também pode ser baixada em CSV.

### Robustez de parâmetros pré-definidos

Existe uma auditoria opcional chamada **Robustez de parâmetros pré-definidos**.

Ela usa uma grade pequena e fixa:

- BOS/CHOCH + OB: alvo 1,5R / 2,0R / 2,5R;
- FVG: gap mínimo 0 / 0,10 / 0,20 ATR;
- OTE: Sweet 70,5 / midpoint da zona / filtro de impulso 0,50 ATR;
- CRT: RR mínimo 0 / 0,50 / 1,00;
- AMD / Power of Three: acumulação 6 / 8 / 10 candles.

A grade não é criada depois de olhar os resultados. Ela está definida previamente no código.

Para cada variante são mostrados:

- sinais;
- trades;
- Gain / Loss / Break-even;
- Win Rate observado;
- expectativa em R;
- Net R;
- Profit Factor;
- Drawdown;
- maior sequência de Loss.

O resumo por operacional mostra a expectativa da variante base, pior/melhor expectativa,
spread entre variantes e se todas possuem amostra mínima.

Estados descritivos:

- **POSITIVE_ALL_PREDEFINED_VARIANTS**;
- **NEGATIVE_ALL_PREDEFINED_VARIANTS**;
- **MIXED_PREDEFINED_VARIANTS**;
- **INSUFFICIENT**.

O AtlasQuant **não escolhe automaticamente a melhor variante** e não usa esse resultado para
mudar o Gate, os pesos ou o operacional ao vivo.

Como essa auditoria executa 15 replays, ela fica desativada por padrão. Ative somente quando
quiser fazer a análise de robustez do histórico atual.


## Relatório consolidado de evidências

Depois de executar o **Comparador dos 5 operacionais**, o AtlasQuant reúne os principais
diagnósticos em uma única tabela.

Para cada operacional, a tela mostra:

- Trades;
- Win Rate observado;
- Expectativa em R;
- Net R;
- Drawdown máximo;
- tamanho da amostra;
- estabilidade temporal;
- walk-forward OOS;
- sensibilidade a custos/slippage;
- robustez de parâmetros, quando ativada;
- cobertura dos diagnósticos disponíveis.

### Cobertura não é nota

A coluna de cobertura informa somente se os diagnósticos tiveram amostra suficiente:

- **COMPLETE** — todos disponíveis;
- **PARTIAL** — parte disponível;
- **INSUFFICIENT** — sem amostra válida suficiente.

Ela não significa “setup bom” ou “setup ruim”.

Quando a auditoria de robustez de parâmetros não foi ativada, ela aparece como **NOT_RUN**.

### Exportações

O relatório pode ser baixado em dois formatos:

- **JSON** — pacote auditável com configurações, resumo e dados detalhados;
- **Markdown** — resumo em texto para leitura rápida e arquivamento.

O JSON usa o schema `ATLASQUANT_BACKTEST_EVIDENCE_V1` e marca explicitamente que o
conteúdo é pesquisa histórica, não altera o Gate e não representa probabilidade de lucro.

Use esse relatório para revisar as evidências do histórico em conjunto. Ele não escolhe
automaticamente um operacional e não modifica os parâmetros do sistema.


## Snapshot reproduzível do Backtest

Depois de gerar o relatório consolidado, o AtlasQuant pode salvar um **snapshot reproduzível** da execução.

O snapshot guarda fingerprints SHA-256 separados para:

- arquivo CSV original;
- candles normalizados;
- configurações do teste;
- código usado no Backtest;
- evidências geradas.

O arquivo usa o schema `ATLASQUANT_BACKTEST_SNAPSHOT_V1`.

O `snapshot_id` depende do conteúdo do teste. Se CSV normalizado, configurações, código e
evidências forem iguais, o mesmo teste gera o mesmo identificador.

### Comparar duas execuções

Abra **Comparar dois snapshots salvos** e envie:

1. o snapshot anterior;
2. o snapshot posterior.

O AtlasQuant informa separadamente se mudou:

- CSV bruto;
- dados normalizados;
- configuração;
- código;
- evidências.

Se houver mudanças de configuração, a tabela mostra o valor anterior e o valor novo.

Se as evidências mudarem, a comparação mostra deltas descritivos de:

- quantidade de trades;
- expectativa em R;
- Net R;
- Drawdown máximo.

Esses deltas não recebem interpretação automática de melhora ou piora.

### Por que isso é útil

Esse recurso ajuda a descobrir se duas execuções produziram resultados diferentes porque:

- o histórico mudou;
- o CSV foi alterado;
- algum parâmetro mudou;
- o código foi atualizado;
- ou apenas as evidências finais mudaram.

O diff também pode ser exportado em JSON para auditoria.
