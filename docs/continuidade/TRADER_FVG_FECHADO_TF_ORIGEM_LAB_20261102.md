# AtlasQuant Trader — FVG com candles fechados e TF de origem (LAB)

02/11/2026 · PR #1803 DRAFT · HARD NO-GO. Sem fonte real e sem tela alterada.

## Objetivo

Aprofundar **somente a pesquisa estrutural do FVG**, mantendo o script
ICT/SMC do TradingView independente e o Radar aprovado intocado.

`atlasquant_trader_fvg_closed_tf_lab.py` aceita **apenas candles
sintéticos** declarados `LAB_SYNTHETIC_OHLC_ONLY` de um par G8.
Exige três sequências distintas, uma para cada timeframe M15, H1 e H4,
com OHLC decimal válido, fuso UTC, barras consecutivas e comprovadamente
encerradas antes da avaliação declarada. Não mistura H4 com M15.
Se o estudo H4 tiver apenas uma barra, informa
`INSUFFICIENT_HISTORY` — **não inventa FVG H4**.

## Definição de pesquisa (não calibrada)

Para três candles FECHADOS consecutivos no **mesmo timeframe**:
- FVG estrutural de alta: `low` do terceiro acima do `high` do primeiro.
- FVG estrutural de baixa: `high` do terceiro abaixo do `low` do primeiro.
- Largura mínima = **2 pontos-base** do limite inferior (limiar
  experimental, sem otimização ou prova de assertividade).
- O registro nasce **somente no fechamento do terceiro candle**:
  `formed_after_utc` guarda esse instante e nunca o retrocede.
- Candles posteriores no mesmo TF atualizam a situação:
  `UNTESTED`, `TOUCHED` ou `FULLY_FILLED`. O estado posterior
  não é usado para declarar a região conhecida antes de nascer.
- Cada região guarda `timeframe`, limites inferior/superior,
  direção, largura, instante de formação e instante da revisão.

O método não define Order Block, BOS, CHoCH, liquidez, tendência
ou entrada operacional. Uma geometria FVG, isolada, **não é
setup validado**, suporte/resistência comprovado nem previsão.
Nenhuma precisão/recall ou taxa de lucro foi demonstrada.

## Recusas e testes

Não aceita livro com estado `VALIDATED`, dados reais, símbolo fora
dos 28, hora sem timezone, H1/M15/H4 misturados, candles futuros,
incompletos, com lacuna, repetidos, OHLC invertido ou preço NaN.
As séries sintéticas podem passar, mas `verified_market_zones=0`,
`live_bias=null`, `live_radar=null`, `trade_signal=null`,
`can_feed_live_radar=false`, `can_feed_real_oos=false`,
`trade_authorized=false`, `worker_enabled=false`,
`scheduler_enabled=false` permanecem invariáveis.

`test_atlasquant_trader_fvg_closed_tf_lab.py` fornece **16 testes
sintéticos**: alta/baixa, M15 e H1 isolados, H4 insuficiente,
H4 com três barras completas, toque posterior, preenchimento,
limiar mínimo, falha de relógio/estrutura/tempo e ausência
de autorização. Integrado à suíte Quality do GitHub.

## Próximo portão

Com fonte legalmente utilizável e 28 pares, estudar critérios
independentes de qualidade das zonas (sessão, volatilidade,
distância do preço, mitigação e contexto D1/H4/M15) e medir
OOS por ativo/timeframe. Não substituir o Pine Script aprovado
sem validação visual separada e autorização do proprietário.

**Sem merge, deploy, Worker AION, ordens, corretora, dados comprados,
API paga, cron ou alteração da interface aprovada.**
