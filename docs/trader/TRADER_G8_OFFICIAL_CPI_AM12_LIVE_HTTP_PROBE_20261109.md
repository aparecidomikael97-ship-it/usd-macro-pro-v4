# AtlasQuant Trader — primeira verificação HTTPS real de CPI no AM12 (LAB)

Referência local: 09/11/2026, noite em Cuiabá (UTC−04). Consulta somente leitura; nenhum dado de conta, broker, MT5 ou ordem foi acessado.

## Fontes oficiais e resultados observados

Ambas as URLs abaixo foram identificadas em páginas dos próprios emissores oficiais. As requisições diretas foram executadas no Python 3.12.10 do PC **am12**, usando `urllib.request` e TLS padrão, sem salvar o corpo ou seguir fluxo de autenticação.

### 1. Bureau of Labor Statistics (EUA) — arquivo CPI setembro/2026

- URL: https://www.bls.gov/news.release/archives/cpi_10142026.htm
- O documento arquivado indica divulgação em **14/10/2026, 08h30 ET**. Esse é conteúdo declarado na página oficial consultada posteriormente, **não** prova de presença naquele instante exato nem primeira captura nossa.
- Requisição direta no AM12: **HTTP 403 Forbidden**. Nenhum corpo de release foi aceito nem gerou hash de fonte; não foram feitas tentativas de contornar o bloqueio.
- Estado: `BLOCKED_SOURCE_ACCESS`, sem valor macro verificado ou sinal.

### 2. Eurostat — flash HICP área do euro outubro/2026

- URL: https://ec.europa.eu/eurostat/web/products-euro-indicators/w/2-04112026-ap
- Página oficial identifica `Flash estimate - October 2026`, titulada `Euro area annual inflation up to 4.0%`, com data editorial **4/11/2026**. O valor apresentado pela fonte é uma **estimativa preliminar**, não CPI final nem surpresa macro calibrada.
- Requisição direta no AM12: **HTTP 200**, URL final igual à URL solicitada, `Content-Type: text/html;charset=UTF-8`; `Last-Modified` ausente nas respostas.
- **Primeira consulta:** 347.622 bytes; SHA-256 `e79ed504f30ac3afa12474a5d1eacd82433764fccbed4b3590c326802ec877c8`; cabeçalho HTTP `Date: Tue, 10 Nov 2026 01:00:29 GMT`.
- **Segunda consulta:** início do relógio local `2026-11-10T01:01:09.365458+00:00`; fim `2026-11-10T01:01:11.300069+00:00`; cabeçalho `Date: Tue, 10 Nov 2026 01:01:17 GMT`; 347.623 bytes; SHA-256 `a3017302bf31e0b4c9d950029be68c599aea82dcbcd70adb30f6d216d5a1c347`; texto contém `October 2026`.
- **Os dois corpos HTML diferiram em 1 byte de tamanho e no SHA-256.** Isto **não** demonstra que o Eurostat revisou a estimativa de inflação; páginas HTML podem incluir conteúdo dinâmico, formatação, marcadores de sessão etc. Não foi executada comparação semântica por campos econômicos.
- Não foi armazenada cópia dos bytes HTML; portanto, os hashes são um **diagnóstico observado** nesta rodada, não um arquivo histórico reproduzível nem prova permanente de custódia.

## Cautela com o relógio

O serviço W32Time no AM12 estava sem sincronização confirmada em verificações anteriores. Nesta coleta, o cabeçalho `Date` da segunda resposta ficou aproximadamente seis segundos à frente do fim registrado pelo relógio do PC. Isso **sugere** diferença de relógio, mas o cabeçalho não é um relógio independente certificado, e o trânsito da requisição introduz incerteza. Não usar os horários para afirmar disponibilidade *point-in-time* em outubro/novembro, nem para liberar D1/W1/MN1.

## Ferramenta reproduzível adicionada

`atlasquant_trader_g8_cpi_http_probe_lab.py`:

- URL estritamente limitada ao host emissor do CPI de cada moeda, HTTPS com configuração padrão de TLS;
- **uma** requisição GET, sem tentativas automáticas, sem cookies/credenciais, sem aceitar redirecionamentos, com limite de 1 MiB, timeout e MIME HTML/PDF;
- coleta em memória de `status`, URL final, HTTP `Date`, `Last-Modified`, tamanho, SHA-256, relógio local antes/depois;
- retorna os bytes apenas ao chamador da biblioteca, sem gravá-los. A CLI imprime somente metadados e hash, nunca o HTML inteiro;
- mesmo com resposta 200 mantém `original_publisher_bytes_at_first_release_attested=False`, `source_history_point_in_time_verified=False`, `collector_clock_independently_attested=False`, `operational_bias=AGUARDAR`.

**Validação:** 8 novos testes sintéticos para resposta normal, oito hosts, domínio incorreto, redirecionamento, HTTP 403, MIME/tamanho inválidos, relógios inválidos e bytes diferentes sem revisão econômica. **123/123 testes locais PASS** junto das cinco suítes G8 anteriores. O novo script foi testado localmente por simulação; a execução real no AM12 desta rodada usou comandos Python equivalentes de diagnóstico, **não** a versão recém-criada do script.

## Próximas barreiras

1. Rodar o script versionado no AM12 e guardar um recibo auditável **com o corpo original** e manifesto em pasta LAB isolada, depois de resolver a confiabilidade do relógio; capturas atuais não devem ser retrodatadas para o dia da divulgação.
2. Tratar a resposta 403 do BLS como limite de acesso. Buscar acesso institucional/documentação do BLS sem contornar a proteção.
3. Extrair campos econômicos (país/região, referência, `FLASH/FINAL/REVISION`, unidade, taxa) e comparar versões semanticamente, com prova de publicação e calendário histórico antes de qualquer viés.

Sem merge, deploy, agendamento, worker, gasto, acesso ao MT5/conta ou trade.
