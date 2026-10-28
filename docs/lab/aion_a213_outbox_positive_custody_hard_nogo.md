# AION A213 — bloquear CONFIRMED autoatestado no Outbox (código de staging, PR Draft)

**28/10/2026 · HARD NO-GO · 0/6 P0 externas homologadas · SEM DEPLOY**

## Falha real reproduzida em A207

A branch histórica A207 Draft #1658 mantém três testes, dois RED no código anterior: um adapter devolve confirmed=True e effect_ref inventado tanto após send quanto durante reconcile, sem produzir efeito externo. Antes desta correção de staging, ExecutionOutbox._confirm gravava action_effects e CONFIRMED. O risco é que uma declaração controlada pelo host foi promovida a verdade sem recibo causal externo.

**A213 altera o código real de atlasquant_aion_execution_outbox.py na branch Draft**, mas não habilita nenhum Worker/adapter de produção e não será implantado ou mesclado automaticamente.

## Modificação de comportamento (default DENY)

| Origem | Retorno autoalegado | Estado novo seguro | Registro action_effects | Reenvio automático |
|---|---|---|---|---|
| adapter.send | accepted=True, confirmed=True | UNCERTAIN, marcador UNTRUSTED_SEND_POSITIVE_NO_EXTERNAL_RECEIPT | Não | Nunca |
| adapter.reconcile | found=True, confirmed=True | Preserva UNCERTAIN ou SENT, marcador UNTRUSTED_RECONCILE_POSITIVE_NO_EXTERNAL_RECEIPT | Não | Nunca |
| adapter.send | accepted=True, confirmed=False | SENT (anterior), exige reconciliação independente | Não | Nunca |
| adapter.send | Exceção, rejeição sem prova | UNCERTAIN (anterior) | Não | Nunca |
| adapter.reconcile | found=False, authoritative_absence=True | Preserva estado e ABSENCE_UNVERIFIED_HARD_NO_GO (anterior) | Não | Nunca |
| Chamado direto a _confirm | Qualquer argumento ou flag | PermissionError A213_INDEPENDENT_EFFECT_RECEIPT_REQUIRED | Não | Nunca |

As respostas positivas não são ignoradas silenciosamente: sua falta de confiança fica no campo last_error. Não persistir effect_ref falso como prova. Pode existir um efeito real que o host não consegue provar; o estado continua ambíguo. Isso é **intencionalmente seguro**, pois não autoriza retry e não inventa sucesso.

## Concorrência e persistência

- SEND grava UNCERTAIN antes de atravessar a borda do efeito, com CAS de lease e dispatch_started_at.
- Um SEND positivo atrasado não pode reverter um estado mais recente: atualização condicionada a estado, lease e instante observados.
- Reconciliação positiva usa CAS sobre estado, tentativa, lease, timestamps, effect_ref e last_error observados para evitar sobrescrever atualizações posteriores.
- Mesmo que um host injete receipt, signature_verified ou outra flag em dicionários callback, NÃO existe caminho para CONFIRMED.
- O método _confirm permanece com a assinatura privada histórica para compatibilidade de chamadas, mas **recusa toda chamada** até existir uma interface externa verificável, revisada separadamente.
- O banco SQLite opera localmente; o CAS não atesta autoridade externa nem protege contra administrador host malicioso alterando o banco fora da aplicação.

Fundamento técnico de transações e isolamento: https://sqlite.org/isolation.html e https://sqlite.org/lang_transaction.html.

## Testes de segurança

- A207: trouxe, **sem modificar**, os três testes originais de regressão para a branch A213; agora devem passar os cenários de efeito forjado.
- A213: 12 testes adicionais com SQLite real, adapters falsos, callbacks simultâneos, fraude em flags de recibo, bypass direto a _confirm, replay, lease, ausência e ZERO_AUTO_RESEND.
- A202–A206, teste amplo do Outbox e campanha de caos: expectativas migradas **porque não existe mais uma origem confiável de CONFIRMED nessa etapa**; ficam preservadas as provas de exclusão mútua, CAS de stale, status incerto, bloqueio de retry, ordenação e congelamento da saga.
- Testes de saga: cenários históricos de conclusão/compensação que precisam exercitar estados posteriores a CONFIRMED usam agora um **fixture explícito de banco de teste**, _test_only_seed_hypothetical_confirmed. Ele injeta dados diretamente na SQLite temporária para representar um estado **hipotético** do sistema de destino; não existe verifier, API de confirmação nem bypass habilitado no código de produção. Isso testa orçamento, contabilidade, ordem e compensação, não a confiabilidade do recibo. Outros cenários de saga exigem que o positivo falso continue UNCERTAIN e bloqueie a próxima ação.
- A212/A211/A210/A209/A208: regressões de contrato de prova, sem conexão externa.

**Limite de regressão declarado:** A204/A206 já não exercitam uma transição CONFIRMED realmente autorizada. Isso ainda é impossível, pois falta P0 de recibo externo. Quando a integração independente for proposta, terão de existir novos testes de corrida entre confirmação *com prova validada* e callback antigo — sem ativar produção prematuramente. Versões históricas dos testes continuam disponíveis nos PRs/commits anteriores. A207 original continua auditável como RED na branch antiga.

## Requisitos para evoluir sem retroceder

1. Definir e implementar verificador de efeito externo cuja chave e origem NÃO venham do host, adapter ou payload autodeclarado.
2. Verificar intenção original, idempotência, provider, efeito causal, identidade do signatário, sequência e checkpoint externo antirollback.
3. Testar assinatura real e consulta independente ao destino, incluindo ataque de retorno positivo falso e ACK perdido.
4. Desenhar uma transição CONFIRMED nova, explicitamente atestada, com CAS atômico e ledger idempotente; não reabilitar _confirm por flag booleana local.
5. Reexecutar caos, dupla confirmação, worker e reprocessamento. Só após P0 e autorização separada do HUMAN_OWNER considerar integração.

Até lá: **0/6 P0, HARD NO-GO, UNCERTAIN=ZERO_AUTO_RESEND.** Sem execução externa, serviços cloud, credenciais, contratação, custos, merge, deploy ou alteração operacional em Negócios.
