# AtlasQuant Trader — checkpoint experimental FVG M15 (04/11/2026)

**Estado:** LAB isolado; **HARD NO-GO** para operação real, merge, publicação e núcleo AION.

## Escopo

`atlasquant_m15_fvg_causal_lab.py` inspeciona uma série **offline**, validada,
de candles OHLC M15 completos de um par canônico G8. Não aceita autenticação,
não abre conexão com corretora e não gera ordens ou recomendações.

## Regra de formação testável, não calibrada

- **FVG de alta:** mínima do 3º candle > máxima do 1º; candle do meio tem corpo de alta.
  Zona entre máxima do 1º e mínima do 3º.
- **FVG de baixa:** máxima do 3º candle < mínima do 1º; candle do meio tem corpo de baixa.
  Zona entre máxima do 3º e mínima do 1º.
- Exige candles **consecutivos** com intervalo exato de 15 minutos. Não confunde
  lacunas entre sessões com FVG.
- Filtros configuráveis, ainda **experimentais**: `minimum_gap_points`,
  `point_size` e `middle_body_min_fraction`; nenhum deles é calibrado.
- A zona **nasce ao fechamento do terceiro candle**. A vela de formação não
  pode mitigar a zona que acabou de formar. Velas futuras não alteram limites
  nem a data de formação de uma zona existente.

## Ciclo de vida

1. `ACTIVE`: criada no fechamento da terceira vela.
2. `TOUCHED`: candle posterior entrou na faixa da zona.
3. `FULLY_FILLED`: candle posterior percorreu o limite mais distante.
4. `INVALIDATED_CLOSE`: fechamento posterior atravessou o limite mais distante.

Cada mudança registra `observed_at`. `FULLY_FILLED` e `INVALIDATED_CLOSE` não
voltam a `ACTIVE` ou `TOUCHED`. `INVALIDATED_CLOSE` é terminal. Esses rótulos
descrevem apenas a geometria histórica, sem supor que seria possível executar
uma operação naquele preço.

## Guardas e limite de interpretação

- Rejeita candles incompletos, futuros, fora da ordem, duplicados, OHLC inválido,
  filtros incorretos, par não canônico, contrato errado e campos sensíveis.
- Sempre mantém `source_authenticated=false`, `trend_verified=false`,
  `setup_accuracy_verified=false`, `profitability_verified=false`,
  `publishable=false`, `trade_authorized=false`.
- Não relaciona diretamente a força diária BCE às entradas M15. Referências
  derivadas do BCE **não** substituem candles bid/ask negociáveis.
- Integração opcional com o replay de risco R da revisão #1814 depende de uma
  etapa posterior com anotações causais verificadas, dados de mercado reais
  e um protocolo de backtest fora de amostra. Nenhuma precisão de trade está
  demonstrada por esses testes sintéticos.

## Evidência esperada antes de ampliar o escopo

Executar `python -m unittest -q test_atlasquant_m15_fvg_causal_lab.py` junto
da suite Quality, verificar todas as verificações do PR, auditar casos com
gaps de sessão, múltiplos FVGs simultâneos, filtros para JPY e dispersão,
e somente depois considerar uma fonte de preços de mercado licenciada.
