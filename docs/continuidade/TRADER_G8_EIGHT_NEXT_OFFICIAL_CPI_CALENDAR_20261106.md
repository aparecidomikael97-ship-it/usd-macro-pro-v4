# AtlasQuant Trader — próximas divulgações oficiais de CPI das oito moedas (LAB)

**Data da pesquisa:** 06/11/2026. **Admissibilidade conservadora:** 07/11/2026 00:00 UTC.

O laboratório anterior, com cinco datas de CPI de competência outubro/2026, cobria USD, CAD, EUR, GBP e AUD. Este complemento registra o **próximo evento oficial** para JPY, CHF e NZD. Portanto, *as oito moedas têm um registro de próximo evento*, mas eles **não representam a mesma competência nem estatística homogênea**.

| Moeda adicionada | Referência | Próxima data do calendário | Publicação e fonte primária |
|---|---|---|---|
| JPY | Outubro/2026 — mensal | **20/11/2026** | [Statistics Bureau of Japan — CPI nacional](https://www.stat.go.jp/english/data/cpi/1582.htm), **não** estimativa de Tóquio de novembro |
| CHF | Novembro/2026 — mensal | **02/12/2026** | [Swiss Federal Statistical Office — calendário anual](https://dam-api.bfs.admin.ch/hub/api/dam/assets/36353838/master), **não** HICP europeu |
| NZD | Trimestre outubro–dezembro/2026 | **27/01/2027** | [Stats NZ — CPI trimestral](https://www.stats.govt.nz/indicators/consumers-price-index-cpi/), **não** índice mensal de itens selecionados |

**Atenção à Suíça:** o FSO **já divulgou** o CPI referente a outubro em **03/11/2026**, com inflação anual de **1,5%**, conforme [boletim oficial](https://www.bfs.admin.ch/en/newnsb/UA8hylpLYO6i). Isso é diferente do **próximo** CPI, referente a novembro, marcado para 02/12. O valor anterior não entra na lista dos futuros eventos nem vira surpresa/viés de negociação.

**Atenção à Nova Zelândia:** a série de CPI nacional ainda é trimestral no recorte da pesquisa de 06/11/2026. A publicação mensal completa está sendo introduzida a partir de 2027 em etapas; este registro não a substitui por um índice parcial.

## Resultado do contrato offline

- Reutiliza os **cinco** registros com hash fixado da etapa anterior. Adiciona só **três** entradas manuais também fixadas por SHA-256, sem duplicar os originais.
- Após o limite de admissibilidade, **oito moedas** têm um evento futuro no momento da pesquisa. Cada um dos **28 pares** mostra dois registros de calendário (um por moeda). Os registros de mesma data continuam visíveis em conjunto.
- Com o passar dos dias, o próximo evento do par muda ou fica sem evento futuro neste recorte. **A data vencida não comprova a publicação do número**; o estado permanece `SCHEDULE_DATE_PASSED_ACTUAL_UNVERIFIED` até futura verificação documental.
- **Não** calcular spread de CPI entre mês e trimestre, entre HICP e CPI, nem entre actual de um período e calendário de outro. Datas agendadas não são observações de inflação e não contêm consenso de analistas.
- Antes de 07/11/2026 00:00 UTC, os três novos eventos e a junção dos oito ficam invisíveis à simulação `as_of`, inclusive se as datas das publicações primárias forem mais antigas.
- Fontes oficiais foram verificadas no texto público. **Bytes das páginas/PDF originais e instante exato de consulta não foram arquivados**; o JSON com transcrição manual, sim, foi fixado por hash. Calendários estão sujeitos a revisão.
- Todos os 28 pares continuam `D1=AGUARDAR`, `W1=AGUARDAR`, sem confiança de acerto, força relativa validada, ranking, surpresa, operação, cron, worker, HTTP, custo ou acesso à corretora.

## Testes e implantação

`python -m unittest -v test_atlasquant_trader_g8_eight_next_cpi_schedules_lab.py`

Somente desenvolvimento em laboratório, em PR rascunho empilhada sobre **#1839**. Nenhuma modificação da interface, merge, deploy ou automação real. **Próxima fase:** usar o calendário como contexto, mas construir comparação de dados realizados e expectativas capturadas antes do evento com a mesma métrica/período, associada a validação prospectiva de retorno de preço M15/D1/W1.
