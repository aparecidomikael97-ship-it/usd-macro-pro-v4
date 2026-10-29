# A242 — Reserva obrigatória da primeira tentativa antes de SEND (somente LAB)

Continuação da A241 [PR #1692](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1692). Adapta a ideia anterior da [A180 #1470](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1470) aos gates e CAS mais recentes A202–A241, **sem raiz externa autêntica**.

## Problema corrigido no stack atual

`ExecutionOutbox.dispatch_claimed` armazenava `UNCERTAIN` com CAS, mas logo invocava `adapter.send` sem exigir qualquer reserva anterior da primeira tentativa por testemunha. Uma gravação SQLite local não é reserva independente nem impede que um host restaurado tente produzir efeito semântico repetido.

## Implementação

- `ExecutionOutbox(..., first_attempt_guard=None)` agora **NEGA por padrão** a chamada `adapter.send`.
- O CAS `CLAIMED → UNCERTAIN` acontece antes de consultar o guard. Mesmo se houver timeout ou perda de ACK da reserva, a tentativa não reentra em RETRY automaticamente.
- Sem guard, erro, retorno False/None/truthy diferente de literal True: mantém `UNCERTAIN`, remove lease da tentativa, marca `FIRST_ATTEMPT_WITNESS_UNVERIFIED_NO_SEND` e não chama adaptador.
- Um guard que retorna True é **ainda não confiável**: CAS adicional exige estado, lease e início da tentativa originais antes de permitir a chamada. Uma mudança concorrente não autoriza SEND.
- A242 preserva a checagem A241 da conexão SQLite antes da fronteira de envio e a recusa A213 de confirmação autoatestada.
- Testes preexistentes que simulam SEND usam `first_attempt_guard=lambda _intent: True` **somente em seus próprios arquivos**, de maneira explícita. Isso não é uma chave, witness ou autorização operacional.

## Testes

12 novos cenários: default DENY, bool estrito, timeout, reserva sintética, ordem durável UNCERTAIN→guard→send, restart sem retry, repetição recusada, tipo inválido, mudança concorrente de estado, pathname adulterado durante callback, autorização prévia negada e demonstração explícita de que um guard do chamador pode mentir.

Com os 1.138 testes A241 no workflow, previsão de **1.150 testes por SO** Ubuntu/Windows (conferir logs). Nenhum provedor, rede, contratação ou envio financeiro.

## Limites fundamentais — P0-3/4 ainda NÃO homologadas

1. Um callback `True` injetado pelo host é **forjável**; não comprova identidade HUMAN_OWNER, fonte externa independente ou reserva autêntica.
2. A mesma intenção pode ser reconstituída com outro identificador semântico, ou o diário/witness pode sofrer rollback; falta autoridade de identidade e high-water irreversível.
3. Não há bootstrap de chaves independentes, quórum H0, recibo de efeito externo, reconciliação pós-COMMIT nem garantia nativa FD/VFS.
4. Chamadas diretas a um adaptador por fora deste Outbox não são cobertas; Worker e provedores seguem proibidos.

**HARD NO-GO · 0/6 P0 homologadas · UNCERTAIN=ZERO_AUTO_RESEND · sem merge/deploy/Worker/contratação/operação real.**
