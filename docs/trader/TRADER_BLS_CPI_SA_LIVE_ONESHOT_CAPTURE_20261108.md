# AtlasQuant Trader — captura real BLS CPI-U ajustado, única, sem produção

**Coleta:** 08/11/2026, `22:39:46.036256Z` a `22:39:52.423604Z`.
**Escopo:** somente HTTP GET público, sem autenticação, custo, worker,
agendamento, negociação ou consulta a conta da corretora.

## Fonte e evidência congelada

| Campo | Valor observado |
| --- | --- |
| Órgão | U.S. Bureau of Labor Statistics (BLS) |
| URL solicitada | `https://api.bls.gov/publicAPI/v1/timeseries/data/CUSR0000SA0` |
| Série verificada no JSON | `CUSR0000SA0` — CPI-U todos os itens, ajustado sazonalmente |
| Requisições HTTP realizadas pelo coletor | 1 |
| Bytes exatos do corpo JSON | 3.114 |
| SHA-256 do corpo original | `34d830f1b67462d7fd6bfeb33935374eb3bfd97606fb38684e3ba0f376a80d47` |
| Último mês retornado com índice válido | `2026-09` |
| Índice setembro de 2026 | `336.298` |
| Índice agosto de 2026 | `334.131` |
| Variação mensal **derivada** (arredondada a 1 casa) | `0.6%` |
| Mês ausente sinalizado como `"-"` no JSON | `2025-10` |

**Arquivo bruto** salvo de forma recuperável em:

`docs/continuidade/bls_cpi_sa_20261108T223952423604Z_34d830f1b674.zip`

O ZIP contém `response.json` com bytes idênticos à resposta e `receipt.json`
com URL, período, hashes e relógios declarados. O próprio ZIP foi reaberto
em verificação read-only depois da captura.

- Tamanho do ZIP: **4.098 bytes**.
- SHA-256 do ZIP: `086112beadddc7adc0e488090fd9d74f6536936ab55597faffca9b448741f320`.
- SHA-256 do JSON dentro do ZIP foi conferido contra o valor registrado.

O coletor validou a resposta usando a série exata, limites de tamanho,
estrutura de JSON, HTTP 200, Content-Type `application/json`, endereço final
exato e solicitação de TLS com CA do sistema. Não aceitou redirecionamentos.

## O que estes números **não** representam

- **Não são CPI de outubro/2026.** O último mês válido na resposta atual é
  setembro. Não há autorização para preencher outubro antes da divulgação.
- `336.298` e `334.131` são **níveis de índice**, não taxas de inflação.
  O percentual acima foi calculado a partir deles, não lido como resultado
  diretamente certificado do boletim de primeira divulgação.
- Esta resposta da API é **mutável**: níveis sazonalmente ajustados sofrem
  revisões históricas. Um snapshot capturado agora não prova os valores
  conhecidos em datas anteriores (*point-in-time*).
- HTTPS com CA e URL correta registra uma coleta técnica, mas não atesta de
  maneira independente o primeiro horário de publicação, a metodologia de
  consenso, o valor inicial de cada divulgação ou a inexistência de revisões.
- O registro não é previsão, recomendação de compra/venda, dado do MetaTrader,
  nem prova de assertividade do AtlasQuant.

## Próximo trabalho autorizado apenas em LAB

1. Preservar cada nova versão **somente quando a fonte for consultada**,
   separando data da consulta, referência econômica e publicação original.
2. Confrontar o índice com o texto oficial do release e registrar revisões
   sem sobrescrever versões anteriores.
3. Para previsões de evento, guardar previamente consenso e método de
   cálculo com testemunho temporal externo. A API sozinha não comprova isso.
4. Antes de viés Forex/índice, medir erro de múltiplos eventos fora da amostra
   e manter regra de abstenção.

**Política:** um GET executado nesta etapa; **não** há atualização contínua,
ordens, Worker, deploy, sinais, cobrança ou publicação de dados em painel.
Todos os vieses continuam `AGUARDAR`.
