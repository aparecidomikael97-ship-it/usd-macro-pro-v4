# AtlasQuant Trader — AUD / CPI mensal ABS original — LAB, 05/11/2026

## Fonte oficial e valores do anúncio

- ABS, anúncio específico (não URL dinâmica `latest-release`): https://www.abs.gov.au/media-centre/media-releases/cpi-rose-43-year-september-2026
- ABS, publicação detalhada do período: https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/consumer-price-index-australia/sep-2026
- Série alvo: `All groups CPI, Australia, monthly and annual movement (%)` **original/não ajustada sazonalmente**, não *trimmed mean* nem **seasonally adjusted**.
- Mês de referência: **setembro/2026**. Variação mês a mês **+0,8%**; variação em 12 meses **+4,3%**. Agosto/2026: variação mensal **+0,4%** e anual **+4,0%**.
- Data/hora exibida no comunicado: **28/10/2026 11:30am AEDT**. O leitor exige relógio de coleta que não anteceda a interpretação desse horário (00h30 UTC). Isso é apenas consistência temporal da entrada, **não prova independente do primeiro instante de publicação**.
- A série completa mensal é diferente das séries trimestrais anexas na página e do antigo indicador mensal incompleto usado até setembro/2025. O ABS inclui também uma série SA (+0,6% m/m, +4,4% a/a em setembro/2026), que **não substitui** a original para o objetivo deste leitor.

## Trabalho implementado (somente dados sintéticos)

1. `atlasquant_trader_abs_aud_cpi_monthly_text_lab.py` recebe texto UTF-8 **fornecido**, não faz requisições HTTP, verifica título e horário do release, cabeçalhos, narrativa e valores de agosto/setembro, recusa duplicatas, formatos inválidos e a substituição pela versão ajustada. Registra SHA-256 do texto fornecido e horário de observação local. Trata-se de um **validador de snapshot fixo** do comunicado de setembro/2026, não de um extrator genérico para meses futuros.
2. `atlasquant_trader_g8_numeric_inflation_coverage_lab.py` ganha entrada AUD opcional; metadados incluem a frequência `MONTHLY`, mês `2026-09`, taxa a/a `4.3` e proveniência `SUPPLIED_OFFICIAL_PAGE_TEXT_STRUCTURALLY_PARSED_UNATTESTED`.
3. Para `AUD/USD`, as observações sintéticas têm o mesmo mês e frequência, mas **metodologias não harmonizadas**, sem diferença de inflação, ranking ou viés calculado. Para `AUD/NZD`, a divergência de frequência é bloqueada: mensal contra trimestral, mesmo ambos se referindo ao final de setembro.
4. Em uma montagem **sintética** opcional de sete moedas (EUR/USD/GBP/JPY/CAD/NZD/AUD), há 21 pares com dados dos dois lados, 7 com um lado e 0 sem números. CHF permanece sem valor numérico observado. Não é cobertura real automática nem histórico verificável.

## Limites e regras preservadas

- Página pública consultada para planejamento e conferência de valores; **não houve captura original autenticada no AM12** nesta etapa. Testes de parser usam texto montado segundo o formato informado no site. `source_sha256` identifica somente os bytes fornecidos, sem autenticar o emissor.
- Não foram comprovados um consenso coletado antes do anúncio, instante de divulgação por autoridade independente, vintage histórica, direitos de redistribuição comercial nem preço de mercado independente para validação externa.
- **HARD NO-GO:** D1/W1/MN1 `AGUARDAR`; sem ativação de Radar ao vivo, sinais, backtest declarado válido, Trader automático, Worker, scheduler, merge, deploy ou custos novos. A PR de interface #1816 não foi tocada.
