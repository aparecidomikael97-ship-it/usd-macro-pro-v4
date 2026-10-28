# AION A207 — confirmação positiva autoatestada (RED-first, LAB)

**28/10/2026 UTC · DRAFT · HARD NO-GO · 0/6 P0 homologadas.**

## Hipótese que precisa ser falsificada

A205 bloqueou reenvio baseado em ausência/rejeição autoatestada.
A206 colocou CAS em resultados atrasados de SEND.
Mas a confirmação **positiva** ainda entra por duas rotas locais:

1. `ExecutionOutbox.dispatch_claimed`: `adapter.send` informa `accepted=True, confirmed=True, effect_ref=...`, levando a `_confirm`.
2. `ExecutionOutbox.reconcile`: `adapter.reconcile` informa `found=True, confirmed=True, effect_ref=...`, levando ao mesmo `_confirm`.

`_confirm` persiste `action_effects` e `CONFIRMED` em SQLite, mas os campos positivos são fornecidos pelo próprio callback injetado. Esse callback **não é** custódia causal independente do efeito externo. Assim, a existência de uma linha no ledger local não comprova, por si, que houve efeito real no provedor.

## Prova RED-first sem efeito externo

`labs/test_a207_untrusted_confirmation_requires_receipt.py` reutiliza a fixture de escopo e SQLite real da A202. Um adaptador fake **não cria efeito algum** (`actual_effects=[]`) mas devolve respostas positivas com `effect_ref` fabricado:

- Teste 01: SEND declara `confirmed=True`, sem efeito.
- Teste 02: SEND declara `SENT`; reconciliação posterior declara `found=True, confirmed=True`, sem efeito.
- Teste 03 (controle): SEND não confirmado permanece `SENT`, sem ledger.

Os testes 01/02 exigem **nenhum `CONFIRMED` e zero registros** em `action_effects` sem prova independente. A hipótese do código atual prevê RED, e **isso é esperado nessa primeira etapa**, não falha acidental de CI. O controle deve ser verde.

O workflow A207 executa somente testes sintéticos com SQLite, Ubuntu e Windows. Não envia mensagens, não carrega credenciais e não acessa provedor.

## Critério para passar de RED a GREEN

Não mascarar o teste com mais uma bandeira `verified=True` no adaptador, flag de host ou token autoassinado. É necessário definir, custodiar e testar uma evidência que o chamador não possa fabricar ou repetir:

- vínculo verificável entre escopo, intenção semântica, chave de idempotência, efeito e provedor;
- origem de confiança e assinatura/testemunha fora da autoridade do host;
- prova monotônica contra rollback e substituição do primeiro efeito;
- compatibilidade com cenários `UNCERTAIN`, atraso de ACK, crash e concorrência SQLite;
- testes negativos de fabricação, replay, revogação e corrida; regressões A202–A206.

Sem essa raiz independente, a correção operacional é **não transformar afirmações positivas do adaptador em certeza de efeito real**. Como testes legados (ex.: A205) aceitam efeitos sintéticos, qualquer futura migração de estado/contrato precisa ser explícita e comprovada, não um atalho que torne o teste verde artificialmente.

## Governança

Trabalho somente em branch LAB e PR Draft. **Sem merge, deploy, Worker, provider, SEND real, trading, alteração em Negócios ou gastos novos.** A207 não homologa nenhuma P0 e não autoriza produção. `UNCERTAIN=ZERO_AUTO_RESEND`.
