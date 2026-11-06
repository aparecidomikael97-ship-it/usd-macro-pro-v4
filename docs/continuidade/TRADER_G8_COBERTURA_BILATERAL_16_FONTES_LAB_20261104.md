# Trader — fonte primária e cobertura bilateral documental G8 (LAB, 04/11/2026)

## Objetivo vinculado ao Checkpoint Mestre

P1: comparar os fundamentos das **duas** moedas de cada um dos 28 pares,
sem chamar documentos recebidos de confirmação independente. P2: dar
visibilidade à ausência ou antiguidade de informações, antes de examinar
viés D1/W1/MN1. A interface aprovada permanece intocada.

## Reuso de contrato existente

`atlasquant_trader_g8_bilateral_receipt_coverage_lab.py` reutiliza:
- `SOURCES`, os 16 portais documentais cadastrados (8 moedas × inflação/
  decisão de juros) em `atlasquant_trader_g8_official_source_receipt_lab.py`.
- `inspect_claimed_macro_receipt_lab`, que recusa HTTPS de outro host,
  horários fora do corte, texto sem hash consistente, campo solto de
  "realizado" e alegações de credencial inexistente.

**Nenhuma informação é baixada nem autenticada** por esse módulo.
Só recebe, classifica e compara recibos textuais fornecidos manualmente.
Um endereço `.gov`, hash SHA-256 ou horário fornecido não prova
conteúdo, custódia, TLS, identidade do publicador nem vintages reais.

## Saída

- Para cada moeda: inflação e política, contagem dos documentos alegados
  de `RELEASED_CONTEXT`, eventos declarados e última publicação.
- Documento de publicação alegada há mais de 90 dias ganha rótulo de
  pesquisa `OLDER_RELEASE_DOCUMENT_CLAIM_ONLY`. **90 dias é um
  limiar interno de triagem, não periodicidade oficial nem garantia de
  atualização**.
- Documentos `SCHEDULED` são contados separadamente e nunca servem
  como prova de divulgação ou de valor realizado.
- Para os 28 pares: estado da moeda-base e moeda-cotada em cada família;
  nenhum par ou período cria inferência de viés negociável.
- Mesmo um lote com os 16 documentos declarados presentes permanece
  `LAB_G8_BILATERAL_DOCUMENTARY_COVERAGE_ONLY`, sem "fonte autenticada".
- Duplicação exata do mesmo (`source_id`, `event_id`) é rejeitada,
  evitando contagens falsas. Lista com mais de 64 itens é recusada.

## Limitações e governança

Ainda faltam: coleta verdadeiramente independente de fonte sob termos
adequados, recibos confiáveis assinados, histórico point-in-time,
consenso pré-evento independente, dados de emprego/atividade,
microeconomia, geopolítica, notícias, calendário em tempo hábil,
dados FX executáveis independentes e backtests walk-forward OOS.

A validação do código serve à integridade do SOFTWARE, não comprova
assertividade de previsão, nem aumenta a contagem de fontes autenticadas.
A PR #1803 continua DRAFT/HARD NO-GO. Sem Worker, Render, cron,
ordens, publicação, novas despesas ou mudanças visuais.

Foram incluídos dez testes novos no arquivo já registrado no job Quality:
lote vazio, agenda futura, documentação unilateral, bilateral, 16
fontes com cautela, antiguidade, URL/hash falsos, duplicação,
horário incorreto e bloqueio de transporte. A conclusão da CI
do commit precisa ser confirmada após o push.
