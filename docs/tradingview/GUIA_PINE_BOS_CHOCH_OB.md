# TradingView — AtlasQuant BOS/CHOCH + Order Block Research V1

Este script Pine é uma ponte de pesquisa técnica para o TradingView. Ele serve para visualizar e testar a parte objetiva BOS/CHOCH + Order Block.

## O que ele faz

- usa pivôs confirmados;
- detecta BOS e CHOCH por fechamento além do swing confirmado;
- aplica tolerância por ATR para reduzir rompimentos marginais;
- evita reutilizar o mesmo swing;
- procura o candle oposto mais recente dentro da perna estrutural atual;
- exige displacement mínimo relativo ao ATR;
- cria uma zona de Order Block;
- permite entrada no midpoint ou na borda proximal;
- usa stop além da borda oposta com buffer de ATR;
- alvo configurável em R;
- possui filtro de sessão e filtro Long/Short;
- usa strategy() para aparecer no Strategy Tester.

## Limites importantes

O script não reproduz a macro do AtlasQuant. Fed, inflação, emprego, força de moedas, eventos e Safety Core continuam no motor Python.
Por isso, resultado do Strategy Tester é pesquisa do operacional técnico, não validação do sistema completo.

O script não usa request.security, não usa lookahead e não consulta dados futuros. Os pivôs só são usados depois de confirmados pelo número de candles à direita configurado.

## Entrada e risco

- Order Block BUY: último candle bearish válido da perna atual;
- Order Block SELL: último candle bullish válido da perna atual;
- entrada: midpoint da zona por padrão;
- stop: além da borda oposta + buffer em ATR;
- alvo: múltiplo de R configurável, padrão 2R.

Esses parâmetros são hipóteses de pesquisa. Eles não são promovidos automaticamente para o Gate do AtlasQuant.

## Como usar

1. Abra o Pine Editor do TradingView.
2. Cole o conteúdo do arquivo atlasquant_bos_choch_ob_strategy_v1.pine.
3. Clique em Add to chart / Adicionar ao gráfico.
4. Abra Strategy Tester.
5. Teste vários pares, sessões e períodos.
6. Compare os resultados com o backtest Python/CSV do AtlasQuant.
7. Não altere pesos do sistema principal com amostra pequena.

## Próximas estratégias

Depois desta base, os próximos candidatos objetivos são FVG, OTE, CRT e combinações de confluência. Cada estratégia deve manter sua própria estatística antes de ser considerada para influência maior no Gate.
