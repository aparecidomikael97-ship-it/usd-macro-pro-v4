# AION P0 — correção de procedência: os dois ERROR originais são do Journal

**20/10/2026 | auditoria forense LAB, sem homologação | HARD NO-GO, 0/6 P0**

## Achado verificado no registro mais antigo e explícito localizado
O [Checkpoint Mestre #1190, comentário 6130979775 (12/10)](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/issues/1190#issuecomment-6130979775) enumera os **SEIS** problemas e diferencia os **4 FAIL** dos **2 ERROR** na bateria local de 76 testes:

1. HUMAN_OWNER: identidade autoafirmada (FAIL).
2. Golden Path: recibo/self-hash fabricado (FAIL).
3. Inbox: primeira inscrição UNKNOWN e repetição (FAIL).
4. H0 pós-reinício: ausência de evidência independente distinguindo H0 de UNKNOWN perdido (FAIL).
5. **Compatibilidade A**: `test_lab_journal.JournalTests.test_readback_rejects_forged_content` (**ERROR**).
6. **Compatibilidade B**: `test_conservative_journal.ConservativeJournal.test_direct_SQL_still_bypasses_limit_characterization` (**ERROR**).

**Mecanismo dos dois ERROR originais:** testes antigos provocavam uma alteração SQL `UPDATE` através do `Journal.db()` público. A API passou a ser **somente leitura** por defesa; assim os testes que exigiam UPDATE via essa interface ficaram incompatíveis. Uma correção que reabilite escrita pública para satisfazer os testes é insegura.

[Comentário 6132259470](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/issues/1190#issuecomment-6132259470) registra em laboratório local os mesmos 76 testes como 73 PASS / 1 FAIL / 2 ERROR; após copiar e migrar **somente os dois arquivos de teste** para injetar corrupção deliberada com `sqlite3.connect(db_path)` de fixture isolada, passou a 75 PASS / 1 FAIL / 0 ERROR (EXIT 1). Original histórico **manteve** 2 ERROR. A primeira bateria seis-P0 tinha 70 PASS / 4 FAIL / 2 ERROR (76 no total).

## Correção de taxonomia; NÃO modificação do documento histórico
A matriz feita em 19–20/10 criou os nomes `SQLITE_COMPAT_READ_PATH` e `SQLITE_COMPAT_WRITE_PATH` para dois erros considerados originais, associando candidatos à *SQLiteChatStore* cross-thread e à Saga/Outbox SAVEPOINT. **O registro explícito de 12/10 não sustenta essa equivalência.**

#1195 (rerun chat STAGING) e #1281 (atomicidade local Outbox/Saga) têm correções e testes reais próprios — não são apagados nem dispensados. Mas **não são os dois testes de compatibilidade Journal** citados no contrato original. Ambas as classes P0 precisam permanecer abertas até revisão da origem. Não renomear a matriz canônica nem declarar a origem corrigida por um teste SQLite posterior.

## O que este novo PR realmente testa
- JSON de procedência com comentários primários por ID, seis slots legados, 76 originais, rastreabilidade e ambiguidades explicitadas.
- 20 testes de integridade que impedem contagem duplicada, promoção indevida e equivalência fictícia com os labels READ/WRITE posteriores.
- 12 testes sobre **SQLite efêmero sintético, NÃO o Journal oficial**: conexão `mode=ro` permite leitura e nega UPDATE/INSERT/DELETE; conexão bruta da **fixture de teste** pode adulterar o conteúdo; comparação com o hash esperado detecta a divergência na mesma instância. O teste que consegue adulterar SQLite bruto comprova a superfície de ataque **não eliminada**, não um P0 fechado.
- CI de Ubuntu e Windows somente leitura, sem egress de fornecedor e herdando a suíte LAB anterior.

## Limite de evidência e aceite futuro
A fonte dos dois testes originais `test_lab_journal.py` e `test_conservative_journal.py` e os logs completos da bateria 76 estão em um LAB local relatado em 12/10; **não foram localizados como arquivos do repositório GitHub disponível nesta branch**. Este PR não executa os dois testes originais e não alega possuir hash/byte-identidade deles. Exigir arquivo original + SHA256 + log anterior + revisão independente antes de promover a migração de testes à CI canônica.

Não conceder acesso de escrita à API pública `Journal.db()`; injeção RAW deve ficar confinada a base efêmera de teste, sem uso no produto, e os contraexemplos de SQLite privilegiado e antirollback continuam abertos. A bateria migrada local de 75/76 tampouco satisfaz os outros 4 FAIL.

**Gates inalterados:** Quality canônica anterior 6.562 / 52 FAIL + 34 ERROR, Security A53 RED, 32 Outbox/Saga producer ERROR OPEN_NOT_WAIVED; 0/6 P0 homologados, Worker OFF, ZERO_AUTO_RESEND, HARD NO-GO. Zero merge, deploy, conta externa, chave real, SMS ou custo adicional.

Referências: [#1190 comment 6130912462](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/issues/1190#issuecomment-6130912462), [#1190 comment 6130979775](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/issues/1190#issuecomment-6130979775), [#1190 comment 6132259470](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/issues/1190#issuecomment-6132259470), [#1346](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/issues/1346), #1364.
