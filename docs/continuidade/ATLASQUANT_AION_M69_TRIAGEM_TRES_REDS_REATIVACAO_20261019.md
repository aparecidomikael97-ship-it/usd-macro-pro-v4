# AtlasQuant / AION — M69: triagem dos três RED históricos de reativação no A118

**19/10/2026 · Análise documental de log oficial e fonte pinada.** Não constitui reexecução da suíte histórica. Estado: HARD NO-GO.

## Evidência primária
- [Quality histórico A118 #38919546692](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/38919546692), job `117035600199`, em 16/10/2026: **6562 testes, 50 FAIL / 34 ERROR**; desses, **1 FAIL e 2 ERROR** são de reativação.
- Fonte original testada: `test_atlasquant_aion_global_worker_reactivation_gate.py`, blob `6c66e11b4c29b2bef1ff277a0c47740cdb0bf220`.
- Origem da negação: `prepare_global_worker_activation_plan` no módulo original de A118 (blob `df43bb4371c784396069f4ede51205b0aa19cc0a`). Depois de checagem estrutural e gate positivo, retorna `BLOCKED` / `INDEPENDENT_ACTIVATION_AUTHORITY_NOT_ENROLLED`, sem chave `plan`.
- Contraprova direcionada posterior M68: [run #39262461789](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39262461789): 2/2 novos negativos Ubuntu e 2/2 Windows; NÃO altera o histórico RED.

## Diagnóstico individual com origem exata do log
1. **FAIL — test_activation_plan_binds_green_post_incident_gate:** linha 439 do teste legado compara `result["status"]` com `ACTIVATION_PLAN_READY`. O original retornou `BLOCKED`, gerando `AssertionError: 'BLOCKED' != 'ACTIVATION_PLAN_READY'`. Leitura: expectativa legada de criação de plano é incompatível com o guard posterior contra autoridade local.
2. **ERROR — test_final_activation_execution_requires_fresh_gate:** linha 469 tenta `plan_result["plan"]` após a negação obrigatória do plano; `KeyError: 'plan'`. **A execução do cenário legado parou antes de chegar à validação final**; ele NÃO fornece evidência do comportamento posterior da função.
3. **ERROR — test_execution_validation_rejects_reopened_gate:** linha 517 também acessa `plan_result["plan"]`, resultando em `KeyError: 'plan'`. O cenário legado NÃO chegou ao validador que pretendia testar.

Os três são resultados da fonte original; M69 não corrige, silencia nem reclassifica o CI histórico como verde.

## Encaminhamento permitido
- Manter íntegros os três registros anteriores e os módulos de negação.
- Elaborar migração explícita da suíte histórica, com rastreabilidade caso a caso. Separar **teste da fronteira de autoridade** (plano obrigatoriamente bloqueado) de **teste puro do gate final** (entrada sintética apenas no validador, jamais emitindo ticket real).
- Não forçar um `plan`, não fabricar F1/T1, não editar guard, não retirar casos e não transformar falhas em `xfail` para mascarar Quality.
- Só depois de revisão independente considerar mudança controlada de expectativas legadas. Nunca alterar logs antigos.
- Priorizar ainda os seis P0; o escopo M68/M69 NÃO prova autenticidade de autoridade externa, recibos, replay incerto, H0 restart, SQLite nem disponibilidade do Worker.

## Invariantes
0/6 P0 homologados; Worker OFF; sem merge, deploy, produção, matrículas externas, reenvio automático ou gasto novo; **HARD NO-GO**.
