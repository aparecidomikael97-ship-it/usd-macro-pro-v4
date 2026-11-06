# AtlasQuant Trader — triagem GBP CPI anual do ONS e versões históricas (LAB)

**Data:** 2026-11-05. **Situação:** fonte oficial identificada, leitor JSON preparatório com testes sintéticos; **não há captura real da API ONS** nem homologação dos bytes de resposta.

## Fonte e formato econômico

- ONS, série `D7G7`: **CPI ANNUAL RATE 00: ALL ITEMS 2015=100** no dataset `MM23`; a unidade publicada é **porcentagem anual**, não índice e não variação mensal.
- Página oficial: https://www.ons.gov.uk/economy/inflationandpriceindices/timeseries/d7g7/mm23
- Página oficial de versões anteriores: https://www.ons.gov.uk/economy/inflationandpriceindices/timeseries/d7g7/mm23/previous
- O ONS documenta a ideia de obter JSON de suas séries com o sufixo `/data`: https://digitalblog.ons.gov.uk/2017/07/13/api-an-introduction/

Na página oficial consultada, a versão atual informa divulgação **21/10/2026**, próxima divulgação **18/11/2026** e setembro/2026 como observação mensal mais recente de **3,5%**. Isso é **informação da página acessada hoje**, não demonstra o instante exato da divulgação em outubro nem é testemunho de que uma versão histórica esteve disponível em hora anterior a algum trade.

O ONS mantém arquivos de versões substituídas, inclusive uma substituída em 21/10/2026 e outra em 16/09/2026. Esta possibilidade de consultar *vintages* oficiais é promissora, mas o contrato **não marcou nenhuma vintage como autenticada**, pois os arquivos originais não foram coletados e confrontados.

## Entrega do LAB

`atlasquant_trader_ons_gbp_cpi_current_lab.py` recebe somente bytes JSON já fornecidos e horário UTC da captura. **Não usa rede** e exige série D7G7, dataset MM23, título e unidade exatos. Analisa exclusivamente `months`, evitando confundir números anuais ou trimestrais com observações mensais; recusa meses fora de ordem, duplicatas, taxa inválida, JSON com chaves duplicadas e data de divulgação declarada posterior à captura. Ausência de taxa é `null` e nunca zero.

Uma data de calendário não é convertida em timestamp de divulgação com precisão intradiária. O horário de captura fornecido pelo próprio computador não atesta autenticidade do ONS. Mesmo com estrutura válida, a resposta é `LAB_CURRENT_GBP_ONS_D7G7_QUARANTINED`, com `original_http_response_observed=false`, `individual_release_instant_verified=false`, `archived_historical_vintage_verified=false`, `consensus_pre_event_attested=false`, `fx_bias=null`, `operational_bias=AGUARDAR` e sem qualquer permissão de operação.

O leitor opcional foi vinculado à matriz dos 28 pares. **Num teste sintético com EUR/USD/GBP preenchidos**, a cobertura é 3 pares com duas moedas, 15 com uma e 10 sem observações. Nenhuma taxa de inflação foi subtraída entre países: HICP EUR, CPI-U NSA EUA e CPI Reino Unido não devem ser presumidos intercambiáveis.

## Verificação e limites

- **16 testes sintéticos novos** do leitor GBP.
- **4 testes sintéticos adicionais** de integração na matriz G8, inclusive alinhamento de meses sem falsa comparabilidade e bloqueio de JSON/horários inválidos.
- Falta obter os **bytes genuínos** das versões do ONS (com hash, URL, data de obtenção, direitos de reutilização e eventual prova histórica). Confirmar se a representação real corresponde ao contrato exploratório antes de aceitar qualquer observação como fonte integrada.

**LAB / HARD NO-GO**. Sem chamada à API, download, custo novo, merge, publicação, Worker, Render, trade ou alteração da interface da PR #1816. Continuidade na Draft PR #1815.
