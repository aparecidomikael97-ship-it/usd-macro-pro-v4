# A233 — SQLite real: rollback no mesmo arquivo, cópia WAL e ACK perdido

**Escopo:** SQLite nativo em arquivos temporários descartáveis, exclusivamente laboratório. **HARD NO-GO · P0 0/6 · `UNCERTAIN=ZERO_AUTO_RESEND`**. Sem integração ao Worker, armazenamento de produção, rede, KMS/HSM, provedor ou cliente real.

## Por que A233 não é mais um formulário

O histórico dos seis P0 em [A183 #1474](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1474) documentou duas pendências diferentes:
- **P0-5:** a identidade por pathname/descritor auxiliar não autentica o **handle nativo** realmente usado no SQLite; ameaças incluem ABA e restore sob o mesmo inode.
- **P0-6:** gravar com WAL, copiar/backupear e reagir a erro depois de COMMIT não produzem, por si, garantia de durabilidade, ausência de duplicidade e recuperação.

Atenção à árvore de código: os experimentos `aion_chat/staged_store.py` e `pinned_snapshot_a183_lab.py` do A183 estão em **PR Draft separada**. Não estão incorporados automaticamente à branch A232/A233. A233 não reivindica integração ou fechamento desses trabalhos.

## Contraexemplos novos executados com SQLite real

| Cenário descartável | O que o ensaio observa | Limite que permanece |
|---|---|---|
| RESTORE sob mesmo inode | Cria valor 1, atualiza e confirma 2, fecha a conexão, regrava os bytes anteriores **no mesmo arquivo**; leitura reaberta volta a 1, mesmo caminho/inode | **Não** é prova de ataque ABA com handle ainda aberto nem teste de durabilidade contra queda física. Mostra que conferir caminho/inode ao reabrir não basta |
| WAL e cópia do arquivo principal | Insere linha 1 e faz checkpoint, confirma linha 2 apenas no WAL; cópia simples do `.db` retorna 1, enquanto o arquivo vivo retorna 2 | Perder `-wal`/sidecars dá instantâneo antigo; exige método SQLite-consistente e identidade de origem autenticada |
| SQLite Backup API | `sqlite3.Connection.backup()` preserva as duas linhas no mesmo ensaio; outro teste chama o `SQLiteChatStore.backup_to()` existente | Resultado `BACKUP_VERIFIED` atesta integridade da cópia naquele teste, **não** origem independente, antirollback, handle/VFS ou recuperação operacional |
| COMMIT com ACK perdido | O COMMIT de um registro SQLite real completa; a exceção `TimeoutError` **simulada em seguida** deixa o chamador no estado `UNCERTAIN`, embora o registro exista | Não simula queda de energia ou ACK do provedor. Não permite reenvio automático |

A restituição de bytes no primeiro ensaio ocorre **depois de fechar a conexão** e com WAL desativado. É proposital, para evitar concluir indevidamente que o ensaio provou correspondência de handle em uma VFS viva.

## Inventário de resultados/decisão

- **P0-5: ABERTO.** Necessita vínculo seguro do handle real ao arquivo, ou mudança arquitetural que dispense confiança em um arquivo SQLite vivo sob host comprometível. Reproduções A183 de pathname/ABA e atualizações sob mesmo inode continuam relevantes.
- **P0-6: ABERTO.** Usar `sqlite3.backup()` é mais adequado que copiar `.db` diretamente no modo WAL, mas não valida identidade nativa, durabilidade pós-commit, sidecars, concorrência, backup/restore atômico ou efeito externo.
- **P0 1–4:** inalterados; identidade HUMANO_OWNER, recibo autenticado, primeira intenção real e testemunha H0 externa permanecem necessários.
- O laboratório não altera o código de execução. Nenhuma ação que possa produzir efeitos financeiros é chamada.

## Artefatos e verificação

- `labs/a233_native_sqlite_p0_repro.py`: três funções de diagnóstico com arquivos temporários `TemporaryDirectory` e dataclasses imutáveis com `p0_5_homologated=False` e `p0_6_homologated=False`.
- `labs/test_a233_native_sqlite_p0_repro.py`: **15 testes** com SQLite nativo; inclui exercício real do método `SQLiteChatStore.backup_to`.
- `.github/workflows/aion-a233-native-sqlite-repro-readonly.yml`: Python 3.12 Ubuntu e Windows com ações pinadas; **1.020 testes por SO esperados** (15 novos + 1.005 regressões A202–A232), contagem a confirmar via logs.

**Próxima engenharia necessária:** determinar a fronteira efetiva de confiança e a API nativa suportada para identidade de VFS/FD; se não houver contrato seguro com Python `sqlite3` puro, não prometer o que ela não fornece. Testar restore sob mesmo inode, conexões abertas, WAL/SHM e falhas pós-COMMIT em sandbox com permissão real. Preservar RED real, nunca transformar caracterização em aprovação.

**HARD NO-GO · P0 0/6 · `UNCERTAIN=ZERO_AUTO_RESEND`. Draft sem merge, deploy ou Worker.**
