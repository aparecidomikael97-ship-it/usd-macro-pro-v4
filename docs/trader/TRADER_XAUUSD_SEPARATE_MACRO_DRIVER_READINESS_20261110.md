# AtlasQuant Trader — XAU/USD separado dos 28 Forex (LAB)

**Checkpoint 10/11/2026 — pesquisa somente, sem sinais ou operação.**

## Escopo

XAU/USD é ouro cotado em dólares, **não** uma nona moeda G8. O registro
`atlasquant_instrument_registry.py` agora expõe a referência separada
`METAL:XAUUSD` e aceita `XAU/USD`, `XAUUSD` ou `METAL:XAUUSD` como aliases
desse instrumento de pesquisa. Os 28 pares Forex continuam exatamente os
mesmos. Não se presume símbolo específico, spread, contrato, tamanho de lote,
horário de sessão ou preço executável da Pepperstone.

O lote MT5 AM12 previamente auditado contém **28 Forex × M15/D1/W1**;
**nenhum histórico de XAU/USD** foi capturado ou validado naquele lote.

## Três componentes documentais necessários

| Componente | Fonte candidata | Unidade e periodicidade | Limite |
|---|---|---|---|
| Rendimento real de 10 anos dos EUA | `DFII10` / Federal Reserve via FRED | Percentual, diário | Juros reais não fornecem direção do ouro por si só |
| Índice amplo do dólar | `DTWEXBGS` / Federal Reserve via FRED | Índice, diário | **Não é** o índice DXY proprietário da ICE |
| Preço do ouro XAU/USD | Pepperstone MT5 | USD por onça-troy, M15 | Sem candles reais de ouro confirmados nesta etapa |

Fontes oficiais para a identificação (não para provar capturas nesta rodada):

- https://fred.stlouisfed.org/series/DFII10 — taxa real de Treasury indexado,
  série H.15 diária.
- https://fred.stlouisfed.org/series/DTWEXBGS — índice nominal amplo do dólar,
  série H.10 diária, base jan/2006 = 100.

Faltam ainda calendário econômico, Fed, notícias verificáveis, contexto
geopolítico e a relação historicamente testada entre esses fatores e o ouro.
Não usar variação de juros ou dólar para criar sinal automático de compra/venda.

## Nova porta de qualidade

`atlasquant_trader_xauusd_macro_readiness_lab.py` é uma função offline que:

1. Verifica se o instrumento é exatamente a referência de ouro, sem aceitar
   um par Forex no lugar.
2. Exige **duas observações distintas** por componente (a presença de um único
   nível não demonstra uma tendência), source ID, unidade e frequência fixos.
3. Rejeita hash com formato incorreto, preço não numérico/não positivo, taxa
   real fora da faixa de plausibilidade, data inválida, duplicata e publicação
   ou captura alegadamente posterior à decisão.
4. Para M15, exige que a publicação/captura alegada ocorra após os 15 minutos
   nominais da barra (sem atestar o timezone nem a sessão do MT5).
5. Como proteção conservadora **não calibrada**, recusa amostras cujo último
   dia de juros reais tenha mais de 7 dias, índice amplo do dólar mais de
   14 dias ou última abertura de candle XAU M15 mais de 1 hora.

Mesmo que as seis observações **alegadas** passem, o estado máximo é
`LAB_XAUUSD_THREE_DRIVER_CLAIMS_PRESENT_UNATTESTED`, com:

- `fred_series_responses_authenticated=false`;
- `pepperstone_xauusd_bars_authenticated=false`;
- `news_and_geopolitics_authenticated=false`;
- `source_clocks_independently_authenticated=false`;
- `historical_point_in_time_verified=false`;
- `xauusd_bias=null`, `score_0_to_10=null`,
  `calibrated_probability=null`;
- `operational_bias=AGUARDAR`, `trade_authorized=false`, `publishable=false`.

Esses thresholds e testes não foram avaliados para previsão, retorno, custo,
risco ou correlação. Nenhuma direção é derivada dos valores alegados.

## Prova local e próximos passos

`test_atlasquant_trader_xauusd_macro_readiness_lab.py`: **17 testes
sintéticos**, incluindo registro separado, fontes corretas/erradas, ausência
de dados, duplicidade, janela futura, M15 incompleta, preço/índice incorreto,
fonte desatualizada e preservação de NO-GO mesmo com todos os campos.

Primeira regressão identificou uma expectativa de dado "desatualizado" que
na verdade ainda estava dentro da janela de 14 dias; o teste foi corrigido
para tornar **ambas** as datas do índice anteriores à janela, e a suíte final
passou: **315/315 testes locais** (`python -m unittest discover -q -p
'test_atlasquant*.py'`).

Próximo trabalho exige snapshots de XAU/USD read-only no terminal autorizado
e evidência independente dos indicadores FRED, com horários/fontes e histórico
point-in-time. AION permanece congelado; foco no viés do Trader.

Nenhum MT5 foi acessado, nenhum dado real de ouro foi obtido, e não houve
deploy, merge, Worker, compra ou ordem.
