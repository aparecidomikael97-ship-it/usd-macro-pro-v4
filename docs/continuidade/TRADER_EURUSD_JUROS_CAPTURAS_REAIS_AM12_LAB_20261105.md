# AtlasQuant Trader — capturas reais de juros EUR/USD no AM12 (LAB)

Data: 05/11/2026 UTC (04/11 à noite em Cuiabá). Continuação isolada da
PR #1815. **Nenhum merge, publicação, Worker, cron, ordem real ou custo novo.**

## Procedimento e conclusão

O AM12 foi localizado **online**; worktree principal ainda em `f4e753e7`
detached com evidências/arquivos não rastreados. **Não alteramos aquele HEAD,
não apagamos nem substituímos logs ou ZIPs.** Após fetch de `9b58ccb8`, os
scripts da PR foram extraídos para a pequena pasta isolada
`policy_capture_lab_20261105`. Foram rodados **34 testes Python PASS**;
depois da correção de semântica BCE, **37 testes PASS** no Windows AM12.
O hash Git de seis fontes/testes isolados bateu com a cópia de desenvolvimento.

As consultas foram **manuais e únicas**, uma fonte por invocação, com URLs
fixas, HTTPS/CA padrão, timeout 8 s, sem redirect nem autenticação paga.
Cada resposta foi mantida em ZIP original privado na pasta `evidence` do AM12.

| Fonte | Última observação no CSV | Valor recebido | Conteúdo bruto | Parser | ZIP reaberto offline |
| --- | --- | --- | --- | --- | --- |
| BCE / EUR, `FM.D.U2.EUR.4F.KR.DFR.LEV` | 2026-11-05 | taxa de depósito **2,50% a.a.** | 199.989 bytes, 674 dias, nenhum gap | `LAB_ECB_DFR_DAILY_LEVEL_QUARANTINED` (V2) | PASS, ainda quarentena |
| Fed/St. Louis / USD, `DFEDTARL` + `DFEDTARU` | 2026-11-04 | faixa-alvo **3,75%–4,00%** | 137.228 bytes | `LAB_FED_TARGET_RANGE_DAILY_QUARANTINED` | PASS, ainda quarentena |

### Custódia BCE

Primeira consulta BCE: `2026-11-05T00:54:18.965588+00:00`, HTTP 200,
`Content-Type: text/csv`. O parser inicial recusou `674` linhas por ter limite
de `250` e tratar datas como mudanças de taxa. A resposta foi preservada:

- `ecb_eur_dfr_effective_20261105T005418965588Z_4d69d202aae3.zip`
- SHA-256 do ZIP antigo: `5fb8ebf43cdd5e1ca78bb6ecd6b885cba3a511d41bdc5fbc3c862a3a745d92f7`
- SHA-256 do CSV bruto: `4d69d202aae3ad1552936a3ddef84b5a5eb0c8995647fc5107c65483b61596e4`
- Reabertura com o leitor **antigo**: integridade PASS, `parser_accepted=false`.

O CSV real contém uma linha por dia de `2025-01-01` a `2026-11-05`, com
`OBS_STATUS=A`; **6 mudanças de nível entre observações consecutivas**.
A última transição de nível foi observada em `2026-09-16`, para `2.5`.
Isso **não prova que o BCE tomou a decisão nesse dia**.

Com o parser diário V2 corrigido e 37 testes locais AM12 PASS, uma **nova
consulta manual** em `2026-11-05T01:02:53.342320+00:00` capturou os mesmos
199.989 bytes e o mesmo SHA bruto, sem modificar a captura anterior:

- `ecb_eur_dfr_effective_20261105T010253342320Z_4d69d202aae3.zip`
- ZIP novo SHA-256: `c9d9dd4d1d6949fb4f651c45c2f8058c1d04b4f2cba7e303c7da372d98e1ceaa`
- Parser atual: `LAB_ECB_DFR_DAILY_LEVEL_QUARANTINED`, semântica
  `ECB_DFR_DAILY_LEVEL_V2`, 674 linhas, 0 gaps, 6 mudanças **observadas**
- Replay offline SHA ZIP + CSV + parser: **PASS**, `trade_authorized=false`

### Custódia Fed/FRED

Consulta em `2026-11-05T00:56:14.957761+00:00`, HTTP 200,
`Content-Type: application/csv`, sem API key:

- `fed_usd_target_range_effective_20261105T005614957761Z_8cd1578ed85f.zip`
- ZIP SHA-256: `153d61f424e8b9ff1c3646e9e022dc5811e837607dd6aa58bb081f7366fdc515`
- CSV SHA-256: `8cd1578ed85f481a5872ded983bf45559687207d89fb943991b0e6e6ab6d62e8`
- Última data `2026-11-04`, inferior `3.75`, superior `4.00`, nenhum dia
  explicitamente marcado ausente no parser
- Replay offline inicial e após atualização BCE: **PASS**

**Os ZIPs são privados no AM12 e não foram commitados no GitHub.** Os hashes
no repositório permitem identificar as capturas, não baixar seu conteúdo nem
comprovar custódia institucional assinada. `Date` e `Last-Modified` HTTP são
alegações do servidor/proxy; horário local não é testemunha independente.

## Conferência documental das decisões (não timestamp exato)

- [BCE: decisão de 10/09/2026](https://www.ecb.europa.eu/press/pr/date/2026/html/ecb.mp260910~314e508016.en.html): aumento da taxa de depósito para **2,50%**, com **efeito desde 16/09/2026**. A fonte documental confirma que a data de efeito difere da data da decisão.
- [Federal Reserve: comunicado FOMC de 28/10/2026](https://www.federalreserve.gov/newsevents/pressreleases/monetary20261028a.htm): manteve a faixa-alvo de **3,75%–4,00%**. A [nota de implementação](https://www.federalreserve.gov/newsevents/pressreleases/monetary20261028a1.htm) distingue a faixa da remuneração de reservas.

As páginas oficiais reforçam a identificação de instrumentos, porém **não
foram capturadas como vintages pré-evento com horário institucional assinado**.
Não se deve transformar data de vigência em instante de publicação ou
interpretação de surpresa sem prova específica.

## Gate bilateral de EUR/USD

Os dois `parser_receipt` reais foram comparados offline no AM12:

- EUR: observação `2026-11-05`, taxa de depósito `2.5`.
- USD: observação `2026-11-04`, faixa `3.75`–`4.00`.
- `different_latest_observation_dates=true`.
- `policy_rate_spread_bps=null`, `market_surprise_bps=null`, `fx_bias=null`,
  `operational_bias=AGUARDAR`, `trade_authorized=false`.

**Não comparar taxa de depósito BCE com o teto da faixa Fed como se fossem
instrumentos intercambiáveis.** Falta expectativa pré-anúncio, instante de
publicação testemunhado, câmbio spot independente, direitos e backtest OOS.

## Testes e próxima etapa

- Desenvolvimento: **126 testes locais PASS** nos sete módulos focados.
- AM12: **37 testes PASS** dos três módulos de política/captura/auditoria.
- CI do SHA novo: conferir após commit. PR #1816 e `main` intactas.
- Próximo gate: preparar um dossier documental de decisão + expectativa
  pré-evento para ambas as moedas, preservando a data/horário de cada item,
  antes de qualquer hipótese direcional.

**HARD NO-GO: somente LAB.**
