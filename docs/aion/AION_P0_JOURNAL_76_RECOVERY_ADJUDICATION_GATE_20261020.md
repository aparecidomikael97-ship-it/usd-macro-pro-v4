# AION P0 — gate de recuperação e adjudicação do Journal (20/10/2026)

**LAB, sem homologação.** HARD NO-GO, 0/6 P0, Worker OFF, ZERO_AUTO_RESEND, sem merge/deploy/fornecedor/custo.

## Fonte, causa original e limites

Checkpoint #1190, comentário [6130979775](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/issues/1190#issuecomment-6130979775): seis incidentes originais = quatro FAIL (HUMAN_OWNER, recibo, Inbox UNKNOWN e H0 após reinício) + dois ERROR do Journal:

- test_lab_journal.JournalTests.test_readback_rejects_forged_content
- test_conservative_journal.ConservativeJournal.test_direct_SQL_still_bypasses_limit_characterization

Ambos faziam UPDATE via Journal.db() público, agora read-only. O caminho #1195 SQLiteChatStore cross-thread e #1281 Saga/Outbox SAVEPOINT **não equivale** aos dois erros Journal originais. Não enfraquecer Journal.db() para satisfazer testes legados.

Baseline LAB original relatado 70 PASS / 4 FAIL / 2 ERROR em 76. LAB posterior com originais 73 PASS / 1 FAIL / 2 ERROR; LAB migrado relatado 75 PASS / 1 FAIL / 0 ERROR, exit 1. São **relatos históricos**, não reexecutados nesta branch.

O dispositivo am12 segue offline na última inspeção. A pasta original relatada é C:/Users/apare/Downloads/AQ_LAB_COMPAT_MIGRATE_20261012. O SHA-256 de SHA256_MANIFEST.json relatado em [6132259470](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/issues/1190#issuecomment-6132259470) é 6ed98d799a8fbf6d985d72b15404463d8115e77b8904a60282fd4e0e1ad2a715; um digest correspondente **não autentica o autor ou a origem externa**. Os dois nomes dos arquivos originais são inferidos dos nomes dos módulos e dependem de conferência no disco.

## Ferramentas (somente depois do acesso autorizado, sem execução de testes recuperados)

- aion_p0_journal_archive_inventory_lab.py: busca 10 artefatos nomeados, calcula SHA-256, sinaliza ausências/duplicatas, compara o manifesto com referência publicada, e sempre mantém as operações bloqueadas. Saídas CLI 2 (faltante/divergente) ou 3 (capturado ainda sem aceitação).
- aion_p0_journal_migration_static_review_lab.py: comparação AST inerte dos nomes e assertions dos dois casos, sem import nem execução de código recuperado; resultado sempre REVIEW_REQUIRED e saída 3.
- Ambos aceitam --root CAMINHO_DA_COPIA_ORIGINAL e imprimem JSON. Gerar relatório fora da pasta original, em local isolado, depois de autorização. Não executar o material diretamente na pasta histórica.

## Oito critérios de aceite sequenciais

1. Capturar **cópia imutável** de fontes originais, migradas, log e manifesto, com hashes e procedência; rejeitar duplicatas até adjudicação manual.
2. Conferir em separado o esquema e as referências internas do manifesto; byte/hash batendo com anotação histórica não basta para provar autenticidade.
3. Revisar AST, diff integral, assertions, imports e contratos; comparação estática não prova comportamento ou segurança.
4. Antes de executar arquivos recuperados, revisar side effects, dependências, credenciais, rede, fixtures e todos os caminhos de escrita; autorizar ensaio hermético com cópia descartável.
5. Reexecutar a bateria **original de 76, sem adulterar os arquivos**, registrar lista dos 76 casos, códigos de saída, hashes pré/pós, logs e versões.
6. Executar os **migrados em base SQLite temporária**, obrigatoriamente mantendo Journal.db() público read-only. Validar injeção negativa, adulteração RAW confinada a testes, H0/rollback e fluxo legítimo.
7. Comparar Windows e Ubuntu e rodar as suites Quality e Security canônicas sem alterar expectativa; manter visíveis os erros de produtor Outbox/Saga.
8. Entregar causa, patch LAB, SHA, prova por caso, contraexemplos, verificação independente, revisão versionada e autorização específica do proprietário antes de qualquer promoção.

## Conclusões proibidas

- Testes positivos do inventário/AST ou correspondência de SHA não equivalem a P0 fechado.
- 75/76 migrados não provam que a origem da falha foi resolvida com segurança.
- Não migrar resultado de testes falsos positivos, nem autorizar recibo self-hash, issuer autodeclarado, retomada H0 sem witness independente, retry automático ou Worker.

**Gate atual: BLOCKED: ORIGINAL_SOURCE_UNAVAILABLE; 0/6 P0; HARD NO-GO.**
