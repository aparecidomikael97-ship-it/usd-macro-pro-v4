# A238 — Backups SQLite de staging: publicar sem sobrescrever (HARD NO-GO)

Continuação da [A237 PR #1688](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1688), somente pesquisa e testes locais. **0/6 P0 homologados.**

## Contraexemplo que motivou o gate

Antes de A238, `SQLiteChatStore.backup_to(destination)` usava `os.replace(temp, destination)`. Com outro banco SQLite já aberto no caminho de destino, o processo antigo podia continuar a ler o inode anterior, enquanto um novo processo abria o backup recém-substituído no **mesmo pathname**. Um backup não pode destruir silenciosamente um banco vivo nem mascarar duas visões simultâneas.

## Alteração em `aion_chat/store.py`

- Destino de backup precisa ser **novo**: recusa arquivo, diretório, symlink (inclusive quebrado) e sidecars `-wal/-shm/-journal`.
- Substitui `os.replace` por `os.link(temp, destination)`, criação atômica se o nome não existir; falha de suporte ao hardlink recusa.
- Após publicar, solicita `fsync` de diretório no POSIX, inspeciona sidecars/identidade de inode visível e limpa temporário.
- Se a publicação pode ter ocorrido e a etapa posterior falha, retorna `BackupPublicationUncertainError` mantendo o destino. Outra tentativa no mesmo nome será negada.
- Relata `directory_sync_requested` e **`power_loss_durability_verified=False`**. Sucesso do sistema operacional não comprova sobrevivência a corte elétrico.

## Testes

`labs/test_a238_sqlite_backup_create_only.py`: 12 cenários com bancos SQLite nativos: backup novo, preservação de banco vivo aberto, symlink pendente, diretório existente, três sidecars, criador concorrente, erro pós-publicação no fsync, falha de limpeza, sidecar concorrente, troca do inode, duas origens concorrendo e plataforma sem fsync de diretório.

CI Linux/Windows executa os 12 testes junto com as **1.095** regressões A237: previsão **1.107 testes por sistema** (confirmar no log). Nunca reduzir falhas de segurança para deixar CI verde.

## O que continua sem resolução

1. O administrador do host pode manipular caminhos, inodes e sidecars; não há autenticação atômica do FD/VFS SQLite aberto.
2. Hardlink e fsync não são prova de persistência contra corte físico, reordenação de storage, rollback do dispositivo ou recuperação após falha de hardware.
3. O manifesto `.manifest.json` de staging ainda é local e não é prova externa de origem nem antirrollback.
4. Não há recibo externo, testemunha H0, identidade HUMAN_OWNER independente ou reconciliação de COMMIT.
5. A nova regra exige um **caminho exclusivo por snapshot**. Qualquer rotina que reutilize o mesmo nome precisa escolher um novo identificador de backup; nenhuma exclusão/rotação automática foi adicionada.

**HARD NO-GO — P0 0/6 — UNCERTAIN=ZERO_AUTO_RESEND.** Proibido merge, deploy, Worker, integração financeira, contratação ou gasto com base nestes ensaios.
