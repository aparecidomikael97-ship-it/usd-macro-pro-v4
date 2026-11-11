# AtlasQuant Trader — 28 FX D1: vínculo real dos arquivos à porta de precisão (LAB, 11/11/2026)

## Lacuna

A revisão anterior implementou no orquestrador `D1_28FX_DATE_COVERAGE`, mas sua relação de pares presentes ainda era fornecida pelo chamador. Alguém poderia apresentar uma lista declarando 28/28 enquanto o arquivo do GBP/NZD não continha a data. Isso bloquearia a validade científica da interpretação do relatório.

## Novo encadeamento: sem atalhos documentais

`atlasquant_trader_fx_d1_archive_precision_join_lab.py` (função `inspect_d1_archive_precision_join_lab`) utiliza arquivos **locais de pesquisa**, sem acessar MT5:

1. Abre os sete manifestos originais de lotes AM12, verifica schema, posições de lotes, segurança e o conjunto completo de **84 IDs únicos** (28 moedas × M15/D1/W1). Apenas os arquivos D1 são abertos e recalculados; integridade dos M15/W1 não é garantida por este módulo.
2. Abre os **28 arquivos `SYMBOL_D1_closedbar.csv.gz`**, recusa symlinks e arquivos desproporcionais, limita descompressão, valida 500 barras, ordem temporal, OHLC positivo, valores básicos, campos e SHA-256 do **CSV descompactado** comparado ao manifesto original.
3. Exige horários documentais de captura **anteriores à decisão** e posteriores ao fechamento nominal da última vela D1. Não converte capturas retrospectivas em evidência prospectiva: dados de 2025 coletados apenas em novembro de 2026 não provam previsões feitas em 2025.
4. Deriva a presença da data escolhida pelos timestamps **efetivamente lidos** em cada CSV, não aceita apenas a lista de 28 moedas fornecida pelo chamador. Se alguém fornecer lista ou horário conflitante, bloqueia.
5. Usa `dataclasses.replace` para fornecer os dados extraídos à `inspect_fx_precision_orchestrator_lab`, que **reexecuta as sete verificações** e rejeita uma coorte D1 incompleta, sem alterar o pacote de entrada nem operar.
6. Mesmo em conformidade documental, `validated_directional_accuracy=null`, `calibrated_direction_probability=null`, `operational_bias=AGUARDAR`, `trade_authorized=false`, `publishable=false`.

Este módulo é propositalmente **fail-closed**: hashes e horários do próprio computador podem ser falsificados em conjunto. Atestado de origem Pepperstone, horário real de divulgação dos indicadores, convenção de fechamento D1 do servidor, custo bid/ask e rastreabilidade externa da previsão **continuam pendentes**.

## Testes adversariais

`test_atlasquant_trader_fx_d1_archive_precision_join_lab.py` gera apenas fixtures sintéticas e cobre:

- 28/28 e sete estágios, sem autorização de negócio;
- GBP/NZD ausente da data mas ainda com arquivo íntegro e 500 barras (27/28, `AGUARDAR`);
- falsidade da lista de 28/28 versus bytes efetivos;
- SHA adulterado, gzip substituído, CSV faltando, manifesto faltando ou duplicado;
- suposta captura após a decisão ou antes do fechamento da barra;
- horário da captura alterado pelo chamador;
- horário de inspeção sem timezone;
- prova de que o algoritmo não escreve nos arquivos.

Os cenários artificiais geram barras todos os dias, inclusive fins de semana, estritamente para testar parsing. **Não representam o mercado**, não permitem backtest ou garantia de resultado.

## Referência local real AM12

O estudo separado no AM12 recontou, com os manifestos de 07/11, **14.000 candles D1** e as cinco datas com cobertura incompleta (incluindo GBP/NZD 30/09/2025). Os arquivos antigos foram capturados em 08/11/2026 e não podem ser usados como prova **prévia** de uma decisão de 2025. A nova barreira preserva essa distinção.

**Escopo e implantação:** módulo de pesquisas em PR #1851, execução Python 3.11/3.12, sem merge, deploy, trabalho externo, despesas, sinal ou negociação.
