# AtlasQuant / AION — G56: matriz de falhas na reconfirmação estrita

**Data:** 2026-10-25. **Branch:** `lab/aion-a190-g56-strict-confirm-transaction-faults-20261025`. **PR Draft:** [#1542](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1542), base G55 LAB, **não main**.

## Recorte e integridade do relato

A G56 **não altera** o motor `atlasquant_aion_execution_outbox.py`. Ela cria uma regressão de oito testes sobre `_confirm()` com `strict_projection_lab=True`, combinando injeções G31/G33/G35 já existentes e SQLite descartável. São evidências de comportamento **local simulado**, sem assinatura externa autêntica, fornecedor, cliente, Worker, envio financeiro ou homologação P0.

## Revisão independente do Codex

Codex CLI Windows 0.164.0-alpha.11.1 em `-s read-only --ephemeral`, sessão `01a17401-0e3b-7632-aa1a-d50414320d8c`, inspecionou `_begin_or_quarantine`, `_commit_or_quarantine`, `_rollback_preserving_original`, `_confirm`, e os testes de falha das G31, G33, G34, G35 e G55. Não editou nem executou testes. Observou que os casos gerais de COMMIT/BEGIN/rollback já tinham cobertura, mas **suas combinações com a reconfirmação G55** não haviam sido verificadas nesse conjunto.

## Cenários de G56 — executados no Windows, 8/8 PASS

Arquivo `labs/a190/test_g56_strict_reconfirm_transaction_faults_lab.py`, commit `0308cb908c38162e60c57be84c5660aa572f23b0`:
1. Reconfirmação íntegra é somente leitura; não altera `confirmed_at`, projeção ou ledger.
2. COMMIT falha antes da durabilidade: exceção original, zero rollback, quarentena e nenhum reenvio.
3. COMMIT efetivado e ACK perdido: **mesma exceção**, zero rollback, quarentena; após reabertura explícita, exatamente um recibo local com timestamp original.
4. BEGIN falha antes de adquirir lock: nenhuma inferência sobre efeito externo, nenhuma tentativa adicional, quarentena.
5. BEGIN chega a adquirir lock, mas ACK é perdido: quarentena sem rollback supostamente seguro, snapshot do disco preservado após fechamento.
6. Projeção G55 adulterada causa erro primário; injeção de falha secundária de rollback preserva o `RuntimeError` G55, encadeia `OSError` e quarentena ambos os handles.
7. Mesmo erro com rollback bem-sucedido preserva o dado bruto adulterado para investigação sem reparo implícito e deixa o banco saudável.
8. Reabertura após COMMIT ambíguo não habilita callbacks/provedor; mantém `unsafe_allow_synthetic_lab_callbacks=False`.

## Bateria de regressão e CI

Workflow `.github/workflows/aion-a190-g56-strict-reconfirm-transaction-faults-lab.yml` foi commitado em `56a318bebc65918f91c8ec7f6e6c49aca95dcefb`, com matriz Ubuntu/Windows. Exige 8 casos G56 + 483 herdados G55-G30 = **491 casos por sistema**.

- Windows local isolado `C:\Users\apare\AtlasQuant-G56-Faults-LAB-20261025`: **491/491 PASS**, exit code 0, worktree limpo, exato SHA de código/workflow `56a318bebc65918f91c8ec7f6e6c49aca95dcefb`.
- [GitHub Actions run #40214675698](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40214675698): Ubuntu job `121233131862` **SUCCESS** com 491 casos e sete marcadores de proteção G56 confirmados no log.
- No momento inicial deste relatório, o job GitHub Windows `121233131964` ainda estava executando; seu resultado deve ser consultado antes de declarar CI multiplataforma verde. O relatório foi adicionado depois do commit testado e não altera o código executado.

## Limites permanentes e recomendações

- A presença de um único registro após reabertura prova somente o resultado do **cenário de SQLite simulado**, não durabilidade diante de perda física de energia, sobrevivência a rollback do arquivo, custódia externa, primeira tentativa idempotente entre IDs distintos ou recibo autêntico de provedor.
- G56 preserva P0-3 `UNCERTAIN` e `ZERO_AUTO_RESEND`. Não autoriza retentativa/reparação automática.
- Testes extremos com interrupção de `BaseException` após BEGIN e resistência física de H0 são **lacunas separadas** não homologadas.
- Achados históricos do Security/Quality canônico e dependências continuam fora deste CI focado.

**0/6 P0 HOMOLOGADOS · HARD NO-GO · UNCERTAIN · ZERO_AUTO_RESEND.** Nenhum merge, deploy, Worker, transação real, gasto ou instalação.
