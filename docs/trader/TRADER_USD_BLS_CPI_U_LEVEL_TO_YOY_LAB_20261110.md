# AtlasQuant Trader — CPI dos EUA (BLS): índice ≠ inflação anual

## Fonte e método

- Emissor: **U.S. Bureau of Labor Statistics (BLS)**.
- API pública documentada: `GET https://api.bls.gov/publicAPI/v2/timeseries/data/CUUR0000SA0`.
- Série `CUUR0000SA0`: CPI-U, todos os itens, média das cidades dos EUA,
  **sem ajuste sazonal**, publicação regular mensal.
- O retorno mensal da API contém **níveis do índice**, não taxas anuais.
  Para o mês `YYYY-MM`, o cálculo de 12 meses exige **o mesmo mês do ano
  anterior**: `(índice atual ÷ índice de 12 meses atrás − 1) × 100`.
- Usar a mesma série e base de referência nos dois extremos. A taxa derivada
  de níveis publicados e arredondada a três casas **não substitui** a taxa
  anual oficial divulgada no comunicado do BLS, usualmente com uma casa.

Documentação oficial:

1. https://www.bls.gov/developers/api_signature_v2.htm
2. https://www.bls.gov/cpi/factsheets/cpi-series-ids.htm
3. https://www.bls.gov/cpi/factsheets/calculating-percent-changes.htm

## Entrega do LAB

`atlasquant_trader_us_bls_cpi_yoy_snapshot_lab.py` é um parser sem rede,
sem operações no computador do usuário, sem ordens e sem escrita de arquivos.
Recebe **bytes JSON fornecidos pelo chamador** e um período-alvo. Confere
emissor/série esperada, estrutura da resposta, meses, nomes, valores,
duplicidade e notas especiais. Se não houver índice do próprio mês e do
mesmo mês do ano anterior, devolve `LAB_BLS_CPI_SNAPSHOT_BLOCKED`.

O cálculo usa `Decimal` e sinaliza explicitamente:

- `derived_value_is_official_published_yoy=false`;
- `local_response_hash_verified=false`;
- `issuer_first_release_authenticated=false`;
- `revisions_independently_audited=false`;
- `historical_point_in_time_eligible=false`;
- `comparable_with_eurostat_without_methodology_checks=false`;
- `can_feed_macro_bias=false`, `trade_authorized=false`, `AGUARDAR`.

## Testes e pendências

**173/173 testes locais aprovados** (`python -m unittest discover -q -p
'test_atlasquant*.py'`), incluindo **12 testes novos** de retorno sintético
BLS. Foram testados período correto/errado, ano homólogo ausente, taxa
derivada, resposta de erro, valor inválido, vintage duplicado, JSON com
atributo duplicado, sinalização de nota preliminar e limite de tamanho.

**Não houve captura real nova da API do BLS nesta etapa.** A ferramenta de
consulta da web não conseguiu abrir diretamente o endpoint; portanto não
inventar valor de outubro/2026, não afirmar que há 2 anos de índices
confiavelmente autenticados e não cadastrar o USD como documentado no
controle dos 28 pares. O endpoint da página de notícias anteriormente
consultado devolveu HTTP 403 no AM12: não contornar bloqueio.

## Próximo gate

Obter por canal oficial autorizado uma resposta BLS real, preservar bytes,
hash e metadados de captura, verificar índices mensais e o valor derivado
sem prometer validade histórica. Avaliar separadamente definição estatística,
consenso econômico, surpresa e reação de política monetária antes de
qualquer comparação EUR/USD ou probabilidade de direção.

Sem deploy, merge, worker, cobrança ou negociação.
