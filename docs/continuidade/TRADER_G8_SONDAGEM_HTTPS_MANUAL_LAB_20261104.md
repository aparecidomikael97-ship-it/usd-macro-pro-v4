# AtlasQuant Trader — primeira sondagem HTTPS manual do catálogo G8 (LAB)

Data: 04/11/2026 · PR #1815 · SEM deploy, Worker, agendador ou feed ativo.

## Problema e avanço

Até esta etapa, o catálogo de 16 fontes G8 aceitava apenas **recibos
documentais informados pelo chamador**, que não provavam sequer que
alguma requisição HTTP havia sido executada.

Criado `atlasquant_trader_g8_single_https_probe_lab.py`. É uma rotina
de **uma consulta manual por invocação**, desativada por padrão. Sem
opção explícita `manually_authorized=True` devolve bloqueio e faz
**zero chamadas HTTP**. Não roda ao importar, não grava snapshots,
não atualiza a interface e não dispara tarefas periódicas.

A rotina exige:
- Identificador de fonte exatamente no catálogo `SOURCES`;
- URL exata do catálogo (não aceita URL livre do chamador);
- HTTPS padrão de Python com `ssl.create_default_context()`;
- Sem redirecionamento automático e sem mudanças de URL final;
- Resposta 200, tipo permitido, não comprimida e limite de 256 KiB;
- Timeout de 1–15 segundos, não controlado por serviço remoto;
- SHA-256 dos **bytes recebidos**, tamanho e horário observado pelo
  relógio do próprio AM12. O cabeçalho `Date` é **declarado pelo
  servidor e não é prova histórica**.

Esse registro apenas comprova que **a rotina observou uma resposta
HTTP naquele momento no computador**, solicitando verificação TLS
convencional. A cópia de bytes não é guardada: logo o hash isolado
não é um arquivo histórico auditável. Sem acesso a valores econômicos
estruturados, sem prova point-in-time pré-evento, nem garantia da
origem ou custódia de uma divulgação específica. Não compõe viés.

## Uma consulta real, pontual, sem custos novos

Em 04/11/2026 23:45:36 UTC, sondagem manual do lead
`US_BLS_CPI` (`https://www.bls.gov/schedule/2026/`) retornou:

- estado: `LAB_CURRENT_OFFICIAL_HOST_HTTP_RESPONSE_OBSERVED`;
- HTTP 200, `text/html`, **100822 bytes**, sem redirecionamento;
- SHA-256 dos bytes:
  `45edf9cc824f317bb9e714e4763744f8decd745f666454bc78676e4a3325c0f6`;
- `http_endpoint_observed_this_session=true`;
- `historical_point_in_time_availability_verified=false`;
- `original_publisher_payload_authenticated=false`;
- `economic_indicator_value_extracted=false`;
- `trade_authorized=false`.

Trata-se de uma página de **calendário de divulgação**, não de valor
oficial de CPI nem de série histórica de inflação. O teste não
autoriza alegações como "CPI veio acima do esperado" ou força de USD.

## Testes e limites

Oito casos novos, usando mock de transporte, sem rede:
bloqueio por padrão; ID/timeout inválido; uma resposta observada;
URL exata nos 16 leads; redirecionamentos; status/mídia; corpo
vazio, excessivo ou incoerente; erro de transporte.

`python -m unittest -q test_atlasquant_trader_g8_official_source_receipt_lab.py`
deu **52 PASS** no AM12, com `python -m py_compile` e
`git diff --check` verdes. A Quality remota do novo SHA deverá
ser confirmada separadamente.

Ainda não há download persistente assinado, certificação de publicação
de indicadores, consenso anterior ao evento, notícia geopolítica
autenticada, preços spot independentes ou backtest OOS.
Permanece **HARD NO-GO / AGUARDAR** em D1/W1/MN1 e em operações.
Não há novas despesas ou execução automática.
