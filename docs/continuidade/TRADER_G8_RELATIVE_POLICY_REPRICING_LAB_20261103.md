# AtlasQuant Trader — reprecificação relativa da trajetória de juros G8 (LAB, 03/11/2026)

## Objetivo e limite

Mikael prioriza **antecipar o viés macro** dos 28 pares entre USD, EUR, GBP, JPY, CHF, CAD, AUD e NZD em D1/W1/MN1. O problema ainda não resolvido é obter **expectativas verificáveis de mercado, no instante correto**, e medir se a informação realmente antecipa o movimento. O presente contrato é **inteiramente sintético**, sem fontes de preços e sem sugestão operacional.

Pesquisa de mecanismo econômico (Federal Reserve, fonte primária): [Monetary Policy and Exchange Rates during the Global Tightening](https://www.federalreserve.gov/econres/notes/feds-notes/monetary-policy-and-exchange-rates-during-the-global-tightening-20240510.html). Há associação empírica entre surpresas de juros **relativas** e movimentos cambiais; risco, prêmio e outros fundamentos também importam. **Associação não prova previsão específica para 2026 nem 90% de acerto**.

## Comparação correta

- Entrada por horizonte e moeda: **mudança da expectativa para a trajetória futura de juros** (pontos-base, BP), observada num *mesmo intervalo de tempo* e com o *mesmo vencimento-alvo* entre as oito moedas. Não utilizar o nível nominal anunciado pelo Fed, BCE, BoE etc. como se ele próprio fosse força cambial.
- Para cada par **BASE/COTADA**: `revisao_relativa_bp = revisao_base_bp - revisao_cotada_bp`.
- O contrato exige **24 células** (8 moedas × 3 horizontes) e devolve 84 comparações experimentais (28 pares × 3 horizontes), sem dupla contagem de par invertido.
- Um desnível superior a **5 BP** é classificado apenas como hipótese de pressão relativa (limiar **arbitrário e não calibrado**); valores próximos ou iguais são hipótese neutra.
- Se a microeconomia ou geopolítica sintéticas estiverem contraditórias ou incompletas em qualquer uma das duas moedas, a hipótese recebe **veto**. Mesmo sem veto, o campo operacional é sempre `directional_bias=AGUARDAR`.
- Exige emissão com horário UTC, recebimento antes da emissão, amostra recente, janelas e vencimentos iguais para todas as moedas do horizonte. Qualquer quebra recusa o lote por inteiro.

### Exemplo exclusivamente fictício

`USD +15 BP`, `EUR -5 BP`, `JPY -10 BP` → pressão relativa matemática `EUR/USD = -20 BP` e `USD/JPY = +25 BP`. **Isto não é previsão de baixa ou alta de preço**; não existe comprovação de que tais revisões ocorreram.

## O que falta para um viés real de alta probabilidade

1. Fonte lícita e independente de curvas de expectativas (ex.: OIS / taxa implícita ou pesquisa por reunião), com convenção idêntica de maturidade, timestamp e licença — **ausente**. Evitar construir "curva implícita" artificial a partir da taxa nominal atual.
2. Captura imutável de cada fonte, calendário e expectativa antes de notícias, com confirmação dos fusos — **ausente**.
3. Modelo de efeitos econômicos não mecânicos: surpresa **versus consenso anterior**, trajetória Fed relativa a outros bancos centrais, atividade, inflação, risco, matérias-primas, posicionamento, microeconomia e geopolítica — **não integrado/validado**.
4. Preços Forex **independentes** do conjunto de evidências e avaliação sem antecipação, walk-forward OOS, com taxa de cobertura/abstenções, intervalo de confiança e baseline — **não comprovados**.

Esses passos exigem pesquisas e autorização de fontes adequadas; não são substituídos por testes de software. Os campos `market_quotes_verified`, `independent_receipts_verified`, `directional_accuracy_oos_proven`, `accuracy_90_proven` permanecem `false`; `probability_calibrated=null`.

## Arquivos, testes e governaça

- `atlasquant_trader_relative_policy_repricing_lab.py`: contrato determinístico sem I/O, rede, dependências externas ou cálculo de probabilidade.
- `test_atlasquant_trader_relative_policy_repricing_lab.py`: **32 testes locais** de orientação do par, 24 observações/84 linhas, independência por horizonte, divergência matemática, veto micro/geopolítico, compatibilidade de observações, corte temporal e recusa de parâmetros falsificados.
- Teste incluído na **Quality tests** do GitHub.

**PR #1803 permanece DRAFT / LAB / HARD NO-GO**. Interface aprovada, `main`, Worker, cron, deploy, corretoras, ordens e serviços pagos intocados. Nenhum ranking é probabilidade, nenhum valor sintético é preço real, nenhuma pressão experimental é ordem.
