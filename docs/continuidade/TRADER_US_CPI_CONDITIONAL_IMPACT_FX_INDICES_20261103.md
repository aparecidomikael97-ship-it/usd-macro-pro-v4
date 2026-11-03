# Trader — Cenários macro pré-evento do CPI e transmissão FX/índices (LAB, 03/11/2026)

## Problema que resolve

O usuário quer **antecipar** o viés dos pares e índices com macro, micro e geopolítica. Um CPI ainda não divulgado exige planejar os caminhos possíveis **sem afirmar qual ocorrerá**. O registro prospectivo do nowcast Cleveland de 03/11 fornece uma previsão de modelo; não fornece consenso oficial de mercado nem surpresa efetiva.

O módulo `atlasquant_trader_us_cpi_conditionals_lab.py` inspeciona o snapshot pré-evento e apresenta **três ramificações hipotéticas sem seleção**, exclusivamente se executado antes de 10/11 13:30 UTC. O registro depois do horário é recusado. Não faz HTTP nem lê preços.

## Árvore de cenários condicionais (sem taxa de acerto)

| Cenário | Condições necessárias (todas) | Exemplos **SE** forem verdadeiras |
| --- | --- | --- |
| **Inflação acima do consenso + Fed mais hawkish relativo** | CPI realizado acima do **consenso pré-divulgação comprovado**, núcleo corrobora, juros esperados dos EUA sobem **mais do que** os da outra moeda, rendimentos relativos respondem, sem choque geopolítico contrário | EUR/USD **baixa condicional**, USD/JPY **alta condicional**. Em bolsas dos EUA, alta dos juros reais sem suporte de lucro pode provocar pressão de baixa |
| **Inflação abaixo do consenso + Fed mais dovish relativo** | CPI e núcleo abaixo, expectativas de política americana cedem **mais que** as da contraparte, sem choque de recessão ou aversão extrema ao risco | EUR/USD **alta condicional**, USD/JPY **baixa condicional**. Índices EUA podem melhorar **somente se** redução de rendimentos não representar piora abrupta do crescimento |
| **Núcleo ou risco geopolítico conflita** | Sinais contraditórios de inflação, rendimentos, crescimento, geopolitica ou posição relativa | **AGUARDAR**, sem direção condicional |

São *exemplos de canais econômicos*, não entradas, ordens ou setas do Radar. Estudos do Fed mostram que **surpresas relativas de política** e risco interferem no câmbio, mas que o efeito varia com o episódio/regime; pesquisas do Fed sobre ações também mostram dependência de crescimento e do tipo de inflação. **Nenhum impacto dos nossos cenários foi estimado ou calibrado.**

Referências de mecanismo:
- Federal Reserve: https://www.federalreserve.gov/econres/notes/feds-notes/monetary-policy-and-exchange-rates-during-the-global-tightening-20240510.html
- Federal Reserve: https://www.federalreserve.gov/econres/feds/good-inflation-bad-inflation-implications-for-risky-asset-prices.htm
- BLS CPI calendário: https://www.bls.gov/schedule/news_release/cpi.htm

## Horizontes e ativos

- **D1:** só há rótulos `ALTA_CONDICIONAL` ou `BAIXA_CONDICIONAL` para os **sete pares com USD**, se a ramificação econômica e todas as condições hipotéticas vierem a ocorrer.
- **W1:** exige adicionalmente que a mudança relativa de política/juros **persista durante a semana**; caso contrário a ramificação não deve ser selecionada.
- **MN1:** um CPI não prova regime mensal, portanto os 28 pares e cinco índices ficam **AGUARDAR** nesse horizonte.
- **21 pares sem USD:** não herdam automaticamente o efeito do CPI americano; **AGUARDAR**.
- **SPX500, NAS100, US30:** ramificações próprias do mecanismo de juros reais × lucro × crescimento; não herdam automaticamente sinal FX.
- **WIN/WDO:** dependem de Brasil/BRL, fiscal, Selic, commodities, abertura e câmbio local; este evento sozinho não fornece direção. **AGUARDAR**.
- **Se houver conflito de geopolítica, núcleo e expectativas:** ramificação mista `AGUARDAR` para todos.

Cobertura técnica de **252 linhas hipotéticas Forex** (28 pares × 3 horizontes × 3 cenários) e **45 linhas hipotéticas índices** (5 × 3 × 3). Essa contagem **não** é quantidade de previsões validadas ou sinais.

## Invariantes

- `selected_branch=null` e todos `branch_selected=false`: o software **não escolhe** se a inflação virá acima ou abaixo.
- `market_consensus_available=false`, `relative_policy_paths_verified=false`, `geopolitics_alignment_verified=false`.
- `bias_primary=AGUARDAR`, `market_probability_calibrated=null`, `accuracy_90_proven=false`, `trade_authorized=false`, `can_feed_live_radar=false`.
- Testes recusam fonte modificada, dados futuros, anúncio pós-evento como cenário pré-evento, falsa probabilidade e transferência da regra FX para WIN/WDO.

## Próxima etapa empírica

Falta medir **expectativa prévia do mercado** (fonte e licença), reprecificação **relativa de yields**, índices de risco e contexto geopolítico **antes** do CPI. Para outros pares é preciso o mesmo conjunto por moeda. Após cada divulgação, arquivar o dado real e julgar os cenários **sem mudar a regra de trás para frente**, acumulando amostra walk-forward por D1/W1/MN1.

PR #1803 **DRAFT / LAB / HARD NO-GO**: zero merge, deploy, Worker, cron, ordens, APIs pagas, mudança do visual aprovado ou alegação de 90%.
