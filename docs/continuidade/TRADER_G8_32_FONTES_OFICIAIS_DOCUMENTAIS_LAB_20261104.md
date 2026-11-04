# AtlasQuant Trader — 32 caminhos oficiais documentais (04/11/2026)

**Prioridade confirmada por Mikael:** viés de 28 pares Forex, 8 moedas, D1
principal, W1 confirmação, MN1 contexto; fundamentos, microeconomia,
geopolítica, notícias e calendário. OB/FVG não entram neste trabalho.

## Ampliação do catálogo, sem baixar dados

O catálogo `atlasquant_trader_g8_country_macro_catalog_lab.py` já possuía
**32 posições** (8 moedas × INFLATION/EMPLOYMENT/POLICY/ACTIVITY), mas vários
`source_info_url` estavam vazios. Agora cada posição aponta para uma **página
documental do respectivo produtor oficial**. As 16 páginas de emprego e
atividade foram pesquisadas em fontes primárias; inflação/juros reaproveitam
as referências oficiais já levantadas na revisão.

| Moeda | Emprego | Atividade econômica |
|---|---|---|
| USD | BLS — Employment Situation | BEA — GDP |
| EUR | Eurostat — LFS/desemprego | Eurostat — National accounts |
| GBP | ONS — UK Labour Market | ONS — GDP first quarterly estimate |
| JPY | Statistics Bureau — Labour Force | Cabinet Office ESRI — GDP |
| CHF | SECO — Labour Market Statistics | SECO — GDP trimestral |
| CAD | Statistics Canada — LFS | Statistics Canada — Economic Accounts |
| AUD | ABS — Labour Force | ABS — National Accounts |
| NZD | Stats NZ — Unemployment Rate | Stats NZ — GDP |

Os 32 endereços HTTPS exatos estão no código e têm testes estruturais
independentes. A origem do domínio e o tema da página foram conferidos como
**leads oficiais de pesquisa**, não como arquivo autenticado de cada indicador.

## Não misturar definições

- **CHF:** desemprego registrado do SECO não é automaticamente idêntico à
  taxa de desemprego da Labour Force Survey na metodologia OIT/ILO.
- **USD:** crescimento trimestral do PIB BEA frequentemente usa taxa
  anualizada; não comparar diretamente à variação não anualizada de outros
  países sem conversão e revisão de sazonalidade.
- **NZD:** taxa de desemprego vem de divulgação trimestral; ausência de dado
  mensal não pode virar um sinal de fraqueza da moeda.
- **EUR:** inflação HICP harmonizada; flash/final/revisões precisam de
  escolha prévia, não podem ser selecionadas retrospectivamente.
- Calendário, consenso, valor anterior, valor divulgado e expectativa de juros
  exigem fontes e carimbos temporais independentes. Links não fornecem isso.

## Limites e próximas etapas

`source_page_is_live_feed=false`, `landing_pages_are_historical_receipts=false`,
`license_for_automated_reuse_verified=false`, `vintage_and_consensus_verified=false`,
`publisher_response_attested=false`, `allowed_for_live_bias=false`.

Não fizemos HTTP automático, assinatura, captura autenticada, licenciamento
comercial, alterações na UI ou operação. O próximo passo será selecionar
series/definições ponto-no-tempo e documentar relógios de publicação para
o verdadeiro motor macro D1/W1/MN1 — sem inventar precisão ou ALTA/BAIXA.

**Governança:** PR #1803 DRAFT/LAB/HARD NO-GO; sem merge, Render,
Worker, AION, ordens, API paga ou novas cobranças.
