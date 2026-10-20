# AION P0 — revisão A53/A76: plano estruturalmente READY ≠ permissão de execução

**20/10/2026 · Auditoria LAB, não uma homologação.**  
**HARD NO-GO · 0/6 P0 · Worker OFF · ZERO_AUTO_RESEND.**

## Evidência canônica existente (não alterada)

A [Quality completa #39430873102](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39430873102) reexecutou **562 módulos / 6.562 testes**, retornando **52 FAIL + 34 ERROR** em vez de 51 +34 no baseline anterior. A diferença de um caso foi identificada nominalmente em [issue #1355](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/issues/1355): `test_atlasquant_aion_activation_denial_coverage_a76.A76ActivationDenialCoverage.test_gate_green`. A asserção histórica `self.assertEqual(e["state"], "READY")` na linha 223 recebe **`BLOCKED`**. O arquivo de testes A76 e `atlasquant_aion_global_worker_activation.py` conservam seus blobs Git entre os snapshots, enquanto `atlasquant_aion_global_worker_reactivation_gate.py` mudou para exigir **fonte externa independente e fresca**. Os 32 ERROR de produtor Outbox/Saga seguem no mesmo conjunto de 86 ocorrências e continuam `OPEN_NOT_WAIVED`.

No [Security canônico #39430166808](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39430166808), o teste A53 `test_a53_local_ticket_cannot_authorize_injected_activation_writer` falha antes de chegar ao writer: a fixture chama `approval()` → `plan()` e exige `ACTIVATION_PLAN_READY`, porém a implementação respondeu `BLOCKED`. **Nenhum acionamento de writer foi demonstrado**. O job adversarial termina vermelho, enquanto os jobs A54 Windows efêmero e auditoria de cadeia de suprimentos passaram. Não declarar Security 365 verde/completamente executada.

## O ponto técnico que muda a decisão

Existe uma distinção que os testes legados positivos não expressavam completamente:

1. **Plano / validade estrutural**: `validate_reactivation_gate_for_plan` pode reconhecer como `READY` um gate de dados localmente íntegro, com digest, TTL e ledger coerentes. Esse `READY` é *formato/planejamento*, NÃO autorização de ativar o Worker.
2. **Admissão imediatamente antes de executar**: `validate_reactivation_gate_for_execution` retorna `BLOCKED`, razão `FRESH_INDEPENDENT_INCIDENT_SOURCE_NOT_ENROLLED`, **até para o gate com `gate_integrity=MATCH`**. Um digest local, um checkpoint e um ticket antigo não verificam se um incidente foi reaberto em outro domínio.
3. **Plano/approval do Global Worker**: `prepare_global_worker_activation_plan` retorna `BLOCKED: INDEPENDENT_ACTIVATION_AUTHORITY_NOT_ENROLLED` para as fixtures históricas A53, pois a fonte de autoridade independente também não está matriculada.
4. **Não rebaixar a proteção:** mexer em `validate_reactivation_gate_for_execution` para devolver `READY` sem testemunha externa poderia transformar uma divergência de teste em passagem de autoridade não comprovada. Qualquer revisão futura da asserção legada A76/A53 requer um revisor técnico independente, proveniência histórica, preservação dos casos RED e Quality/Security canônicas novas. Nem `skip`, `xfail`, alteração de default, bypass de fixture ou política de exclusão resolvem a lacuna.

## Novos 12 testes adversariais LAB

`tests/test_aion_p0_a53_a76_legacy_ready_mismatch_lab.py` avalia: negação de plano A53, negação de execução com gate **não requerido** e com gate **requerido+íntegro**, separação entre `READY` do plano e `BLOCKED` da execução, booleans falsos/verdadeiros autoafirmados, ticket local com digest compatível, validação de aprovação sem abrir writer, estabilidade/replay, campos de falso `external_authority_verified` e imutabilidade de inputs. Dois últimos casos conferem as asserções originais e flags de não execução; **nenhum caso escreve em repositório/provedor nem ativa Worker**.

A CI read-only Ubuntu+Windows executa os 12 novos testes e os originais A74/M71 de negação, mais regressões SQLite/Saga. Um PASS nesse LAB só confirma que **o contrato mais estrito continua fail-closed** — os dois testes históricos positivos A53/A76 **continuam RED, sem waiver**.

## Próximo gate externo real (não autorizado neste LAB)

Um `READY` de execução exige identidade do emissor externo, challenge/nonce autenticado, epoch monotônico e observação fresca de incidentes que sobreviva ao rollback/restauração do processo AION, além de autorização do HUMAN_OWNER e compromisso causal com a primeira tentativa. Nada disso foi provido por este PR; uma instalação AWS, envio de SMS ou credencial produtiva exige decisão posterior e não deve ser presumida.

**Status permanece:** Quality 52 FAIL +34 ERROR (**86 ocorrências**), 32 Outbox/Saga `OPEN_NOT_WAIVED`, Security Gate RED em A53, 0/6 P0 homologados, HARD NO-GO, Worker OFF, ZERO_AUTO_RESEND. Sem merge/deploy/contratação/gasto.
