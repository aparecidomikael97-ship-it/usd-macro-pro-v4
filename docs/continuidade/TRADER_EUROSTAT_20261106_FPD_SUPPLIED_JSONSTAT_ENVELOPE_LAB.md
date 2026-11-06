# AtlasQuant Trader — envelope JSON-stat FPD recebido de terceiros (LAB)

**06/11/2026. Nenhuma resposta real da API Eurostat foi obtida neste ensaio.**

## Objetivo restrito

Inspecionar **offline** um único objeto JSON-stat 2.0 que alguém forneça como
possível resposta de `prc_hicp_fpd` para a área do euro em **setembro de 2026**.
O módulo `atlasquant_trader_eurostat_fpd_ea21_payload_envelope_lab.py` nunca
realiza HTTP, não aciona agendamento e não interpreta um número de inflação.

Ele só aceita um envelope sintético ou fornecido manualmente com:

- Alegação de URL HTTPS no host e caminho oficiais, e filtros exatos para
  `geo=EA21`, `freq=M`, `time=2026-09`; `unit`, `coicop` e `release`
  são **códigos ainda não confirmados contra a resposta real**.
- Até 64 KiB de JSON UTF-8, sem chaves duplicadas ou valores não finitos;
  `class=dataset`, `version=2.0`, `source=ESTAT`, seis dimensões de
  cardinalidade unitária e uma única observação numérica estrutural.
- Data `updated` declarada no próprio JSON não posterior ao relógio de
  captura informado, que por sua vez não pode superar o horário de análise.
- Contexto documental existente e conferido por SHA-256 sobre Eurostat EA21
  e EUR/USD. O recorte de setembro não é liberado nem documentalmente
  antes do piso conservador de 17/10/2026 UTC.

Se passar, a saída é somente
`LAB_SUPPLIED_JSONSTAT_ENVELOPE_QUARANTINED_NOT_SOURCE_ATTESTED`, com hash
dos bytes **fornecidos**, quantidade de bytes e metadados estruturais.
Se falhar, devolve `LAB_BLOCKED`. Em nenhum caso a observação numérica é
devolvida, convertida em inflação, comparada com USD ou transformada em
direção compradora/vendedora.

## Limites incontornáveis do ensaio

**O URL também é uma alegação do remetente** — checar a grafia do endereço
não atesta TLS, HTTP, origem do conteúdo nem o momento em que a Eurostat
efetivamente serviu os bytes. O timestamp `updated` também é auto-declarado.
O contrato real do dataset pode conter outros códigos, dimensões ou valores
que este protótipo desconhece; um erro de schema implica bloqueio, e não
adaptação silenciosa.

O dataset `prc_hicp_fpd` registra primeira publicação, mas **não equivale a
um arquivo imutável de todas as versões**: segundo a própria Eurostat,
os dados iniciais de janeiro/2026 foram alterados indevidamente em março
e restaurados em abril. A API oficial normalmente fornece a versão mais
recente, sem mecanismo geral de reconstrução de cada instante histórico.

Links primários:

- [Eurostat: API de dados](https://ec.europa.eu/eurostat/en/web/user-guides/data-browser/api-data-access/api-introduction)
- [Eurostat: dataset `prc_hicp_fpd`](https://ec.europa.eu/eurostat/databrowser/product/page/prc_hicp_fpd)
- [Eurostat: aviso de correção HICP](https://ec.europa.eu/eurostat/web/hicp/information-data)
- [Eurostat: outubro de 2026, EA21 e flash](https://ec.europa.eu/eurostat/web/products-euro-indicators/w/2-04112026-ap)

## Testes e próximo portão

Os testes usam **exclusivamente objetos falsos e explícitos** (inclusive um
valor fictício 777) para comprovar o isolamento. O código `FIN` e a unidade
`RCH_A` presentes na massa de teste são **hipóteses sintéticas**, não valores
confirmados do dataset; nunca devem migrar para conectores reais por cópia.

Próximo portão: receber legalmente uma resposta oficial pequena com recibo
verificável de obtenção e consultar os códigos reais do catálogo. Isso exige
uma rota de rede autorizada, ou envio do recibo pelo usuário. Sem ela, só há
teste de estrutura, não autenticação nem avaliação *point-in-time*.

**Política inalterada:** D1/W1 dos 28 pares em `AGUARDAR`; 0 previsões
validadas; acurácia não calculada; 0 solicitações HTTP e R$ 0 novos; sem
operação, deploy, merge, Worker, publicação ou alteração das três abas.
