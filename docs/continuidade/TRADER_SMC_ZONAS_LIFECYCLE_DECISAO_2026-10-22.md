# AtlasQuant Trader — SMC Master v0.3: ciclo de vida de zonas e visual limpo
**Decisão do proprietário de 22/10/2026, após capturas do TradingView.** Complementa T58 do Checkpoint LAB em PR Draft #1473. **Sem merge/deploy/Worker/broker.**

## Regra de apresentação confirmada
- BOS/CHOCH/MSS: manter só os **3 últimos eventos** por padrão, configurável; nunca marcar todos os candles históricos.
- Order Blocks e FVGs: manter **somente as zonas recentes ainda válidas**, com destaque visual mais forte; limite inicial **2 OB ativos + 2 FVG ativos**, independente de direção. Limites são visuais, não prova de que uma zona antiga deixou de ser válida.
- Quando o preço **mitiga**, permitir **desaparecer** ou **esmaecer** para cor bem clara; por padrão apenas **1 zona mitigada de cada tipo** continua visível, e a projeção dela é encerrada no candle de mitigação.
- Mitigação ≠ invalidação. Nesta versão LAB, invalidação de zona bullish é fechamento abaixo da base; bearish, fechamento acima do topo; zona invalidada é removida. Primeiro toque/enchimento completo são opções configuráveis e não definem verdade institucional absoluta.
- Defaults propostos: OB = primeiro toque; FVG = preenchimento completo; mitigados = esmaecer; 150 candles de prazo máximo dos objetos ativos; sweeps desligados; D1 HTF desligado.
- MSS do protótipo é classificação heurística de reversão estrutural com candle de deslocamento, não implementação homologada da metodologia.
- CRT e AMD continuam no **segundo Pine separado** e com estudos D1; não fazem parte da limpeza OB/FVG.

## Status real
Artefato LAB local criado nesta sessão: **AtlasQuant_Indicadores_LAB_v03.zip** (SMC Pine v0.3, ICT Pine v0.2 inalterado, README), SHA256 `67a1383db18a8c84c8c87b5d1c43c8249d4dc733fae2594123a13d08f30f0afe`. ZIP validado por integridade e verificação estática limitada. **Não foi compilado no TradingView nem submetido a backtest/forward ou homologação**. Não inventar equivalência com LuxAlgo.
A manutenção futura deve portar o código Pine para versão controlada no repositório e revisar visual/semântica por screenshots de M15/H2/D1 em múltiplos pares.
P0 homologados = 0/6; HARD NO-GO para operações do núcleo; os scripts são apenas experimentos de leitura gráfica, sem ordens reais.