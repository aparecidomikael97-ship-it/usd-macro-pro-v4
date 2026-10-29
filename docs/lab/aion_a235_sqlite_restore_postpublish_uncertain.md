# A235 — resultado incerto após publicação SQLite não é falha sem efeito

**Estado:** mitigação parcial em staging e laboratório, **HARD NO-GO · P0 homologados 0/6 · `UNCERTAIN=ZERO_AUTO_RESEND`**. Nenhum merge, Worker, deploy, corretora, cliente, contrato, senha, assinatura real ou serviço pago.

## Risco concreto remanescente do A234

O A234 trocou o perigoso `os.replace(temp, target)` por `os.link(temp, target)`: o segundo operador só cria um caminho novo e jamais substitui um banco existente. Mas depois do `os.link`, **o banco já pode estar visível para outra conexão**. Uma falha na remoção do temporário poderia ser relatada apenas como falha genérica, sem separar "nenhum efeito" de "houve publicação, mas não sei se terminou". Há também uma janela entre a última checagem dos sidecars e a publicação do arquivo.

**A235 não resolve P0-5/6 integralmente.** Ele reduz falsos "restore concluído" e distingue especificamente o resultado incerto **depois** da publicação.

## Mudança no código real do staging, isolado em Draft

1. `aion_chat.store.RestorePublicationUncertainError` herda de `StorageUnavailableError`: todas as camadas que já negavam indisponibilidade continuam recusando a restauração, agora com estado explícito de resultado incerto.
2. Depois de `os.link(temp,target)`, verifica novamente o aparecimento de `-wal`, `-shm` e `-journal`. Uma criação simulada durante a publicação força `RESTORE_PUBLICATION_OUTCOME_UNKNOWN_SIDECAR_RACE_ZERO_AUTO_RETRY`.
3. Compara `st_dev` e `st_ino` do temporário com o destino recém-publicado. Uma troca visível força `RESTORE_PUBLICATION_OUTCOME_UNKNOWN_TARGET_CHANGED_ZERO_AUTO_RETRY`. Isso **não atesta** qual handle está em uso na VFS SQLite.
4. Se a inspeção ou limpeza final falhar (por exemplo `PermissionError` em `temp.unlink()`), responde `RESTORE_PUBLICATION_OUTCOME_UNKNOWN_POST_LINK_IO_ZERO_AUTO_RETRY`. **Não remove o destino publicado e não recomenda retry.**
5. Na próxima chamada, um destino existente continua sendo recusado, inclusive quando a chamada anterior terminou em exceção.

## Testes reais

`labs/test_a235_sqlite_restore_postpublish_uncertain.py`: **15 testes novos** em arquivos SQLite temporários e com falhas injetadas no ponto exato, incluindo WAL, SHM, journal, permissão negada no unlink, troca de destino, destino desaparecido, validação de origem, recusa antes de publicar, integração ao wrapper `restore_verified_staging_backup` e inexistência de retry automático nessa API.

`.github/workflows/aion-a235-sqlite-restore-postpublish-uncertain.yml`: regressão A202–A234 + resiliência staging, Python 3.12, Ubuntu e Windows, SHA das actions pinado. **1.065 testes esperados por SO** (15 novos + 1.050 A234); confirmar nos logs.

## Falhas restantes não mascaradas

- O pós-check **não fecha a corrida** contra um atacante com controle do diretório, que pode criar/remover sidecar depois da checagem; seriam necessários isolamento de processo/FS, locks ou arquitetura diferente, verificados por privilégios reais.
- Comparar inode não vincula o handle SQLite nativo, não prova ausência de rollback com **mesmo inode** e não resiste a controle admin/root.
- Não houve teste físico de queda de energia; `os.link()` e a limpeza de temporário não substituem `fsync`/garantia de ordenação e persistência do diretório.
- `RESTORE_VERIFIED` é um sucesso **local do staging**, não comprovante de H0, origem externa, efeito financeiro nem P0 homologado. Nenhuma operação externa foi chamada.

**Próximo gate:** protocolar publicação/reconciliação física com risco de crash e custódia independente, sem confundir esse trabalho com homologação do VFS ou recibo financeiro. `UNCERTAIN=ZERO_AUTO_RESEND` sempre.
