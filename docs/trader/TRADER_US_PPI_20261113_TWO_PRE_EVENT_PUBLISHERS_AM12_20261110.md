# AtlasQuant Trader — PPI out/2026, DUAS fontes pré-evento e separação consenso/forecast — 10/11/2026

**Estado:** LAB / fontes preservadas somente no computador AM12 / NO-GO sinal, ordem ou publicação / sem custos adicionais. O resultado oficial do PPI **ainda não foi divulgado** neste checkpoint. A data oficial é [13/11/2026 às 08h30 ET](https://www.bls.gov/schedule/news_release/ppi.htm) (**09h30 MT; 13h30 UTC**).

## Evidências realmente capturadas ANTES do evento

1. **TD Economics**, [tabela *Upcoming Economic Releases and Events* 9–13 Nov 2026](https://economics.td.com/domains/economics.td.com/documents/reports/bottom-line/tables/2026-11-06/upcoming.htm):
   - No AM12: **11/11/2026 00:58:10–00:58:12 UTC** (10/11 20h58 MT), HTTP 200, cabeçalhos preservados, documento 32.822 bytes; SHA-256 do HTML original **`5f9d9eb128e5a3763ec6a3081bee7ba8c248a665a9d50e0ee132e9cbe037a42a`**.
   - Colunas distintas `Consensus Forecast` e `Last Period`. Para **13/11 às 8h30, período outubro, variação mensal**:
     - **PPI Final Demand:** consenso +0,4%; anterior +1,3%.
     - **PPI Ex Food and Energy:** consenso +0,3%; anterior +0,7%.
   - Relatório inicial: `docs/trader/TRADER_US_PPI_20261113_PRE_EVENT_TD_SNAPSHOT_AM12_20261110.md`.

2. **Trading Economics**, [calendário dos Estados Unidos](https://tradingeconomics.com/united-states/calendar):
   - Captura original com redirecionamento **HTTP 301 → 200 OK**, efetuada no AM12 **11/11/2026 01:15:51–01:15:54 UTC** (10/11 21h15 MT). Resposta final observada `200 text/html; charset=utf-8`.
   - Cabeçalho HTTP final **Date: Wed, 11 Nov 2026 01:15:59 GMT**; `TE-Rendered-At: 2026-11-11T01:15:09Z` — horário da renderização reportado pelo próprio servidor, **não carimbo imutável de primeira publicação**.
   - HTML **1.401.914 bytes**; SHA-256 **`175c163514590db8e2ddd651f0c9865bd2eed298211f92072549233f670e23c0`**.
   - Na linha `PPI MoM OCT` de 13/11, colunas: **Actual vazio, Previous +1,3%, Consensus +0,4%, Forecast +0,3%**.
   - Na linha `Core PPI MoM OCT`: **Actual vazio, Previous +0,7%, Consensus +0,3%, Forecast +0,3%**. A [definição TE para Core PPI MoM](https://tradingeconomics.com/united-states/core-producer-prices-mom) refere-se ao núcleo **excluindo alimentos e energia**, **não** a "ex-food/energy/trade services".
   - **Ponto central:** o consenso da Trading Economics (+0,4% geral) coincide com o da TD, embora a *projeção da própria TE* (+0,3% geral) seja diferente. **Nunca substituir Consensus pelo campo Forecast.**

### Comparação entre as fontes

| Métrica, outubro, percentual mês/mês | TD Economics — consenso | Trading Economics — consenso | Trading Economics — projeção própria |
|---|---:|---:|---:|
| PPI geral | +0,4% | +0,4% | +0,3% |
| PPI núcleo sem alimentos/energia | +0,3% | +0,3% | +0,3% |

**Duas fontes publicadoras ≠ duas pesquisas metodologicamente independentes.** Origem e janela de coleta dos participantes não verificadas. O horário mostrado pelo Trading Economics (01:30 PM, GMT) **não é o horário de Mato Grosso**; o evento permanece ancorado ao calendário oficial BLS.

## Prova local e arquivos não distribuídos

Pasta somente leitura do laboratório no AM12:
`C:\Users\apare\Documents\AtlasQuant\Trader\PPI_US_20261113_PRE_EVENT_LAB`

- Primeira fonte: `td_economics_ppi_preview_20261106.html`, `td_economics_headers.txt`, `AM12_PPI_PRE_EVENT_CONSENSUS_LOCK_20261111_005812Z_LAB.json`.
- Segunda fonte: `te_uscalendar_20261110_snapshot.html`, `te_uscalendar_headers.txt`, `AM12_PPI_TWO_PUBLISHERS_PRE_EVENT_COMPARE_20261111_LAB.json`.
- Script local de conferência: `audit_ppi_two_publishers_pre_event_lab.py`.
- **Nenhum dos HTMLs/cabeçalhos foi enviado ao GitHub**. Os cabeçalhos podem conter cookies temporários; só os hashes, valores de pesquisa e contexto entram na documentação.
- O script verificou os hashes e os dados observados em ambos os arquivos. O registro local distinguiu: `two_publishers_consensus_match=true`, `official_actual=null`, `dollar_direction=null`, `profit_probability=null`, `trade_authorized=false`, `bias=AGUARDAR`.

## Módulo novo e testes

- `atlasquant_trader_us_ppi_te_second_consensus_lab.py`: parser offline do HTML TE, com verificação de identidade e fronteiras das linhas, período `OCT`, data `2026-11-13`, ausência de realizado, cabeçalho `Actual/Previous/Consensus/Forecast`, hash, tamanho e janela pré-evento.
- `test_atlasquant_trader_us_ppi_te_second_consensus_lab.py`: **12 testes sintéticos**, concluídos no AM12 com Python 3.12; o script de integração separada, rodado contra os dois HTMLs reais, também retornou sucesso.
- O workflow `.github/workflows/atlasquant-trader-d1w1-offline-lab.yml` executa os testes em Python 3.11 e 3.12. **Os HTMLs de terceiros não são fixtures CI**.
- Rejeições previstas: valor oficial já presente antes do evento, métricas/títulos errados, consenso/forecast embaralhados, data errada, hash alterado, HTTP 403, sessão depois do evento, valores impossíveis, linhas duplicadas e alterações de percentagens.

## Sequência para sexta-feira

1. A conferência de quinta-feira à noite **já foi agendada**; capturar eventual mudança de expectativa em novo arquivo, sem sobrescrever as fontes de 10/11. Se nenhuma evidência fresca, informar a limitação.
2. **Somente após o evento** 13/11 13h30 UTC, buscar documento BLS oficial do *Producer Price Index* (a captura automatizada do BLS pode retornar 403; uma captura manual por navegador pode ser necessária), registrar dados da fonte original, data/hora de captura e SHA.
3. Comparar **realizado mensal de final demand** com **consenso mensal**, e **realizado mensal ex food/energy** com **consenso mensal dessa mesma definição**; reportar diferença em pontos percentuais. Não confundir com ex food/energy/**trade services**, anual, valor da série, `Previous` ou projeção TE.
4. Não inferir EURUSD/USDJPY/XAUUSD/WIN/WDO da surpresa isolada; validar histórico prospectivo, reação e volatilidade antes de liberar viés.
5. Manter PR #1851 em rascunho, no LAB, sem operar, sem trabalhador programado novo e sem custo.

**Conclusão:** evidência real de **duas publicações capturadas antes do evento**, consenso convergente, projeção própria TE separada; ainda **nenhum resultado oficial**, nenhuma precisão validada.
