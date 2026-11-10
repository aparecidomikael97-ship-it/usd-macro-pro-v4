# AtlasQuant Trader — coerência do CPI americano na matriz G8 (LAB)

Data da revisão: 2026-11-10 (UTC). Escopo: recepção **sintética** dos
indicadores macro `CPI_YOY` para D1/W1; sem operação, conta ou conexão MT5.

## Problema corrigido

O leitor de resposta da API BLS já recusava calcular o YoY de outubro de 2026
usando um índice inventado de outubro de 2025, e o leitor de capturas já
rejeitava horários declarados anteriores à liberação oficial. Mas o validador
G8 dos 28 pares recebia outro envelope, com campos declarados pelo chamador,
e não aplicava esses dois vetos. Essa inconsistência permitia um estado de
"metadados completos, não atestados" em uma rota paralela.

## Contratos agora alinhados

- **USD CPI setembro/2026:** publicação oficial BLS em 2026-10-14,
  08h30 EDT = **12h30 UTC**. `published_at_utc` e `captured_at_utc`
  anteriores a esse piso bloqueiam a recepção da matriz G8.
- **USD CPI outubro/2026:** publicação oficial BLS em 2026-11-10,
  08h30 EST = **13h30 UTC**. A mudança de horário de verão é explícita.
- **Índice BLS outubro/2025 ausente:** a divulgação de novembro de 2026
  reconhece a ausência da base de comparação. A matriz G8 rejeita qualquer
  `CPI_YOY` americano que tente usar outubro/2025 como observação ou
  como mês homólogo de outubro/2026.
- O veto é **por moeda**. Dado USD rejeitado afeta os sete pares com USD;
  os demais pares não são descartados automaticamente.
- As demais frequências, fontes, moedas e eventos preservam o comportamento
  conservador do laboratório. Nada é convertido em força monetária, sinal,
  pontuação ou probabilidade validada.

Fontes primárias:

- https://www.bls.gov/news.release/archives/cpi_10142026.htm
- https://www.bls.gov/news.release/archives/cpi_11102026.htm

## Limites mantidos

Mesmo após um carimbo de horário plausível, **não** há prova independente da
origem, horário da primeira divulgação, revisão histórica nem custódia do
arquivo. O sistema continua retornando `AGUARDAR` e `trade_authorized=False`.
O registro é uma proteção pontual para fatos oficialmente conhecidos, não
um calendário universal de divulgações, nem autorização de backtest ou radar.

Testes offline incluem os limites de segundos das divulgações e a propagação
da rejeição para os sete cruzamentos do USD. A publicação segue em PR de LAB.
