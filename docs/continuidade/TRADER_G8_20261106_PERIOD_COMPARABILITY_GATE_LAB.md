# AtlasQuant Trader — auditoria de comparabilidade, não ranking de moedas

**Base:** 16 referências oficiais retrospectivas do PR #1826, corte
**06/11/2026 17:00 UTC**, somente LAB, sem requisições HTTP.

## Por que a cobertura 28/28 ainda não entrega viés?

Estar documentado não significa ser comparável. Os índices de preços são
elaborados para realidades estatísticas diferentes; o [HICP do Eurostat](https://ec.europa.eu/eurostat/web/hicp/information-data)
é um índice harmonizado europeu, não automaticamente idêntico ao CPI dos EUA,
Suíça, Austrália, Japão ou Canadá. A [Stats NZ](https://www.stats.govt.nz/indicators/consumers-price-index-cpi/)
publica seu CPI principal de 2026 em base **trimestral**, não como CPI mensal
de setembro. Juros oficiais também têm instrumentos e datas de reunião
distintos; subtrair suas taxas nominais não prova força cambial.

## Resultado reproduzível do novo bloqueio

| Tipo de comparação de períodos | Quantidade dos 28 pares |
|---|---:|
| Dois CPI **mensais no mesmo mês de referência** | **11** |
| CPI mensais **em meses diferentes** | **10** |
| Um CPI trimestral (NZD) e outro mensal | **7** |
| Documento ainda não admissível no corte 06/11 | **0** |

Exemplos:

- **GBP/USD:** dois CPI de setembro; período igual **não** prova mesma
  cesta de consumo, metodologia, previsão ou surpresa econômica.
- **EUR/CHF:** dois CPI de outubro, mas HICP *flash* da área do euro e
  CPI nacional suíço são indicadores de métodos e abrangências diferentes.
- **EUR/USD:** Eurostat com outubro e BLS com setembro; qualquer comparação
  instantânea das taxas anuais misturaria referências diferentes.
- **AUD/NZD:** CPI australiano mensal de setembro contra CPI neozelandês
  do **terceiro trimestre inteiro**; o período não equivale.

## Critérios para liberar pesquisa quantitativa no futuro

1. Guardar bytes originais e timestamp auditável de consulta e divulgação
   de cada série (não basta página aberta hoje).
2. Organizar versões históricas conforme realmente conhecidas no momento
   da decisão; não revisar retroativamente uma previsão passada.
3. Normalizar CPI por frequência, tipo de série, ajuste sazonal, cálculo e
   mês de referência; documentar onde a harmonização não é possível.
4. Modelar **mudança de postura e expectativa dos bancos centrais**, não
   usar taxa nominal isolada como placar de força cambial.
5. Disponibilizar consenso **anterior ao evento** e registrar surpresa
   real, com sua fonte e carimbo de tempo.
6. Validar sinais hipotéticos D1/W1 contra deslocamentos de preços futuros,
   custos de transação, janelas de entrada M15 e período fora da amostra.

**A implementação bloqueia os seis itens acima**. No corte estudado,
`macro_score_available = false`, `best_pair_of_day = null`, sem ranking e
`D1 = W1 = AGUARDAR` para todos os pares. As contagens de 11/10/7 são
apenas inventário de períodos, **não 11 sinais positivos**.

Não há integração à interface, execução, agendamento, merge, Worker, deploy,
contratação de dados, previsão de 80–90% ou custo adicional. O próximo passo
é pesquisar uma série comparável e armazenar as versões históricas verificáveis
antes de propor qualquer algoritmo que atribua força às moedas.
