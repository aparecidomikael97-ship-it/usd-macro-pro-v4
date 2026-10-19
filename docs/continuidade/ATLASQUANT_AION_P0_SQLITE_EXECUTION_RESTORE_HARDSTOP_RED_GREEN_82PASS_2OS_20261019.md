# CHECKPOINT MESTRE AION — P0 SQLite: RESTORE DE EXECUÇÃO RECUSADO PELA API, RED→GREEN, 82 PASS × 2 SO

**Data:** 19/10/2026. **Veredito:** GO-LAB restrito ao método oficial de restauração de SQLite. **NENHUM P0 HOMOLOGADO.** HARD NO-GO, 0/6 P0, Worker OFF, ZERO_AUTO_RESEND, nenhum merge, deploy, custo, credencial ou provedor acionado.

## Justificativa factual e origem

A118 original `c62fab663c6349d7320f7843c8d09587c514426b`, `aion_chat/store.py` Git blob `6df8ad55673acaca6eeeb0bc3e3898d7a10b08ba`. Restauração oficial `SQLiteChatStore.restore_from_backup(source,target)` só verificava quick_check, foreign key check e hash; um backup integro, porém antigo, podia apagar `UNCERTAIN` posterior, retornando a `PENDING` e reabrindo claim LOCAL. Isso já havia sido demonstrado com a API ORIGINAL nas rodadas P0 anteriores; nenhum despacho real foi possível (gate de produtor não matriculado).

Branch `lab/aion-p0-sqlite-execution-restore-hardstop-20261019`, derivada do laboratório consolidado `a172c88f67e47d001b804b16808b8648cba3804e`.

## Testes primeiro; erros e correções sem apagar histórico
- `test_aion_p0_sqlite_execution_restore_hardstop_lab.py`: **13 cenários escritos ANTES de qualquer patch**, commit `042d83d8a5e6ffd71bf13934f52e8b8d37636c0c`.
- CI Ubuntu/Windows `.github/workflows/aion-p0-sqlite-execution-restore-hardstop-lab.yml`, commit `e89737093f764e8897564b48c886f50682f8ae11`, permissões `contents:read`.
- [**RED original #39321611432**](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39321611432): Ubuntu job `118296797096`, **9 FAIL em 13 testes** (4 PASS), pois restauração aceitava bancos com tabelas Outbox/Saga/Budget ou sobrescrevia destino corrompido e ignorava WAL órfão.
- Patch inicial de `aion_chat/store.py`, commit `0f0ba9f033c2d1e257e542b4bc695a595c680eac`: bloqueio explícito de exec ledger tanto no source quanto target; alvo ilegível/órfão não restaura; validação antes e depois da cópia temporária.
- O histórico `test_aion_p0_original_sqlite_compat_concurrency_restore_lab.py::test_06` passou a exigir *recusa e retenção* de `UNCERTAIN`, em vez de `RESTORE_VERIFIED` da versão insegura; commit `2dafeb7d7d84fa12ccd3ebd1cdd2a3c4754b1951`. O baseline original A118 não foi editado.
- [#39321841939](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39321841939) ainda falhou num cenário chat-only existente por um falso bloqueio de sidecar WAL legítimo. **Não foi escondido nem relaxou o guard de tabelas de execução.**
- Refinamento commit `543a47e0d3a897a6a5a6903826d6255307d18d37`: WAL/SHM órfão sem banco principal é recusado; quando target existe, a consulta SQLite lê seu esquema/estado WAL de forma consistente. Não supõe que mera existência do nome `-wal` prova transação insegura.

## GREEN final auditado

[**GitHub Actions #39322051809**](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39322051809), HEAD `543a47e0d3a897a6a5a6903826d6255307d18d37`, `status=completed`, `conclusion=success`.

- Ubuntu job `118298301131`: **82/82 PASS**.
- Windows job `118298300520`: **82/82 PASS**.
- Matriz por SO: **13** novos restore source/target hardstop + **8** concorrência/restore A118 (expectativa de recusa atualizada em LAB) + **3** histórico de backup/restauração chat-only/corrupção + **4** A110 efeitos ambíguos + **27** SQLiteChatStore/Outbox thread + **27** Saga/Budget thread = **82 casos distintos, 164 execuções PASS**.
- Pin CI confirmado: `aion_chat/store.py` A118 blob original `6df8ad55673acaca6eeeb0bc3e3898d7a10b08ba`; Outbox LAB blob `cd78ed43ad63888408eb599e28379c193c541de2`. A proteção de envio A118 não foi afrouxada.
- Documento do LAB `docs/aion/AION_P0_SQLITE_EXECUTION_RESTORE_HARDSTOP_LAB_20261019.md`, commit `c772f4dcd9b9710e10958ef0aacac6708a602c8c`.

## O que foi realmente corrigido em LAB

- A **API oficial** `SQLiteChatStore.restore_from_backup` nega restauração sem witness independente se a fonte OU o destino contiver alguma das tabelas de execução conhecidas (`action_decisions`, `action_outbox`, `action_effects`, `aion_authority_spend`, `aion_execution_sagas`, `aion_execution_saga_steps`, `aion_execution_saga_events`), mesmo vazias; erro `StorageUnavailableError("P0_EXECUTION_RESTORE_REQUIRES_INDEPENDENT_WITNESS")`. Nenhum override para contornar.
- Preserva target com `UNCERTAIN`; não substitui alvo corrompido ou com WAL órfão. Chat-only segue restaurável a new path ou sobre chat-only, como comprovado.
- Conserva checagem de integridade e revalida staging copy antes de `os.replace`. Não se emitiu autoridade, não se consultou fornecedor, nenhuma operação externa, Worker OFF.

## CRÍTICO — O que permanece aberto; NÃO declarar P0 encerrado

1. **Manual/externo ainda contorna:** copiar, reimaging, restaurar snapshot da VM/disco, manipular volume, substituir DB fora do `restore_from_backup`, ou restaurar backup na máquina/host ainda pode apagar `UNCERTAIN` e reabrir claim LOCAL. Sem witness assinado e monotônico sob custódia FORA do rollback domain, a prova de atualidade é impossível para a base isolada.
2. Inspeção usa nomes exatos das tabelas de execução A118 conhecidas, não detecta tabelas renomeadas, novos esquemas, forks, ocultação maliciosa; um adversário que controle banco e fontes pode tentar contornar. A detecção não é prova externa de veracidade.
3. Checagem de source e target antes de `os.replace` não é CAS atômico contra processo paralelo que escreva no destino; TOCTOU de restore continua por arquitetar. A prova robusta requer bloqueio de startup e sincronização comprovável.
4. Chat-only restore pode perder mensagens mais recentes por definição de snapshot. Não é restauração sem perda, nem rollback sem risco de privacidade/retention.
5. Sem testes físicos de blackout, fsync de storage real, reboot H0, multi-host, credenciais HUMAN_OWNER, produtor com recibo autenticado, reconciliação external-fence, RED M71, Quality/Security integrais ou auditoria independente.
6. A correção está em branch LAB. **Nenhum merge/deploy** autorizado nem executado. Seis P0 e HARD NO-GO inalterados.

## Próxima prioridade por impacto
Implementar/testar em LAB um **gate de inicialização e de primeira intenção que exige prova de high-water externa** (identidade do witness fora da conta/host/backup, epoch+sequence CAS, vínculo a owner/tenant/host/intenção, revogação e testemunho assinado). Esse gate deverá negar ao ficar indisponível ou retornar replay/epoch inferior; sem custódia real não atribuir `verified=true` a entradas locais. Apenas depois, testar contra restore manual e retomar P0. Evitar aumentar contadores artificiais de mocks sem evidência externa.

**Estado final: 0/6 homologados, HARD NO-GO, ZERO_AUTO_RESEND, Worker OFF, sem gastos.**
