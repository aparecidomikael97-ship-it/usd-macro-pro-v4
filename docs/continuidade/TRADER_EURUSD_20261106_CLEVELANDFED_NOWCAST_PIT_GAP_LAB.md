# AtlasQuant Trader — Cleveland Fed: modelo de inflação ≠ consenso (LAB)

**Checkpoint:** 2026-11-06. **Escopo:** documentar a possibilidade de usar previsões de inflação com data original, **sem** atribuir ao sistema previsões passadas que não foram comprovadas.

## Fonte primária verificada

- Federal Reserve Bank of Cleveland: https://www.clevelandfed.org/indicators-and-data/inflation-nowcasting
- O Fed de Cleveland informa que publica estimativas de inflação por modelo em dias úteis, por volta das 10h da manhã (Eastern Time). **Não são consenso de mercado**.
- A fonte distingue CPI mensal dessazonalizado, CPI trimestral anualizado e CPI em doze meses. O **headline CPI em doze meses** usa dados **não dessazonalizados**. Misturar medidas cria uma comparação falsa.
- O site descreve um gráfico histórico comparando previsões com a primeira divulgação oficial. Essa existência **não prova por si só** a data, o conteúdo e a imutabilidade de um arquivo original de uma sessão específica.

## Lacuna objetiva do caso setembro de 2026

1. A divulgação oficial do CPI americano de setembro ocorreu em 14/10/2026 (já documentada no laboratório anterior). O alvo de pesquisa é a estimativa de **13/10/2026**, antes da divulgação.
2. No levantamento realizado em 06/11/2026 não foi obtido um **arquivo oficial original verificável**, com número explícito do nowcast de 13/10, horário de publicação independentemente comprovado e hash do conteúdo capturado na data.
3. Algumas páginas jornalísticas reproduzem valores supostamente desse nowcast. **Não são o arquivo original oficial** nem satisfazem o teste de disponibilidade no momento (*point-in-time*, PIT); não são transcritos neste caso.
4. Um valor de nowcast mostrado **hoje** pelo site é uma observação de outra data; não pode ser retroativamente marcado como conhecido em 13/10.
5. Mesmo com um nowcast original comprovado, a diferença entre CPI divulgado e **previsão de modelo** seria um *erro desse modelo*, **não** uma surpresa diante de consenso de analistas, e muito menos uma direção comprovada para EUR/USD.

## Garantias implementadas

- Casebook de pesquisa com SHA-256 fixo, fonte primária e classificação de modelo, sem número de estimativa inventado.
- Depende das provas cronológicas anteriores de política, CPI e pesquisas ECB/NY Fed; falha de qualquer antecessor fecha o portão.
- Pesquisa de 06/11 só fica visível ao motor no relógio conservador **07/11/2026 00:00 UTC** (não reescreve conhecimento disponível em outubro).
- Campos `oct13_model_nowcast_percent`, `us_september_cpi_model_error_percentage_points`, `matched_pre_release_market_consensus_by_currency` e `september_cpi_surprise_by_currency` sempre ficam vazios.
- Resultado operacional: `AGUARDAR`; sem sinal, ordens, confiança estimada, HTTP, cobrança, cron, worker ou publicação.
- Testes offline rejeitam tentativas de inserir 3,60%, 3,70%, evidências falsas, unidade trocada, relógio ingênuo, arquivo alterado ou dados ancestrais adulterados.

## Próximo passo autorizado apenas para LAB

Localizar ou capturar **vintage histórico oficial original** do nowcast de 13/10/2026 para setembro de 2026. Exigir prova verificável de disponibilização antes do CPI, conteúdo integral, hash, mesma medida (headline CPI YoY NSA) e competência econômica. Se não houver, manter `AGUARDAR`. Para eventos futuros, preservar captura com carimbo temporal durante o período em que a fonte ainda exibe a previsão.

**Sem merge/deploy, custos, operações reais ou metas de 80%/90% declaradas.**
