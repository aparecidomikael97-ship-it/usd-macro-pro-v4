# AtlasQuant Trader — leitor preparado para PPI de outubro/2026 (primeira divulgação)

**Checkpoint: 10/11/2026, LAB, antes do evento oficial. Nenhum resultado do PPI de outubro foi capturado, calculado ou inventado. Sem sinais, ordens, nova assinatura, merge ou deploy.**

## Fonte e data

- Calendário [BLS oficial do PPI](https://www.bls.gov/schedule/news_release/ppi.htm): **sexta-feira 13/11/2026, 08h30 ET / 13h30 UTC / 09h30 Mato Grosso**.
- Amostra real anterior para validar a **estrutura de categorias**, e não os resultados futuros: [PPI setembro/2026, relatório BLS de 15/10/2026](https://www.bls.gov/news.release/archives/ppi_10152026.htm). Esse documento histórico exibe na tabela 1 tanto:
  - **Final demand** / commodity code **FD 4** (PPI geral de demanda final);
  - **Final demand less foods and energy** / **FD 49104** (núcleo sem alimentos/energia);
  - **Final demand less foods, energy, and trade services** / **FD 49116** (núcleo alternativo, **não usar no lugar de FD 49104**).
- O HTML original histórico do BLS retornou **HTTP 403** ao `curl` do AM12 nesta rodada; mantido como arquivo de erro em `PPI_US_20261113_PRE_EVENT_LAB/BLS_PRIOR_REFERENCE`. A estrutura de códigos foi verificada na página pública de pesquisa; **não** foi feito ensaio de parser com bytes oficiais do BLS.

## Preservar os dois consensos anteriores ao evento

- **TD Economics**, captura em 11/11 00h58 UTC, HTML SHA256 `5f9d9eb128e5a3763ec6a3081bee7ba8c248a665a9d50e0ee132e9cbe037a42a`, consenso PPI geral outubro MoM **0.4%**, PPI núcleo FD 49104/equivalente “Ex Food and Energy” **0.3%**.
- **Trading Economics**, captura em 11/11 01h15 UTC, HTML SHA256 `175c163514590db8e2ddd651f0c9865bd2eed298211f92072549233f670e23c0`, **Consensus** geral **0.4%**, núcleo **0.3%**. O campo **Forecast** é projeção própria do site, não consenso, e permanece separado.
- Cópias integrais dos dois HTMLs e cabeçalhos continuam apenas no AM12, em `Documentos/AtlasQuant/Trader/PPI_US_20261113_PRE_EVENT_LAB`. Relatório de evidências anterior: `docs/trader/TRADER_US_PPI_20261113_TWO_PRE_EVENT_PUBLISHERS_AM12_20261110.md`.
- **Duas publicações coincidentes não comprovam pesquisas estatisticamente independentes nem autorização de redistribuição.**

## Nova entrega técnica (sem ativação)

**Arquivos:**
- `atlasquant_trader_us_ppi_oct2026_actual_table_guard_lab.py`
- `test_atlasquant_trader_us_ppi_oct2026_actual_table_guard_lab.py`

O módulo aceita *somente depois* da data de divulgação um candidato de HTML completo da URL esperada `https://www.bls.gov/news.release/archives/ppi_11132026.htm`. Verifica:
1. UTC do evento, captura alegada posterior, data/hora de avaliação, status HTTP 200, URL, MIME, tamanho e SHA256 dos bytes. Esses metadados ainda são **declarações locais, não certificação independente**.
2. Identidade de **PRODUCER PRICE INDEXES - OCTOBER 2026**, data **Friday, November 13, 2026** e texto de PPI geral SA MoM.
3. **Tabela 1 de variações mensais sazonalmente ajustadas**; procura grupo/código **FD/4** para headline e **FD/49104** para núcleo. Exige que o valor headline da tabela concorde com a primeira frase do comunicado. Se a tabela estiver diferente da estrutura prevista, bloqueia e exige nova auditoria.
4. Rejeita usar como núcleo o grupo **FD/49116** (sem alimentos, energia e serviços de comércio) ou **FD/413** (somente bens), misturar índice/YoY com MoM, duplicidades, headers ambíguos, texto alterado e origem inválida.
5. A comparação apenas documental contra os **dois hashes e os dois valores de consenso pré-evento já congelados** fica inacessível antes de haver leitura de um candidato pós-publicação aceito. Quando existir, calcula diferenças em **pontos percentuais**, não probabilidades de acerto nem direção de FX.
6. Não ativa qualquer worker, alerta, conexão com MetaTrader 5, trade, publicação ou aberturas de conta.

**Validação:** 22 testes unitários de *HTML sintético futuro* executados no laboratório e no computador AM12, todos aprovados. **Não são observações de PPI real** e **não representam backtest.** A verificação executada no AM12 em `2026-11-11T01:36:51Z` retornou:
`state=LAB_WAIT_BLS_PPI_OCT2026_RELEASE`, `head_actual=null`, `core_actual=null`, `operational_bias=AGUARDAR`, `trade_authorized=false`.

**CI:** `.github/workflows/atlasquant-trader-d1w1-offline-lab.yml` foi atualizado para executar o módulo e os testes em Python 3.11 e 3.12. O CI utiliza somente fixtures sintéticas, nunca as capturas HTML de terceiros.

## Próximos passos em ordem

1. **Quinta-feira 12/11 à noite:** tarefa já agendada de conferência de consenso; se mudar, conservar outra versão, horário e SHA (nunca sobrescrever as anteriores).
2. **Sexta-feira 13/11 somente depois de 13h30 UTC:** obter do BLS HTML válido. Caso o acesso automatizado retorne 403, pedir captura manual em navegador **depois** da publicação. Um 403 não vira dado macro.
3. Inspecionar estrutura **real da tabela 1**; se diferente do ensaio sintético, adaptar o parser em laboratório, revalidar, sem aceitar texto de resultados digitados.
4. Gerar registro documental `surpresa = realizado (mesma métrica) − consenso congelado antes do evento`. Não produzir viés do EURUSD, USDJPY, ouro ou índices sem evidência adicional de reação, regime e testes fora da amostra.
5. Manter **PR #1851 em rascunho**, sem merge/deploy/ordens; script AtlasQuant Flow v1.1 continua guardado na Biblioteca para fase própria.

**Estado operacional:** GO-LAB; NO-GO integração/viés operacional; HARD NO-GO operação real.
