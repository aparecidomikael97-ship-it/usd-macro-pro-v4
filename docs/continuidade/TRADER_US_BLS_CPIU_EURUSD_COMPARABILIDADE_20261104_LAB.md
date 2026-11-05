# AtlasQuant Trader — CPI-U oficial USD e proteção comparativa EUR/USD (LAB)

Checkpoint da sessão 04/11/2026, captura UTC já em 05/11/2026.
PR #1815; **sem merge, deploy, Render, Worker, cron ou ordens reais**.

## Nova fonte USD (oficial, sem registro pago)

Bureau of Labor Statistics, API pública V1; série
`CUUR0000SA0` — CPI-U All Urban Consumers, U.S. city average,
all items, **NOT seasonally adjusted**, índice com base 1982–84=100.

URL fixa: `https://api.bls.gov/publicAPI/v1/timeseries/data/CUUR0000SA0`

A API V1 documenta consulta GET de uma série e limita consultas sem
registro. Nada foi agendado, nenhum pagamento ou chave API contratado.
O módulo `atlasquant_trader_bls_us_cpiu_once_lab.py` só aceita uma
requisição HTTPS manual autorizada em `manually_authorized=True`.
Não faz requisições ao importar. Limite de 128 KiB e timeout 1–15s,
URL fixa, CA padrão, sem redirects e com ZIP opcional (sem overwrite).

O parser valida série exata, índices numéricos, ordem temporal,
duplicidades, anos, mês, notas e status. **Índice NÃO é inflação %**.
A taxa anual é derivada APENAS se existem os índices do mesmo mês
em anos consecutivos; caso contrário devolve `None` sem inventar.

A resposta real tinha duas particularidades previstas na documentação
BLS:
- `M13`: MÉDIA ANUAL; 2 registros descartados do conjunto mensal.
- `2025-M10`: valor literal `-`; período marcado como AUSENTE, não
  zero nem índice para cálculo. Não interpolar/reconstruir.

## Uma consulta real e cópia verificável no AM12

Resposta capturada às **2026-11-05T00:14:35.209185+00:00**:

- último índice: **2026-09 336,940**
- índice de comparação: **2025-09 324,800**
- inflação derivada: **3,7377%** = `(336.940/324.800 - 1)*100`
  com arredondamento a quatro decimais, NÃO é taxa percentual
  publicada diretamente pela API nem surpresa ante consenso
- 32 índices mensais numéricos, 2 médias anuais M13 ignoradas,
  1 mês explicitamente ausente `2025-10`
- hash SHA-256 dos bytes JSON:
  `4f42c496a41fbdac2c0ef5a4a32fd636da3bd7ab8a3801ee9654b5052929cb5b`
- ZIP SHA-256:
  `08db6247d744133ca470b663c11183d4e4402cd4e8123c8f72de85b94788e154`

Arquivo privado no AM12 (NÃO commitado no GitHub):
`C:\Users\apare\AtlasQuant_Trader_G8_LAB_20261104\evidence\bls_us_cpiu_20261105T001435209185Z_4f42c496a41f.zip`

O ZIP contém `response.json` (bytes exatos) e
`observation_receipt.json` (hash/horário/flags). Foi reaberto
OFFLINE para verificar ambos hashes, valores mensais, ausência M10,
M13 e a conta da taxa anual.

## Regra de proteção bilateral EUR/USD

Módulo `atlasquant_trader_eurusd_inflation_comparability_lab.py`,
exclusivamente read-only, verificou as duas capturas reais
(Eurostat EUR HICP, BLS USD CPI-U):

- EUR: **2026-10 4,0%**, `e` = estimativa, não definitiva;
- USD: **2026-09 3,7377%**, derivação local do CPI-U NSA;
- **meses diferentes** e **metodologias diferentes**;
- falta instante verificável de divulgação por observação, consenso
  pré-evento, histórico de vintages point-in-time, contexto de
  emprego/juros/atividade/geopolítica e preço Forex independente.

Consequência: `comparison_difference_percentage_points=None`,
`inflation_ranking_of_currencies=None`,
`operational_bias=AGUARDAR`, `trade_authorized=false`.
O sistema **não** subtrai percentuais incompatíveis, nem interpreta
inflação mais alta como valorização automática da moeda.

## Testes e limitações

Novos módulos cobertos por testes puramente offline; execução local
final com **89/89 PASS** nos 4 módulos de testes (G8, EUR, USD,
comparabilidade). Quality CI passa a executar os novos testes.

Os ZIPs preservam bytes da **captura atual**, não constituem prova de
que os indicadores estavam disponíveis no instante de vieses passados.
Nem o horário do computador nem os hashes equivalem a custódia
institucional assinada. Não há taxa de acerto comprovada ou
homologação de execução de ordens. Próximos passos: snapshots
pré-evento de consenso com autoridade própria, dados de política
monetária de ambos os bancos centrais, taxa de mercado independente
e testes OOS/walk-forward.

**HARD NO-GO**: trabalho em LAB apenas, PR DRAFT, nenhuma mudança
na PR #1816 aprovada anteriormente, nem na branch `main`.
