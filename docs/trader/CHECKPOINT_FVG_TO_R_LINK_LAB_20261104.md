# AtlasQuant Trader — FVG → replay R causal (LAB, 04/11/2026)

**PR de pesquisa:** #1814, sem merge/deploy. **HARD NO-GO** para operações,
Worker, núcleo AION, integrações com corretoras e novas cobranças.

## Problema resolvido em contrato offline

O replay M15 já exigia `signal_bar_index` e horário de confirmação, mas não
conseguia demonstrar se uma anotação de FVG realmente existia naquela vela.
`atlasquant_m15_fvg_r_link_lab.py` vincula duas peças existentes:

1. Lê somente o **prefixo histórico até o sinal** e usa o detector FVG
   experimental para verificar a formação exatamente ao fechar a terceira vela.
2. Exige índice causal exato, candles `complete=true` e OHLC históricos M15.
3. Deriva lado do cenário da geometria (`BULLISH→BUY`, `BEARISH→SELL`). Não
   aceita lado informado nem sinalização de autenticação por quem envia dados.
4. Exige filtros explícitos de FVG e um **plano de risco fornecido** (stop,
   alvo, spread e slippage hipotéticos), sem calcular entradas ou stops ideais.
5. Passa a série completa ao replay somente para conhecer o desfecho
   histórico hipotético a partir da **próxima abertura M15**. A parte futura
   **não participa** da seleção ou da formação do FVG.

## Interpretação correta

`fvg_formation_geometry_verified=true` significa apenas que aquela regra
geométrica sintética existe antes da entrada simulada. **Não** é uma
confirmação de força cambial, tendência, probabilidade, qualidade de execução,
resultado ao vivo nem assertividade do setup. Sempre mantém falsos:

- `source_authenticated`, `signal_causal_verified`, `trend_verified`;
- `spread_slippage_verified`, `setup_accuracy_verified`;
- `profitability_verified`, `publishable`, `trade_authorized`.

O contexto semanal/diário (viés), Order Blocks, notícias, spread de mercado e
sessões ainda não foram validados como filtros de entrada. O vínculo testa
apenas **FVG causal → custo hipotético → resultado histórico em R**. A
presença de um resultado TARGET não autoriza trade nem constitui estimativa
de lucro futuro.

## Testes e próximos portões

`python -m unittest -q test_atlasquant_m15_fvg_r_link_lab.py` verifica
formações de alta/baixa, prefixos imutáveis diante de velas futuras,
invalidação de índice inadequado, stop-primeiro em candle ambíguo,
campos sensíveis e flags impostoras, barras inválidas e planos de risco.

Após a bateria remota: somente avaliar backtests retrospectivos com dados
obtidos legalmente, viés W1/D1, métricas separadas por par/sessão e validação
fora da amostra. **Nenhuma fonte de preço nova foi ativada.**
