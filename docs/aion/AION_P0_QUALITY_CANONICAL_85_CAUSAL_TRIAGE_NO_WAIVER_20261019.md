# AION P0 — Triagem causal das 85 ocorrências RED da Quality canônica

**19/10/2026 | SOMENTE LAB | 0/6 P0 homologados | HARD NO-GO | Worker OFF | ZERO_AUTO_RESEND**. Nenhum merge, deploy, ativação, fornecedor, credencial, pagamento ou dispensa de teste.

## Fonte da verdade e método

- Último Quality canônico completo antes desta rodada: [GitHub Actions #39334210568](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39334210568), Ubuntu job `118339499707`, commit `44a4de01817d896e056810025d6c68ec8e34112f`, seleção original de **562 root test files** em `.github/workflows/quality-tests.yml`; executou **6.562 casos, 51 FAIL, 34 ERROR** (sem waivers).
- O arquivo de registro `docs/aion/AION_P0_QUALITY_CANONICAL_85_FAILURES_CASE_REGISTRY_20261019.json` foi extraído **automaticamente dos blocos `FAIL:`/`ERROR:` dos logs completos**. Cada ocorrência contém módulo, **classe de teste, método e contexto de subTest** quando existir, tipo de falha, última exceção e classificação de TRIAGEM INICIAL `OPEN_NOT_WAIVED`.
- São **85 ocorrências**, correspondentes a **83 identificadores completos de testes**: dois métodos de Outbox têm dois subcasos cada, `retryable=True` e `retryable=False`. Por isso os mesmos nomes aparecem em dois erros distintos, e **NÃO** devemos deduplicá-los como se fossem só um.
- O registro não é uma correção de produto; os subcasos foram extraídos por leitura de logs, sem execução de Worker e sem atualização de seleção Quality.

| Módulo | FAIL | ERROR | Evidência de triagem |
|---|---:|---:|---|
| `test_atlasquant_aion_global_worker` | 21 | 0 | Asserções exigem execução, leases, resultados de CAS/recibos que agora encontram `BLOCKED`; revisar individualmente |
| `test_atlasquant_aion_global_worker_activation` | 15 | 0 | Fixtures esperam `ACTIVATION_PLAN_READY`, porém readiness nega sem autoridade externa |
| `test_atlasquant_aion_worker_runtime` | 6 | 0 | Alguns testes esperam trabalho/retentativa local; execução foi negada cedo; avaliar sem liberar global Worker |
| `test_atlasquant_aion_global_worker_live_verification` | 5 | 0 | Evidência ao vivo não confiável retorna `BLOCKED_UNVERIFIED_LIVE_EVIDENCE` |
| `test_atlasquant_aion_global_worker_readiness` | 2 | 0 | Fixtures esperam PASS sem autoridade real |
| `test_atlasquant_aion_global_worker_reactivation_gate` | 1 | 2 | Falha de plano legado e dois `KeyError: 'plan'` derivados da recusa anterior da etapa de plano; **não confundir com replay M71 corrigido no validador final** |
| `test_atlasquant_aion_execution_outbox` | 0 | 23 | `PermissionError: INDEPENDENT_PRODUCER_NOT_ENROLLED`; incluindo duas parametrizações distintas de dois métodos |
| `test_atlasquant_aion_execution_saga` | 0 | 9 | `PermissionError` de `INDEPENDENT_PRODUCER_RECEIPT_NOT_ENROLLED` ou `INDEPENDENT_PRODUCER_NO_EFFECT_FENCE_NOT_ENROLLED` |
| `test_quality_workflow_coverage` | 1 | 0 | Seleção canônica não enumera 15 root files adicionais de LAB nesse snapshot |
| **Total** | **51** | **34** | **85 ocorrências ainda abertas** |

### Raiz da ativação — reproduzida, não deduzida da mensagem

Execução read-only em fixtures existentes `test_atlasquant_aion_global_worker_reactivation_gate` e `test_atlasquant_aion_global_worker_activation` confirmou:
- `_runtime_armed_contract(runtime)`: `READY`.
- `validate_reactivation_gate_for_plan(...)`: `READY` para o gate local íntegro e não expirado.
- `_readiness_contract(readiness)`: **`BLOCKED / INDEPENDENT_ACTIVATION_AUTHORITY_NOT_ENROLLED`**.
- Consequentemente `prepare_global_worker_activation_plan(...)`: `BLOCKED` com o **mesmo motivo**, sem `plan`, sem modificação da flag e sem execução do Worker. Os dois `KeyError: 'plan'` no teste antigo são consequência de o fixture assumir um plano que foi justamente recusado. Isso **não** prova que a proteção seja desnecessária nem permite conceder autorização sintética.
- Para o caso de execução pós-incidente M71, o validador final agora retorna `BLOCKED / FRESH_INDEPENDENT_INCIDENT_SOURCE_NOT_ENROLLED` em LAB (13/13 por SO no [workflow #39335745839](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39335745839)); a fonte real ainda não foi matriculada.
- Os 32 erros de Outbox/Saga estão ligados a *recusa de confiança externa*. Não mudar `PermissionError` para estado de sucesso, ignorar recibos falsos ou desligar guarda para tornar os antigos testes verdes. Para recuperar cobertura de transições profundas será necessário contrato de testes isolado e autorizações externas comprovadas, **sem tocar no dispatch produtivo**.

### Quality coverage — problema separado

O teste `test_every_root_test_file_is_executed_by_quality_workflow` detectou **15 arquivos de LAB** não enumerados na lista histórica do Quality. Muitos possuem CI dedicada; um deles é teste negativo M71 originalmente RED por design. **Incluir cegamente todos no Quality e exigir sucesso pode esconder teste negativo ou gerar falha eterna.** A solução futura precisa classificar explícita e auditavelmente suites PROD vs LAB, exigir execução CI verificável por cada arquivo e tornar inválidas omissões sem entrada de governança; não simplesmente ignorar nomes contendo `lab`. O teste canônico original ficou intocado.

### Segurança canônica e limite de evidência

A Security original selecionada A74/A76 passou **365/365** no mesmo período; não equivale a Quality GREEN nem P0 homologado. As falhas de integração do Worker/Saga/Outbox não podem ser descartadas automaticamente por serem decorrentes de hardstop: seus cenários positivos também abrangem regras de retry, reversão, escopo e persistência ainda sem cobertura end-to-end, logo representam **dívida de homologação**.

## Artefatos verificáveis e política de decisão

- `docs/aion/AION_P0_QUALITY_CANONICAL_85_FAILURES_CASE_REGISTRY_20261019.json`: todos os 85 registros com `OPEN_NOT_WAIVED` e assinatura da origem pela referência de Actions e SHA do código-base.
- `test_aion_p0_quality_85_causal_inventory_lab.py`: auditoria de 12 cenários que valida nomes reais de funções/classes, 85/51/34, quatro subTest contextuais, fornecedor ausente, Quality coverage intacto, M71 BLOQUEADO, razão de readiness exata e ausência de chamada ao writer.
- `.github/workflows/aion-p0-quality-85-causal-inventory-lab.yml`: matriz Windows/Ubuntu com 12 contratos de inventário, 13 do M71 com asserção original e Security canônica 365 (Ubuntu).
- A primeira CI identificou **um erro do próprio inventário**: deduplicava falhas por `module+method` e contava 73 em vez de 85. Corrigido após ler `test_class` e contexto de `unittest.subTest`. Não tratar essa correção da auditoria como defeito do produto.
- Nenhum script usa `xfail`, marca `skip`, remove um teste, altera `.github/workflows/quality-tests.yml`, aciona fornecedor, Worker ou plano positivo de feature flag. A nova suíte PASS não é evidência de que os 85 testes canônicos originais passaram.

## Próximos trabalhos por impacto

1. Preservar `INDEPENDENT_ACTIVATION_AUTHORITY_NOT_ENROLLED` e a nova trava M71 `FRESH_INDEPENDENT_INCIDENT_SOURCE_NOT_ENROLLED` até fonte externa autenticamente matriculada.
2. Transformar o `Quality coverage` em registro auditável por **suíte e workflow individual**, exigindo cada LAB em CI real antes de deixar de ser enumerado em Quality. Não usar padrões genéricos que escondam testes.
3. Triagem dos **32 caminhos Outbox/Saga** por invariantes de segurança: o teste original não alcança mais a lógica interna por bloqueio pré-efeito; projetar regressões de teste isolado com guarda de produtor sempre ativa, sem elevar fixtures locais a prova externa.
4. Analisar 21 casos do Global Worker e seis da execução local sem permitir lease CAS/Worker; identificar os casos que testam apenas retorno positivo não autorizado e os que cobrem riscos ocultos.
5. Os **dois P0 originais de compatibilidade SQLite seguem com IDs/stack traces canônicos não mapeados**; não promovê-los a `CLOSED` por mini-testes locais.
6. Reexecução canônica da Quality integrada só depois de alterações supervisionadas; manter `51 FAIL/34 ERROR` como último baseline completo até evidência em contrário.

**Conclusão: inventário causal e bloqueios rastreados em LAB, nenhum dos seis P0 homologado. HARD NO-GO / Worker OFF / ZERO_AUTO_RESEND.**
