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

## Confronto com o ALFRED — PARCIAL, ainda sem valores de vintage

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

Tentamos localizar os valores de vintage **13/01/2026** e
**13/02/2026** de CPIAUCNS para a observação de dezembro/2025.
**Não foi possível obter o CSV de vintage neste ambiente.**
Portanto, seus valores estão registrados como `null` no
manifesto e `alfred_vintage_agreement_verified=false`.

É proibido completar essas duas lacunas copiando 324,054 do BLS,
de dados atuais da série ou inferindo que a ALFRED concorda.
O confronto comprovado nesta etapa é **BLS original versus BLS
comunicado posterior**; a reconciliação *independente* ALFRED
continua pendente.

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
nas duas datas de vintage. Conferir o valor específico
de **dezembro/2025**, registrar fonte bruta, hashes e
instante de aquisição REAL de hoje (não retrodatado).
Se o CSV exigir interação ou não estiver acessível, conservar
`null` e informar a pendência; não fabricar um valor.

Depois, auditar o consenso da mesma divulgação junto de
seu horário público de disponibilização. Uma pesquisa
trimestral SPF não é o consenso de 08h30 daquela notícia.

**LAB/HARD NO-GO:** não houve compra, API paga, chave,
merge, deploy, Worker, cron, ordem, ou alteração no Radar.
