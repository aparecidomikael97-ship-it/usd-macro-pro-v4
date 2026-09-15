USD Macro Pro V11.0.6 — Strength Attribution + Audit Integrity

Base: V11.0.5. Não altera pesos nem Score Mestre.

Correções de auditoria reproduzidas e tratadas:
- M15 SEM/AGUARDAR GATILHO não confirma execução.
- Campos operacionais ausentes falham fechado.
- Risco desconhecido não vira NORMAL.
- timestamps NaN/NaT/pd.NA/futuros não são frescos.
- Market Map antigo/incompleto não é pronto.
- mudança de direção invalida técnica calculada para o lado anterior.
- caches H1/M15 validam OHLC real, não apenas quantidade.
- evidência técnica velha não entra como confirmação/positivo atual.
- ADR ausente fica N/D e bloqueia execução.
- SMT exige timestamps realmente alinhados.
- falha da API após mudança de direção não reaproveita confirmação antiga.
- cache Streamlit de JSON considera token/repo/branch.
- negação de notícias (ex.: rules out rate cuts) é tratada.
- FVG totalmente invalidado não é reativado por revisita posterior.
- validação histórica não usa candle anterior ao congelamento do sinal como entrada.

Strength Attribution:
- Macro puro da base x cotada.
- Fed base x cotada.
- Ajustes dedicados/residual.
- fatores a favor de cada moeda.
- conta líquida reconciliada exatamente com a força final.

Scores continuam sendo pontos internos do modelo, não pips nem probabilidade de lucro.
