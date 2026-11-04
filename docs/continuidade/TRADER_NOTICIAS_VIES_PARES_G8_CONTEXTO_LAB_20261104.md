# AtlasQuant Trader — notícias oficiais no contexto dos 28 pares (LAB)

## Objetivo e prioridade permanente

Viés **D1, W1, MN1** dos 28 cruzamentos G8, explicando por que cada moeda
está forte ou fraca com **macro, micro, geopolítica, notícias, calendário e
força cambial independente**, inclusive evidência contrária. Este documento
não altera esse foco e não promove FVG/OB, candles ou sinais de M15.

## Entrega deste bloco

`atlasquant_trader_news_pair_context_lab.py` cruza os 28 pares/3 horizontes
da matriz de hipótese + calendário documental com até cinco **respostas HTTP
sintéticas** já normalizadas pelo contrato offline. O cruzamento só aceita:

- Cronologia coerente: hora de avaliação, do recebimento e alegação de
  publicação do artigo sem uso de informação posterior à captura.
- Resposta reconhecida por fonte oficial previamente cadastrada, sem fonte
  duplicada, com payload e identificadores estruturados e flags de confiança
  **explicitamente falsas**.
- Eventos do calendário V1/V2 conforme reprodução da versão documental
  original, sem acréscimo ou omissão de lançamentos no dossiê.
- Uma das situações 200 (XML documental), 304 (alegação de inalterado sem
  reutilizar manchetes), 429/5xx (indisponibilidade), 3xx (bloqueio de
  redirecionamento) e status não aceito (bloqueio).

Cada cartão por par e horizonte inclui:

1. Hipótese sintética de força em comparação à macro, **sem certeza**.
2. Eventos do calendário curado e seu risco temporal, **sem direção inferida**.
3. Artigos documentais nos últimos 1, 7 ou 30 dias, separados por moeda,
   com título, URL, horário declarado e identificação de revisão. Esses
   intervalos são apenas **janelas retrospectivas do noticiário**, não os
   candles D1/W1/MN1 e muito menos previsão de preço.
4. Falhas de cobertura e a lista de comprovações ainda necessárias.
5. `AGUARDAR` como **único** viés operacional: motivo da força da moeda,
   contraprovas, atualidade e probabilidade **não comprovados**.

O painel não trata um título como explicação causal. Exemplo: uma notícia de
inflação do BLS pode justificar abrir uma investigação sobre USD, mas não
prova que o dólar subiu, que houve surpresa frente ao consenso ou que um
par deverá subir. É necessário reunir valores, consenso, vintages,
expectativas, curva de juros, mercado e outros fatores.

## Cobertura exata e o que não foi feito

O piloto de canais segue limitado a **USD (3 leads)** e **EUR (2 leads)**.
GBP, JPY, CHF, AUD, CAD e NZD ainda não têm leads RSS homologados nesse
conector; isso **não** significa ausência de acontecimentos nessas moedas.
Uma lista vazia também não prova que o dia não teve notícias. O sistema
exibe os vazios em vez de inventar cobertura G8.

**Nenhum feed real foi consultado**, nenhuma atualização automática foi
ativada, nenhum dado foi persistido e nenhuma notícia adquiriu custódia TLS
ou evidência de latência real. Testes usam documentos simulados e não
validam assertividade de mercado. Os controles de source-of-truth,
contraprovas e backtest OOS continuam obrigatórios.

### Frequência e custo

Somente **três revisões completas planejadas** por dia na fase grátis
(06:35, 10:45 e 17:15, horário de Brasília); ainda **não estão ligadas**.
Sem coleta extra, plano horário, cron, Render, Worker, compra de serviço ou
ordem. Futuro horário pago depende de decisão separada do proprietário.

## Testes locais

```sh
python -m unittest -q \
  test_atlasquant_trader_news_pair_context_lab.py \
  test_atlasquant_trader_official_http_collection_contract_lab.py \
  test_atlasquant_trader_official_rss_capture_lab.py \
  test_atlasquant_trader_bias_calendar_exposure_link_lab.py
```

Os testes novos cobrem 28×3 sem notícia, 7 pares expostos a USD, USD/EUR,
304 sem notícia reciclada, 429 sem promoção, fontes duplicadas, outro host,
falsificação de hash e relógio, BUY_NOW, eventos de calendário forjados,
contagem de fontes ausentes e recusa de cabeçalho ou estado operacional
incompatível. O teste foi incluído na lista da workflow Quality.

**Status:** PR #1803 DRAFT, HARD NO-GO, sem merge ou publicação. A próxima
etapa relevante é validar fontes originais e ampliar cobertura oficial G8,
seguindo no dossiê causal até viés confiável e auditável.
