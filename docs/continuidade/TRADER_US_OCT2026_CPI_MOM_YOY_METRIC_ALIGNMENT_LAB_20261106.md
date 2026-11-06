# AtlasQuant Trader — EUA: CPI de outubro/2026, ausência do anual e consenso mensal (LAB)

**Pesquisa:** 06/11/2026. **Visível no LAB somente após:** 07/11/2026 00:00 UTC. **Sem publicação, sinal ou negociação.**

## Correção prioritária de conceito econômico

O Bureau of Labor Statistics (BLS) não publicou o índice **CPI-U all-items de outubro de 2025**, em decorrência da paralisação federal e da ausência de coleta correspondente. Seu FAQ oficial diz que, para a maioria das séries sem índice de outubro/2025, **não serão divulgadas variações de 12 meses referentes a outubro/2026**. O all-items é uma dessas séries. Portanto, a projeção anual documental do Fed de Cleveland para outubro/2026 (**3,74%**) não pode ser subtraída de uma variação anual do BLS que estará **indisponível** nessa divulgação.

Fontes primárias:

- [BLS: impacto da paralisação de 2025 sobre o CPI, especialmente perguntas 2 e 16](https://www.bls.gov/cpi/additional-resources/2025-federal-government-shutdown-impact-cpi-faq.htm)
- [BLS: explicação das séries all-items e core sem dado de outubro de 2025](https://www.bls.gov/bls/2025-lapse-revised-release-dates.htm)
- [BLS: calendário de novembro/2026](https://www.bls.gov/schedule/2026/11_sched_list.htm)

A divulgação do CPI de outubro/2026 está agendada para **10/11/2026, 08h30 no horário de Nova York (13h30 UTC)**. Um horário previsto **não é** prova de que o resultado foi publicado, nem de seu número.

## Expectativa disponível para a medida correta

A [análise da Reuters de 06/11/2026](https://www.reuters.com/business/take-five/global-markets-themes-graphic-2026-11-06/) relata um levantamento segundo o qual economistas esperavam **+0,3% na variação mensal** do CPI de outubro. É uma referência documental para a **medida mensal, com ajuste sazonal**, distinta da previsão **anual** de 3,74% do modelo Cleveland Fed.

| Medida | Referência pré-publicação | Pode ser comparada ao primeiro resultado oficial de novembro? | Estado LAB |
|---|---|---|---|
| CPI-U all-items **anual**, outubro/2026 | Fed Cleveland: modelo **3,74%** | **Não**; índice all-items de outubro/2025 não foi publicado | Bloqueada a surpresa anual |
| CPI-U all-items **mensal** (ajustado), outubro/2026 | Reuters: consenso relatado **0,3%** | Mesmo alvo de indicador/período, em princípio; falta o resultado oficial e prova de captura ponto-no-tempo | Apenas candidato documental |
| CPI-U de novembro/2026, **anual** | Fed Cleveland: estimativa de modelo **3,88%** | Outro período e outro evento; não misturar com outubro | Não é consenso do evento de outubro |

O arquivo de pesquisa é uma **transcrição humana fixada por SHA-256** no repositório. Isso permite descobrir adulterações posteriores dos bytes locais, **não** atesta a página original nem o exato instante em que a previsão dos analistas foi coletada. O número mensal **não é introduzido como consenso autenticado** e nenhum resultado oficial de outubro é inventado.

## Aplicação na Matriz de 28 pares

- **7 pares com USD**: informação de que a variação anual de outubro não será publicada e referência pré-evento mensal relatada de 0,3%; sem viés.
- **21 pares sem USD**: não herdam informação específica do CPI americano.
- **28 pares**: `D1=AGUARDAR`, `W1=AGUARDAR`; sem surpresa, ranking, "melhor par", acurácia, decisão M15 ou autorização de negociação.
- Mesmo após 10/11/2026 13h30 UTC, a passagem do relógio **não cria** dado oficial realizado.

## Critério para avançar

Será necessário comprovar a previsão de mercado existente antes da divulgação, com **instante e versão verificáveis**; obter o resultado **oficial mensal** do mesmo evento depois da divulgação; guardar unidades e eventuais revisões; e só então estudar a surpresa mensal em conjunto com retornos de preço futuros, sem antecipar informação. Medir surpresa não equivale a demonstrar vantagem preditiva ou 80–90% de acerto.

**Arquivos:** recibo `TRADER_US_OCT2026_CPI_MOM_YOY_METRIC_AVAILABILITY_CONSENSUS_LAB_20261106.json`, módulo `atlasquant_trader_us_oct2026_cpi_metric_availability_consensus_lab.py` e testes homônimos. Sem HTTP no código, trabalhadores, cron, custos novos ou ordens.
