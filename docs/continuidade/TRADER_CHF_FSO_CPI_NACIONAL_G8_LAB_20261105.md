# AtlasQuant Trader — CHF CPI nacional FSO, LAB (05/11/2026)

Fonte oficial: https://www.bfs.admin.ch/en/newnsb/UA8hylpLYO6i e https://statistik.admin.ch/en/asset/36894291.
Publicação datada de 03/11/2026; referência **outubro/2026**; CPI nacional **101,7 pontos** (dezembro/2025=100), variação mensal **+0,2%**, variação anual **+1,5%**. A indicação de calendário de 08h30 NÃO é prova do instante real em que o documento estava acessível.

O leitor `atlasquant_trader_fso_chf_cpi_oct2026_text_lab.py` recebe texto UTF-8 fornecido pelo chamador, sem HTTP, autenticação do site, arquivo histórico independente ou uso comercial autorizado nesta etapa. Texto, colunas, índice e taxas são checados como **snapshot congelado**, não scraping genérico, e a observação local é guardada com SHA-256. O filtro conservador exige coleta em ou após 04/11/2026 UTC para não tratar uma data de divulgação como instante comprovado.

A integração opcional expande a matriz sintética G8 de 7 para 8 moedas: 28 pares podem conter números dos dois lados, mas **isso é apenas cobertura de exemplos**. Não há comparação metodológica harmonizada com demais CPI/HICP, não há consenso anterior, vintage point-in-time nem spot M15 independente. CPI suíço nacional não pode ser substituído silenciosamente por HICP suíço, e 101,7 pontos não é inflação de 101,7%.

**HARD NO-GO:** direções D1/W1/MN1 = AGUARDAR, sem spread, ranking, viés, operação, Worker, Scheduler, merge, deploy ou nova despesa. PR #1816 e interface preservadas.