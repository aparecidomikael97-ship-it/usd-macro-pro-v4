# AtlasQuant Trader — Eurostat `prc_hicp_fpd`: EA21 e histórico de primeira publicação

**Pesquisa retrospectiva em 06/11/2026 — LAB, sem captura API nem sinal FX.**

## Descoberta 1 — o euro de 2026 é EA21, não EA20

A [nota oficial do Eurostat para outubro de 2026](https://ec.europa.eu/eurostat/web/products-euro-indicators/w/2-04112026-ap)
registra que a Bulgária se juntou à área do euro em **01/01/2026**.

- **Até dezembro de 2025:** composição **EA20**.
- **De janeiro de 2026 em diante:** composição **EA21**.
- A publicação *Euro indicators* usa a composição que evolui com o tempo:
  EA20 antes da entrada da Bulgária, EA21 depois. Não se deve confundir
  este encadeamento com uma série de composição fixa.

**Correção aplicada** ao catálogo do PR #1828 (em nova revisão empilhada):
o experimento futuro agora procura a geografia **EA21**, nunca EA20
para a área do euro corrente em 2026. Isso corrige a documentação de
pesquisa; **não** altera o viés EUR nem opera o mercado.

## Descoberta 2 — dados publicados inicialmente não são prova imutável

O [dataset oficial `prc_hicp_fpd`](https://ec.europa.eu/eurostat/databrowser/product/page/prc_hicp_fpd)
declara armazenar valores de índices e variações mensais/anuais tal como
publicados pela primeira vez. Sua estrutura documenta as dimensões
`freq`, `unit`, `coicop`, `release`, `geo` e tempo, conforme o Data Browser.
Em 2026, utiliza a classificação **ECOICOP versão 2 (COICOP 2018)**.

O próprio [Eurostat informa uma exceção relevante](https://ec.europa.eu/eurostat/web/hicp/information-data):

1. **25/02/2026:** primeira divulgação dos dados completos de janeiro.
2. **03/03/2026:** atualização indevida desse conjunto de primeira publicação.
3. **24/04/2026:** restauração do conjunto original de primeira publicação.

Logo, mesmo uma base chamada *first published* precisou de correção.
Sem os bytes originais e a comprovação do horário em que eles estavam
disponíveis, não podemos tratá-la como testemunha histórica perfeita.

## Descoberta 3 — outubro *flash* não é outubro completo

| Em 06/11/2026 | Situação documental |
|---|---|
| HICP **completo de setembro/2026** | Dataset indica última observação 2026-09, atualizado em 16/10 |
| HICP **flash de outubro/2026** | Página divulgada em 04/11, referência retrospectiva separada |
| HICP **completo de outubro/2026** | Divulgação **agendada para 18/11**, número não capturado nem inferido |

Fontes: [dataset first released](https://ec.europa.eu/eurostat/databrowser/product/page/prc_hicp_fpd),
[Eurostat — outubro flash](https://ec.europa.eu/eurostat/web/products-euro-indicators/w/2-04112026-ap).

O módulo novo usa piso conservador **17/10 00:00 UTC** para tornar visível
somente a *referência ao metadado* de setembro no laboratório. O *flash*
de outubro segue o piso documentado no caso EUR/USD existente (05/11 UTC).
Mesmo depois de 18/11, o laboratório **não inventa** HICP completo sem
uma captura e pesquisa novas.

## O que foi e o que não foi verificado

**Confirmado em páginas oficiais:** código do dataset, dimensões em texto,
mudança EA20 → EA21, classificação ECOICOP v2, datas de atualização e
correção, datas do *flash* e próximo conjunto completo.

**Ainda pendente:** resposta original da API, códigos de dimensão efetivamente
retornados, disponibilidade específica de `geo=EA21`, unidade exata de taxa
anual, códigos da dimensão `release`, carimbo de disponibilização histórica,
licença para redistribuição, consenso pré-evento e verificação quantitativa.
A [API oficial](https://ec.europa.eu/eurostat/en/web/user-guides/data-browser/api-data-access/api-introduction)
tem formatos de resposta, inclusive JSON-stat, mas uma consulta filtrada não
ficou acessível nesta investigação. **Não declaramos download executado.**

**Estado final:** rascunho LAB offline, sem publicar, sem Worker, sem sinal,
sem pontos no ranking e sem custo novo. Todos os vieses D1/W1 seguem
`AGUARDAR`. O próximo experimento será **inspecionar uma resposta real e
pequena do dataset filtrado**, com recibo de origem, sem assumir schema
pelas páginas de documentação.
