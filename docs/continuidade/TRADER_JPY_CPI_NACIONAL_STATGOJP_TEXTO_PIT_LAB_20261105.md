# AtlasQuant Trader — JPY: CPI nacional do Japão, separação das variantes (LAB)

**Pesquisa:** 05/11/2026. **Escopo:** leitura preparatória de texto UTF-8 explicitamente fornecido, sem download do HTTP original nem captura histórica.

## Fonte primária confirmada

Statistics Bureau of Japan, divulgação nacional do CPI:
https://www.stat.go.jp/data/cpi/sokuhou/tsuki/index-z.html

Na página consultada, a observação nacional mais recente é **setembro/2026**, com data de publicação de calendário **23/10/2026**, na base de índice **2025=100**:

| Medida oficial da divulgação nacional | Índice base 2025 | Taxa anual divulgada |
| --- | ---: | ---: |
| Todos os itens, **headline** | 102,2 | 2,1% |
| Todos os itens **exceto alimentos frescos** | 102,3 | 2,1% |
| Todos os itens **exceto alimentos frescos e energia** | 102,8 | 2,4% |

A página oficial de resultados distingue **Japão nacional** de **prévia da área de Tóquio**, que possui calendário e cobertura geográfica próprios: https://www.stat.go.jp/data/cpi/1.htm. A base japonesa mudou para 2025 a partir do relatório de 2026 publicado em agosto; os índices das bases 2020 e 2025 não podem ser misturados sem rebase documentado: https://www.stat.go.jp/english/data/cpi/index.html.

## Leitor protegido

`atlasquant_trader_jp_national_cpi_summary_text_lab.py` recebe somente **texto UTF-8 extraído** e um horário de observação local informado. O parser exige a frase de `2025年基準` e `全国`, mês de referência, data de calendário e os **três** grupos numerados de indicadores nacionais. Recusa Tóquio como substituto, anos da era Reiwa incompatíveis, linhas duplicadas, números inválidos, HTML bruto, horários ausentes e datas de divulgação futuras no calendário japonês. Converte ``下落`` (queda) em taxa negativa e ``横ばい`` (estabilidade) em zero somente quando o valor publicado é zero.

O leitor **não recalcula a taxa anual a partir do índice arredondado**. A própria fonte oficial alerta que taxas publicadas podem diferir do cálculo com valores de índice arredondados: https://www.stat.go.jp/data/cpi/1.htm.

Em entradas de teste sintéticas, o indicador japonês aparece de modo **opcional e explicitamente marcado como transcrição não atestada** na matriz dos 28 pares, com `series_kind=JP_NATIONAL_CPI_ALL_ITEMS_2025_BASE_YOY_TRANSCRIBED_TEXT` e status `SUPPLIED_OFFICIAL_PAGE_TEXT_STRUCTURALLY_PARSED_UNATTESTED`.

- Sem JPY fornecido, o comportamento atual da matriz não muda.
- Com EUR, USD, GBP e JPY num teste totalmente sintético, **6 pares** passam a ter os dois lados numericamente preenchidos, **16** têm apenas um lado, **6** nenhum lado.
- Nenhum deles recebe comparação metodológica, subtração internacional de inflação, ranking de força, viés direcional ou permissão de negociação.

## Pendências para integração com fonte real

1. Capturar bytes genuínos do site do órgão japonês ou extrato oficial de e-Stat, com URL, hash, data de coleta, formato/charset, TLS, série e direitos de uso.
2. Validar a extração de texto contra bytes reais (o leitor de texto ainda **não** aceita HTML oficial sem extração auditada).
3. Localizar versões anteriores/vintages, horários independentes de divulgação e consenso pré-evento. Não confundir data de calendário com instante de publicação.
4. Só então estudar os pares com JPY com preços M15 independentes e validação fora da amostra.

**HARD NO-GO**, sem Worker, Render, merge, deploy, compra de serviço, sinal ao vivo ou trade. Etapa na PR Draft #1815; interface PR #1816 preservada.
