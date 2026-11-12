# AtlasQuant Trader — primeira captura real de CPI arquivada no AM12 (LAB)

Data local: **09/11/2026, 21h16 em Cuiabá** (10/11/2026 01h16 UTC). Somente pesquisa; MT5, conta e ordens não foram consultados.

## Resultado observado, não simulado

O novo `atlasquant_trader_g8_cpi_http_probe_lab.py`, transferido para `am12`, foi executado **diretamente** no PC autorizado contra a URL oficial do Eurostat:

https://ec.europa.eu/eurostat/web/products-euro-indicators/w/2-04112026-ap

O comunicado é um **FLASH** HICP da área do euro referente a **outubro de 2026**. A página pública indica uma estimativa anual de 4,0% (fonte primária); nosso coletor de bytes ainda **não extrai nem autentica semanticamente** esse número.

- Probe do script versionado: HTTP **200**, URL final igual à solicitada, MIME `text/html`, **347.790 bytes**, hash SHA-256 `2540f9681fee105a5444d3364dc01047f4557153706c47fd11deeff1b15e0484`. Nenhum arquivo criado nessa execução.
- Depois, `atlasquant_trader_g8_cpi_local_archive_lab.py` realizou **uma nova** consulta HTTPS para criar um snapshot local; o HTML pode mudar entre consultas (os hashes acima e abaixo são diferentes). Isso **não** é prova de revisão do CPI.
- **Captura arquivada:** HTTP 200, MIME `text/html`, **347.622 bytes**, SHA-256 `7013d492f8afad1130743c86488afaf1f366fb660d072a35abf69a4c1cbd7525`.
- Relógio local alegado: início `2026-11-10T01:16:34.676590+00:00`, término `2026-11-10T01:16:36.895523+00:00`. Cabeçalho de resposta `Date: Tue, 10 Nov 2026 01:16:42 GMT`; `Last-Modified` ausente.
- A diferença de aproximadamente cinco segundos entre hora local final e `Date` do servidor é evidência adicional de cautela quanto ao relógio do AM12; **não** atesta NTP nem a hora original de divulgação.

## Arquivos no PC do usuário, não no repositório

Pasta de pesquisa isolada:

`C:\Users\apare\AppData\Local\AtlasQuant\LAB\CPI_Official_Probe_20261109_AM12\captures`

Foram criados **somente dois arquivos novos**, por criação exclusiva (sem sobrescrever):

1. `EUR_CPI_FLASH_2026-10_20261110T011636Z_7013d492f8af.html` — os 347.622 bytes da resposta obtida naquela consulta.
2. `EUR_CPI_FLASH_2026-10_20261110T011636Z_7013d492f8af.manifest.json` — URL, moeda, período, etapa `FLASH`, tipo, status, datas alegadas, tamanho e SHA-256; contém flags de não atestação e `AGUARDAR`.

O verificador abriu os dois arquivos e retornou `LAB_LOCAL_ARCHIVE_BYTES_SELF_CONSISTENT_UNATTESTED`. Uma **segunda leitura independente** via Python no AM12 confirmou novamente **347.622 bytes** e o mesmo SHA-256. As duas entradas foram listadas e o manifesto de 25 linhas conferido.

Os arquivos HTML **não** foram enviados ao GitHub, não contêm dados do MT5 nem de contas, e podem ser revistos localmente. A pasta do LAB e os dois arquivos permanecem no AM12.

## Hashes dos scripts transferidos

As cópias no AM12 foram comparadas byte a byte via SHA-256 ao workspace onde passaram nos testes:

| Arquivo | SHA-256 verificado |
| --- | --- |
| `atlasquant_instrument_registry.py` | `f57e8382fb2822aa892b983aaad7672c7695395a7549e8ebee8509bfa86b92c1` |
| `atlasquant_fx_universe.py` | `d19e72461d169e6030159804a5692173961e720b5c73fb63d5a98ba83dc4c0f5` |
| `atlasquant_trader_g8_macro_asof_lab.py` | `9a820a2fb8052262b5a4b09bacae330e3880859f30fc791758074a599513b2d1` |
| `atlasquant_trader_g8_cpi_http_probe_lab.py` | `561351f96a4a6c43f89530fc2fa1815e98cb0ebce5b1e8baf259efa4720d1a12` |
| `atlasquant_trader_g8_cpi_local_archive_lab.py` | `987d6cd413e4d9d9752584a1e8a7b3c333a025ad2104910f9027416203cc2458` |

## Validação e limites

- Novo arquivador `atlasquant_trader_g8_cpi_local_archive_lab.py` e seus **7 testes sintéticos** verificam criação exclusiva, reabertura, adulteração, path traversal, fonte/etapa errada, 403 e mudanças dinâmicas de HTML.
- Suite G8 completa nesta rodada: **130/130 testes locais PASS**. Os testes são sintéticos, mas as capturas HTTP e o arquivo HTML desta seção são reais no AM12.
- As flags `issuer_first_release_authenticated=False`, `clock_independently_authenticated=False`, `historical_point_in_time_eligible=False`, `economic_value_extracted=False`, `operational_bias=AGUARDAR` e `trade_authorized=False` permanecem aplicadas.
- Não existe prova independente do horário da primeira divulgação, da autenticação da página original nesse instante ou da integridade histórica de outubro. O hash do snapshot prova integridade atual **somente se comparado a uma cópia confiável desse registro**, não certificação financeira.
- O BLS continuou com HTTP 403 no teste anterior; **não** houve tentativa de contornar.

Próximo P0: extrair e validar semanticamente o cabeçalho, a região, o período e os **4,0% preliminares** desse HTML; distinguir alterações de layout versus dados; atestar horários e histórico antes de conectar fonte a D1/W1/MN1 ou estimar probabilidades. Sem merge, deploy, worker, scheduler, serviço pago ou ordem.
