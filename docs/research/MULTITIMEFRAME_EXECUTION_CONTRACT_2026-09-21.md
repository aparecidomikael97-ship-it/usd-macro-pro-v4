# Contrato de execução multitimeframe do AtlasQuant

## Objetivo

Separar **detecção de setup** de **entrada válida**. Um operacional pode aparecer em qualquer timeframe suportado, mas isso não autoriza uma entrada de Backtest/Paper.

Timeframes de pesquisa: **M15, M30, H1, H4, D1 e W1**.

## Regra obrigatória de entrada

Uma entrada só pode ser contada como execução quando, no instante do sinal, os quatro blocos abaixo estiverem confirmados:

1. **Leitura/contexto alinhado** — o cenário que dá sentido ao operacional está coerente com o timeframe e o contexto superior.
2. **Direcionamento alinhado** — o lado BUY/SELL do setup não contradiz o direcionamento usado pela leitura.
3. **Filtros alinhados** — filtros de qualidade, risco, dados, evento, liquidez e demais filtros aplicáveis estão liberados.
4. **Gatilho alinhado** — o gatilho objetivo do operacional foi confirmado no timeframe de execução.

Se qualquer bloco estiver falso, a entrada é bloqueada. Se a evidência estiver ausente no modo estrito, a entrada também é bloqueada.

## Contexto por timeframe

- M15: contexto H1/H4.
- M30: contexto H1/H4.
- H1: contexto H4/D1.
- H4: contexto D1/W1.
- D1: contexto W1.
- W1: leitura e gatilho próprios do W1, com contexto de posição preservado.

Esse mapa define a hierarquia de contexto; não transforma sozinho uma leitura em entrada.

## Backtest

O Backtest preserva timeframe e trading_style em cada sinal e resultado. O histórico point-in-time pode conter contexto genérico do par e contexto específico do timeframe. O específico tem prioridade, e snapshot futuro nunca é usado.

No modo de execução alinhada, sinais sem os quatro blocos obrigatórios recebem ALIGNMENT_BLOCKED e não entram em Gain/Loss/Win Rate.

## Paper / Forward Test

O Paper deve usar candle do **mesmo timeframe de execução**. Um candidato H1 não pode ser preenchido/fechado com M15 só porque M15 está disponível.

Enquanto o executor Paper de determinado timeframe ainda não existir, o candidato fica BLOCKED_TIMEFRAME. Isso é preferível a criar uma estatística falsa.

## Segurança

Este contrato é de pesquisa e validação. Ele não habilita corretora, ordens reais, promoção automática de estratégia, mudança automática de Gate ou promessa de resultado futuro.
