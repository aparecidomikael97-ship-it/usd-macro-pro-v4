# AION P0 — Outbox: transações SQLite externas não podem ser confirmadas pelo bloqueio

**Data:** 21/10/2026. **Apenas laboratório, PR Draft.** Worker OFF, ZERO_AUTO_RESEND, HARD NO-GO, 0/6 P0 homologados.

## Defeito local analisado

O código real de `ExecutionOutbox.release_expired_claims` já proíbe empréstimo de transação SQLite externa: `OUTBOX_NESTED_TRANSACTION_UNSUPPORTED`. Mas `dispatch_claimed` não tinha essa barreira e sua rotina interna `_set_blocked` usava `with self.db:`, um context manager do `sqlite3.Connection`. Em Python, quando a conexão já tem uma transação aberta, sair do `with connection:` sem erro faz `COMMIT` da transação, **inclusive alterações que pertencem ao chamador**. Se a operação de dispatch for negada pela autorização local, o fluxo usa exatamente `_set_blocked`: isso abre risco de confirmação indevida da transação externa, inclusive savepoints, em vez de devolver controle ao dono. Se o CAS falhar e lançar exceção, o mesmo `with` pode reverter o trabalho externo.

A falha foi observada **somente num cenário in-process no mesmo SQLite local**, sem acesso a fornecedor, Worker, mensagens, webhook ou credenciais. Não significa que o AION tenha realizado uma transação externa real nem que exista exploit remoto.

## Testes adversariais (RED antes da correção)

`tests/test_aion_p0_outbox_parent_transaction_denial_lab.py` cria SQLiteChatStore + ExecutionOutbox reais em banco descartável; enfileira e reivindica uma intenção local sem adaptador e depois abre `BEGIN IMMEDIATE`/SAVEPOINT próprio com um marcador ainda não confirmado. Verifica:

- `dispatch_claimed` negado por política e `_set_blocked` não podem confirmar ou desfazer os marcadores do chamador;
- a rejeição deve ocorrer **antes** de consultar callbacks de política/adapter;
- savepoints continuam válidos para `ROLLBACK TO SAVEPOINT`;
- o CAS privado com snapshot de lease stale não pode causar rollback da transação externa;
- fora de transação aninhada, o bloqueio normal `REVOKED` continua funcionando e não gera efeito;
- `release_expired_claims` mantém a barreira já existente.

No HEAD sem patch `d7e84a20986d451e5f76093751ee9ed78ba243c4`, [run #39619304685](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39619304685), o Windows marcou **6 FAIL de 9**, todos no contrato de não empréstimo de transação, sem simular autorização externa. O resultado antes do patch não deve ser reinterpretado como falha dos contratos de produtor.

## Correção de produção PROPOSTA, ainda não mesclada

Em `atlasquant_aion_execution_outbox.py`:
1. `_set_blocked` chama `_require_connection_thread`, então rejeita qualquer conexão já em transação com `RuntimeError("OUTBOX_NESTED_TRANSACTION_UNSUPPORTED")` **antes de validação de estado, UPDATE ou comitê SQLite**.
2. `dispatch_claimed` usa o mesmo guard antes de obter data do relógio, snapshot, chamar `authorize`, exigir budget, inspecionar adaptador ou tocar banco.
3. Fora de transações existentes, o comportamento do CAS pre-dispatch e do hardstop de produtor externo continua igual.
4. `_confirm` continua `INDEPENDENT_PRODUCER_RECEIPT_NOT_ENROLLED`, `reconcile` continua `INDEPENDENT_PRODUCER_NOT_ENROLLED`; nenhum caminho abre efeito ou reenvio.

O fix escolhe **negar** o uso com transação aninhada em vez de adotar automaticamente SAVEPOINT, pois autorização/política e eventual envio externo precisam de uma fronteira transacional explicitamente homologada. Não altera o armazenamento de idempotência, fences externos, rollback físico, head/latest ou identidade do HUMAN_OWNER.

## Evidência exigida para fechamento da PR

A CI específica read-only deve executar nove casos novos e 156 regressões anteriores em Ubuntu e Windows: **165 execuções por sistema**, 330 execuções selecionadas no total se todas passarem. Reexecutar sem skips nem waivers a Quality original de 588 módulos / 6.895 testes, Security A74 365 e H0 A79 64. O baseline anterior está RED: 51 FAIL e 34 ERROR.

**Esta correção só protege a transação local do chamador. H0 e os seis P0 continuam não homologados. Sem merge, deploy, ativação do Worker, efeito externo ou gasto adicional.**
