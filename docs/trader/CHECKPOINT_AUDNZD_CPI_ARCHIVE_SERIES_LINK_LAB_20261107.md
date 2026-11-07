# AtlasQuant Trader — vínculo da evidência CPI AUD/NZD (LAB, 07/11/2026)

**Prioridade P0:** dados econômicos verificáveis das **duas moedas** antes de qualquer viés W1/D1. **Estado:** implementação apenas em branch isolada, sem integração ao aplicativo, ao Radar, ao G8 V1, à escala 0–10 ou à execução de operações.

## Avanço desta etapa

Foram ligados dois validadores existentes — `atlasquant_audnzd_cpi_archive_receipt_lab.py` (PR #1849) e `atlasquant_cpi_series_contract_lab.py` (PR #1848) — por meio de `atlasquant_cpi_archived_series_link_lab.py`.

O novo vínculo só classifica os registros trimestrais de setembro de 2026 como **evidência descritiva vinculada** quando:

1. Os bytes das cópias arquivadas do XLSX ABS Tabela 17 e PDF Stats NZ coincidem exatamente com os hashes já fixados no LAB e seu conteúdo é extraído com sucesso;
2. O contrato V2 aceita país AUD/NZD, identidade interna da série, frequência trimestral, competência, números, datas de publicação/captura/decisão *declaradas pelo chamador* e domínio do órgão;
3. Cada registro de série usa o hash correto do arquivo correspondente, a competência `2026-09`, a data de divulgação declarada correspondente e o valor numérico reproduzido do documento;
4. Nenhuma condição de look-ahead estrutural é detectada. Uma revisão que muda período, valor, hash, frequência ou data de divulgação é recusada.

**Leituras registradas:** índice ABS `Data1!J319=99.73` e `J323=103.64`, dando **3,9% a/a arredondado de índices publicados**; CPI Stats NZ **3,7% a/a reportado**, ambos referentes a setembro/2026. A diferença descritiva é **0,2 ponto percentual**, **não** previsão de direção AUD/NZD. Mesmo com periodicidade igual, cestas e metodologias nacionais não estão harmonizadas e a causa de movimento do FX não está comprovada.

## Evidência e limites

- SHA256 ABS XLSX (cópia arquivada): `59c89bf477cec8075dfa80f1c29f97654f16f148b11427bed35fbad869eb7d47`.
- SHA256 Stats NZ PDF (cópia arquivada): `c0c685d36bdaa6afcaabba7bd1b656e4b46120032eb41d0a4e6dc01af0901bb7`.
- Comparar bytes a essas cópias arquivadas **não** autentica a origem junto ao emissor, data/hora original de publicação, revisão histórica disponível na época da decisão, disponibilidade P-I-T, expectativas anteriores ao dado ou independência da coleta.
- Os timestamps específicos nos testes são **exemplos sintéticos declarados**; o documento arquivado contém apenas a **data alegada** de divulgação, não a hora independentemente atestada. Portanto `historical_point_in_time_verified=False`, `release_instant_independently_attested=False`, `capture_instant_independently_attested=False` e `issuer_origin_independently_authenticated=False` em todos os retornos.
- O módulo V2 ainda usa identificadores *internos* `AUD_QUARTERLY_CPI_YOY` e `NZD_QUARTERLY_CPI_YOY`, não IDs originais completos do emissor; só este par/período está coberto pelo vínculo.
- `score_0_to_10=None`, `probability_of_directional_move=None`, `can_feed_live_radar=False`, `automatic_alert_enabled=False`, `trade_authorized=False`, `operational_bias=AGUARDAR` sem exceções.

## Testes nesta rodada

- Em Python 3.13 com cópias XLSX/PDF do próprio projeto: **32 testes aprovados** (`test_atlasquant_cpi_archived_series_link_lab.py` + `test_atlasquant_audnzd_cpi_archive_receipt_lab.py`), sem pulos. Executado também `py_compile` dos dois arquivos novos.
- Os testes sintéticos e os testes com os dois documentos detectam alteração de bytes, incoerência dos números, SHA trocado, competência diferente, série mensal no lugar da trimestral, horários inválidos e tentativa de promover documentação incompatível.
- CI em que não existam as cópias privadas **pula os testes condicionais que usam documentos reais**: os 32 aprovados são resultado da execução **local** com arquivos disponíveis, não uma alegação de aprovação automática do GitHub.

## Próximas prioridades, sem mudar o plano

1. Implementar cadeia de custódia histórica de fontes, ID oficial de cada série, periodicidade por país, datas/horas reais e consultas da época (*vintage point-in-time*); nunca preencher horários faltantes com números inventados.
2. Expandir a prova bilateral a CPI/juros das outras moedas de G8, depois a expectativas, atividade, micro e geopolítica, mantendo política de fontes ausentes = `AGUARDAR`.
3. Somente com dados atestados estudar histórico do comportamento de preço D1/W1, walk-forward fora da amostra e calibração da escala seletiva 0–10; nenhuma vantagem estatística foi demonstrada aqui.
4. Preservar nowcast pré-notícia e notícia × posição como duas camadas distintas, sem ordens automáticas. AION/Negócios/Investimentos seguem congelados; nenhuma cobrança ou deploy.

**Operacional:** nada neste LAB executa ordens, acessa broker, agenda atualização ou muda a interface publicada. Não fazer merge automático.


## Adendo — horário local oficial e conversão UTC (07/11/2026)

**Achado crítico:** a regra anterior só comparava `published_at_utc[:10]` com a data local alegada pelo recibo. Na Nova Zelândia, 22/10/2026 10h45 NZDT equivale a **21/10/2026 21h45 UTC**: a mesma divulgação tem datas diferentes nas duas zonas. Na Austrália, 28/10/2026 11h30 AEDT equivale a **28/10/2026 00h30 UTC**. Testar somente o dia UTC podia rejeitar um horário correto do NZD, aceitar um horário pré-divulgação do AUD ou aceitar um horário já pertencente ao dia seguinte no país da fonte.

**Fontes primárias e relógios divulgados (não testemunhos independentes de acesso ao XLSX/PDF):**
- [ABS — CPI setembro/2026](https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/consumer-price-index-australia/sep-2026): **28/10/2026 às 11h30 AEDT**, `Australia/Sydney`, equivalente a `2026-10-28T00:30:00Z`.
- [Stats NZ — CPI trimestre setembro/2026](https://www.stats.govt.nz/information-releases/consumers-price-index-september-2026-quarter/): **22/10/2026 às 10h45 NZDT**, `Pacific/Auckland`, equivalente a `2026-10-21T21:45:00Z`.

**Correção isolada no módulo de ligação:** manter as horas **locais oficiais** como constantes para esses dois eventos conhecidos, usar `zoneinfo.ZoneInfo` para conversão com horário de verão, rejeitar alegações `published_at_utc` anteriores à hora oficial (`PRE_OFFICIAL_RELEASE_CLOCK`) e comparar a data do recibo com a data na zona do **emissor**, nunca no UTC. Uma alegação com horário igual ou posterior ao comunicado apenas passa essa verificação de consistência; **não** prova que aqueles bytes, aquele consenso ou aquela revisão estavam realmente disponíveis nessa hora.

**Regressões:** seis novos testes locais: conversão exata DST; AUD 1 segundo antes/na hora do release; NZD 1 segundo antes/na hora; NZD dia seguinte local; mantendo teste de recusa de data incorreta. Suíte específica completa com arquivos arquivados: **38/38 PASS localmente**, sem testes pulados; `py_compile` OK. O módulo de recibo fixo e o contrato de séries continuam dependências existentes (não modificados).

**Segurança inalterada:** `release_instant_independently_attested=False`, `capture_instant_independently_attested=False`, `historical_point_in_time_verified=False`, `issuer_origin_independently_authenticated=False`, `can_feed_live_radar=False`, `score_0_to_10=None`, `operational_bias=AGUARDAR` e `trade_authorized=False`. A divulgação oficial conhecida **não** pode substituir a prova de primeira captura dos bytes, o registro do consenso pré-evento ou a cadeia de custódia exigida pelos futuros backtests.

**Próximo P0:** criar política explícita de *primeiro visto* (snapshot de coleta com SHA, relógio observado/externamente comprovado e série/vintage do emissor), separar declaração histórica da coleta real e só então estudar cobertura e disponibilidade temporal dos outros pares. Sem mexer no Radar, na produção ou em orçamento.
