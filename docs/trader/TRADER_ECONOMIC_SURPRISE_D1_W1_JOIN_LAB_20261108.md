# AtlasQuant Trader — P0: surpresa econômica e bloqueio de viés D1/W1 (LAB)

**Data:** 08/11/2026. **Estado:** somente laboratório, sem emissão de viés, rede, cobrança, MT5, publicação, automação ou negociação.

## O que foi integrado

1. `atlasquant_trader_economic_surprise_veto_lab.py` reutiliza o roteador econômico existente `atlasquant_trader_g8_event_relevance_lab.py` para reconhecer indicadores e unidades. O valor **surpresa = realizado − consenso pré-evento** é tratado como diferença documental, **nunca** como direção de moeda ou probabilidade de acerto.
2. São exigidas **duas fotografias cronológicas distintas** do calendário, do resultado e da macro: uma tomada no corte W1, outra no corte D1. Informação conhecida no diário não pode ser inserida retroativamente na fotografia semanal.
3. Uma divulgação de alto impacto **sem resultado**, **sem consenso registrado antes do evento**, ou com **resultado novo posterior à última captura macro** veta a hipótese documental. Quando há surpresa diferente de zero, o filtro também veta até existir interpretação econômica pré-definida e validada separadamente. Surpresas iguais a zero não autorizam sinal.
4. Notícias futuras de alto impacto nos 30 minutos antes da divulgação são bloqueadas. Para não barrar o sistema eternamente por notícia antiga, o contexto de reação foi inicialmente limitado a **2 dias para D1** e **8 dias para W1**. Estes são parâmetros de pesquisa, **sem otimização nem comprovação estatística**.
5. Duplicidades por `event_id` são recusadas pelo roteador existente. O novo módulo também recusa **a mesma divulgação com IDs diferentes**, com ou sem mudança artificial do horário, além de mudança de horário divulgada entre fotografias que exige revisão.
6. O filtro novo é conectado ao mesmo `atlasquant_trader_evidence_join_lab.py` que já consolida a matriz das 28 combinações de moedas, os bloqueios de expectativas de juros e as verificações de candles fechados. **Fontes ausentes continuam explicitamente em `AGUARDAR`**.

## Como interpretar os resultados

- `research_veto=True`: a hipótese não possui contexto econômico documental suficiente ou está em revisão por surpresa não interpretada; não é sinal.
- `research_veto=False`: não foram identificados bloqueios **nos dados alegados pelo chamador**; **não equivale** a evidência real, melhoria de assertividade, autorização de viés ou compra/venda.
- Campos permanentes: `operational_bias=AGUARDAR`, `publishable=False`, `live_alert_allowed=False`, `trade_authorized=False`, `calibrated_direction_probability=None`.
- Registros do calendário, consenso, resultado e horários ainda podem ser **fictícios ou forjados** por quem os fornece. O roteador verifica consistência, não autentica a primeira publicação ou um histórico de versões de fonte externa.
- O CPI anterior capturado pelo BLS é **índice atual revisável**, não prova do valor na primeira divulgação. Não alimenta automaticamente a surpresa e não deve ser confundido com consenso pré-evento.
- O problema de lacunas históricas do MT5, incluindo GBPNZD D1 em 30/09/2025, continua separado e bloqueado.
- Um resultado de CPI maior que o consenso pode fortalecer **ou** enfraquecer uma moeda conforme expectativas de juros, riscos e posicionamento. Por isso, não existe regra automática “surpresa positiva = compra”.

## Testes e escopo

Suítes locais, com um **espelho de teste** do roteador G8 e do registro dos 28 pares: `test_atlasquant_trader_economic_surprise_veto_lab.py` e as duas suítes já existentes de expectativas de juros. Esses testes usam **somente dados sintéticos**. O teste completo em CI no repositório real deve ser executado antes de qualquer uso operacional. A integração foi feita por atualização cirúrgica do módulo `atlasquant_trader_evidence_join_lab.py` e de suas asserções legadas.

**Próximo passo P0:** reunir calendários econômicos, consensos pré-evento com data atestada e valores oficiais de primeira publicação; criar cenários **walk-forward** independentes, comparando acerto direcional e taxa de abstenção por D1 e W1. Adicionar fator apenas se demonstrar ganho fora da amostra. A meta de pesquisa de 65%–70% não constitui desempenho observado.
