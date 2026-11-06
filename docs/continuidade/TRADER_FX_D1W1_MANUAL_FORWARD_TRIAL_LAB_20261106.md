# AtlasQuant Trader — protocolo de ensaio prospectivo manual D1/W1 (LAB, 06/11/2026)

## Objetivo concreto

Iniciar uma avaliação futura **sem usar o preço depois do movimento para criar a previsão**. Esta revisão estabelece janelas Forex válidas e um formato de *candidato ao pré-registro*, mas **NÃO inicia um estudo real automaticamente e NÃO fabrica uma direção para nenhum par**.

Novo módulo `atlasquant_trader_fx_manual_forward_trial_lab.py`, com duas funções sem acesso à rede, sem gravação de arquivo e sem agendamentos:

- `plan_next_fx_forward_trial_lab(as_of_utc=...)`: identifica a próxima sessão diária D1 e a próxima sessão semanal W1, na convenção das **17h de Nova York**, considerando o fuso `America/New_York`, o horário de verão e o fim de semana. Requer **60 minutos de antecedência** antes do começo do período. Abrange os 28 pares G8: **56 vagas de ensaio**, não 56 previsões. Nenhuma direção é gerada e nenhuma disponibilidade de preço é inferida.
- `inspect_fx_forward_candidate_lab(forecast_raw=..., macro_raw=..., as_of_utc=...)`: recebe bytes JSON de previsão **fornecidos externamente** e bytes JSON macro, passa pelos validadores já existentes, compara símbolo, horizonte, início/fim da sessão, horário declarado de criação, instante da decisão e corte de dados, e exige vínculo pelo **SHA-256 dos bytes exatos**. Requer que o horário declarado de criação da previsão esteja no máximo 5 minutos antes da execução manual. Não requer M15 do resultado, pois a previsão precisa ser registrada antes da sessão.

**Exemplo de janela planejada, não previsão:** se executado na sexta-feira, 06/11/2026 às 12h50 UTC, o plano D1 começa domingo 08/11 às 22h UTC e termina segunda-feira 09/11 às 22h UTC. O W1 inicia domingo 08/11 às 22h UTC e termina sexta-feira 13/11 às 22h UTC. Horário de inverno de Nova York: 17h NY = 22h UTC. Essas horas são uma convenção de pesquisa, não atestação dos horários de uma corretora.

## Por que o resultado permanece bloqueado

Um **hash não prova a data de criação**, nem um timestamp escrito num JSON prova que existia antes do período. Mesmo um candidato perfeitamente coerente fica em `LAB_FORWARD_CANDIDATE_HASH_BOUND_AWAITING_EXTERNAL_WITNESS`. O campo `candidate_direction_claim` reflete unicamente uma direção **alegada** pelo criador do arquivo de entrada: não é sinal, recomendação ou viés operacional. `NEUTRO` significa abstenção, nunca acerto binário.

É necessária uma testemunha externa verificável (por exemplo, registro criado antes da sessão em plataforma independente com horário de servidor e conteúdo não editável sem rastro), a versão congelada do modelo, a prova das publicações originais e a aferição posterior dos preços M15/bid/ask com fusos e custos. Registrar a previsão hoje não valida automaticamente sua qualidade nem implica o direito de redistribuir dados do provedor.

A função mantém permanentemente `candidate_external_precommit_witnessed=false`, `candidate_macro_publication_times_verified=false`, `future_outcome_already_known=false`, `validated_prediction_count=0`, `validated_accuracy=null`, `directional_bias=null`, `operational_bias=AGUARDAR`, `trade_authorized=false`.

### Dados reais disponíveis vs. ainda pendentes

Já obtivemos XML do BCE via HTTPS no AM12 e uma amostra de 116 candles EURUSD M15 do MT5, porém a amostra M15 é de **abril/2026**, enquanto o XML tem referências de **agosto–novembro/2026**. Falta uma série alinhada, o fuso/bid-ask verificável e entradas macro com recibos de disponibilidade *point in time*. A antiga conta MT5 Demo apresentou falha de autenticação; **nenhum sinal real deve ser derivado dessas amostras**.

### Garantias de implantação

Os novos testes `test_atlasquant_trader_fx_manual_forward_trial_lab.py` usam exclusivamente JSON e CSV simulados e conferem os 28 pares, horários NY EDT/EST, mudança do DST, falta de antecedência, previsões antigas/futuras, dados macro posteriores ao corte, fonte macro trocada e abstenções, sempre sem sinal operacional.

**HARD NO-GO**: desenvolvimento na PR #1815, interface da PR #1816 intocada. Sem Worker/Scheduler, monitoramento automático, API paga, envio de ordens, publicação, merge, deploy ou gasto novo.
