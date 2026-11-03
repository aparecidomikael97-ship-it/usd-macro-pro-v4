# AtlasQuant Trader — cenários macro pré-evento, G8/índices (LAB, 02/11/2026)

## Finalidade definida pelo proprietário

Antecipar **hipóteses direcionais condicionais** para as oito moedas G8/28 pares Forex e, de forma independente, SPX500, NAS100, US30, WIN e WDO. Saída por horizonte: **D1** (decisão diária prioritária), **W1** (semana) e **MN1** (contexto mensal). A decisão deve expor o que poderia fortalecer/enfraquecer cada moeda, o evento futuro que muda a hipótese e os riscos contrários. A análise é de macroeconomia, microeconomia e geopolítica; OB/FVG/BOS/CHoCH não são requisito do núcleo de viés.

## O que foi implementado

- Módulo isolado `atlasquant_trader_exante_macro_scenarios_lab.py`, sem importação no app, no Radar ou Worker.
- Recebe **hipóteses manuais e sintéticas**, explicitamente pré-evento, com horário UTC de emissão, identificadores de evidência, links HTTPS, horários de evento/publicação/captura, fundamentação e marcadores MACRO/MICRO/GEOPOLITICS.
- Exige um livro completo de oito moedas e cinco índices **para cada horizonte**. Compara apenas base menos cotada (28 pares/horizonte); índices usam **hipótese macro específica**, não um sinal transferido automaticamente do dólar.
- Oferece ALTA/BAIXA/NEUTRO/AGUARDAR como **rótulos de hipótese de laboratório**. MICRO ou GEOPOLITICS `CONTRA`/`DESCONHECIDO` impõem AGUARDAR; ausência de macro impõe AGUARDAR; evidência incoerente rejeita a entrada inteira.
- Separa `SCHEDULED` (evento ainda futuro em relação à emissão; calendário anunciado antes) de `RELEASED_CONTEXT` (publicado e capturado antes). Fatos divulgados após emissão e campos de resultado retrospectivo são rejeitados.
- Em sucesso: 84 hipóteses Forex + 15 índices (3 horizontes); nenhuma ordem, sinal de entrada ou probabilidade.
- Contratos testados em `test_atlasquant_trader_exante_macro_scenarios_lab.py`, adicionados ao fluxo `quality-tests.yml`.

## Limitações e próximos gates

Este módulo **não calcula probabilidade**, não lê notícia automaticamente, não autentica URLs, não infere causalidade econômica e não demonstra retorno ou direção futura. O texto de evidência é **fornecido manualmente como sintético**; mesmo um link oficial digitado não é prova de origem autenticada. O BCE é referência cambial diária (não preço independente de negociação intradiária). Nenhuma assertividade de 90% foi comprovada.

1. Implementar ingestão **somente leitura** com trilha de origem e licença das séries oficiais de indicadores, decisões e calendários por país; registrar `observed_at / published_at / captured_at / revised_at`, série/vintage e consenso disponível no instante. Não usar revisões futuras no passado.
2. Criar regras econômicas **condicionais por regime** (ex.: inflação acima do consenso pode apoiar juros/FX, mas o sinal pode inverter em risk-off ou com posicionamento prévio). Sem mecanismo comprovado de causalidade, mostrar cenário e objeções, não confiança numérica.
3. Incorporar dados independentes históricos de FX e índices, licitamente usáveis, e verdade de eventos; congelar previsão **antes da notícia**. O piloto BCE com sete cotações e 21 cruzamentos derivados não valida a previsão de 28 preços independentes.
4. Testar walk-forward OOS por D1/W1/MN1, par, índice e regime; reportar amostra, base rate, acerto, abstinência, cobertura, comparação ingênua e calibração. Somente então considerar a meta aspiracional de 90%.
5. Integrar visual **aprovado** apenas após revisão de qualidade, interpretação e autorização separada.

## Garantias

`state=LAB_EXANTE_CONDITIONAL_HYPOTHESES_ONLY`, `probability_calibrated=null`, `accuracy_90_proven=false`, `trade_authorized=false`, `worker_enabled=false`, `scheduler_enabled=false`, `can_feed_live_radar=false`.

**LAB / HARD NO-GO:** PR em rascunho, sem merge, deploy, conta/corretora, ordens, Worker, cron, API paga, serviço contratado ou alterações do visual aprovado.
