# A316 — Checagem cruzada de intenção na mensagem e no recibo SQLite (LAB)

**HARD NO-GO · ZERO_AUTO_RESEND · P0 homologadas 0/6 · sem merge, Worker, deploy, ordens, provedor ou novos custos.**

## Contexto e mudança concreta

A315 validou no GitHub Actions **28/28 workflows**, incluindo os 22 testes novos em Ubuntu e Windows. Seu modo sintético `strict_semantic_intent=True` armazena um recibo de `intent_id` e a mensagem dentro do mesmo COMMIT do SQLite. A deduplicação local já resistia à troca do ID de transporte e à reinicialização, porém a exclusão hostil de **somente a linha do recibo** ainda aceitava uma segunda mensagem, porque o registro original não guardava o identificador semântico.

A316 adiciona uma checagem cruzada **somente ao caminho sintético opt-in A315**:

1. Antes de gravar a primeira mensagem, busca qualquer mensagem pré-existente do mesmo `owner/tenant/workspace/intent_id`, lendo a etiqueta interna `metadata.a316_semantic_intent_id` dentro do SQLite. Esta busca acontece sob o mesmo `BEGIN IMMEDIATE`.
2. Se a tabela de recibos não tiver a intenção, **mas houver uma mensagem já etiquetada**, a conexão é marcada `FAILED / A316_LOCAL_INTENT_RECEIPT_MISSING_ZERO_AUTO_RETRY` e a nova gravação é recusada. Não há novo COMMIT, marcador nem reenvio.
3. Em uma gravação nova, salva `a316_semantic_intent_id` e `a316_payload_digest` dentro do campo JSON da mensagem; esse JSON, o recibo e a contagem de mensagens entram no **mesmo COMMIT cercado**.
4. Em replays cujo recibo existe, verifica o ID e o digest dentro da mensagem original. Dados divergentes, ausência do rastro ou mensagem inexistente causam `FAILED / A315_LOCAL_INTENT_RECEIPT_DIVERGED`, sem retry.
5. A busca restringe a identidade de `owner/tenant/workspace`; dados de uma conta diferente não bloqueiam intenções válidas de outro escopo. Chamadores continuam impedidos de enviar metadados arbitrários.
6. Os seis escritores originais e o modo padrão permanecem sem alteração. Não há tabela nem COMMIT adicional; o sétimo método opt-in já auditado na A315 permanece cercado.

## Contraprovas que permanecem

**Uma exclusão de apenas um registro já não basta**: a mensagem remanescente bloqueia a repetição. Mas se o host puder **apagar o recibo e alterar também o campo JSON da mensagem**, a intenção pode ser registrada novamente com outro ID. Esse contraexemplo faz parte dos testes A316 e demonstra por que duas cópias dentro do **mesmo arquivo e do mesmo computador NÃO** são custódia independente, nem provam P0-3.

Outros limites: o operador do próprio host/DB pode apagar ou restaurar ambas as cópias, a tabela de recibos não é testemunha imutável, não existe prova de efeito externo nem de ACK de provedor, e nenhum UID/VFS/FD/WAL/SHM de produção está autenticado. Um registro antigo criado antes de A316, sem o novo metadata, é tratado como ambíguo, **não** recebe atestação retroativa.

## Validação

```sh
python -m unittest -v labs.test_a316_orphan_intent_crosscheck_lab labs.test_a315_semantic_intent_atomic_commit_lab
```

Executar Ubuntu e Windows com SQLite real descartável; incluir A314/A313/A312/A311/A310/A309/A246/A247/A292/A293/A299 como regressões.

**Aceitação LAB:** comprovada redução de uma duplicação local quando **apenas o recibo foi removido**.

**Aceitação operacional P0-3:** ainda impossível. Exige prova de intenção imutável sob autoridade independente/off-host, vínculo de identidade/nonce/geração, proteção antirollback e reconciliação verificável do resultado de efeito externo, sem qualquer retry automático.
