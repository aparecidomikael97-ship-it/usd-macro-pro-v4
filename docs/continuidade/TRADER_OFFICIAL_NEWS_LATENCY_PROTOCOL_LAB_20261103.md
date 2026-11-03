# AtlasQuant Trader — protocolo de atraso de notícias oficiais (LAB, 03/11/2026)

**Não há feed ligado, monitoramento, execução, cron, Render alterado, API paga nem subscrição.** Este protocolo é 100% offline, para determinar se os caminhos oficiais gratuitos têm atraso relevante ANTES de pedir autorização para gastar com outro fornecedor.

## Evidência que precisamos, sem confundir relógios

O módulo `atlasquant_trader_official_news_latency_lab.py` aceita, **somente para os dois eventos BLS com horário previsto conhecido**, um registro por evento com os seguintes instantes:
- `scheduled_release_at_utc`: horário oficial PROGRAMADO do evento. **Não comprova quando o BLS publicou nem quando o feed recebeu a notícia**.
- `feed_published_at_utc`: `pubDate` alegado pelo feed (metadado do emissor), **não uma prova de divulgação real ou um recibo independente**.
- `first_seen_at_utc`: primeira detecção ALEGADA no sistema que consultou a fonte.
- `captured_at_utc`: recebimento/captura ALEGADO do payload.
- `displayed_at_utc`: exibição ALEGADA ao usuário.

O protocolo calcula cinco intervalos descritivos em segundos somente se esses instantes forem coerentes e anteriores ao instante de avaliação. Mantém o modo explícito `SYNTHETIC_CONTRACT_TEST` ou `MANUAL_UNATTESTED`. SHA-256 do corpo recebido confere integridade após o registro, **não autenticidade do servidor, relógio de captura ou o evento no conteúdo**. Nenhum XML de origem é executado ou convertido em resultado/consenso/sinal. O corpo fica apenas em memória e não é arquivado nem enviado para o Radar.

A ingestão por HTTP, metadados TLS, certificados, assinatura/timestamp de terceiros, primeira observação confiável, atraso real e disponibilidade histórica NÃO foram implementados nem atestados. O estado dos dois modos continua `news_delay_verified=false`. Importante: pubDate pode diferir do instante de disponibilização do dado, e horário do calendário não é uma observação de latência.

## Eventos que o piloto aceita

- Emprego EUA em **06/11/2026 13:30 UTC** (horário programado BLS), entrada documental `BLS_US_EMPLOYMENT_20261106`, fonte prevista `https://www.bls.gov/feed/empsit.rss`.
- CPI EUA em **10/11/2026 13:30 UTC**, entrada `BLS_US_CPI_20261110`, fonte prevista `https://www.bls.gov/feed/cpi.rss`.

**Copom de 04/11 e MPC BoE de 05/11 não entram no cronômetro em segundos:** a agenda cadastrada possui apenas o dia (DATE_ONLY). Eles seguem no roteador de notícias, mas sem inventar um horário preciso.

## Proteções

- Lista fechada de eventos, feeds BLS, hosts HTTPS e caminhos de item; IDs duplicados impedidos para não escolher a detecção mais favorável.
- Exige HTTP 200 DECLARADO, tipo RSS/XML permitido e bytes UTF-8 finitos com SHA-256 correspondente; arquivos adulterados, fonte/host diferente, clock impossível ou informação futura são recusados.
- Cortes conservadores: piloto recusa sequência de mais de 7 dias após evento ou apresentação com mais de 2 dias após primeira detecção. Isso é triagem LAB, não SLA real.
- Nenhum resultado liberado para previsão ou operação, nem para afirmar que fornecedor gratuito é melhor/pior que um pago.
- A regra de avaliação de custo exige **no mínimo 10 eventos com recibos de entrega independentes** como critério candidato; esta etapa tem **0 recibos independentes**, e dispõe de apenas dois eventos elegíveis: portanto **não recomendamos contratar nada** com base nesses números.

## Estado da pesquisa em 03/11

Não existe amostra real pós-lançamento dos eventos de 06/11 e 10/11 — eles ainda são futuros. Os exemplos dos testes são payloads e horários **INVENTADOS EXPLICITAMENTE PARA TESTAR O CONTRATO**. A aparência de segundos calculados nos testes NÃO deve ser citada como medição de desempenho do BLS.

**Prioridade prática seguinte:** após as divulgações, obter provas dos horários de publicação e entrega, revisar direitos de uso e custos de qualquer automação, comparar uma amostra suficiente de eventos e só então avaliar se uma fonte paga traz vantagem concreta. Para antecipação, a qualidade/atualização de **consensos e reprecificação antes dos eventos** é um eixo diferente da latência das notícias.

Testes: `python -m unittest -q test_atlasquant_trader_official_news_latency_lab.py`. Integrado ao CI Quality para verificação remota, sem permissão de deploy ou pagamento.

**PR #1803 DRAFT / HARD NO-GO.**
