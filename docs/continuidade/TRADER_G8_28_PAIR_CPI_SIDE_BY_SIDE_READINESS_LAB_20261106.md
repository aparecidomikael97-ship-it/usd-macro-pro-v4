# AtlasQuant Trader — matriz G8: inflação das duas moedas + próximos eventos (LAB)

**Pesquisa-base:** 06/11/2026. **Resultado combinado conservador a partir de:** 07/11/2026 00:00 UTC. **Sem ativação operacional.**

O novo módulo reúne (sem duplicar as evidências) os documentos econômicos de oito moedas, a auditoria de compatibilidade dos 28 pares e as oito próximas datas oficiais de CPI. A saída responde à pergunta **“por que o viés ainda não está pronto?”**, mostrando o lado base e o lado cotado, os períodos, a diferença metodológica e as datas futuras de cada um.

## Resultado de cobertura documental

| Situação do período de CPI | Pares | Exemplo | Consequência |
|---|---:|---|---|
| Mesmo mês, duas medições nacionais | 11 | EUR/CHF (outubro em ambos) | Mesmo mês **não** garante metodologia ou estágio equivalente; EUR é flash de HICP e CHF é CPI nacional |
| Meses diferentes | 10 | EUR/USD (outubro flash EUR × setembro CPI-U USD) | Sem diferencial numérico válido deste recorte |
| Mensal versus trimestral | 7 | NZD/CHF (NZD trimestre jul–set × CHF outubro) | Não fingir que o indicador trimestral da NZD é mensal |
| **Total** | **28** | | Todos `D1=AGUARDAR` e `W1=AGUARDAR` |

Em 07/11/2026, o estudo tem **16 referências documentais retrospectivas** já fixadas no repositório — 8 de inflação e 8 de decisão de juros —, mais **8 datas de eventos futuros**. As referências históricas são leituras de páginas de órgãos oficiais **sem bytes HTML originais nem verificação independente de que a página tinha aquele conteúdo em cada horário histórico**. Os números são conservados como **texto declarado pelo documento**, nunca transformados em spread negociável.

## Exemplos para a futura Matriz

**EUR/USD**

- EUR: HICP da área do euro, estimativa flash, **outubro/2026**, **4,0%** em variação anual declarada no documento.
- USD: CPI-U all-items americano, **setembro/2026**, **3,7%** em variação anual declarada no documento.
- Próxima publicação desse par no recorte: CPI-U de outubro dos EUA, **10/11/2026**.
- Resultado: **não comparar 4,0 e 3,7 como força de EUR contra USD**; meses, metodologia e estágio não coincidem.

**NZD/CHF**

- NZD: CPI da Nova Zelândia **trimestre encerrado em setembro**, inflação anual documental de **3,7%**.
- CHF: CPI nacional suíço **outubro**, inflação anual documental de **1,5%**.
- Próxima publicação do par: CHF de novembro, **02/12/2026** (NZD trimestral seguinte em 27/01/2027).
- Resultado: comparar datas não cria um CPI mensal da NZD nem determina alta/baixa do NZD/CHF.

**EUR/GBP**

- Duas divulgações previstas para **18/11/2026** (EUR e GBP); não descartar uma delas por empate.
- Mesmo com calendário completo, não há consenso pré-evento autenticado ou comprovação de relação do evento com M15/D1/W1.

## Bloqueios que aparecem em **todos os 28 pares**

1. Captura independente dos bytes originais e do instante de consulta das fontes.
2. Expectativas de mercado coletadas **antes** de cada divulgação, com fonte e unidade.
3. Normalização metodológica das séries CPI, HICP e CPI trimestral.
4. Verificação prospectiva dos resultados de preço D1/W1 com regras pré-comprometidas (sem vazamento futuro).

Mesmo os 11 pares com período mensal idêntico **não** têm autorização para subtrair taxas de inflação e produzir direção. Não há ranking das moedas, “melhor par”, percentual de acerto ou sinal operacional. Nem toda diferença de inflação aponta o sentido da moeda porque expectativas, bancos centrais e preço já podem ter antecipado a informação.

## Implementação e estado

- Reutiliza as validações dos cinco calendários (#1839), dos três restantes (#1840) e dos três casebooks oficiais de inflação/juros existentes; sem baixar ou inventar novas séries.
- Código novo: `atlasquant_trader_g8_cpi_side_by_side_readiness_lab.py`.
- Testes: `test_atlasquant_trader_g8_cpi_side_by_side_readiness_lab.py` e suíte `quality-tests.yml`.
- Rascunho de laboratório empilhado sobre #1840; sem merge, deploy, worker, cron, HTTP, ordens nem cobrança.

**Próximo salto de pesquisa:** capturar um par de indicadores de mesma competência com versões ponto-no-tempo e expectativas pré-publicação verificáveis. Só depois testar se esse conjunto de informações prevê retornos de preço em amostras futuras independentes.
