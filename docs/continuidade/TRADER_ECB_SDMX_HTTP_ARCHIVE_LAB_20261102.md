# AtlasQuant Trader — captura HTTP oficial BCE EXR (LAB, 02/11/2026)

PR #1803 DRAFT · HARD NO-GO · sem deploy, merge, cron, Worker, sinais ou ordens.

## Resultado verificável

Em **02/11/2026**, foi executada uma consulta manual HTTP GET à **API oficial do BCE**,
sem autenticação ou API paga, com sete séries EUR-base para AUD, CAD, CHF, GBP,
JPY, NZD e USD, intervalo 26/10/2026–02/11/2026.

- Endpoint exato: https://data-api.ecb.europa.eu/service/data/EXR/D.AUD+CAD+CHF+GBP+JPY+NZD+USD.EUR.SP00.A?startPeriod=2026-10-26&endPeriod=2026-11-02&format=csvdata
- HTTP 200; `Content-Type: text/csv`.
- `Date` observado no cabeçalho HTTP: **2026-11-02T21:52:10Z**.
- `Last-Modified` observado no cabeçalho: **2026-11-02T14:57:16Z**.
- Comando manual concluiu até **2026-11-02T21:52:24Z** (relógio local do executor).
- CSV original versionado: `docs/continuidade/ecb_exr_g8_20261026_20261102_raw.csv`.
- Manifesto ao lado: `TRADER_ECB_SDMX_ARCHIVE_MANIFEST_LAB_20261102.json`.
- Tamanho da resposta CSV: **9457 bytes**, SHA-256: `308439eb0230551fd7f80fa134a4c92829c81d8fcddaf94425bcb891c6e96038`.
- **42 observações**, sete moedas × seis datas de referência:
  26, 27, 28, 29, 30 de outubro e 2 de novembro.
- Conferência numérica: as sete taxas dos dias 30/10 e 02/11 coincidem
  com o caso documental anterior. O CSV entrega `0.8338` (GBP 30/10)
  onde a página mostra `0.83380`; isso é a **mesma taxa decimal**,
  não uma divergência nem autorização para alterar o texto do CSV.

## Escopo do código e limites

`atlasquant_trader_ecb_sdmx_archive_lab.py` é **offline**: recebe bytes
já guardados e manifesto, sem disparar HTTP. Valida SHA-256/tamanho,
endpoint permitido, respostas/relógios declarados, esquema EXR,
set completo das sete moedas em cada data, datas declaradas,
taxas decimais, duplicações e estado das observações. Recusa erros
e mantém as flags de Radar, OOS, Worker, scheduler e ordens em falso.

**O hash prova somente que os bytes guardados correspondem ao manifesto.**
Manifesto e bytes foram guardados juntos; nenhum deles é assinatura do BCE.
Cabeçalhos HTTP e horário do executor são metadados observados, não
recibos assinados por testemunha independente. `Last-Modified` da
resposta não é a hora provada de publicação de cada taxa e não define
disponibilidade histórica ponto-no-tempo. O primeiro download deste
lote foi **depois** das datas antigas: não se pode retroagir esse
horário para fingir que a série estava disponível na época.

Essas 42 observações são referências informativas do BCE, **não OHLC,
ticks, preços executáveis ou 28 fontes spot independentes**. Os 21
cruzamentos não-EUR são apenas álgebra a partir das sete pernas.
Não há base para exibir sinal, Top 10 operacional, desempenho real
nem viés preditivo D1/W1/MN1. A série curta também não calibra W1/MN1.

## Procedimento manual reproduzível (não automatizado)

1. Revisar no site oficial a convenção da série `EXR.D.*.EUR.SP00.A`
   e a política de reutilização estatística.
2. Em ambiente aprovado, consultar **manualmente** o endpoint acima.
   Não adicionar chave ou tarefa agendada.
3. Guardar os bytes UTF-8 **exatamente como recebidos**, datas e headers
   HTTP da consulta, sem reformatar CSV nem converter casas decimais.
4. Calcular SHA-256 sobre os bytes e guardar manifesto em mesma revisão.
   Uma resposta posterior pode mudar, e deve gerar **novo** registro,
   nunca sobrescrever silenciosamente a amostra anterior.
5. Executar `python -m unittest -q test_atlasquant_trader_ecb_sdmx_archive_lab.py`;
   Quality CI roda os mesmos contratos sem rede. Falha implica recusa.

Referências oficiais:
- https://data.ecb.europa.eu/help/api/data-examples
- https://data.ecb.europa.eu/data/datasets/EXR/EXR.D.USD.EUR.SP00.A
- https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html
- https://www.ecb.europa.eu/stats/ecb_statistics/governance_and_quality_framework/html/usage_policy.en.html

Próximos portões: política comercial revisada; captura com evidência
independente do instante de disponibilidade; fonte FX spot externa,
autorizada e sincronizada para M15/H1/H4; estudo OOS com custos e
calibração pré-definidos. Nenhuma dessas condições foi satisfeita por
esta captura. **HARD NO-GO permanece obrigatório.**
