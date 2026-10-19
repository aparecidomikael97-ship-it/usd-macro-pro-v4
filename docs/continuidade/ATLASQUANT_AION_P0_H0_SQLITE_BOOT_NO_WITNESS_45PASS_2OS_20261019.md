# Checkpoint Mestre — AION P0 H0: observação SQLite real no boot, 45 PASS/OS, custódia externa ainda AUSENTE

**Data:** 19/10/2026. **Veredito:** GO-LAB de diagnóstico somente leitura. **0/6 P0 HOMOLOGADOS; HARD NO-GO; Worker OFF; ZERO_AUTO_RESEND; sem merge, deploy, gasto, credencial, inscrição de testemunha, SMS ou execução externa.**

## Sequência verificada e objetivo

Anteriormente a API oficial de `SQLiteChatStore.restore_from_backup` recebeu bloqueio explícito para bases de execução quando não há witness externo, com [82 PASS/OS](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39322051809). Mesmo assim o proprietário do host pode substituir um arquivo SQLite por um snapshot anterior via sistema operacional, fora da API. Após rollback manual o arquivo antigo pode exibir um `PENDING` íntegro e apagar `UNCERTAIN` posterior. Sem um high-water de custódia realmente independente, não existe teste somente local que prove que isso não aconteceu.

## Implementação em LAB (sem modificação da aplicação operacional)
- Branch `lab/aion-p0-h0-boot-first-effect-readonly-20261019`, base `543a47e0d3a897a6a5a6903826d6255307d18d37` (última correção SQLite de restore).
- `atlasquant_aion_p0_h0_sqlite_startup_observer_lab.py`, commit inicial `6c136d458c7d8acb32a268c990f8e051ea8e99d0`, revisão de fechamento SQLite Windows `0b10d488baf20310b224fa636241bb46f518ced8`. Diagnóstico REAL de arquivo SQLite pela URI `mode=ro` e `PRAGMA query_only=ON`; inspeciona `quick_check(1)`, presença do esquema operacional, contagens agrupadas de estados da tabela `action_outbox`, erros de abertura e caminhos não regulares. Emite relatório agregado sem segredos/PII, **nunca `READY`**.
- `test_aion_p0_h0_sqlite_startup_observer_lab.py`: **16 casos novos** (manual restore intencional, falso witness, objeto hostil, CLI, no DB, DB corrompido, PENDING, UNCERTAIN, BLOCKED_PRODUCER, estado desconhecido, schema parcial, budget-only, hash local). Primeiro commit `2cac8a82ec336889552503c2fa450d5d53e09606`; correção de fixture de contexto Windows `ceb91fbd130bdb078385e207b790525f0122019f`; correção adicional de validade de intenção do fixture `016e0f23a1c1b929139859e234fdd0df60b87ce5`. Nenhum assert de que testemunha externa existe foi inserido.
- Workflow `.github/workflows/aion-p0-h0-sqlite-startup-observer-lab.yml`, commit `b17a5254577299652e2b30cdb21222f8aba49755`, permissões `contents:read`, runners Ubuntu/Windows. Pina blobs A118 store original, SQLite restore LAB, Outbox LAB e Global Worker readiness original.
- Documento completo de escopo/contrato de custódia e limites em `docs/aion/AION_P0_H0_LOCAL_BOOT_SQLITE_DIAGNOSTIC_NO_EXTERNAL_WITNESS_20261019.md`, commit `437ed74011f570d8d77587e676fa57292dd9bc4e`.

## Histórico RED de testes (não alegar RED da aplicação)

Primeira execução [Actions #39323827122](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39323827122) falhou nos nove casos que usavam o Outbox porque o fixture enviou `valid_until=NOW+1h`, ultrapassando o máximo seguro de validade do **próprio Outbox**. É um erro do **teste**, não um defeito de produto. Foi corrigido para `NOW+5min` no commit `016e0f23a1c1b929139859e234fdd0df60b87ce5`. Não esconder esse histórico nem usar a palavra RED→GREEN para correção de código de produto: o novo diagnóstico nunca concedeu autoridade.

## GREEN de validação (logs inspecionados)

[**Actions #39323959715**](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39323959715): `completed/success`, head `016e0f23a1c1b929139859e234fdd0df60b87ce5`.
- Ubuntu job `118304876518`: **16** H0 locais + **13** restore hardstop + **8** original SQLite/restore + **5** A73 testemunha indisponível + **3** A79 causal no-effect = **45/45 PASS**.
- Windows job `118304876061`: mesmas contagens, **45/45 PASS**.
- **45 casos distintos, 90 execuções aprovadas.** Workflow confirma `H0_PREVIOUS_BARRIERS_PINNED`.
- Nunca foi executado banco operacional do usuário, backup real, Worker, provedor, envio, chamada à API de mídia/empresa, nem ação fora de GitHub LAB.

## Evidência concreta mais importante

Em teste local sintético:
1. SQLite real contém Outbox `PENDING`; backup é criado.
2. SQL *somente de fixture* marca estado `UNCERTAIN`, que a leitura diagnóstica observa.
3. O banco é fechado e o backup anterior é copiado por `shutil.copyfile` **diretamente**, contornando a API protegida (simulação do restore manual).
4. O Outbox original LAB volta a observar `PENDING`. A leitura H0 observa o banco válido e PENDING, mas continua com `state=BLOCKED`, `independent_witness_authenticated=false`, `external_highwater_compared=false`, `local_rollback_detected=false` e **`local_rollback_ruled_out=false`**. Sem comparação independente, NÃO se pode afirmar que detectou rollback nem que atestou integridade histórica.
5. O CLI `python -B atlasquant_aion_p0_h0_sqlite_startup_observer_lab.py path.sqlite3` sempre emite diagnóstico agregado em JSON e sai com **código 2**, não 0; chamadas automáticas precisam interpretar como NO-GO. O `_caller_witness_claim` não é sequer inspecionado, inclusive objetos `__bool__` hostis. Não há qualquer formato de claim local que libere a execução.

## Status da integração e limites CRÍTICOS

1. O módulo H0 é **diagnóstico independente em branch LAB**. **NÃO** está conectado ao boot operacional, `ExecutionOutbox.claim_next`, `dispatch_claimed` ou ao Worker; por si só não fornece uma barreira técnica obrigatória contra outro caminho que o ignore. O hardstop pré-adaptador já presente no Outbox A118 e a trava F1/T1 do Global Worker continuam separadamente ativos no LAB.
2. O caso de rollback manual confirma um limite fundamental: DB antigo restaurado pode ser perfeitamente íntegro, logo `PRAGMA quick_check=ok`, contagem e hash local NÃO são prova de estado mais recente.
3. **Não existe custodiante/serviço externo realmente enrolado**; não há assinatura de testemunha independente verificada, CAS monotônico fora do domínio de backup, alta-water externa atestada, nonce consumido, matrícula de issuer/chave ou recibo terminal do fornecedor. Não contar nenhum P0 como concluído.
4. A conexão em modo readonly não envia SQL de escrita. Entretanto SQLite WAL pode exigir/administrar `-shm` e auxiliares; não é atestado de imutabilidade física ou ausência de toda alteração de filesystem.
5. Faltam crash elétrico/reboot Windows real, Windows Hello real, provedor de recibos, CPF/identidade do proprietário comprovada, H0 H1 recuperação, red team Quality/Security completo, M71 stale READY e auditoria externa. A maturidade ainda é HARD NO-GO.

## Próxima decisão técnica de maior valor

Não inflar mocks para parecer que o P0 foi encerrado. Antes de ligar um guard H0 obrigatoriamente ao primeiro efeito, definir o **custodiante independente**: conta/identidade separada com key enrollment autenticado, epoch+sequence CAS linearizável e durável fora de snapshots do executor, vínculo owner/tenant/host/intent, nonce/fence terminal, indisponibilidade que bloqueia e auditoria independente. Qualquer serviço com custo, permissão de GitHub externa, ativação de Worker, credencial ou ação real exige aprovação explícita do proprietário.

**Conclusão:** observação H0 real em SQLite validada nos dois SO, nenhuma prova externa de antirollback produzida, nenhum P0 homologado; HARD NO-GO preservado.
