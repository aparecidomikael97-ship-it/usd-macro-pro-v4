# A176 — Auditoria P0-3 Outbox, do RED ao GREEN (LAB)

**Data:** 2026-10-22. **PR Draft:** #1466 (empilhada sobre #1465). **Main não alterada. HARD NO-GO, 0/6 P0 homologados.**

## Descrição do risco localizado no código
O módulo `atlasquant_aion_execution_outbox.py` possuía dois caminhos para autorização de reenvio depois de ultrapassar a fronteira de efeitos externos:

1. `dispatch_claimed`: após chamar `adapter.send(...)`, uma resposta `{"accepted": false, "retryable": true}` alterava o outbox para `RETRY`. O adaptador não prova que o efeito externo não ocorreu.
2. `reconcile`: para um outbox `UNCERTAIN` ou `SENT`, o retorno `{"found": false, "authoritative_absence": true}` colocava em `RETRY`. Esse booleano é autoafirmação do adaptador, não um recibo verificável de ausência de efeito.

Esses caminhos eram exercitáveis pelo código LAB e **não devem ser chamados de operação real explorada**. A reexecução externa não foi provocada; simulamos a superfície de chamada com adaptadores locais.

## Prova RED
[CI GitHub Actions #39867407275](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39867407275), Ubuntu: 33 testes, **4 FAIL**, os quatro casos adversariais `test_01` a `test_04`. O estado retornado era `RETRY` quando a propriedade de segurança exigia `UNCERTAIN`.

## Correção candidata — somento LAB
- Resultado `retryable=True` vindo do `send` após cruzar fronteira vira `UNCERTAIN` + razão `ADAPTER_RETRY_CLAIM_UNVERIFIED_NO_RESEND`; não retorna à fila.
- Reconciliador não converte declaração `authoritative_absence=True` em `RETRY`: conserva `UNCERTAIN/SENT`, `STILL_UNCERTAIN`.
- Permanece a possibilidade de reconciliação sintética para `CONFIRMED` quando `found=True,confirmed=True`; **isto não autentica o recibo**.
- Atualização explícita de um teste histórico que **esperava** erroneamente retentativa após falso atestado de ausência. Testes de Outbox e Saga continuam executados, sem liberar comportamento inseguro.

## Prova GREEN final
[CI GitHub Actions #39867557973](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39867557973): **Ubuntu 33/33 + Windows 33/33 = 66 execuções aprovadas**. Foram executados os cinco testes adversariais A176 e os testes históricos de Outbox e Saga, com rede proibida.

Evidências emitidas nas duas plataformas:
- `A176_RETRYABLE_AFTER_SEND=QUARANTINED`
- `A176_UNTRUSTED_ABSENCE=QUARANTINED`
- `A176_LYING_RETRYABLE_ADAPTER=NO_AUTO_RESEND`
- `A176_UNCERTAIN_RESTART=NO_AUTO_RESEND`
- `A176_SIMULATED_FOUND_RECEIPT=CONFIRMED_LAB_ONLY`

## Riscos remanescentes — não considerar encerrados
1. **P0-3:** `send` devolvendo `accepted=False,retryable=False` ainda mapeia `FAILED` após cruzar fronteira; falta provar via provedor confiável que a rejeição significa realmente efeito zero. Um novo ID de operação ainda pode representar o mesmo efeito.
2. **P0-2:** `reconcile` com `found=True,confirmed=True` aceita afirmações do adaptador sem autenticação independente de origem/recibo. `CONFIRMED` LAB **não prova efeito real**.
3. **P0-3/4:** apagar ou restaurar o banco local pode apagar estados, como A174/A175 mostraram. Falta testemunha monotônica externa e recuperação H0 com evidência de infraestrutura real.
4. **P0-3:** todos os call sites de adaptação/terceiros e quaisquer interfaces de reenvio com ID novo precisam passar por auditoria; este patch não atesta cobertura integral do sistema.
5. **P0-5/6:** não há prova do vínculo atômico da conexão SQLite com o arquivo nativo. A correção A176 não mexe nessa frente.
6. A Quality canônica completa não foi reexecutada; não contar 66 execuções como 66 cenários independentes homologados.

## Governança
Somente testes sintéticos, PR Draft, sem merge/deploy/Worker, sem chaves, sem cadastro externo, sem envios reais, sem ativação operacional ou gasto adicional. `ZERO_AUTO_RESEND` obrigatório. Nenhum P0 homologado.
