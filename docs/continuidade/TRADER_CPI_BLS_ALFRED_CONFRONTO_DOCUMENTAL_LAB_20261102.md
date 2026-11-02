# AtlasQuant Trader — confronto documental CPI EUA/ALFRED (LAB)

Data: 02/11/2026 | PR #1803 DRAFT | HARD NO-GO

## Amostra real, com limites claros

**Evento:** CPI-U dos EUA, mês de referência dezembro de 2025.

O arquivo público original do Bureau of Labor Statistics é o comunicado
**USDL-26-0042**, datado de **13/01/2026 às 08:30 Eastern Time**:
https://www.bls.gov/news.release/archives/cpi_01132026.htm

Nesse comunicado, o BLS informou:
- **2,7%** de inflação acumulada em 12 meses, **sem ajuste sazonal**.
- **+0,3%** no mês, **com ajuste sazonal**.
- Índice CPI-U nível **324,054**, base 1982–1984=100, **sem ajuste sazonal**,
  correspondente ao mês **dezembro/2025**.

O segundo comunicado público, sobre janeiro/2026, foi divulgado
em **13/02/2026 às 08:30 Eastern Time**, número **USDL-26-0186**:
https://www.bls.gov/news.release/archives/cpi_02132026.htm

A Tabela 1 do comunicado de fevereiro repete **324,054** para o
índice CPI-U **sem ajuste sazonal de dezembro/2025**. Assim,
**os dois documentos oficiais concordam nesse valor histórico**.
Isso NÃO prova que toda e qualquer outra revisão tenha sido nula.
O segundo comunicado também discute revisões dos ajustes sazonais,
que **não devem ser confundidos com a série não ajustada**.

## Confronto com o ALFRED — primeira divulgação confirmada, export de vintages pendente

A série apropriada do ALFRED para o nível 324,054 é **CPIAUCNS**:
https://alfred.stlouisfed.org/series?seid=CPIAUCNS

CPIAUCNS significa índice de preços ao consumidor todos itens,
**sem ajuste sazonal**. A série **CPIAUCSL** é sazonalmente
ajustada e NÃO pode ser comparada com 324,054 como se fosse
o mesmo indicador; unidades, série e observação devem coincidir.

O ALFRED documenta a consulta de séries em datas de vintage
e o uso dos períodos históricos `realtime_start/realtime_end`:
- https://alfred.stlouisfed.org/series/downloaddata?seid=CPIAUCNS
- https://fred.stlouisfed.org/docs/api/fred/realtime_period.html

Encontramos agora uma página de **release histórico do próprio ALFRED**
para 13/01/2026, que mostra explicitamente:
- Série **CPIAUCNS**, dado de referência **Dec 2025**, **324,054**;
- Série distinta, ajustada sazonalmente, **CPIAUCSL**, Dec 2025, **326,030**.

Fonte oficial: https://alfred.stlouisfed.org/release?ob=pv&od=desc&rd=2026-01-13&rid=10&rt=used&t=used

Portanto, para **a primeira publicação de 13/01**, a igualdade
BLS–ALFRED de **324,054** foi confirmada por duas fontes documentais.
Esse dado NÃO foi obtido de um CSV de vintages nem de uma cópia
histórica com hash sob custódia da AtlasQuant.

A página de release de **13/02/2026** no ALFRED informa para
**CPIAUCNS** apenas **1 observação nova ou revisada**, referente
a **Jan 2026 = 325,252**. A listagem não apresenta dezembro
como observação alterada naquele release.

Fonte oficial: https://alfred.stlouisfed.org/release?ob=pv&od=desc&rd=2026-02-13&rid=10

Isso é **evidência indireta** de manutenção do índice de dezembro,
coerente com o segundo comunicado BLS. Entretanto, a página de
13/02 não mostra explicitamente o **valor de dezembro sob a
vintage daquela data**. O campo `feb13_dec2025_value` permanece
`null`; `alfred_vintage_agreement_verified=false` porque não
concluímos o confronto de TODAS as datas solicitadas.

**Não preencher o valor de fevereiro a partir da lista de mudanças,
nem do BLS ou da série atual**. Foi tentada a abertura do CSV
pela navegação pública, mas esse ambiente não conseguiu ler o
conteúdo CSV e a conexão direta também esteve indisponível.
Datas de publicação e releases históricos não equivalem a recibos
de disponibilidade intradiária sob custódia independente.

## Corte do viés: 07:00 em Mato Grosso

Em 13/01/2026:
- Emissão candidata do viés: **07:00 America/Cuiaba (UTC-4)**,
  equivalente a **11:00 UTC**.
- Hora do comunicado BLS: **08:30 America/New_York (UTC-5)**,
  equivalente a **13:30 UTC**, ou **09:30 America/Cuiaba**.

O resultado real, inclusive 2,7% e 324,054, **não poderia entrar
na fotografia de 07:00 naquele dia**. Somente o evento no
calendário poderia estar presente antes da divulgação.

O horário de embargo BLS é evidência documental do momento
programado de liberação, NÃO é recibo da ingestão feita
por nosso sistema em janeiro/2026. O corte das 07:00 é
proposta de LAB, não escolha final do proprietário.

## Fontes, evidências e status técnico

| Verificação | Estado |
|---|---|
| HTML oficial do comunicado original BLS consultado | Documentalmente verificado |
| HTML oficial do comunicado BLS posterior consultado | Documentalmente verificado |
| Nível de dezembro sem ajuste sazonal igual nos dois BLS | **Confirmado: 324,054** |
| ALFRED identifica série CPIAUCNS | **Confirmado (metadados)** |
| ALFRED release 13/01, dezembro/2025 CPIAUCNS 324,054 | **CONFIRMADO diretamente na página oficial** |
| ALFRED release 13/02, nova/revisada janeiro/2026 325,252 | **Confirmado (listagem de mudanças)** |
| ALFRED valor de dezembro/2025 sob vintage 13/02 | **NÃO EXTRAÍDO diretamente** |
| CSV de vintages ALFRED para as duas datas | **NÃO OBTIDO** |
| Cópia bruta dos comunicados arquivada com SHA-256 | Não |
| Consenso exato de mercado antes do evento | Não |
| Recebimento dos bytes pela AtlasQuant naquela hora | Não |
| Direitos de reuso do dado ALFRED/uso comercial | Não revisados |
| FX spot dos 28 pares com origem independente | Não |
| Assertividade OOS real | Não |

Documento estruturado:
`docs/continuidade/TRADER_CPI_BLS_ALFRED_CASO_REAL_LAB_20261102.json`.

A auditoria permite pesquisar qualidade de dados, não habilita
o backtest real nem o motor operacional. Uma conferência de
dois comunicados não demonstra relação causal entre CPI e
direção do dólar. Falta o consenso anterior, a cadeia de
custódia, os preços dos pares, critérios OOS e autorizações.

## Próxima etapa concreta

Obter, sem usar API paga, o export ALFRED **CPIAUCNS**
com as duas datas de vintage e confirmar especificamente
o valor de dezembro/2025 na **segunda vintage (13/02)**.
O primeiro valor da publicação ALFRED 13/01 já foi conferido
na listagem oficial e NÃO precisa ser inferido. Registrar
os bytes de qualquer futuro export, hashes e o instante
REAL de aquisição (não retrodatado).
Se o CSV exigir interação ou não estiver acessível, conservar
`null` e informar a pendência; não fabricar um valor.

Depois, auditar o consenso da mesma divulgação junto de
seu horário público de disponibilização. Uma pesquisa
trimestral SPF não é o consenso de 08h30 daquela notícia.

**LAB/HARD NO-GO:** não houve compra, API paga, chave,
merge, deploy, Worker, cron, ordem, ou alteração no Radar.
