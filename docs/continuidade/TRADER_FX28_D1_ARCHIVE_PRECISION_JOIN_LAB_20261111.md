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

## Integração obrigatória do estudo macroeconômico

A revisão seguinte conecta `atlasquant_trader_fx_macro_precision_byte_join_lab.py` diretamente à função de verificação de arquivo, sem invocar o orquestrador de sete estágios por uma via que aceite apenas presença declarada de pares. O argumento `d1_archive_root` é **necessário para qualquer candidato**, embora permaneça opcional na assinatura para que chamadas antigas falhem com `LAB_MACRO_PRECISION_ABSTAIN`, em vez de iniciar um fluxo alternativo. O módulo retorna `d1_archive_bytes_gate_state`, `d1_archive_bars_checked`, `d1_archive_series_bytes_matched` e seus estágios de pesquisa.

Se não houver arquivo, se os horários forem posteriores à decisão ou se qualquer SHA-256 divergir, o relatório mantém os dados macro analisados, **mas não fornece candidato de direção**. A ausência de GBP/NZD comprovada nos arquivos também bloqueia o candidato quando os documentos macro são sinteticamente completos.

O histórico AM12 de novembro não pode autenticar decisões feitas em 2025. A ligação é necessária para pesquisa documental, mas jamais atesta a corretora, o horário de disponibilidade dos preços, a validade dos indicadores macro nem uma taxa de acerto de 80%.

### Escopo da obrigatoriedade

A porta é obrigatória neste **estudo combinado de bytes macro e precisão**. Outros módulos internos podem continuar a executar verificações independentes para depuração e pesquisa, mas seus resultados permanecem `AGUARDAR` e não são um atalho autorizado para radar ou publicação. Qualquer interface pública exigirá sua própria proibição explícita de bypass.

### Segundo ponto de integração: CPI semântico

A bateria revelou que `atlasquant_trader_g8_cpi_semantic_byte_join_lab.py` chamava o estudo macro sem repassar o caminho do arquivo D1. Agora o argumento opcional `d1_archive_root` é transmitido a ele. **Omitir esse argumento não produz qualquer candidato**; o estágio `D1_ARCHIVE_BYTES_CUSTODY` bloqueia a pesquisa. Quando a fixture sintética tem sete manifestos e 28 CSVs válidos, os testes conseguem alcançar e conferir separadamente o veto posterior `M15_PRICE_COST`.

O relatório semântico preserva `upstream_d1_archive_bytes_gate_state` e marca a proveniência/cronologia como não autenticadas. Um status de valor CPI conciliado com bytes do próprio chamador **não equivale** a uma hipótese direcional ou prova independente da fonte.
