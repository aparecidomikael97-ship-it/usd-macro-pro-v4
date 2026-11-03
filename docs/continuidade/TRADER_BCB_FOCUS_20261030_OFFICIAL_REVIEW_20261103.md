# AtlasQuant Trader — revisão oficial do Focus (30/10; publicado em 03/11/2026)

**Fonte primária diretamente acessada por leitor público em 03/11/2026, sem custo ou cadastro:**
- Página oficial BCB: https://www.bcb.gov.br/publicacoes/focus/30102026 — exibe título "Relatório de Mercado — 30/10/2026" e **data de publicação 03/11/2026**; link "Baixar (pdf)" aponta ao arquivo abaixo.
- PDF oficial (2 páginas): https://www.bcb.gov.br/content/focus/focus/R20261030.pdf — **texto extraído e conferido** por ferramenta de leitura da página; **bytes PDF não foram baixados nem versionados**, não há SHA-256 dos bytes, prova de TLS assinada, horário independente de recebimento ou selo de custódia. Não substitui arquivo original.

## Dados confirmados documentalmente na tabela oficial

12 medianas anuais: IPCA 2026 **5,22%**, 2027 **4,76%**, 2028 **4,00%**; Selic para fim de ano 2026 **13,50% a.a.**, 2027 **12,50%**, 2028 **11,00%**; Câmbio (R$/US$) referência dezembro 2026 **5,34**, 2027 **5,40**, 2028 **5,40**; PIB 2026 **1,76%**, 2027 **1,20%**, 2028 **1,80%**. Por exemplo, as contagens 144 (IPCA), 143 (Selic), 120 (Câmbio) e 117 (PIB) referem-se aos respondentes **dos últimos 30 dias da edição de 2026**, não odds de eventos econômicos.

As oito linhas de 2026 e 2027 conferem com o arquivo mais antigo BCB 23/10 (medianas anteriores) e com os valores novos reportados na imprensa em 03/11. Agora a **existência da publicação oficial e os valores do texto do PDF foram conferidos**, mas **sem atestado criptográfico do arquivo PDF original**.

A página 2 traz categorias/datas adicionais, diferentes das expectativas anuais:

| Mediana Focus, edição 30/10 | Referência | Valor |
|---|---|---|
| IPCA, variação mensal | outubro/2026 | 0,27% |
| IPCA, variação mensal | novembro/2026 | 0,35% |
| IPCA, variação mensal | dezembro/2026 | 0,60% |
| Inflação 12 meses suavizada | horizonte móvel | 4,96% |
| Câmbio R$/US$, referência mensal | novembro/2026 | 5,32 |
| Câmbio R$/US$, referência mensal | dezembro/2026 | 5,34 |
| Selic, taxa de fim de mês | novembro/2026 | 13,50% a.a. |
| Selic, taxa de fim de mês | dezembro/2026 | 13,50% a.a. |

**Não inferir que Selic 13,50% de novembro significa um corte certo no Copom de 04/11.** A taxa pode mudar depois, há reuniões e cronogramas diferentes e essas medianas não são distribuição de probabilidades por reunião. A pesquisa Reuters de 33/48 respondentes esperando manutenção na reunião é outra população e outro tipo de pergunta — 68,75% é proporção de entrevistados, não probabilidade de mercado implícita.

## Controles incluídos

O módulo `atlasquant_trader_bcb_focus_official_review_lab.py` recebe a transcrição versionada em `docs/continuidade/TRADER_BCB_FOCUS_20261030_OFFICIAL_REVIEW_LAB.json`. Os campos e valores são travados contra 12 medianas anuais e oito mensais copiadas do texto da fonte oficial. Compara oito linhas de 2026/27 aos contratos Focus anteriores e à primeira leitura secundária, preservando cronologia e os estados de cada etapa. Rejeita registros extras, datas trocadas, cotação incoerente, mudança de fonte, denominação, tipo, valores falsos, amostras booleanas e alegação indevida de PDF original arquivado.

Para não simular informação pré-existente, a triagem documental usa um **corte conservador 03/11 às 15:00 UTC**: este é um controle de laboratório escolhido após a publicação do dia, **não o horário de publicação ou primeiro recebimento efetivamente atestado**. Nenhuma previsão ponto-no-tempo passa a ser certificada por este corte.

O resultado possui seis linhas descritivas WIN/WDO × D1/W1/MN1. Em todas: `directional_bias=AGUARDAR`, `probability_calibrated=null`, `actual_copom_decision_known=false`, `point_in_time_forecast_input_attested=false`, `can_feed_live_radar=false`, `can_feed_real_oos=false`, `trade_authorized=false`.

Os testes `test_atlasquant_trader_bcb_focus_official_review_lab.py` foram adicionados à suíte Quality CI. Passar nesses contratos prova coerência de transcrição e bloqueios, **não comprova autenticação original, rapidez da captura, previsões WIN/WDO nem OOS**.

### Próxima prioridade

Verificar o comunicado efetivamente publicado pelo Copom **após** a reunião e comparar com as hipóteses pré-evento já documentadas, sem inserir retrospectivamente o resultado como informação anterior. Para medir antecipação de preço, ainda faltam reprecificação de futuros DI, preço do dólar/índice no momento apropriado e protocolo de forecast pré-registrado.

**PR #1803 DRAFT / HARD NO-GO.** Sem contratação de fontes, cron, Worker, interface, Render, deploy, merge ou ordens.
