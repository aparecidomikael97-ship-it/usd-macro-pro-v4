# A190 G5 — evidência real de processos mortos antes/depois de COMMIT

**Data local de referência:** 2026-10-23. **Missão:** #1486; PR Draft #1492, empilhada sobre G4 #1491.

## CI e proveniência

- **Run GitHub Actions #40046495275:** https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40046495275
- **Estado real:** completed/success; ambos jobs individualmente verificados com logs e SHA do checkout.
- **SHA exato testado:** 101c0ff5c978ff6fbe4fd8621e260206783e4268. Um commit posterior apenas documental não representa uma reexecução de código.
- **Ubuntu job #120729315467:** SUCCESS, 30 tests in 1.935s, OK.
- **Windows job #120729315223:** SUCCESS, 30 tests in 4.473s, OK.
- Composição por runner: 5 G5 + 5 G4 + 6 G3 + 10 A189 + 4 A185 = **30 testes**; nos dois SO, **60 execuções**.
- Python 3.12, arquivos temporários, SQLite WAL real, subprocesso PID distinto do pai, barreira no ponto real antes/depois de COMMIT. Nenhuma chamada externa.

## Provas selecionadas por marcador dos dois logs

| Marcador do G5 | Ambos SO | Significado exato |
| --- | --- | --- |
| A190_G5_REAL_PROCESS_KILL_BEFORE_COMMIT=ROLLED_BACK_AFTER_REOPEN | PASS | Filho foi morto com transação aberta sem COMMIT; novo processo conta 0 |
| A190_G5_PRECOMMIT_NO_ACK=UNCERTAIN_NO_AUTO_RESEND | PASS | Política do harness do pai não autoriza retry após ausência de ACK |
| A190_G5_REAL_PROCESS_KILL_AFTER_COMMIT=ROW_SURVIVES_REOPEN | PASS | Filho fez COMMIT, morreu antes de ACK e processo novo encontrou registro |
| A190_G5_POSTCOMMIT_MISSING_ACK=UNCERTAIN_NO_AUTO_RESEND | PASS | Mesmo com row local, efeito externo continua indeterminado |
| A190_G5_HOST_ROLLBACK_AFTER_REAL_PROCESS_CRASH=UNSAFE_READMISSION_RED | PASS = **RED** | Após comprovar row1, o host restaurou snapshot antigo e removiu seus sidecars locais: row0 e mesmo identificador volta a poder ser reservado |
| A190_G5_REAL_CRASH_THEN_RELABELED_ID=DOUBLE_LOCAL_RESERVATION_RED | PASS = **RED** | Mesmo ID é rejeitado; evento relabelled e mesmo conteúdo semântico recebem outra reserva |
| A190_G5_AION_STORE_REAL_CHILD_KILL_AFTER_COMMIT=REOPEN_SEES_CONVERSATION | PASS | SQLiteChatStore real guardou conversa artificial; novo store reaberto a encontrou |
| A190_G5_AION_STORE_NO_ACK=NO_PROVIDER_CONFIRMATION | PASS | Nenhum recibo ou operação de fornecedor foi emitido |
| A190_G5_REAL_PROCESS_INTERRUPTION=EXERCISED_BEFORE_AND_AFTER_COMMIT | Observado | Etapa CI completa garantiu que todos os marcadores e testes rodaram |

## Por que isso ainda não resolve H0/P0

1. Matar processo não interrompe energia, kernel, cache de escrita de disco, controlador SSD, sistema de arquivos nem SO. Não foi testado desligamento/reinício H0 real.
2. O harness usa um marcador externo para posicionar o ponto de kill **exatamente no laboratório**; esse marcador é observável pelo teste, mas não existe contrato de ACK/provider independente. O pai marca UNCERTAIN por política sintética e não produz efeitos.
3. O mesmo host ainda consegue restaurar banco e WAL/SHM localmente. O A190 G2 mostrou ainda a possibilidade de o root/admin restaurar piso local. Para antirollback H0 de verdade, é indispensável raiz e sequenciamento monotônico fora do domínio de falha.
4. Repetir mesmo event_id é barrado por UNIQUE; mudar event_id autoalegado repete intenção com o mesmo hash. A G3 já havia demonstrado falha de origem de evento, e o G5 a reproduziu após processo morto.
5. Não há teste de fornecedor com idempotência original, recibo de efeito autenticamente emitido, HUMAN_OWNER real, FIDO2, serviço custodiador externo, revogação de VFS/FD nativo ou recuperação sob WAL/SHM/ABA adversariais de hardware.
6. Quality/Security canônicas não foram reexecutadas no G5, e os cinco external-RED por SO e 43 advisories continuam pendentes — não confundir estes jobs com homologação global.

## Decisão e governança

Próxima necessidade para uma prova de engenharia útil: escolher fonte independente de raiz/evento original e custódia/efeito de fornecedor, incluindo política de retenção, ACLs, custo, H0 offline e verificação do contrato de idempotência. Sem autoridade externa, continuar endurecendo in-process não fecha P0 de antirollback e primeira operação; não declarar o contrário.

**Status invariável:** P0 0/6; HARD NO-GO; UNCERTAIN; ZERO_AUTO_RESEND. Somente LAB Draft; sem merge/main/deploy/Worker, fornecedor ou cliente real, segredos, serviço contratado, gasto novo ou operação real.
