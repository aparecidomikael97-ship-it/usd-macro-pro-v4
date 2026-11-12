# AtlasQuant Trader — vínculo pré-registro → acerto por evento (LAB, 11/11/2026)

## Objetivo
Evitar que uma previsão anterior seja alterada no relatório depois de conhecido o preço, e impedir que um mesmo PPI represente sete eventos estatísticos independentes. Faz a junção **estrita** das oportunidades previstas com as observações posteriores.

- Entrada: manifesto congelado, previsões `ForecastPrecommitClaim`, lista e SHA de recibos preservados, observações `ObservedOpportunity`, horário UTC de inspeção.
- Compara uma a uma: identificador, ordem, par, horizonte D1/W1, direção, horário da previsão e fim da janela de resultado. Falha se faltar um item ou se a previsão abstida ganhar rótulo de vitória.
- A auditoria de cobertura e raiz de evento só roda depois dessas verificações. Ela não atribui independência causal.
- Um histórico original alterado que já possua recibos preservados é bloqueado. **Um atacante que altere tanto a previsão quanto toda a cadeia local pode continuar produzindo uma cadeia aparentemente válida.** A solução não é afirmar que SHA local prova horário; é obter testemunha externa efetivamente confiável antes do evento.
- A leitura dos resultados do mercado, o horário da fonte, a integridade da corretora, a verificação externa das assinaturas e a qualidade da classificação não foram comprovados.

## Testes
`test_atlasquant_trader_selective_precommit_bridge_lab.py` cobre correspondência legítima e dez cenários de robustez, inclusive troca de direção, perda de oportunidade, horário adulterado, rótulo precoce e abstenção.
A validação isolada usou dependências simuladas. O workflow da PR executará a suíte com os módulos reais do repositório.

## Política obrigatória
**Sempre LAB / NO-GO / AGUARDAR.** Sem trades, alertas, merge, deploy, requisições externas ou novas despesas. Nenhuma porcentagem descritiva equivale a probabilidade calibrada ou resultado financeiro comprovado.
