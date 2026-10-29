# A240 — Veto de mudança de pathname SQLite (somente LAB)

Continuação da A239 [PR #1690](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1690). **0/6 P0 homologados; HARD NO-GO.**

## Falha atacada

Uma conexão SQLite previamente aberta pode continuar lendo o arquivo antigo se outro processo trocar o pathname por `os.replace` no Linux. O store anterior só verificava `self.db is not None` e integridade SQL do handle antigo, podendo tratar a conexão obsoleta como saudável.

## Guarda local implementado

- Na criação do `SQLiteChatStore`, captura `st_dev/st_ino` do pathname regular e recusa symlink ou identidade indisponível.
- Antes de operações que passam por `_require_open` e antes de `storage_health`, compara novamente o pathname. Falha ou alteração gera estado `FAILED` e impede uso da conexão antiga no fluxo protegido.
- O resultado de `storage_health` não usa `PRAGMA` se o nome já mudou; não transforma leitura do arquivo antigo em prova de saúde da rota atual.
- Esse é um **veto local de mudança visível do caminho**, não prova do descritor FD/VFS realmente aberto. Chamadas diretas a `.db`, corridas entre check e uso, rollback do mesmo inode e controle hostil do filesystem continuam fora dessa garantia.

## Testes

9 testes novos: leitura normal, substituição nativa Linux (Windows pode negar por bloqueio de OS), remoção nativa do caminho, falha persistente por identity mismatch, health sem PRAGMA, backup negado, symlink de entrada, escrita WAL normal e leitura escopada negada. Regressões A239 inteiras continuam: **1.130 testes por sistema esperados**, sujeitos aos logs Ubuntu/Windows.

## Pendências

Nenhum teste usa um VFS SQLite instrumentado que forneça o FD autêntico, vínculo atômico entre validação/COMMIT e identidade, proteção contra host administrador, prova de corte de energia, testemunha externa monotônica ou recibo de efeito. P0-5 e P0-6 exigem mais que esta comparação.

**HARD NO-GO · P0 0/6 · UNCERTAIN=ZERO_AUTO_RESEND · sem merge/deploy/Worker/contratação/efeito financeiro.**
