# AtlasQuant Trader — Importação defensiva de duas vintages ALFRED (somente LAB)

Data da pesquisa: 02/11/2026 | PR #1803 DRAFT | HARD NO-GO

## Resultado do trabalho

A origem do CPI de dezembro/2025 já está confrontada com o BLS e
a **listagem oficial ALFRED de 13/01/2026**. A pesquisa ainda não
conseguiu acessar um **CSV completo de duas vintages** com o valor
de dezembro sob a versão de **13/02/2026**.

Para evitar que um CSV futuro forneça sem aviso a série ATUAL
sob rótulo de passado, criamos
\`atlasquant_trader_alfred_vintage_csv_lab.py\`, que aceita APENAS
um CSV passado explicitamente pelo pesquisador e o manifesto
\`docs/continuidade/TRADER_CPI_BLS_ALFRED_CASO_REAL_LAB_20261102.json\`.
**Não busca nada automaticamente e não insere dados reais no Trader.**

## Fontes e formato do arquivo candidato

A ALFRED oferece uma página oficial para selecionar vintages e
baixar dados de uma série:
https://alfred.stlouisfed.org/series/downloaddata?seid=CPIAUCNS

A documentação oficial descreve a matriz: período de observação
nas linhas e datas de vintage nas colunas:
https://alfred.stlouisfed.org/help/downloaddata

Existe também um endpoint de CSV de gráficos **não documentado
oficialmente** que foi descrito e testado por pesquisador
independente em outubro/2026:
https://prismdatalab.com/posts/alfred-vintages-data-revisions.html

O formato candidato para apenas DUAS versões de CPIAUCNS usa
identificação explícita de **DUAS** séries e duas datas:
\`id=CPIAUCNS,CPIAUCNS\`
e \`vintage_date=2026-01-13,2026-02-13\`.

O CSV esperado tem colunas, na mesma ordem:
\`observation_date,CPIAUCNS_20260113,CPIAUCNS_20260213\`.

**ATENÇÃO**: a fonte de pesquisa alerta que o endpoint não
documentado pode ignorar parâmetros malformados e devolver
a última vintage no lugar da desejada. Mesmo um cabeçalho
correto NÃO comprova que a data é realmente uma data de
revisão; isso exige consulta à lista oficial de vintages.
Nenhuma chamada foi bem-sucedida aqui; não existe CSV
adquirido ou autenticado. Respeitar os termos de uso do ALFRED.

## Validador offline de conteúdo ainda não confiável

A função \`inspect_alfred_cpi_vintages_csv_lab(csv_text, manifest)\`:

- Exige explicitamente as colunas exatas de ambas as datas
  para CPIAUCNS (não CPIAUCSL ou série atual).
- Exige a linha \`2025-12-01\` com os dois valores numéricos
  finitos e positivos, sem duplicatas, sem campos de
  resultado futuro e com limite de tamanho.
- Compara ambos os números candidatos com **324,054**
  do comunicado BLS sem ajuste sazonal.
- Sinaliza divergência para revisão humana; não altera
  os valores para fazê-los combinar.
- NUNCA certifica a origem, o instante histórico da
  disponibilidade, consenso intradiário, licença, histórico
  completo ou assertividade real. Mantém
  \`source_content_authenticated=false\`,
  \`real_historical_custody_verified=false\`,
  \`real_oos_authorized=false\` e
  \`trade_authorized=false\`.

O arquivo de testes fornece um CSV **INVENTADO APENAS
COMO FIXTURE** para verificar que o parser não confunde
colunas ou datas. O valor de fevereiro no manifesto
histórico continua \`null\`; não atualizar esse valor
com a fixture usada em um teste.

### Tests / estados

\`test_atlasquant_trader_alfred_vintage_csv_lab.py\`:
25 testes determinísticos de segurança, incluídos no
Quality CI. Cobrem confronto candidato, alteração da
série, cabeçalhos trocados/omitidos, valores inválidos,
duplicatas, linha ausente, divergência entre vintages,
documento de referência falsificado e ausência de
permissão operacional.

Os testes verificam APENAS como o parser reage a entradas
deliberadamente construídas, não o funcionamento do site
ALFRED nem a autenticidade de bytes recebidos.

## Próxima evidência necessária

1. Obter um export oficial que contenha **dois valores
   de CPIAUCNS para a observação 2025-12-01**, um em cada
   vintage; não usar CSV atual sem coluna histórica.
2. Arquivar bytes originais do export, URL de aquisição,
   SHA-256 e instante REAL de recebimento atual.
3. Conferir o conteúdo no validador offline, registrar
   divergências e a lista de datas realmente reconhecidas.
4. Revisar termos de uso, receber fonte de consenso
   específica do evento pré-divulgação e completar
   histórico independente spot para 28 pares.
5. Só com prova externa e política pré-comprometida
   avançar aos testes OOS sem olhar o futuro.

LAB / HARD NO-GO: nenhum CSV foi baixado, nenhuma API paga
chamada, nenhuma ordem ou serviço ativado; não houve
Worker, cron, merge, deploy ou gasto adicional.


## Revisão de segurança — corte temporal por observação em cada vintage

Durante a auditoria, foi identificado um risco que o cabeçalho
correto não detectava: um CSV podia declarar
\`CPIAUCNS_20260113\` e ainda conter o índice referente a
**janeiro/2026**, que só saiu na publicação de fevereiro.

O importador agora recusa:
- qualquer valor de **janeiro/2026** na coluna de 13/01/2026,
  independentemente do cabeçalho;
- qualquer observação **de fevereiro/2026 ou posterior**
  em ambas as vintages, pois nem a divulgação de 13/02
  podia conhecer o CPI de fevereiro;
- linha de janeiro/2026 com valor de 13/02 que não corresponda
  a **325,252**, registrado oficialmente no segundo release BLS
  e na listagem ALFRED de 13/02;
- datas mensais fora do primeiro dia do mês, linhas fora da
  sequência crescente, duplicatas e dados numéricos inválidos
  até mesmo em meses que não sejam dezembro/2025.

A linha de janeiro/2026 é **opcional** porque um export
recortado somente em dezembro pode legitimamente omiti-la.
Se estiver presente, deve obedecer às regras acima.

Essa proteção reduz vazamento de dados futuros apenas
**dentro do conteúdo declarado no arquivo**. Não verifica
que a origem do arquivo é o ALFRED, que os headers são
autênticos ou que a AtlasQuant já o tinha recebido no
passado. Todos os resultados seguem somente candidatos
de LAB e \`real_oos_authorized=false\`.

Foram acrescidos **oito testes**, totalizando **25**;
o arquivo de evidência real de fevereiro permanece ausente.
