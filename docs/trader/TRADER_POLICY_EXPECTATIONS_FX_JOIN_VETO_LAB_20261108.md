# AtlasQuant Trader — integração de contradições de juros ao diagnóstico de viés FX (LAB)

**08/11/2026. Status: pesquisa isolada; PR #1851 permanece DRAFT.**

## O que foi conectado

- A comparação das mudanças de expectativas de juros das duas moedas (base menos cotada) é avaliada **separadamente nos cortes de D1 e W1**, sem transportar uma cotação posterior para uma decisão anterior.
- O módulo `atlasquant_trader_policy_join_veto_lab.py` faz a conexão explícita ao candidato de viés: **contradição documental em qualquer horizonte => veto de pesquisa**; dados ausentes, fora do prazo, instrumentos inconciliáveis ou alteração na data-alvo => **veto de pesquisa**.
- Sem contradição documental **não** significa fonte comprovada, chance calculada, modelo validado ou sinal. Por isso, mesmo alinhamento positivo nunca altera `operational_bias=AGUARDAR`, `publishable=False`, `trade_authorized=False`.
- `atlasquant_trader_evidence_join_lab.py` passa a chamar essa verificação como **nova condição de abstenção**. A ausência de cotações para as duas moedas é reportada, nunca preenchida ou tratada como alinhamento.
- Preserva os bloqueios anteriores do join: documentação macro bilateral não autenticada, preço MT5 sem calendário e P-I-T atestados, notícias sem cobertura completa, resultados não verificados, amostra e calibração insuficientes. A concordância de juros não pode desbloqueá-los.

## Limitações e definição quantitativa

A série é uma *alegação* de taxa implícita futura de 3 meses, para **uma mesma data-alvo por par**, e não juros oficiais. A aritmética `mudança_base − mudança_cotada`, em pontos-base, é hipótese de pesquisa; não mede automaticamente reação do câmbio. O limiar de 5 bps também **não foi calibrado em mercado real**. A metodologia, os horários, as fontes, os valores e SHA de cada snapshot são fornecidos pelo chamador e **não têm testemunho independente**. O corte do W1 pode ser diferente do D1, exigindo dois conjuntos de evidência.

**Não existe assertividade medida de 65%, 70%, 80% ou 90% nesta etapa.** Avaliar a contribuição incremental do detector exigirá série real de expectativas, consenso pré-notícia, vintages e resultados externos, além de comparação fora da amostra com e sem o filtro e cobertura dos casos em `AGUARDAR`.

## Provas de laboratório

- `test_atlasquant_trader_policy_join_veto_lab.py`: **11/11 testes novos sintéticos**.
- Com os 25 testes sintéticos anteriores de expectativas: **36/36 PASS** no ambiente local, em execução offline com um registro mínimo de 28 pares idêntico ao inventário do projeto.
- A alteração no join do projeto também ajusta uma asserção antiga sobre o número de bloqueios, agora maior em 1 por ausência explícita da nova fonte. **Isto não equivale à execução de toda a suíte do repositório** nem valida o feed real do MT5.

## Condições de entrega

Somente arquivos de laboratório. Nada foi lançado no aplicativo, `main`, MetaTrader 5, broker, worker, agendador, ordens, cobranças ou alerta. Os índices WIN/WDO e americanos exigem pesquisa e validação próprias. **Próxima etapa:** obter vintages de expectativas reais, com fornecedor e data original, e integrar surpresas econômicas verificadas; comparar cobertura e acerto direcional D1/W1 com e sem o veto, em avaliação temporal intocada.
