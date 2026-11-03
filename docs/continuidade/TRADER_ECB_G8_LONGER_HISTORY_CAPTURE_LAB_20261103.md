# AtlasQuant Trader — preparação do histórico BCE para D1/W1/MN1 (03/11/2026)

**PR #1803 DRAFT · LAB / HARD NO-GO · sem custos, rede no código, ordens,
Worker, agendamento, deploy, UI nova ou merge.**

## Nova peça entregue

O módulo `atlasquant_trader_ecb_g8_history_window_lab.py` planeja uma
consulta **manual e específica** de histórico EUR-base oficial de 7 moedas
(AUD, CAD, CHF, GBP, JPY, NZD e USD) para um intervalo de **30 a 120 dias
corridos**. O código não busca dados: apenas fornece URL exata da API oficial,
nome esperado do arquivo, contrato de validação e portas de recusa.

Para dar sequência à amostra curta atual, a primeira janela planejada é
**01/09/2026 a 02/11/2026**:

- Endpoint autorizado:
  https://data-api.ecb.europa.eu/service/data/EXR/D.AUD+CAD+CHF+GBP+JPY+NZD+USD.EUR.SP00.A?startPeriod=2026-09-01&endPeriod=2026-11-02&format=csvdata
- Caminho futuro, **ainda não criado e não baixado**:
  `docs/continuidade/ecb_exr_g8_20260901_20261102_raw.csv`
- O manifesto futuro deve seguir o esquema de arquivo BCE já existente,
  com SHA-256 dos **bytes originais**, tamanho, datas efetivamente publicadas,
  horário declarado da captura, cabeçalhos HTTP e URL canônica. Não inventar
  cotações em feriados, valores ausentes, horário real de publicação ou revisão.
- O validador recusa path trocado, endpoint diferente, CSV corrompido, duplicado
  ou incompleto, datas/relógios incoerentes e intervalos fora do contrato.
  Ele reutiliza o validador oficial do nosso LAB em memória sem alterar
  o arquivo nem os campos originais do manifesto.

Com arquivo futuro válido, `build_ecb_g8_history_outcomes_lab()` usará o
cálculo ex-post de D1/W1/MN1 já testado para gerar **resultados realizados
posteriores** de 28 pares. Um mês de histórico basta para exemplificar um
resultado MN1, **não** para medir competência preditiva.

## Estado real em 03/11/2026

- Captura oficial existente no GitHub: **26/10 a 02/11**, seis dias úteis,
  42 referências. Continua preservada.
- **A janela estendida ainda NÃO foi coletada**: o acesso HTTP direto ao
  endpoint não ficou disponível neste ambiente. Não há arquivo oficial
  correspondente para auditar e nenhum resultado mensal real foi gerado.
- Os testes automatizados usam um **CSV gerado artificialmente em memória**,
  somente para provar o contrato. Essas linhas não são dados do BCE e não
  foram salvas como histórico no repositório.
- Portanto: **nenhuma previsão real emitida, nenhum acerto OOS real certificado,
  nenhuma probabilidade estatística calibrada**, no sentido de que a medição
  ainda não existe — não interpretar como desempenho observado zero.

## Sinais verdadeiros continuam bloqueados

O hash prova que bytes e manifesto combinam, **não assinatura do BCE**.
Uma captura agora de dados antigos é retrospectiva, e jamais autoriza
afirmar que uma previsão feita no passado teria conhecido aqueles dados.

Os 21 cruzamentos não-EUR derivados não são 21 preços independentes. Referência
do BCE não é spot executável, nem substitui OHLC intradiário M15/H1/H4. As
informações macro, geopolíticas e de consenso deverão ter suas próprias
datas de divulgação e vintage preservados para futuras avaliações
pré-evento. Não há prova de taxa de acerto de 90%.

## Próximos passos

1. Em ambiente com acesso permitido, **capturar manualmente** CSV oficial
   para a janela proposta, sem custo e sem agendamento.
2. Versionar bytes intactos e manifesto fiel. Verificar linhas/datas/valores
   com o novo contrato; *não* conferir apenas um total de linhas.
3. Gerar rótulos mensais retrospectivos para a amostra e ampliar o período
   futuramente, guardando cada captura como evidência distinta.
4. Só depois comparar previsões **realmente emitidas antes de eventos**
   com rótulos posteriores, contra baselines, abstenções, custos e regimes.
5. Tratar índices EUA e WIN/WDO em modelos próprios: não aplicar retorno FX
   como viés direcional de índices.

Testes:
`python -m unittest -q test_atlasquant_trader_ecb_g8_history_window_lab.py`

Documentação oficial:
- https://data.ecb.europa.eu/help/api/data-examples
- https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html
- https://www.ecb.europa.eu/stats/ecb_statistics/governance_and_quality_framework/html/usage_policy.en.html

**Não é aprovação de fonte em produção. HARD NO-GO permanece.**
