# A234 — correção parcial real: restauração SQLite não sobrescreve o banco existente

**Escopo:** código de armazenamento de **staging** em branch **Draft**, testado exclusivamente com bases descartáveis. **HARD NO-GO · P0 0/6 · `UNCERTAIN=ZERO_AUTO_RESEND`.** Nenhuma alteração direta de produção, Worker, provedor, assinatura, custódia externa, pagamento ou infraestrutura.

## Contraprova antes da correção (SQLite nativo)

No Linux, criar duas bases `source=1` e `target=2`, manter uma conexão ao target aberta e executar `os.replace(source, target)` permite que **a conexão antiga continue lendo 2**, enquanto **a conexão nova leia 1** no mesmo pathname. Dois arquivos nativos distintos ficam associados a conexões que parecem tratar do mesmo caminho. No Windows, a substituição pode falhar por lock; esse bloqueio circunstancial não comprova segurança universal.

No código anterior de `aion_chat/store.py`, `SQLiteChatStore.restore_from_backup` executava exatamente `os.replace(temp, target)` após validação do backup. Um teste do A233 já demonstrou rollback no mesmo inode depois de fechar a conexão, e a investigação A183 reproduziu ABA mais forte. **Não podemos afirmar que conferir somente pathname resolve P0-5.**

## Alteração nesta Draft

1. Mantém a validação de integridade SQLite do arquivo de origem e a cópia `sqlite3.Connection.backup` para um arquivo temporário no mesmo diretório do destino.
2. **Recusa desde o início** destino já existente: arquivo, diretório, symlink ainda que quebrado; e recusa qualquer presença dos sidecars `-wal`, `-shm` e `-journal` daquele caminho.
3. Antes da publicação faz novo veto a destino ou sidecars que apareceram.
4. **Não usa mais `os.replace` na restauração.** Publica por `os.link(temp, target)`: a criação é atômica e falha se alguém criou o pathname do destino entre a inspeção e a publicação. O temporário é removido depois. Se o sistema de arquivos não suporta hardlink, **nega** a operação; não faz fallback de cópia parcial.
5. Mantém a recusa em erro e limpeza de temporário. Um novo restore para destino já preenchido é recusado, sem apagar o arquivo existente.

Este é um **enrijecimento da API**, não autenticação de host/arquivo. Não há lock externo de sidecars, proteção contra um atacante administrador que remova/troque a raiz de diretórios ou os links, nem prova de que outro processo não possui handle antigo de arquivo apagado. `os.link` sozinho não fornece `fsync` do diretório contra perda de energia, comprovação de sequência monotônica, custódia externa, validação de identidade VFS nem garantia de durabilidade H0.

### Comportamento intencionalmente incompatível

Uma restauração anteriormente permitida que **sobrescrevia um banco existente** agora deve falhar. A recuperação segura de um banco em uso deve ocorrer por um protocolo futuro de parada, revogação de handles, isolamento de serviço, seleção de raiz independente, migração e reconciliação — **não** por substituição silenciosa do arquivo.

## Ensaios A234

`labs/test_a234_sqlite_restore_create_only.py` possui **20 novos casos** com SQLite nativo, inclusive:
- Recusa de alvo existente aberto, sem alteração da leitura antiga nem nova;
- Destino inexistente que aceita exatamente uma publicação; segunda tentativa negada;
- Recusa de sidecars isolados, banco corrompido, diretório e arquivo vazio;
- Corrida de dois chamadores tentando publicar o mesmo caminho, com só um sucesso;
- Corrida injetada **no instante de `os.link`**: o arquivo que apareceu permanece intocado;
- Falha fechada quando a plataforma não aceita `os.link`;
- Exercício de `restore_verified_staging_backup` e do `backup_to` reais do staging.

Workflow `.github/workflows/aion-a234-sqlite-restore-create-only.yml`: Python 3.12 em Ubuntu e Windows, com ações pinadas, 20 casos novos, mais regressões A202–A233 e `test_atlasquant_aion_chat_staged_runtime_resilience`. A contagem final será confirmada nos logs, sem declarar vitória por suposição.

**P0-5 (read/native VFS) e P0-6 (write/commit) continuam ABERTOS**, assim como P0-1/2/3/4. A234 corrige apenas um caminho destrutivo de restauração no staging; não estabelece segurança de sistemas de efeitos reais. Nenhuma alteração entra na `main` sem nova análise e homologação.
