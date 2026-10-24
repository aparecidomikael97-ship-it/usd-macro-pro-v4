# A190 G4 — evidência CI real de WAL/SHM, live reader, FD/path e AION Store

**Dia do proprietário:** 2026-10-23. **PR #1491:** Draft, baseada em G3 #1490, missão #1486.

## Rastreabilidade exata

- **SHA efetivamente testado** (código, workflow e preflight): e8c2ffa30c13f1f9fe88f5974f555b8ba621a74c.
- **Run GitHub Actions:** https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40046115860 — completed/success conferido.
- **Job Ubuntu:** 120728118303, completed/success, log "Ran 9 tests in 0.288s", OK, SHA checkout no log.
- **Job Windows:** 120728118628, completed/success, log "Ran 9 tests in 1.262s", OK, SHA checkout no log.
- **Contagem verdadeira:** 5 casos A190 G4 novos + 4 A185 herdados = 9 por SO / **18 execuções de teste** no total, Python 3.12, SQLite nativo em runners reais.
- Dependências LAB mínimas já utilizadas no projeto: cryptography==50.0.2, requests==2.34.2.

## Resultados — dois SOs, sem ocultar diferença observada

| Marcador ou condição | Ubuntu (runner) | Windows (runner) | Limite da evidência |
| --- | --- | --- | --- |
| A190_G4_MAIN_FILE_ONLY_COPY=LOST_COMMITTED_WAL_ROW_RED | Reproduzido | Reproduzido | Row com COMMIT no WAL perdida na **cópia avulsa main.sqlite** |
| A190_G4_SQLITE_BACKUP_API=INCLUDES_COMMITTED_WAL_ROW | Comprovado neste caso | Comprovado neste caso | Backup via API sqlite inclui a row; não prova restore atômico |
| A190_G4_REAL_WAL_AND_SHM=CREATED_AND_EXERCISED | Observado | Observado | Sidecars físicos criados e WAL não vazio |
| A190_G4_PINNED_SQLITE_READER=STALE_SNAPSHOT_WITH_NEWER_COMMITTED_WAL | Reproduzido | Reproduzido | Duas visões temporais com leituras efetivas |
| A190_G4_LIVE_READER_PREVENTS_WAL_TRUNCATE=BUSY_THEN_SUCCESS | Reproduzido | Reproduzido | SQLite não trunca enquanto snapshot antigo está aberto; após rollback, checkpoint passa |
| A190_G4_LIVE_PATH_REPLACEMENT_RESULT=... | STALE_OPEN_HANDLE_VS_NEW_PATH | OS_DENIED_WHILE_HANDLE_OPEN; AFTER_CLOSING_HANDLES=PATH_REPLACEMENT_SUCCEEDED | **Diferença real** Linux/Windows; não homologar por extrapolação entre SOs |
| A190_G4_SAME_NATIVE_FILE_ID_DIFFERENT_COMMITTED_CONTENT=RED | Reproduzido | Reproduzido | Dev/inode pode permanecer igual após conteúdo mudar; identidade não é prova de histórico |
| A190_G4_REAL_AION_SQLITE_CHAT_STORE_MAIN_ONLY_COPY=STALE_RED | Reproduzido | Reproduzido | SQLiteChatStore real com conversa sintética; cópia avulsa, não API oficial, ficou atrás do WAL |
| A185 shared-handle/revocation/raw/reopen | 4 marcadores | 4 marcadores | Regressões preexistentes exercidas, com seus bypasses históricos ainda RED |

**Inspeção estática adicional e delimitada:** aion_chat/store.py, nesta base, define backup_to usando wal_checkpoint("FULL") + self.db.backup(target) + validação do backup e journal_mode=DELETE. Portanto **não** concluir que o método oficial de backup AION usa a cópia bruta insegura. O teste G4 força deliberadamente um método de backup incorreto, para demonstrar por que o caminho correto importa. Um FULL checkpoint e uma cópia API também NÃO substituem autenticidade de origem, piso remoto, proteção de handles nativos e H0.

## Ausências de prova que mantêm NO-GO

- Nenhum VFS customizado/obrigatório nem enforcement do FD de **todas** conexões AION; apenas arquivo real + conexão SQLite real e FD OS separado em G4-3.
- Nenhum ataque admin/root com privilégio de kernel ou fora do host, hardware antirollback, WAL/SHM atômico durante restore hostil, same-inode ABA com reabertura, corrupção de journaling/power-loss, parada súbita ou boot H0.
- Não demonstra autoridade HUMAN_OWNER, primeira operação semanticamente única, contrato de fornecedor, assinatura externa autêntica ou recibo de efeito; G3 permanece RED.
- Quality/Security canônicas NÃO reexecutadas nesta PR; os cinco requisitos external-RED por SO e as 43 advisories herdadas permanecem pendentes até evidência externa própria.
- GREEN do CI é **reprodução de limites/bypasses e controles positivos**, NÃO resolução de G4/P0. Nenhuma mudança em produção, main/Worker, deploy ou despesas.

**Estado inalterado:** 0/6 P0 HOMOLOGADOS; HARD NO-GO; UNCERTAIN; ZERO_AUTO_RESEND. PR Draft somente LAB.
