# Trader — fontes primárias G8 e recibos macro não autenticados (LAB, 02/11/2026)

## Objetivo
Preparar a próxima etapa do **viés macro antecipatório D1/W1/MN1**, sem confundir pesquisa de páginas oficiais com um histórico genuinamente observado **antes** de cada previsão. Cobertura documental de USD, EUR, GBP, JPY, CHF, AUD, CAD e NZD; famílias **inflação** e **decisão de política monetária**. Não é um banco de dados econômico, feed de notícias ou modelo direcional.

## Catálogo das fontes
Os links pesquisados estão centralizados em `atlasquant_trader_g8_official_source_receipt_lab.py`. A mesma classificação vale para as 16 fontes (8 moedas × 2 famílias):

| Moeda | Inflação | Juros/política |
| --- | --- | --- |
| USD | BLS | Federal Reserve / FOMC |
| EUR | Eurostat (HICP) | BCE |
| GBP | ONS | Bank of England |
| JPY | Statistics Bureau | Bank of Japan |
| CHF | Swiss FSO | SNB |
| AUD | ABS | RBA |
| CAD | Statistics Canada | Bank of Canada |
| NZD | Stats NZ | RBNZ |

**Atenção:** algumas URLs apontam à página **latest release** ou à lista de comunicados, que muda. Esta página não fornece por si só uma **vintage histórica intradiária**. O catálogo não verifica licença comercial, dados baixados, consenso que estava disponível, reação de mercado ou preços independentes.

## Gate de recibos manuais

`inspect_claimed_macro_receipt_lab` recebe um excerto textual entregue pelo chamador (não realiza HTTP) com identificação da fonte, URL de documento, evento, tipo `SCHEDULED` ou `RELEASED_CONTEXT`, horário de evento, publicação/captura, e hash SHA-256 do texto. Exige:

1. Domínio HTTPS exatamente igual ao portal cadastrado da fonte e nenhum usuário embutido, porta incomum ou fragmento;
2. Publicação ≤ captura ≤ emissão da hipótese;
3. Evento futuro para `SCHEDULED` ou evento não posterior à publicação para `RELEASED_CONTEXT`;
4. Hash e campos estritos, tamanho limitado, horário UTC explícito, nenhum campo `actual` solto.

Mesmo aprovado estruturalmente, o resultado é **`LAB_OFFICIAL_RECEIPT_QUARANTINED_UNATTESTED`**. SHA-256 prova consistência do texto que o chamador forneceu — **não comprova** que esse texto veio da fonte, foi capturado naquela hora, é autêntico, está licenciado ou estava disponível ao mercado em determinada data. O gate recusa promovê-lo ao motor de viés.

## Próxima etapa antes de integrar ao cenário
- Obter capturas independentes e assinaturas/headers/armazenamento durável com relógio confiável, respeitando termos das fontes.
- Definir vintages, periodicidades, série, unidade e calendário exato; ter **consenso pré-divulgação** de origem independente (pesquisa de banco central não é automaticamente o consenso de uma notícia).
- Relacionar cada recibo a **um evento, moeda e horizonte**, sem reutilizar dados de USD para justificar EUR ou índices sem argumento explícito.
- Combinar política monetária, atividade, empregos, inflação, micro e geopolítica com hipóteses condicionais e riscos contrários. Separar indicadores efetivos de expectativas.
- Conduzir backtest walk-forward com cotações FX/índices independentes e observação de divulgação **point-in-time**, sem promessa de 90%. 

## Governança
Sem HTTP, download, API paga, conta, corretora, ingestão real ou atualização de UI. O PR #1803 continua **DRAFT / LAB / HARD NO-GO**. Nenhum merge, deploy, Worker, cron, ordem ou sinal. `can_feed_exante_bias=false`, `macro_direction_inferred=false`, `trade_authorized=false`.

## Referências primárias consultadas
- BLS calendário de lançamentos: https://www.bls.gov/schedule/2026/
- FRED vintages (dia ≠ recibo intradiário): https://fred.stlouisfed.org/docs/api/fred/series_vintagedates.html
- RBA decisões de taxa: https://www.rba.gov.au/monetary-policy/int-rate-decisions/
- BOJ calendário/decisões: https://www.boj.or.jp/en/mopo/mpmsche_minu/
- RBNZ decisões OCR: https://www.rbnz.govt.nz/monetary-policy/monetary-policy-decisions
- SNB política monetária: https://www.snb.ch/en/the-snb/mandates-goals/monetary-policy/decisions
