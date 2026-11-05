# AtlasQuant Trader — CAD: CPI nacional da Statistics Canada (LAB)

**Pesquisa:** 05/11/2026. **Status:** página oficial localizada; leitor experimental para texto extraído, sem bytes HTTP originais nem prova histórica.

Fonte primária: Statistics Canada, The Daily, tabela 1 de setembro/2026:
https://www150.statcan.gc.ca/n1/daily-quotidien/261019/t001a-eng.htm

## Valores exibidos na tabela oficial

| Canadá, todos os itens, sem ajuste sazonal | Valor |
| --- | ---: |
| Índice setembro/2025 | 164,9 |
| Índice agosto/2026 | 169,8 |
| Índice setembro/2026 | 170,0 |
| Variação de agosto a setembro/2026 | 0,1% |
| Variação anual de setembro/2025 a setembro/2026 | **3,1%** |

O **nível do índice tem base 2002=100**; não é taxa percentual. O nível 170,0 e a taxa anual 3,1% não podem ocupar o mesmo campo. A tabela declara `Not seasonally adjusted` e `Date modified: 2026-10-19`. **Data de modificação da página não demonstra o horário da divulgação econômica.**

## Contrato de texto e bloqueios

`atlasquant_trader_statcan_cad_cpi_table_text_lab.py` recebe somente uma transcrição UTF-8 das linhas da tabela, no formato de texto separado por `|`, e um horário de coleta informado pelo pesquisador. Verifica título nacional exato, família **sem ajuste sazonal**, anos e meses das cinco colunas, **três** unidades `(2002=100)`, **duas** unidades `% change`, linha `All-items` única, data de modificação de calendário, formatos decimais, limites e horários conscientes do fuso. Recusa índices de províncias, resultados ajustados sazonalmente, duplicatas, HTML bruto ou taxas ausentes/inválidas.

As variantes `Food`, `All-items excluding food` e `All-items excluding food and energy` ficam separadas. A taxa anual divulgada na coluna final é mantida diretamente, **sem recálculo a partir dos índices arredondados**.

O parser **ainda não é um coletor HTTPS** e não interpreta HTML original. Um texto fornecido manualmente continua não autenticado, independentemente de hash. Seu estado é `LAB_CANADA_CPI_SUPPLIED_TABLE_TEXT_QUARANTINED`, sempre com autenticidade, instante de divulgação, vintage, consenso, direitos de redistribuição e viés real não verificados.

O teste de integração na matriz dos 28 pares aceita o CAD opcionalmente com `SUPPLIED_OFFICIAL_PAGE_TEXT_STRUCTURALLY_PARSED_UNATTESTED`. Em teste sintético com EUR, USD, GBP, JPY e CAD presentes:

- **10 pares** possuem duas moedas numericamente preenchidas;
- **15 pares** possuem uma moeda preenchida;
- **3 pares** não possuem nenhuma moeda preenchida.

Esses números são **cobertura de entrada sintética, não assertividade operacional**. Todas as comparações metodológicas, diferenças de inflação, rankings de força e vieses D1/W1/MN1 permanecem bloqueados.

## Próximas evidências

1. Quando AM12 online, coletar bytes e cabeçalhos reais da fonte, registrar URL, hash e horário, e validar extração de texto contra o conteúdo efetivo.
2. Identificar vintage histórica e hora original de divulgação independentemente da data de modificação da página.
3. Comprovar consenso antes do evento, preço M15 independente, custos, horários e qualidade de backtest fora da amostra.
4. Só depois estudar eventual comparação econômica CAD contra as demais moedas.

**HARD NO-GO**, sem merge, publicação, Worker, ordem real ou novo serviço pago. Continuidade na Draft PR #1815; UI da PR #1816 preservada.
