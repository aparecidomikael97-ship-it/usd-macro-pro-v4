# AtlasQuant Trader — Pesquisa ex-post dos sete pares USD (LAB)

Data: 02/11/2026 · PR #1803 · HARD NO-GO.

## Motivo

A inspeção do repositório encontrou sete séries de OHLC D1 ligadas ao dólar
no arquivo dados/autopilot_daily_cache_v107.json, com 320 registros por par
(2.240 no total), de 22/10/2025 a 17/09/2026.

O arquivo **não certifica a origem, a licença, a hora de disponibilidade do
fechamento, o fuso de sessão nem a consistência com o mercado**. São 581
candle labels de sábado/domingo na soma das sete séries (83 por par). Não
tratar essa convenção automaticamente como boa ou ruim; requer reconciliação
com a fonte. Ele está velho demais para o viés diário de novembro de 2026.

## O que implementamos

- atlasquant_trader_fx_7usd_expost_lab.py reconstrói descrições
  matemáticas de **movimentos relativos já passados**, usando somente
  sete pernas cotadas com USD, sem API e sem sinais.
- Para cada par A/B observado, r(A/B) = log(close_B / close_A).
  Quando USD é moeda cotada, inverte o sinal para obter r(USD/C).
- Para cada moeda C diferente de USD, força relativa centrada x_USD - x_C
  = r(USD/C). A soma das forças das oito moedas é zero. Essa escala em
  pontos-base é DESCRITIVA, não força preditiva ou chance de lucro.
- Reconstrói 28 movimentos históricos algébricos, com r(A/B)=x_A-x_B.
  **Sete** são pernas observadas no *cache não verificado*, e os outros
  **21 são diferenças implícitas**, não cotações independentes.
- Cada registro classifica os cruzamentos como
  OBSERVED_LEG_UNVERIFIED_CACHE ou IMPLIED_ALGEBRAIC_NOT_INDEPENDENT.
  Número de preços de mercado verificados independentemente: **zero**.
- Exige pares exatos, mesmos timestamps, OHLC consistente, dados
  em ordem, valores finitos, intervalo já encerrado e endpoints
  realmente presentes; rejeita dados incompletos ou contraditórios.
- Reutiliza a auditoria do legado para identificar fim de semana,
  bloqueio de fonte e falta de licença. Não interpreta timestamps
  de rótulo de candle como disponibilidade conhecida naquela data.
- 21 testes test_atlasquant_trader_fx_7usd_expost_lab.py:
  matemáticas, orientação EUR/USD e USD/JPY, par derivado EUR/JPY,
  todos os 28 cruzamentos, cenários adversos e o arquivo antigo real.
  Só executam em LAB pela suíte Quality CI.

## O que NÃO permite

- Não gera viés D1, W1, MN1 para operação, Top 10 ou previsão.
- Não habilita o Radar, execução, monitoramento, API ou cron.
- Não mede assertividade, P&L ou probabilidade de lucro.
- Não simula que existiam 28 preços independentes.
- Não permite backtest pontual certificado usando arquivo não
  atestado — os dados poderiam ter sido corrigidos/revistos
  depois da data suposta de disponibilidade.

## Próximos passos legítimos

1. Comprovar proveniência/licença/convenção de sessão do cache
   e decidir se a pesquisa das sete pernas pode ser mantida.
2. Validar séries históricas independentes dos cruzamentos para
   testar qualidade do modelo de força derivada e suas divergências.
3. Só então executar backtest OOS com previsões registradas
   ponto-no-tempo, comparadas com resultados posteriores e
   baselines por par, período e regime.
4. Separadamente, incluir a análise macro oficial no processo de
   viés e medir se ela melhora a direção observada.

Sem merge, deploy, Worker AION, cron, API, dinheiro ou ordens.
O Checkpoint Mestre e a interface aprovada permanecem preservados.
