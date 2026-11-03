# AtlasQuant Trader — entrada offline de histórico B3 autorizado (LAB, 03/11/2026)

**Objetivo:** preparar a análise do gap de WIN e WDO em 04–05/11 sem violar a proibição de coleta automatizada da página pública de boletins da B3, sem contratar serviços e sem antecipar a decisão do Copom. Não há arquivo de cotações reais neste PR.

## Regra principal

A B3 informa que a página de boletins diários/Pesquisa por Pregão não pode ser utilizada para **coleta automatizada, inclusive com ferramentas de IA**:
https://b3.com.br/pt_br/market-data-e-indices/servicos-de-dados/market-data/historico/boletins-diarios/pesquisa-por-pregao/pesquisa-por-pregao/

**Não automatizar downloads dessa página.** É possível avaliar no futuro dados exportados por meio já utilizado e autorizado pelo proprietário (por exemplo terminal/corretora), mas a licença e os direitos de upload/armazenamento/reutilização precisam ser confirmados para cada fornecedor. A mera posse de uma planilha **não prova permissão de uso**. Nenhum acesso a corretora ou serviços externos foi configurado.

## Entrega do laboratório

`atlasquant_trader_b3_offline_export_intake_lab.py` recebe **bytes de CSV somente na memória**, com cabeçalho exato:

`instrument,contract_id,session_role,quote_type,observed_at_utc,price_points`

Aceita 2 ou 4 registros: um `PRE_20261104` e um `POST_20261105` para cada instrumento analisado. Os contratos **candidatos**, conforme calendário B3, são `WINZ26` e `WDOZ26`, exigidos iguais nas duas observações. Não são prova de liquidez nem de negócio real.

O manifesto exige: método `USER_MANUAL_EXPORT_UNVERIFIED` ou `SYNTHETIC_FIXTURE`, nome de origem e anotação `USER_NOTE:`, `csv_sha256`, indicação clara de que coleta automatizada **não** foi feita e o marcador `NOT_INDEPENDENTLY_REVIEWED` para os direitos de uso. A origem e os direitos **não são autenticados por esse manifesto**, pois os campos são declarados pelo chamador. SHA-256 detecta alteração interna dos bytes em relação ao manifesto, **não confirma origem do mercado**.

Bloqueia contratos diferentes, séries de outro vencimento, preço de ajuste, campos intrusos, linhas extras/duplicadas, formato de preço inválido, fórmulas de planilha, dados com timezone ausente, tick depois do fechamento regular em 04/11, tick antes da abertura candidata de 05/11 ou observação posterior ao momento de avaliação. Não coleta dados e não grava arquivos.

Os valores só produzem **diferenças aritméticas candidatas** entre duas cotações declaradas. Não há garantia de que sejam realmente o último negócio antes do evento e o primeiro negócio da sessão seguinte. Mesmo para um arquivo alegadamente real:

- `market_reaction_real_verified=false`
- `market_data_access_rights_independently_verified=false`
- `full_market_tick_history_available=false`
- `copom_caused_the_gap=false`
- `market_price_prediction_accuracy=null`
- `directional_bias=AGUARDAR`
- `can_feed_live_radar=false`, `trade_authorized=false`
- `automated_collection_enabled=false`, `b3_boletins_ai_scraping_enabled=false`
- `worker_enabled=false`, `scheduler_enabled=false`, `render_configuration_changed=false`

**Os exemplos de testes são fictícios.** Nenhum valor de WIN/WDO de 04–05/11 foi obtido, e a decisão de juros do Copom permanece pendente até a divulgação oficial.

## Exigências antes de usar dados reais

Conferir separadamente a licença da origem do arquivo, identidade do contrato completo e vencimento, calendário B3 e exceções da sessão, ticks com horários/negócios verificáveis, custo do spread e slippage, o comunicado oficial e o papel de outras notícias no gap noturno. Não chamar a diferença de causalidade do Copom. Não transformar o estudo de um único evento em taxa de acerto estatística.

`test_atlasquant_trader_b3_offline_export_intake_lab.py`: 32 testes sintéticos de esquema, fonte, direitos pendentes, precisão temporal e proteção contra falsas cotações. A qualidade integrada é verificada pela CI no PR #1803; nenhuma aprovação presumida antes de terminar.

**LAB / HARD NO-GO: sem novos custos, Render, Worker, scraping, schedulers, merge, deploy, live Radar, alteração visual ou ordens.**
