# AtlasQuant Trader — PPI EUA outubro/2026: primeira expectativa capturada ANTES da divulgação

**Captura realizada em 10/11/2026 à noite (Mato Grosso), no computador AM12. Estado: LAB, NÃO há PPI realizado ainda, NÃO há sinal de Forex.** Documento do checkpoint de pesquisa.

## Calendário e fonte da expectativa

- **Evento futuro:** divulgação oficial do **PPI de outubro/2026** pelo BLS, sexta-feira **13/11/2026, 08h30 ET = 13h30 UTC = 09h30 Mato Grosso**. Calendário original: [BLS, November 2026](https://www.bls.gov/schedule/2026/11_sched_list.htm).
- **Expectativa capturada hoje em fonte de instituição financeira:** [TD Economics, *Upcoming Economic Releases and Events: Nov 9–13, 2026*, documento datado de 06/11](https://economics.td.com/domains/economics.td.com/documents/reports/bottom-line/tables/2026-11-06/upcoming.htm).
- A tabela da TD possui colunas separadas **Consensus Forecast** e **Last Period**. Para a sexta-feira 13/11 às 8h30, mês de referência **outubro**, unidade **M/M % Chg.**:
  - **PPI Final Demand:** consenso **+0,4% mensal**, período anterior **+1,3%**.
  - **PPI Ex Food and Energy:** consenso **+0,3% mensal**, anterior **+0,7%**.
- Não confundir os valores anteriores +1,3 e +0,7 com as expectativas. Não comparar sazonalizado, índice absoluto ou YoY com MoM sem conferir metodologias nos comunicados futuros.
- **Não foi apurada a lista de participantes, a metodologia ou a janela de coleta da pesquisa de consenso**, nem sua primeira publicação independente.

## Evidência local preservada antes do evento

A captura foi executada pelo Desktop Commander no AM12 com `curl.exe`, solicitando a URL exata e preservando o HTML e cabeçalhos.

- **Início observado no relógio local da máquina (UTC):** `2026-11-11T00:58:10.7665046Z`.
- **Fim observado no relógio local da máquina (UTC):** `2026-11-11T00:58:12.0214570Z`.
- Status HTTP observado: **200 OK**, tipo **text/html**, URL efetiva sem redirecionamento de domínio.
- `Last-Modified` do servidor: **Fri, 06 Nov 2026 18:00:39 GMT**.
- `Date` do servidor: **Wed, 11 Nov 2026 00:58:18 GMT**.
- Corpo original: **32.822 bytes**, SHA-256 **`5f9d9eb128e5a3763ec6a3081bee7ba8c248a665a9d50e0ee132e9cbe037a42a`**.
- **Arquivos preservados apenas no PC**, sem publicar cópia de terceiro no GitHub: `Documentos/AtlasQuant/Trader/PPI_US_20261113_PRE_EVENT_LAB/td_economics_ppi_preview_20261106.html`, `td_economics_headers.txt`, `AM12_PPI_PRE_EVENT_CONSENSUS_LOCK_20261111_005812Z_LAB.json`.
- Horário local, `Date` e `Last-Modified` são evidências e afirmações do ambiente/fonte, **não timestamp assinado por terceiro** nem prova imutável da primeira versão publicada. **A diferença essencial do CPI anterior:** captura explícita no AM12 em data *anterior* ao evento futuro.
- Tentativa de obter texto reproduzido pela MarketScreener/Dow Jones respondeu **403** e foi segregada como `BLOQUEADO_HTTP_403_DOW_JONES_NAO_E_CONSENSO.html`. Nunca entra nos dados elegíveis. A existência de números semelhantes em outros sites não substitui captura própria.

## Código e validação

Módulo: `atlasquant_trader_us_ppi_pre_event_preview_lab.py` e testes `test_atlasquant_trader_us_ppi_pre_event_preview_lab.py`.

O leitor offline analisa os bytes HTML de tabela (não fragmento de mecanismo de busca), exige cabeçalho **Consensus Forecast**, nome, mês, dia, horário e unidade de cada linha; rejeita duplicidade, mudanças de campo, SHA divergente, relógio no futuro, corpo incorreto, PDF/404, `Last-Modified` posterior ao evento e snapshots obtidos depois de 13/11 13h30 UTC.

- **15 testes sintéticos PASS** no laboratório e **15 PASS no AM12/Python 3.12**.
- **Execução separada com arquivo real no AM12:** `LAB_PRE_EVENT_PPI_CONSENSUS_ARCHIVED_LOCAL_NO_TRADE`, valores esperados **0,4 / 0,3**, anteriores **1,3 / 0,7**, e registro do SHA mencionado.
- O GitHub Actions executa testes sintéticos em Python 3.11 e 3.12; **não contém o HTML real de terceiros**.
- Campos de segurança: `operational_bias=AGUARDAR`, `ppi_surprise=null`, `eurusd_bias=null`, `trade_authorized=false`, `publishable=false`, `source_provenance_independently_attested=false`, `historical_backtest_point_in_time_attested=false`.
- Um rótulo `ready_for_later_retrospective_comparison_lab=true` **não equivale a aprovar backtest ou operação**; apenas indica que há um arquivo pré-evento com verificações locais que pode ser confrontado com o realizado futuro.

## Próximo passo (sem execução automática de operações)

**Antes do PPI:** se o consenso mudar, arquivar **outra versão**, com novo SHA e horário de captura, sem sobrescrever a primeira; verificar termos de uso antes de qualquer redistribuição comercial. **Após 13/11 09h30 MT:** obter a publicação oficial *original*, com data, hora de acesso e hash, extrair a mesma métrica MoM e comparar com o snapshot efetivamente registrado antes. Não inventar resultado agora e **não inferir direção do USD/índices/ouro de uma surpresa isolada**. Registrar cobertura, abstenção e desempenho fora da amostra ao longo de muitos eventos.

**Estado:** somente PR draft, custo adicional zero, sem deploy, sem corretora, sem trade, sem atualização do Flow PRO.
