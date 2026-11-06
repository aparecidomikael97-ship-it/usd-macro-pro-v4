# AtlasQuant Trader — primeira previsão prospectiva (LAB, 06/11/2026)

**Objetivo:** começar um histórico de previsões guardadas *antes* do resultado oficial, para que o AtlasQuant não calcule precisão com dados que só ficaram conhecidos depois.

## Evidência pública pesquisada em 06/11/2026

1. **Fonte primária:** Federal Reserve Bank of Cleveland — https://www.clevelandfed.org/indicators-and-data/inflation-nowcasting
2. Linha consultada no texto público: `Inflation, year-over-year percent change` → `October 2026` → coluna `CPI` = **3,74%**, `Updated 11/06`. É estimativa do **modelo** de inflação cheia americana em doze meses (CPI headline YoY NSA), não consenso profissional nem CPI publicado.
3. **Calendário oficial:** Bureau of Labor Statistics — https://www.bls.gov/schedule/2026/11_sched_list.htm — primeira divulgação do CPI de outubro prevista para **terça-feira, 10/11/2026, às 08:30 ET (13:30 UTC)**. Horário de divulgação é um calendário que pode ser alterado pelo BLS; reconfirmar antes de usar.
4. **Proveniência:** transcrição manual da página oficial feita no dia 06/11; conteúdo JSON fixado por SHA-256. **Não possuímos os bytes HTML originais, hash da página ou horário exato de captura atestado independentemente.** O campo `Updated 11/06` é a data de atualização publicada pela fonte, não o instante exato da nossa consulta.
5. O portão conservador considera essa pesquisa visível a partir de **07/11/2026 00:00 UTC**. Até lá não permite acesso ao valor em simulações *as-of*. A previsão é anterior à divulgação **prevista** em 10/11, mas a prova permanece na categoria `transcrição manual`, não `captura assinada`.

## O que podemos e não podemos afirmar

- **Podemos** afirmar que o site oficial exibia uma previsão de modelo **3,74%** para outubro de 2026 na consulta de 06/11, e que o evento oficial estava agendado para 10/11.
- **Ainda não podemos** informar o CPI oficial de outubro, o erro dessa previsão, surpresa contra analistas, acurácia de um sistema D1/W1, força do USD ou direção para qualquer par Forex.
- Só após a publicação do CPI, com documento BLS verificado, poderemos calcular `realizado - 3,74` como **erro da previsão do modelo**, não como surpresa de consenso. Um único evento não fornece taxa de acerto confiável nem sinal de operação.
- O portão documental é **somente LAB**: retornará sempre `AGUARDAR`, nenhuma autorização para live Radar, scheduler, worker, trade ou deploy; custo extra zero.

## Próximo checkpoint

Depois de 10/11, consultar a primeira divulgação BLS e registrar período, unidade, número publicado, hora da publicação, URL oficial, original dos dados (se disponível) e hash. Confirmar se a previsão de 3,74% se referia exatamente à mesma série (headline CPI YoY NSA). Preservar os dois registros antes de qualquer comparação, e **não** confundir diferença entre modelo e observado com direção de EUR/USD.
