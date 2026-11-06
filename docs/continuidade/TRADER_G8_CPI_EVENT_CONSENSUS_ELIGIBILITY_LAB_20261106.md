# AtlasQuant Trader — qual expectativa serve para a surpresa de CPI? (LAB)

**Pesquisa-base:** 06/11/2026. **Resultado conservador visível:** somente a partir de 07/11/2026 00:00 UTC. **Sem operação, publicação ou agendamento.**

Esta etapa conecta o calendário das próximas divulgações, as referências documentais das duas moedas de cada um dos **28 pares Forex G8** e quatro observações de expectativas já registradas. O objetivo é evitar que uma expectativa sobre outro período, outra população ou uma estimativa de modelo seja usada como se fosse o **consenso de analistas para a divulgação exata de CPI**.

## Quatro referências, nenhuma substitui o consenso do evento

| Origem documental | Dado anotado | Natureza e período | Por que não serve como consenso do próximo CPI |
|---|---|---|---|
| Fed de Cleveland | **3,74%** | *Nowcast* estatístico, CPI-U dos EUA referente a outubro/2026 | Projeção de **modelo**, não agregação autenticada de previsões de analistas antes da publicação de 10/11 |
| Fed de Cleveland | **3,88%** | *Nowcast* estatístico, CPI-U dos EUA referente a novembro/2026 | Período diferente e também projeção de **modelo**; publicação prevista para dezembro |
| BCE, Survey of Monetary Analysts | **3,2%** | Mediana de participantes selecionados para **2026T3** | Pesquisa com analistas, mas de **trimestre**, não previsão do evento mensal HICP de outubro da área do euro |
| Fed de Nova York, Survey of Consumer Expectations | **3,9%** | Mediana de **famílias**, expectativa de inflação **um ano à frente** a partir de setembro | População e horizonte diferentes; não é previsão de analistas do CPI-U mensal americano |

Os quatro valores são **transcrições documentais bloqueadas por recibos de hash** já existentes no LAB. Esses recibos verificam apenas que os bytes armazenados no repositório não mudaram; **não** comprovam independentemente os bytes originais das páginas nem o instante de sua captura. Não são observações operacionais em tempo real.

**Correção de disponibilidade do indicador:** o [FAQ oficial do BLS](https://www.bls.gov/cpi/additional-resources/2025-federal-government-shutdown-impact-cpi-faq.htm) documenta a ausência do índice all-items de outubro/2025; por isso a variação **anual** do CPI de outubro/2026 não terá resultado oficial comparável na divulgação seguinte. A projeção de modelo **3,74% anual** não permite uma surpresa ex-post anual. O estudo complementar de alinhamento mensal/anual explica a referência de **0,3% mensal** da Reuters, também ainda não autenticada como consenso ponto-no-tempo.

Fontes públicas de contexto: [Fed de Cleveland, Inflation Nowcasting](https://www.clevelandfed.org/indicators-and-data/inflation-nowcasting); [BLS, calendário de novembro/2026](https://www.bls.gov/schedule/2026/11_sched_list.htm); [BCE, SMA setembro/2026](https://www.ecb.europa.eu/stats/ecb_surveys/sma/shared/pdf/ecb.smar260911_september.en.pdf); [Fed de Nova York, SCE setembro/2026](https://www.newyorkfed.org/newsevents/news/research/2026/20261007.html).

## Roteamento pelas duas moedas, sem fabricar viés

- **7 pares com USD:** mostram os dois *nowcasts* dos EUA e a pesquisa de expectativas das famílias como **contexto não elegível** para consenso do CPI exato.
- **7 pares com EUR:** mostram a pesquisa trimestral de analistas do BCE também como **contexto não elegível**.
- **EUR/USD pertence aos dois grupos:** são **13 pares distintos** com ao menos um desses contextos; os outros **15 pares** não recebem indevidamente essa informação de USD/EUR.
- Em todos os **28 pares**, o consenso de mercado para a próxima divulgação permanece **nulo nos dois lados**, assim como surpresa (`realizado − consenso`), erro posterior do modelo, placar macro relativo, ranking e melhor par do dia.
- A passagem do horário agendado de 10/11 ou 10/12, isoladamente, **não** gera número oficial realizado, erro de previsão nem viés. Uma divulgação precisa ser autenticada explicitamente.

## Barreiras para sair de `AGUARDAR`

1. Uma **previsão de consenso de analistas para o evento exato**, capturada com evidência de que existia **antes** de o resultado sair, período, conceito, unidade e origem.
2. Verificação independente da fonte original e de seu horário de captura.
3. Um resultado **oficial do mesmo evento**, autenticado após a divulgação, para calcular a surpresa; comparar evento com evento, não projeções com períodos distintos.
4. Testes prospectivos e fora da amostra para saber se isso acrescenta capacidade de prever retorno de preço de Forex, em vez de presumir que inflação alta significa moeda forte.

**Saída:** `D1=AGUARDAR`, `W1=AGUARDAR`, sem confiança numérica, meta de 80%/90%, gatilho M15, sinal de compra/venda ou operação real. **Zero** acesso HTTP, novos custos, ordens, publicação, worker ou agendamento.

**Arquivos:** `atlasquant_trader_g8_cpi_event_consensus_eligibility_lab.py` e `test_atlasquant_trader_g8_cpi_event_consensus_eligibility_lab.py`, registrados na suíte `quality-tests.yml`. Rascunho de laboratório empilhado sobre a etapa anterior de prontidão documental dos 28 pares.
