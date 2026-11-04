# Trader — primeiro freeze prospectivo pré-CPI e triagem de consenso (LAB, 03/11/2026)

## Resultado prático
Uma estimativa pública **observada antes** do CPI de 10/11 foi registrada com data/hora declarada e agora ficará ancorada em um **commit GitHub**. Isso preserva o que NÓS anotamos antes do evento; **não é recibo autenticado do site, vintage imutável do provedor ou histórico validado para 90%**.

**Snapshot:** `TRADER_CPI_PROSPECTIVE_FREEZE_20261103.json`
- Observação de pesquisa: **03/11/2026 09:01:28.942 UTC** (declaração do ambiente de pesquisa, não horário independentemente auditado).
- Na página do Cleveland Fed a linha de **outubro/2026** ainda indicava atualização **11/02**.
- Nowcast outubro: CPI **0,24% m/m SA**; núcleo **0,21% m/m SA**; CPI **3,74% a/a NSA**; núcleo **2,48% a/a NSA**.
- Próximo BLS CPI outubro: **10/11/2026 13:30 UTC** (8h30 EST), ainda não divulgado na observação.
- Consenso de mercado, dado realizado, licença de redistribuição da página, HTML/headers de resposta e custódia externa: **não comprovados**.

Fontes primárias: https://www.clevelandfed.org/indicators-and-data/inflation-nowcasting e https://www.bls.gov/schedule/news_release/cpi.htm.

O módulo `atlasquant_trader_cpi_prospective_freeze_lab.py` conserva os quatro valores e calcula SHA-256 do **registro declaratório**. Antes de 10/11 mostra apenas `LAB_PROSPECTIVE_DOCUMENTARY_NOWCAST_PRE_EVENT`. Depois de 10/11, se não houver novo fato, `LAB_CPI_EVENT_PASSED_OUTCOME_NOT_INGESTED`; **não reaproveita a previsão como valor divulgado**. Um modo de teste calcula erro absoluto somente com resultado **sintético, identificado e pós-evento**, sem jamais relatar backtest real.

## Pesquisa de fornecedores de consenso (sem adesão e sem consumo de API)

| Origem | Pode fornecer o quê? | Bloqueio no LAB |
| --- | --- | --- |
| **Fed de Cleveland** | Nowcast do CPI/PCE e núcleo, atualizado em dias úteis | **Modelo**, não consenso dos analistas. Página dinâmica, sem vintage histórica comprovada nesta pesquisa |
| **Trading Economics** | Calendário e consenso segundo documentação da própria API | API requer assinatura/plano; **não autorizada compra** nem consulta autenticada |
| **Finance Calendar** | Divulgação e calendário de 8 moedas; anúncio comercial diz incluir consenso | **Contradição documental:** referência técnica atual afirma explicitamente que `consensus` **não é coletado** e retorna `null`; outra página promete preenchimento ~2 dias antes. Também há informações conflitantes sobre chave/cota. **Não promover como consenso** |
| **Philadelphia Fed SPF** | Pesquisa periódica de previsões | **Trimestral**; não é consenso exato do CPI publicado no dia 10/11 |

Referências oficiais dos fornecedores:
- https://tradingeconomics.com/api/pricing.aspx e https://docs.tradingeconomics.com/get_started/
- https://www.financecalendar.com/api/reference/ (campo `consensus`) e https://www.financecalendar.com/api/forex-calendar/ (texto comercial)
- https://www.philadelphiafed.org/surveys-and-data/real-time-data-research/survey-of-professional-forecasters

### Decisão de compra/uso
**Nenhum fornecedor foi contratado, chave gerada ou API consultada em produção.** Finance Calendar pode voltar para avaliação se corrigir documentação e comprovar origem/quotas/termos, mas **não** é fonte de consenso homologada. Até então, `market_consensus=null` e a inferência de direção continua **AGUARDAR**.

## O que poderemos medir depois do evento

Após a publicação oficial do BLS, com recibo de origem e hora independente, comparar `CPI_real_m/m_SA` e `núcleo_real_m/m_SA` com os **modelos congelados** nesta data. Isso medirá inicialmente **erro do nowcast**, não taxa de acerto direcional do Forex. Para avaliar EUR/USD/28 pares e índices, será necessária a previsão direcional predefinida, preço futuro independente, contexto BCE/Fed/risco, regime, tamanho da amostra e avaliação walk-forward OOS.

O commit GitHub e os jobs de CI ajudam a demonstrar que **o nosso registro existia antes do CPI**. Não demonstram sozinhos que o valor estava no site na hora declarada, que tínhamos consenso do mercado, ou que a política futura do Fed fortaleceria o USD.

**PR #1803: DRAFT, LAB / HARD NO-GO.** Visual aprovado, `main`, contas, Worker, cron, deploy, ordens e gastos intocados. Sem prometer 90% de probabilidade.
