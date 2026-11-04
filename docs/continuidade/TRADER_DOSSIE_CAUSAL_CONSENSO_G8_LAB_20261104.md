# AtlasQuant Trader — surpresa econômica e dossiê causal G8/28 pares (LAB)

## Objetivo fixo do Checkpoint Mestre

A prioridade continua sendo **força relativa e viés D1/W1/MN1 de 28 pares
Forex**. A explicação deve juntar macroeconomia, microeconomia,
geopolítica, notícias, calendário e sinais contraditórios, sem inventar
uma causa da força/fraqueza antes de haver evidências independentes.
FVG/OB e sinais técnicos não são o foco deste bloco.

## O que foi implementado

O módulo `atlasquant_trader_macro_causal_dossier_lab.py` une:

1. O dossiê de **notícias e calendário documental**, incluindo os atuais
   14 leads RSS de sete moedas (NZD pendente, nenhum feed real baixado).
2. A prova de laboratório pré-existente `atlasquant_trader_macro_surprise_pit_lab.py`,
   que distingue **valor anterior, consenso conhecido antes da publicação,
   data anunciada, resultado divulgado e hora de recebimento**.
3. Os 28 pares e três horizontes, expondo resultados econômicos sintéticos
   associados à moeda-base ou moeda-cotada, sempre com viés operacional
   `AGUARDAR`.

### Exemplo matemático, estritamente sintético

| Item | Valor de teste |
|---|---:|
| CPI anterior | 2,1% |
| Consenso congelado antes do evento | 2,3% |
| Resultado informado depois do evento | 2,6% |
| Surpresa bruta | +0,3 ponto percentual |
| Classificação | Acima do consenso |
| Efeito comprovado no USD/JPY | **Não comprovado** |

Isso **não** significa que o USD subiu. O impacto depende de expectativas
prévias, surpresa marginal, revisão de séries, função de reação do banco
central, juros reais, posicionamento, apetite ao risco, atuação da outra
moeda e outros eventos. Diferentes indicadores têm diferentes unidades e
sinais econômicos: jamais somar diretamente CPI, desemprego e GDP para
fabricar uma pontuação de força.

## Proteções de precisão e anticontaminação temporal

- A mesma evidência recebe distinções entre **ainda agendada** e
  **resultado divulgado**, não podendo transformar evento futuro em dado
  realizado na hora de avaliação.
- O dossiê reconstrói o cálculo de surpresa a partir dos campos básicos.
  Recusa números, horários, sinais ou permissões adulterados, eventos
  duplicados e séries com consenso capturado depois da publicação.
- Manchetes só podem aparecer vinculadas à moeda do respectivo publicador,
  com URL e hora coerentes. Calendário V1/V2 deve bater integralmente com a
  versão documental canônica.
- Artigos e resultados **passados** nas janelas de 1, 7 e 30 dias são
  contexto retrospectivo; eventos futuros nas próximas janelas são risco
  agendado. **Não** são candles D1/W1/MN1, retorno esperado nem backtest.
- Divergência entre surpresas brutas acima e abaixo do consenso fica
  marcada como **dados mistos a investigar**, não como contradição
  macroeconômica automaticamente provada.
- Indicadores de confiabilidade permanecem negativos: origem autenticada,
  consenso independente, impacto de política monetária, contraprovas,
  preços FX independentes, calibração OOS, performance e viés operacional.

## Status real

Todas as evidências de teste são **sintéticas**. Nenhuma manchete real foi
coletada, nenhum contrato foi homologado com dados de mercado e nenhuma
afirmação sobre força ou fraqueza atual das moedas é feita. O módulo não
ativa serviços, acesso HTTP, notificações, ordens, Render, Worker nem AION.

As **três revisões gratuitas diárias** (06:35, 10:45 e 17:15 em Brasília)
continuam **planejadas, não executadas**; serviço horário pago só com
autorização futura. PR #1803 DRAFT, HARD NO-GO, sem deploy/merge.

## Validação

```sh
python -m unittest -q \
  test_atlasquant_trader_macro_causal_dossier_lab.py \
  test_atlasquant_trader_news_pair_context_lab.py \
  test_atlasquant_trader_official_http_collection_contract_lab.py
```

**Próximo critério de qualidade:** amostras de dados originais com recibo,
consenso/vintage PIT verificáveis, resultado de evento, contexto da política
monetária, força FX de fonte independente e validação walk-forward antes
de explicar uma direção real com confiança calibrada.
