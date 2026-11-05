# AtlasQuant Trader — primeira série macro EUR capturada com bytes e hash (LAB)

Checkpoint 04/11/2026 · PR #1815 · sem integração no Radar, Worker ou produção.

## Descoberta e mudança de dataset

O dataset antigo da Eurostat `prc_hicp_manr`, usado para inflação
anual harmonizada, foi **descontinuado em 2025**. Para os dados de
2026, o dataset oficial é `prc_hicp_minr`, ECOICOP versão 2.
Não comparar série antiga e nova ignorando mudanças de classificação.

Documentação oficial:
- https://ec.europa.eu/eurostat/web/hicp/information-data
- https://ec.europa.eu/eurostat/en/web/user-guides/data-browser/api-data-access/api-introduction
- https://ec.europa.eu/eurostat/databrowser/view/prc_hicp_minr/

## Consulta de laboratório

URL FIXA da API:
`https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/prc_hicp_minr?format=JSON&lang=EN&geo=EA&unit=RCH_A&coicop18=TOTAL&lastTimePeriod=3`

Parâmetros: inflação harmonizada da área do euro (`geo=EA`, área
geográfica com composição histórica variável), mensal (`M`),
taxa anual (`RCH_A`), cesta total (`coicop18=TOTAL`).

Uma execução manual no AM12 às **2026-11-04T23:59:59.392193+00:00**
retornou JSON-stat 2.0 da Eurostat (`source=ESTAT`) com:
- 2026-08: **3,2%** (sem marca de estimativa);
- 2026-09: **3,8%** (sem marca de estimativa);
- 2026-10: **4,0%**, com flag `e` = **estimativa, não final**.

O campo `updated` do dataset foi
`2026-11-04T11:00:00+0100` (10:00 UTC), mas essa é a
**atualização da tabela**, não um comprovante de quando cada valor
foi divulgado ou estava disponível para uma operação passada.

## Prova reprodutível dos bytes recebidos nesta captura

Foi criado, sem sobrescrever documentos anteriores, um ZIP local:

`C:\Users\apare\AtlasQuant_Trader_G8_LAB_20261104\evidence\eurostat_eur_hicp_20261104T235959392193Z_6a7b15ae64f2.zip`

O arquivo contém:
- `response.json`: bytes **exatamente recebidos** nesta consulta;
- `observation_receipt.json`: URL, SHA-256, horário local do AM12,
  status de estimativa e gates de confiabilidade.

SHA-256 dos bytes JSON:
`6a7b15ae64f20ed6555efd8794eb75e268d597de219753c7e12247978b64edfe`

SHA-256 do próprio ZIP:
`604922ec67418fa8ea543368c63f813e7546a428d098fdc369331295554a37fc`

O pacote **não foi adicionado ao GitHub**. Continua no computador do
usuário; pode ser reprocessado offline. O hash comprova integridade
contra cópia alterada se conferido externamente, mas não certifica
origem institucional ou disponibilidade no passado.

## Engenharia, confiança e testes

Novo `atlasquant_trader_eurostat_eur_hicp_once_lab.py`:
- Opt-in explícito, sem requisições na importação.
- HTTPS CA padrão e URL/consulta EXATAS, sem redirects.
- Máximo de 128 KiB, JSON-stat de estrutura/dimensões estritas;
  recusa geo, unidade, classificação, períodos e valores inválidos.
- Não inventa observações ausentes, rejeita períodos futuros.
- Marca `e` como estimativa, **nunca transforma ausência de flag em
  garantia de valor definitivo**.
- O armazenamento de bytes só ocorre com diretório indicado
  explicitamente; modo ZIP exclusivo sem sobrescrever.
- Fonte atual e relógio do AM12 **não** são histórico de vintages
  point-in-time. Eurostat comunica que a API pública contém
  a versão mais atual, sem histórico de revisões anteriores.
- Nunca gera surpresa real/consenso, causa macro, sinal de negociação,
  execução automática ou viés D1/W1/MN1.

Foram adicionados **11 testes** offline, todos com respostas simuladas;
a suíte local G8 + EUR totalizou **63 PASS no AM12**, com compilação
Python também aprovada. A CI do novo SHA deve ser verificada depois.

Sem merge, deploy, cron, Render, Worker, ordens ou novos custos.
HARD NO-GO / AGUARDAR preservados.
