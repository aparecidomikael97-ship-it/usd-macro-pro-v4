# A267 — Nenhum callback de autorização/orçamento no despacho NORMAL

**Somente LAB · HARD NO-GO · 0/6 P0 homologadas · sem Worker, merge, deploy, efeito externo ou custo.**

## Problema confirmado após A266

O Outbox normal já não obtinha reserva independente e não chamava `adapter.send`; a A266 também adiou o acesso à propriedade `adapter.send` para depois da reserva. Porém `dispatch_claimed()` ainda chamava `authorize(dict(decision))` em `_authorization_gate` e, para decisões com risco, `cumulative_authority_guard(dict(decision))` **antes de consultar a reserva independente**.

Esses callbacks são fornecidos pelo próprio host. Mesmo quando seus resultados seriam recusados, apenas executá-los poderia produzir chamadas de rede, uso de credenciais, débitos ou outros efeitos. **A recusa do resultado não impede o efeito do callback.**

## Alteração A267 — código real mais simples

- `atlasquant_aion_execution_outbox.ExecutionOutbox.dispatch_claimed` normal **não consulta, não verifica `callable` e não invoca** os objetos `authorize`, `cumulative_authority_guard` ou `adapter`.
- Continua conferindo de maneira local estado `CLAIMED`, proprietário da lease, vencimento da lease e expiração da autorização já registrada. Se a autorização gravada expirou, preserva o bloqueio `BLOCKED_REAPPROVAL/AUTHORITY_EXPIRED`, sem callback.
- Se ainda não expirou, faz a transição atômica SQLite `CLAIMED -> UNCERTAIN` vinculada ao escopo, proprietário e instante da lease, limpa a lease e registra `NO_INDEPENDENT_AUTHORITY_NO_CALLBACK_NO_SEND`. **Zero SEND, zero callback, zero reenvio automático.**
- A implementação completa histórica do dispatcher que invoca política, guardião cumulativo, primeira reserva sintética e adapter foi **retirada do módulo normal** e copiada para `labs/a259_synthetic_outbox_fixture.py` dentro de `SyntheticFirstAttemptOutboxLab.dispatch_claimed`. Os testes A202–A266 que usam essa fixture continuam podendo reproduzir simulações de SEND sem afetar o código que compõe o pacote mínimo A260.
- A A266 passa a verificar a ordem `reserva -> CAS -> getattr(adapter.send)` na classe **LAB**, além de exigir que esse `getattr` esteja ausente da classe normal.

## Ensaios A267

13 testes: callbacks que explodem ao ser chamados, orçamento vinculado com `authority_budget_ref` e `risk_points`, falsos relatórios positivos, objetos não chamáveis, autorização local vencida, outro proprietário da lease, segundo despacho após UNCERTAIN, reinício com zero auto resend, 40 tentativas concorrentes com SQLite separado, compatibilidade de envio *fictício* em LAB, inspeção de fonte de duas classes, separação de importações e **XFAIL explícita**: um host adversarial que consegue importar/alterar classes Python ainda pode usar a simulação perigosa.

A CI Ubuntu/Windows deve executar A267, A266, A265, A264/A263 e regressões A260–A243, A202–A206, A213, Outbox, Saga e Chaos Campaign. **A CI verde não é homologação de P0.** Nenhuma chamada real a provedor será testada.

## Limites honestos

- O mecanismo normal fica **sem caminho positivo** para autorizações ou reservas externas; essa decisão limita a execução, mas é intencional até prova independente.
- O caminho `UNCERTAIN` é conservador para não autorizar reenvio; não significa que foi feita uma chamada real.
- A classe LAB é deliberadamente perigosa: outros módulos no checkout podem importá-la. A260–A262 ainda não são bloqueios obrigatórios no Render; a `main` segue sem proteção administrativa verificada (A263, proposta A264 não aplicada).
- P0-1 a P0-6 ainda exigem identidade e custódia independentes, testemunha de primeira tentativa monotônica, SQLite nativo FD/VFS/COMMIT e recibos reais. Nenhuma foi homologada.

**HARD NO-GO, 0/6 P0, UNCERTAIN=ZERO_AUTO_RESEND.** Prioridade Trader, Investimentos preparado, Negócios congelada, sem gastos novos.
