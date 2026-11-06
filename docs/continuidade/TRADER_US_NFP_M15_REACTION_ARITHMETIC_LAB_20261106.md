# AtlasQuant Trader — NFP de outubro/2026: aritmética M15 pós-divulgação (LAB)

Data do estudo: 2026-11-06. Escopo: **somente laboratório, sem nova cobrança ou conexão a corretora**.

## O que já é diferente de uma previsão

O casebook documental já separa a pesquisa econômica da Reuters (publicada em
2026-11-04, com previsão de +65 mil empregos) do resultado do relatório NFP
do BLS (divulgado em 2026-11-06 às 13h30 UTC, com +165 mil). A diferença
aritmética de +100 mil **não comprova** reação do preço, causalidade ou um
viés direcional que pudesse ter sido emitido antes do evento. Não há cópia
atestada, capturada antes da divulgação, da página da Reuters.

O novo `atlasquant_trader_us_nfp_m15_reaction_lab.py` faz outra pergunta,
separada: **quanto uma cotação M15 alegadamente fornecida pelo próprio usuário
mudou na primeira hora depois do evento?** Não busca nem inventa preços.

## Janela fixa e cálculo

* Evento: **2026-11-06 13:30 UTC**. Quatro barras M15 completas de 12:30 até
  13:30 UTC e quatro barras completas de 13:30 até 14:30 UTC; não usa velas
  abertas. A coleta (`captured_at_utc`) precisa ocorrer após 14:30 UTC.
* Referência: fechamento da barra 13:15–13:30 UTC. Resultado: fechamento
  da barra 14:15–14:30 UTC. Retorno do **par** em pontos-base:
  `(fechamento_final / fechamento_pre_evento - 1) × 10000`.
* Nos pares **USD/JPY, USD/CHF, USD/CAD**, USD está na base e a orientação USD
  preserva esse retorno. Nos pares **EUR/USD, GBP/USD, AUD/USD, NZD/USD**,
  o USD está na cotação; a orientação matemática é a taxa recíproca:
  `(fechamento_pre_evento / fechamento_final - 1) × 10000`. Isso não equivale
  precisamente a simplesmente negar o retorno arredondado do par.
* Uma mudança superior a **1000 pontos-base em módulo** é barrada como
  anomalia de entrada a ser revisada por humano; esse limiar é somente de
  plausibilidade da pesquisa, **não** é gerenciamento de risco.

## Contrato de entrada e segurança

* Recebe o JSON documental **fixo** de NFP como bytes, mais um JSON de
  candles exportados pelo usuário no contrato
  `ATLASQUANT_MT5_M15_OFFLINE_EXPORT_V1` / `MT5_COPY_RATES_RANGE_OFFLINE_EXPORT`.
* Reutiliza **ambos** os validadores existentes. Exige o par canônico G8 com
  USD, timestamps UTC declarados, OHLC decimal válido, barras ordenadas sem
  lacunas e horário de coleta verificável estruturalmente.
* Retorna hashes SHA-256 da documentação e do export para rastreabilidade;
  não guarda credenciais e não chama rede, Render, MetaTrader ou TradingView.
* Como o relógio e as velas podem ter sido montados ou alterados pelo
  exportador, os números carregam explicitamente o sufixo `unverified`.
  A origem do broker, o lado bid/ask, o carimbo UTC original, o spread, o
  slippage, o preço de execução, o contrato de redistribuição e a versão
  histórica ainda **não estão atestados de modo independente**.

## O que o resultado **não** autoriza

O retorno pós-notícia **não** demonstra que o AtlasQuant teria previsto o
movimento. A informação oficial já tinha sido publicada quando essa janela
começa. Reações podem resultar de inúmeros fatores; não se atribui
causalidade exclusivamente ao NFP. Este teste não altera força macro do USD,
viés D1/W1, Radar, acurácia, taxa de acertos ou escolha de operação.

Campos obrigatoriamente fechados: `fx_bias=null`, `usd_macro_strength=null`,
`validated_prediction_count=0`, `validated_accuracy=null`,
`operational_bias=AGUARDAR`, `trade_authorized=false`,
`can_feed_live_radar=false`, `publishable=false`,
`worker_enabled=false`, `scheduler_enabled=false`, custo novo `R$0`.

Os testes de aceitação são **sintéticos** (17 cenários): EUR/USD e USD/JPY,
precisão da cotação invertida, ausência de movimento, mutações de casebook,
relógios errados, janelas incompletas, lacunas, preços e formatos inválidos,
evento antes da divulgação e proibição de promoção operacional.

## Próximo passo, quando houver dados reais

Receber uma exportação MT5 offline criada pelo próprio usuário **após** o
evento e auditar, separadamente, o relógio da corretora e sua origem. Então
será possível calcular um retorno **observacional ainda não atestado**.
Para avaliar alguma pretensão de previsão, seria necessário antes congelar
vieses D1/W1 com horário/proveniência confiáveis, e depois avaliá-los em
uma amostra futura com critério e linha de base definidos, sem vazamento
de eventos já publicados. Por enquanto: **NO-GO de uso real**.
