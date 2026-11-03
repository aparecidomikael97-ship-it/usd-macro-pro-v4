# Trader — fundamentos oficiais anteriores aos eventos (LAB, 03/11/2026)

## Finalidade
O proprietário priorizou **antecipar o viés macro** dos 28 pares Forex e índices, com D1/W1/MN1, considerando diferenças entre oito moedas, microeconomia, geopolítica e notícias. A camada de eventos anterior mapeou apenas a *exposição*. Este pacote acrescenta os **últimos números oficiais que já eram públicos** antes dos três eventos pesquisados.

**Crítico:** último resultado publicado ≠ consenso para o próximo evento ≠ resultado do próximo evento ≠ surpresa ≠ previsão de força da moeda.

## Referências oficiais, dados de setembro de 2026
| Evento futuro | Último documento publicado | Leitura histórica transcrita | Unidade e significado |
|---|---|---|---|
| BoE 05/11 | Decisão 17/09/2026 | Bank Rate 3,75 | Taxa básica vigente na decisão de setembro, % |
| Emprego EUA 06/11 | BLS 02/10/2026 | Payroll +29; desemprego 4,2 | Variação de empregos, **milhares**; taxa de desemprego U3 em % |
| CPI EUA 10/11 | BLS 14/10/2026 | CPI 0,6; CPI 3,7; núcleo 0,3 | Inflação cheia ajustada **mês/mês**; cheia sem ajuste **ano/ano**; núcleo ajustado **mês/mês**, todos % |

Fontes:
- BoE: https://www.bankofengland.co.uk/monetary-policy-summary-and-minutes/2026/september-2026
- BLS emprego: https://www.bls.gov/news.release/archives/empsit_10022026.htm
- BLS CPI: https://www.bls.gov/news.release/archives/cpi_10142026.htm

As três páginas são fontes oficiais observadas durante esta pesquisa, mas os seis valores são **transcrições manuais**, não bytes originais arquivados com atestado independente de obtenção. Hash de commit do GitHub comprova a existência deste **registro de pesquisa** em sua data, não o carimbo original da fonte.

## Contrato de laboratório
`atlasquant_trader_pre_event_fundamentals_lab.py` associa seis leituras históricas aos três IDs canônicos de `atlasquant_trader_macro_event_exposure_lab.py`. Ele:
1. valida campos e valores exatos, rejeitando campos injetados como `confidence_pct`, fontes falsas e datas adulteradas;
2. não permite gerar leitura retroativa anterior ao registro de pesquisa de 03/11/2026;
3. disponibiliza contexto pré-evento apenas enquanto o evento está no futuro; no dia da decisão (quando o horário é desconhecido) sinaliza que a divulgação **pode já ter ocorrido**; depois do evento exige atualização com nova publicação;
4. mapeia disponibilidade por oito moedas e 28 pares, **sem comparar 3,75% do BoE com 3,7% do CPI** (medidas incompatíveis);
5. mantém `bias=AGUARDAR`, `direction_probability=None` em todos os pares, e `current_event_consensus_available=false`, `current_event_actual_available=false` para os eventos futuros ou já vencidos sem leitura nova.

Cobre **GBP e USD**, apenas duas moedas; EUR, JPY, CHF, CAD, AUD e NZD continuam sem últimas observações homologadas nesta fatia. Não é cobertura G8 completa e não há índice derivado de força macro real.

## Próximo critério técnico
1. Selecionar e validar série oficial com unidade/período compatível para os oito bancos centrais e para inflação/emprego/atividade, preservando publicação e revisão.
2. Identificar consenso externo publicado **antes** do evento (distinto de nowcast, pesquisa de expectativas de juros e resultado anterior); verificar licença e histórico ponto-no-tempo.
3. Comparar `actual - consensus` **somente depois** de publicação e captura e de acordo com a interpretação específica do indicador e do regime; não converter automaticamente em alta do USD/GBP.
4. Avaliar se hipóteses preditivas D1/W1/MN1 acrescentam precisão fora da amostra, incluindo abstenções, reversões, spreads de risco e confiabilidade por regime.

**HARD NO-GO:** não utilizar como sinal ou recomendação, não ativar Worker, job agendado, API paga, corretora, deploy, merge ou interface. Não anunciar probabilidade de 90% sem calibração real. Os 34 testes do novo módulo são vinculados ao Quality.
