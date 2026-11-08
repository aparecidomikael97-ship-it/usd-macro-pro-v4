# AtlasQuant Trader — notícias por moeda e pares afetados (LAB)

**Situação em 08/11/2026:** roteador genérico de *relevância documental*
testado apenas com eventos **sintéticos**. Não é um feed, não busca notícias,
não agenda atualizações, não emite viés ou aviso e não executa operações.

Arquivo: `atlasquant_trader_g8_event_relevance_lab.py`.

## O que ele faz

1. Recebe um evento econômico com identificador, moeda G8, indicador, unidade,
   período, importância, horário de publicação programado e horário em que o
   calendário teria sido capturado.
2. Se houver consenso, exige que a sua captura seja **anterior** à divulgação.
   Uma projeção de modelo não é automaticamente o consenso de analistas daquele
   anúncio; a natureza da fonte precisa ser auditada em outro módulo.
3. Se houver resultado real, exige que a publicação e a captura sejam **após**
   o horário programado e não posteriores ao instante da análise.
4. Calcula `real - consenso` apenas quando ambos existem, na **mesma métrica e
   unidade declarada**. Esse resultado é só aritmética documental, não a
   probabilidade de acertar a direção do par.
5. Encaminha o contexto aos **sete pares que contêm a moeda**. Exemplo:
   uma notícia de USD é relevante para EUR/USD, GBP/USD, AUD/USD, NZD/USD,
   USD/JPY, USD/CHF e USD/CAD; não contamina os outros 21 pares.
6. Marca se a moeda afetada é a **BASE** ou a **COTADA**. Quando há notícias
   de ambas, o mesmo par pode carregar os dois eventos. Não soma surpresas
   econômicas de unidades, períodos ou países distintos.
7. Guarda a fase: **antes da divulgação**, **horário passou sem resultado**,
   **resultado sem consenso** ou **resultado e consenso documentais**.

O universo contempla as oito moedas G8 e os **28 pares**. Para CPI mensal,
NFP mensal, PIB trimestral e decisões de política monetária, as periodicidades
e unidades devem corresponder ao indicador. Um PIB trimestral não entra como
CPI mensal; as datas de decisão devem existir no calendário.

## O que ele não permite inferir

Um CPI americano **acima do consenso** pode influenciar juros, dólar, ações
e apetite a risco por diferentes canais. Isso não prova, isoladamente, que
EUR/USD cairá ou US500 subirá/cairá. A reação dependerá de expectativas já
precificadas, política monetária, liquidez, posicionamento, notícias
concorrentes e regime de mercado.

Por isso, todo resultado mantém:

```text
source_original_bytes_authenticated = False
pre_event_consensus_independently_attested = False
post_event_actual_independently_attested = False
market_reaction_direction_validated = False
relative_currency_strength_available = False
calibrated_direction_probability = None
fx_bias = None
index_bias = None
operational_bias = AGUARDAR
live_alert_allowed = False
publishable = False
trade_authorized = False
```

Um hash fornecido pelo chamador **não autentica** o emissor, o conteúdo ou a
disponibilidade histórica do documento. A lista de eventos fornecida também
**não atesta cobertura completa** do calendário; uma lista vazia não significa
que não existam notícias.

## Próximas dependências de dados reais

- Conectar um calendário com fonte, horário e direitos de uso verificáveis,
  preservando as três consultas diárias inicialmente alinhadas, sem anunciar
  atualização de indicadores quando não houve número novo.
- Capturar consenso da divulgação exata **antes do evento** e resultado
  oficial **depois do evento**, mantendo registros de primeira divulgação,
  revisões e fonte original. A pesquisa documental de CPI americano já
  existente permanece independente.
- Ligar o aviso de **revisão necessária** ao filtro de viés raro e ao estudo
  de previsão pré-evento. Um novo resultado poderá exigir recálculo, mas não
  obrigará a inverter o viés ou enviar sinal.
- Criar módulo específico de fatores de índices/futuros, sem reutilizar
  mecanicamente a orientação BASE/COTADA do Forex.
- Validar prospectivamente por ativo/horizonte e regime antes de sugerir
  qualquer nota probabilística ou recomendação de gestão de posição.

## Verificação

`test_atlasquant_trader_g8_event_relevance_lab.py`: **20/20 testes sintéticos
aprovados**, incluindo oito moedas, sete pares por moeda, dupla notícia
no GBP/USD, fuga temporal, ausência de valor realizado, cálculos positivos e
negativos, incongruências de unidade/período, duplicatas e nenhuma direção FX.

Com os testes do filtro seletivo e da junção de evidências:
**61/61 testes selecionados aprovados**. Duas suítes antigas ligadas a
casebooks não carregaram porque seus arquivos JSON originais não estavam
no checkout. Não equivalem a reprovação deste módulo nem a execução completa
da regressão. Sem merge, deploy, cobrança, worker, agendamento, MT5 ou alerta.
