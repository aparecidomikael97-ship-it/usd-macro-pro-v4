# A315 — Intenção semântica atômica com SQLite e reinicialização (LAB)

**HARD NO-GO · ZERO_AUTO_RESEND · P0 homologadas 0/6 · sem Worker, deploy, merge, ordens, provedor ou contratação.**

## Problema real

A314 provou um canal Unix temporário com `SO_PEERCRED`, conta cliente separada do escritor e banco sintético inacessível diretamente ao cliente. Ao repetir **o mesmo request_id**, porém, o escritor criava **duas conversas**. Identidade de processo e permissão de arquivo não são idempotência de intenção.

Na A315, o `SQLiteChatStore` recebe um modo adicional, **desligado por padrão**, restrito a diretórios de teste `a315-lab-*` com marcador `.a315-synthetic-only`:

```python
SQLiteChatStore(
    path,
    strict_local_data_version=True,
    strict_private_write_helpers=True,
    strict_sql_authorizer=True,
    strict_semantic_intent=True,
)
```

O uso do modo sem A309/A310 é recusado. O caminho antigo `append_message` é **bloqueado neste modo**; o novo caminho explícito é:

```python
store.append_message_once(
    scope,
    Message(conversation_id, "user", "A315 TEST corpo imutável", id=transport_id),
    intent_id="intencao-estavel",
)
```

- O identificador da intenção é **independente** do identificador da mensagem/transporte.
- Uma chave composta `(owner,tenant,workspace,intent_id)` tem unicidade em uma tabela `a315_local_intent_receipts` no **mesmo arquivo SQLite** que as mensagens.
- Digest SHA-256 do contrato, identidade de escopo, conversa, papel e conteúdo protege contra reusar uma intenção com conteúdo diferente **quando o registro local não foi adulterado**.
- `BEGIN IMMEDIATE` serializa a checagem; **mensagem, contador de conversa e recibo** são gravados em uma única transação SQLite, protegida pelo marcador pré-COMMIT A247/A251.
- Quando o COMMIT foi reconhecido, um replay do mesmo `intent_id`, mesmo com novo `message.id`, retorna `DUPLICATE_LOCAL_NO_EFFECT` e o ID original; não grava a segunda mensagem, não publica novo marcador.
- O mesmo `intent_id` com conteúdo ou destino diferente retorna `INTENT_PAYLOAD_CONFLICT_DENIED`, sem alteração.
- Se o ACK de COMMIT é incerto, o handle fica `FAILED`, o marcador permanece e reiniciar o processo **não autoriza reenviar**.
- Verifica consistência do recibo com a linha da mensagem. Inconsistência causa falha local sticky, sem retry.
- Entrada é propositalmente estreita: só `user`, mensagens sintéticas `A315 TEST `, sem anexos, metadados externos, provedor, ordem ou efeito não local.

## Provas negativas obrigatórias

**A315 não fecha a P0-3.** A tabela de intenções pertence ao **mesmo host e mesmo banco** que a mensagem. O teste adversarial fecha o `SQLiteChatStore`, remove apenas a linha da tabela de intenções por uma conexão não autorizada e reabre; a mesma intenção com **novo ID de mensagem** pode novamente gravar outra linha. A proteção contra rollback/reconciliação da intenção original, independente do host, continua ausente.

Outras provas que faltam: assinatura vinculada a autoridade independente; nonce e geração persistente fora do host; ACK de efeito/provedor; custódia off-host; semântica de idempotência na fronteira do efeito; leitura da identidade nativa VFS/FD/WAL/SHM; restauração assinada; governança de revogação. SHA-256 local sozinho não autentica o produtor nem o histórico.

## Execução

```sh
python -m unittest -v labs.test_a315_semantic_intent_atomic_commit_lab
```

Testes com SQLite real, processos Python novos, modo estrito, COMMIT com ACK sintético perdido e adulteração de prova local. Regressões A314/A313/A312/A311/A310/A309/A246/A247/A292/A293/A299 em Ubuntu e Windows. Nenhum custo adicional nem novo serviço.

**Aceitação LAB:** idempotência **local** da mesma intenção com outro identificador, entre reinicializações e quando registro não adulterado; não afirma exatamente-uma-vez operacional.

**Aceitação P0-3:** somente quando a mesma intenção puder ser vinculada a custódia/recibos independentes e resistente a rollback, e seu efeito externo real puder ser reconciliado sem reenvio automático. Não demonstrado nesta PR.
