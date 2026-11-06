# AtlasQuant Trader — cadeia D1/W1 de evidências macro + previsão + MT5 M15 (LAB, 06/11/2026)

## Objetivo: parar de acumular módulos isolados

Esta etapa conecta **três controles existentes** para um único diagnóstico somente de laboratório:

1. `atlasquant_trader_fx_premove_lab.py`: exige que a previsão alegada tenha sido registrada antes de uma sessão D1/W1 no fechamento convencional de 17h de Nova York.
2. `atlasquant_trader_g8_macro_asof_lab.py`: verifica os metadados de inflação anual e juros das **duas moedas** do par, sem aceitar divulgação/captura futura.
3. `atlasquant_trader_mt5_m15_bars_csv_lab.py`: valida somente a **estrutura** de um CSV de candles M15, sem assumir o fuso do broker ou tratar o spread informado como custo real.

Novo orquestrador: `atlasquant_trader_fx_d1w1_evidence_chain_lab.py`, função `inspect_fx_d1w1_evidence_chain_lab(forecast_raw=..., macro_raw=..., as_of_utc=..., mt5_m15_csv_raw=...)`.

**A função só aceita os bytes originais de cada entrada e executa novamente os leitores.** Não aceita dicionários externos afirmando que já passaram. A previsão tem de apontar para o **SHA-256 exato dos bytes JSON macroeconômicos recebidos**, conter o **mesmo par** e declarar hora de criação igual à hora de decisão do envelope macro. Toda captura macro declarada, mesmo de um registro que não seria selecionado, deve ocorrer até o **data_cutoff_utc** da previsão. Se um indicador não existir, estiver antigo ou se um CSV M15 for inválido, o diagnóstico registra bloqueios explícitos.

## Bloqueios independentes mantidos obrigatoriamente

**Estrutura correta ≠ prova de que os dados estavam disponíveis na hora.** O vínculo SHA demonstra apenas que a previsão aponta para aqueles bytes; ele não atesta quando o material foi criado ou se a fonte era autêntica. Até com os três arquivos matematicamente consistentes, o diagnóstico mantém estes bloqueios:

- `MACRO_SOURCE_RELEASE_AND_VINTAGE_NOT_INDEPENDENTLY_ATTESTED`: sem testemunho externo de publicação, coleta e revisão da fonte;
- `FORECAST_NOT_EXTERNALLY_PRECOMMITTED_BEFORE_MOVE`: sem registro independente anterior ao período que demonstre que a previsão de fato existia;
- `M15_TIMEZONE_BID_ASK_AND_EXECUTION_UNVERIFIED`: CSV sem fuso de servidor, bid/ask executável e identidade da fonte atestados;
- `OUT_OF_SAMPLE_PREDICTIVE_ACCURACY_NOT_MEASURED`: não há medição de eficácia preditiva fora de amostra.

As taxas do BCE/Eurosistema que já foram capturadas são **referências diárias indicativas**. A exportação real MT5 de 116 barras é de **abril/2026**, sem janela compatível com as taxas diárias de **agosto–novembro**; 47 barras indicavam spread zero. Nenhuma operação foi ou será inferida a partir dessas amostras.

O módulo **não** calcula vieses, força de moeda, números macro, probabilidades ou acertos. Campos de saída permanentes: `fx_bias=null`, `operational_bias=AGUARDAR`, `validated_prediction_count=0`, `validated_accuracy=null`, `trade_authorized=false`, `worker_enabled=false`, `scheduler_enabled=false`, `new_cost_brl=0`.

Os cenários sintéticos do novo teste `test_atlasquant_trader_fx_d1w1_evidence_chain_lab.py` cobrem os 28 pares, D1/W1, CSV ausente/ruim, dados macro antigos/futuros, diferença de horário, pares trocados, hash não correspondente, registros capturados entre o corte dos dados e a criação do viés, além de confirmação de bloqueio mesmo com arquivos estruturalmente válidos. **Não representam assertividade real.**

## Próximo passo para evidência real

Quando o AM12 puder ser usado novamente, normalizar o horário do broker sob documentação confiável e exportar M15 numa janela alinhada aos dados macro. Registrar as previsões antes da sessão em armazenamento com timestamp externo, auditar as revisões das fontes econômicas e aferir a direção real posteriormente. A amostra deve incluir perdas, abstenções, taxa base, custo, tamanho e intervalo de confiança; **não usar 80%/90% como resultado sem demonstração.**

**HARD NO-GO:** PR #1815 isolada, interface #1816 intocada; sem merge, deploy, Worker, scheduler, contratação, operação real ou acesso à conta.
