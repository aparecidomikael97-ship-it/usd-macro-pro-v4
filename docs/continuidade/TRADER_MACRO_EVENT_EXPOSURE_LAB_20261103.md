# Radar Macro — exposição a eventos por ativo, sem direção inventada (LAB 03/11/2026)

## Prioridade do proprietário
Antecipar movimentos de Forex (G8, 28 pares) e dos índices SPX500, NAS100, US30, WIN e WDO, usando macroeconomia, microeconomia, geopolítica e informações disponíveis **antes** do movimento. FVG, OB e BOS **não** são o eixo deste trabalho. A qualidade probabilística deve ser medida prospectivamente, não presumida como 90%.

## O que este pequeno piloto realmente prova
O módulo `atlasquant_trader_macro_event_exposure_lab.py` transpõe três datas de calendários oficiais para uma **matriz de risco de eventos**, sem produzir direção de preço ou estimativa de probabilidade:

1. Banco da Inglaterra: decisão MPC **05/11/2026**, com horário tratado apenas como **dia inteiro em UTC** (faixa conservadora, não horário oficial). Fonte: https://www.bankofengland.co.uk/monetary-policy/upcoming-mpc-dates
2. BLS: Employment Situation de outubro **06/11/2026 às 08:30 horário do leste dos EUA (EST)**, equivalente a **13:30 UTC** em novembro. Fonte: https://www.bls.gov/schedule/news_release/empsit.htm
3. BLS: CPI de outubro **10/11/2026 às 08:30 EST**, equivalente a **13:30 UTC**. Fonte: https://www.bls.gov/schedule/news_release/cpi.htm

Fontes oficiais foram consultadas no trabalho de pesquisa, mas o código contém **transcrição documental manual, sem download custodiado dos bytes nem carimbo externo de captura**. Esses calendários podem ser alterados: para uso corrente precisam de nova checagem oficial independente. Não há consensos, números realizados, surpresa econômica, probabilidade implícita ou cotações nesse piloto.

## Janela e associação
- D1 = próximas 24 horas; W1 = próximos 7 dias corridos; MN1 = próximos 30 dias corridos. São **janelas móveis de agenda**, não candles de mercado.
- Moeda correspondente a um dos lados do par = **exposição direta daquele par à agenda da moeda**, não confirmação da direção.
- SPX500/NAS100/US30 = contexto macroeconômico doméstico de divulgações dos EUA; **nenhuma direção atribuída**.
- WIN/WDO = canal indireto possível de contexto americano, **sem sensibilidade comprovada**.
- Horário do BoE sem precisão de minutos recebe `DATE_ONLY_MAY_ALREADY_HAVE_OCCURRED` no próprio dia ou `WINDOW_EDGE_TIME_UNCERTAIN` perto da fronteira. Nunca se afirma que a divulgação ainda está por vir depois de um horário possivelmente já ocorrido.
- Evento de minuto exato deixa de ser classificado como futuro **no próprio instante anunciado**; isso não afirma ter sido divulgado nem apurado.

### Exemplo determinístico de 03/11/2026, 12:00 UTC
| Horizonte | Eventos elegíveis na agenda | Exposição documental |
|---|---|---|
| D1 | Nenhum dos três | Nenhum evento deste recorte nas próximas 24h |
| W1 | BoE 05/11; emprego EUA 06/11 | 13 pares FX únicos (7 com GBP, 7 com USD, removendo GBP/USD duplicado); 5 índices com contexto USD |
| MN1 | Os dois anteriores + CPI EUA 10/11 | 13 pares FX únicos; 5 índices com contexto USD |

**Não significa que os demais 15 pares estão livres de notícias.** Cobertura do piloto = apenas 3 eventos de **2 moedas** das 8. Não modela mudanças de expectativa, diferencial de juros prospectivo, economias restantes, geopolítica, impactos reais nem interação entre fatores.

## Segurança e critério da próxima etapa
- `bias=AGUARDAR` e `direction_probability=None` em todas as **84 linhas FX** (28 × 3) e **15 linhas de índices** (5 × 3).
- `calendar_complete=false`, `calendar_realtime_refreshed=false`, `independent_source_receipt_verified=false`.
- `can_feed_live_radar=false`, `trade_authorized=false`, Worker e scheduler bloqueados. **HARD NO-GO** de operação, custo, deploy, merge e alteração da interface aprovada.
- A agenda precisa crescer para os bancos centrais e indicadores das oito moedas e, depois, receber números macro/expectativas anteriores a cada evento, com carimbo de conhecimento (`as-of`), controle de revisões, surpresa e retorno de mercado validado. Só então avaliar probabilidade com backtest temporal e amostras fora do treino. Nunca equivaler contagem de eventos a previsão de direção.

O Quality executa `test_atlasquant_trader_macro_event_exposure_lab.py` e cobre datas de fronteira, 28 pares/5 índices, horários UTC, identificação das fontes, recusa de agenda injetada e flags de abstinência.
