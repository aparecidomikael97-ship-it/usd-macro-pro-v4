# AtlasQuant Trader — duas previsões, dois prazos de divulgação (LAB)

**Data do registro documental:** 06/11/2026.

O site oficial do Federal Reserve Bank of Cleveland, https://www.clevelandfed.org/indicators-and-data/inflation-nowcasting, exibia duas linhas distintas na seção de estimativa de inflação cheia CPI em 12 meses, atualizadas em 06/11:

| Competência da previsão de modelo | Projeção YoY não dessazonalizada | Primeira divulgação BLS agendada | Fonte da agenda |
| --- | ---: | --- | --- |
| Outubro 2026 | **3,74%** | 10/11/2026, 08h30 ET (13h30 UTC) | https://www.bls.gov/schedule/2026/11_sched_list.htm |
| Novembro 2026 | **3,88%** | 10/12/2026, 08h30 ET (13h30 UTC) | https://www.bls.gov/schedule/2026/12_sched_list.htm |

**Atenção à natureza da evidência:** transcrições manuais de texto público oficial, não HTML original arquivado nem horário exato de consulta atestado por terceiro. Pinagem de SHA-256 preserva **os arquivos do laboratório**, não cria prova adicional sobre o conteúdo HTML remoto. Para simulações cronológicas conservadoras, ambos os registros só são visíveis a partir de 07/11/2026 00:00 UTC.

**Critérios implementados:**

- Cada mês mantém seu próprio alvo, valor, prazo de publicação BLS e estado pré/pós-divulgação; o CPI de outubro publicado em novembro não pode ser usado como CPI de novembro, cuja divulgação está prevista para dezembro.
- Depois da data agendada, o resultado efetivo **continua não preenchido** até existir registro oficial BLS verificado; o calendário pode sofrer alterações.
- É proibido converter `3,88 - 3,74` diretamente em aceleração *realizada*, consenso econômico, força do dólar ou direção de EUR/USD; valores são previsões para horizontes distintos.
- Não há dados de consenso de analistas exatos, erro de previsão já calculado, métricas de acurácia ou autorização de sinal. Resultado: `AGUARDAR`.
- A inclusão na matriz dos 28 pares dependerá de contexto comparável de ambas as moedas e validação prospectiva; não é saída operacional.

**Próxima etapa:** depois de cada primeira divulgação, conferir a publicação BLS daquela competência e a medida CPI-U cheia YoY NSA; registrar a primeira versão do dado e somente então calcular erro do modelo, sem confundir isso com surpresa de consenso nem com direção do câmbio.

**Somente LAB.** Sem merge, deploy, cron, HTTP programático, contratação ou trade.
