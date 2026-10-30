# A310 — Composição opt-in de autorizador SQL com cerca de COMMIT (LAB)

**HARD NO-GO · ZERO_AUTO_RESEND · P0 homologadas: 0/6 · sem novas contratações.**

## Avanço concreto sobre A309

A309 acrescentou o modo opt-in que exige transação protegida para os dois auxiliares privados `_update` e `_save_record`. A A309 encerrou **26/26 workflows GitHub Actions verdes**, mas contraprovas demonstraram que código Python pode escrever diretamente em `SQLiteChatStore.db`.

A310 modifica `aion_chat/store.py` **apenas nesta branch de pesquisa**. Introduz um segundo opt-in:

```python
SQLiteChatStore(
    path,
    strict_private_write_helpers=True,
    strict_sql_authorizer=True,
)
```

Ambos os flags permanecem desligados por padrão. A310 exige A309 habilitada e autentica apenas a **região cooperativa do próprio método público na mesma thread**, nunca uma identidade humana externa.

- Instala o callback `sqlite3.Connection.set_authorizer` depois de inicializar e verificar o banco.
- Fora das seis operações públicas de escrita, recusa em SQLite opcodes de `INSERT`, `UPDATE`, `DELETE`, DDL, `ATTACH`, `DETACH`, alteração de PRAGMA e transações SQL manuais.
- Dentro de `create_conversation`, `append_message`, `archive_conversation`, `add_attachment_metadata`, `save_checkpoint`, `save_context_summary`, o callback habilita o acesso SQL somente durante a chamada inteira do método, ainda sujeito à cerca de COMMIT A247/A251 e à proteção privada A309.
- Revoga o acesso após o método e reinstala o autorizador para invalidar instruções SQL previamente preparadas/cached. Falha ao reinstalar coloca o handle em `FAILED` e proíbe retry cego.
- Consultas de leitura e PRAGMAs conhecidos de saúde continuam acessíveis.

## Testes negativos e limites honestos

Os testes usam somente SQLite real em arquivos temporários. Eles demonstram recusa de DML/DDL direto, `PRAGMA writable_schema`, mudança de `journal_mode`, `BEGIN IMMEDIATE`, execução da SQL anteriormente autorizada, tentativa de chamar `_fenced_chat_transaction` sem método público e falha sintética de ACK após COMMIT.

**Contraprova importante:** a conexão `store.db` permanece acessível. Código Python com controle do objeto pode executar `store.db.set_authorizer(None)` e então fazer uma gravação sem marcador de COMMIT. Outros processos com acesso ao banco também podem ignorar o callback local. A flag `_sql_authorizer_writer_tid` é Python mutável. Portanto, A310 **não** representa isolação hostil nem fecha P0-6.

O A310 também **não comprova** VFS/FD nativo do SQLite (P0-5), WAL/SHM autênticos, durabilidade elétrica, custódia de intenção/revogações fora do host, recibos externos, proprietário ou reabertura autorizada.

### Invariantes

Nenhum efeito externo; nenhum reenvio; P0 homologadas 0/6; HARD NO-GO; ZERO_AUTO_RESEND. PR draft empilhada sobre A309, sem merge, Worker, deploy, ordem ou pagamento. Este modo opt-in é apenas para testes, não deve ser ativado operacionalmente.

## Verificação

`python -m unittest -v labs.test_a310_optin_sqlite_authorizer_composition_lab`

Regressões A309, A292, A246, A247, A293 e A299 também devem passar no Ubuntu e no Windows. Execuções verdes demonstram **coerência local com cenários sintéticos**, não autorização operacional.

## Próxima etapa útil

A exclusividade de gravações e a autoridade precisam sair de `self.db` e do mesmo interpretador Python, com uma fronteira de execução separada, trilha durável de intenção e provas independentes de entrega/efeito. Não confundir aumentar guardas locais com resolver isso. O plano de implementação deve passar por uma revisão de arquitetura e P0, sem abrir Worker/deploy.
