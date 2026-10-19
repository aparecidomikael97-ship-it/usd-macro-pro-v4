# Checkpoint Mestre — AION P0 Quality 85 FAIL/ERROR: inventário causal SEM waiver, 12+13 PASS por OS

**Data 19/10/2026. Veredito: GO-LAB APENAS PARA TRIAGEM DE EVIDÊNCIA. 0/6 P0 HOMOLOGADOS. HARD NO-GO. Worker OFF. ZERO_AUTO_RESEND.** Nenhum merge, deploy, Writer, execução externa, Cloudflare/AWS, gasto novo, credencial ou contratação.

## Por que esta rodada foi priorizada

O último checkpoint confirmou RED da Quality canônica: 6.562 testes, 51 FAIL + 34 ERROR, e M71 corrigido somente no validador LAB (13 PASS por sistema), além dos seis P0 canônicos ainda sem homologação. Nesta rodada a prioridade foi **triar cada uma das 85 ocorrências RED sem quebrar hardstops legítimos**. O trabalho é de evidência/contrato, não altera produção nem a lista da Quality.

### Fonte real das 85 ocorrências

[Actions #39334210568](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39334210568), Ubuntu job `118339499707`, HEAD `44a4de01817d896e056810025d6c68ec8e34112f`. A seleção extraída de `.github/workflows/quality-tests.yml` continha 562 root test files; 6.562 casos executados, **51 FAIL / 34 ERROR**, sem `xfail` ou exclusões. O baseline novo NÃO foi reexecutado neste ramo e continua RED. A Security canônica dessa seleção A74/A76 tem 365/365 PASS em rodadas anteriores e na rodada presente, mas NÃO supera a Quality.

## Inventário com contexto de parametrização (sem falsa deduplicação)

Branch LAB isolada `lab/aion-p0-quality-85-causal-triage-20261019`, originada de `25ea40d30c2873b915340116782bad008328fd3a` (registro M71 corrigido).

Artefatos verificados por fetch Git:
- `docs/aion/AION_P0_QUALITY_CANONICAL_85_FAILURES_CASE_REGISTRY_20261019.json`, commit inicial `e2db6d484c243c906c21f43ae503ef45ad648535` e revisão `392a75749cce51d31f3202ded0c076448a62e675`, blob **`6116ec66054b4610455574eae77d9be60ffe436d`**. JSON 39.478 bytes contém as **85 ocorrências identificadas por module + test_class + test method + subtest_context**, tipo FAIL/ERROR, última exceção extraída dos logs, triage_group e `OPEN_NOT_WAIVED` para TODOS. São **83 identificadores completos de teste**, mas duas funções de Outbox têm dois subcasos `retryable=True/False` cada, somando 85 ocorrências. Nunca reduzir 85 para 73 deduplicando módulo+método ou para 83 ignorando subTest.
- `test_aion_p0_quality_85_causal_inventory_lab.py`, commits `1b4681c968e1dc30b7572d81af395871052a2560`, correção de identidade do subTest `37574db24d6d7b66da79dee588fcad639cae16bc`, pinagem de causa exata `aa06dc069d44e3df0b3467a16e020554599f5901`, blob **`47e5694eed917ef2085fbf6f96c0771e59e0e825`**. **12 testes** auditam registros contra funções reais no checkout, total 85/51/34, 4 subcasos, 32 erros de produtor, red M71 histórico, red coverage, fonte da recusa de ativação, e ausência de chamada a writer com approval inválido.
- `.github/workflows/aion-p0-quality-85-causal-inventory-lab.yml`, commit `ccba4b0b509e77d441494a1ab12c96e855af2e0f`, blob **`b07142bc8e729963f6e2a86503306c23d7e3f37f`**, Ubuntu+Windows 12+13 contratos, Security 365 em Ubuntu; CI com `contents: read` e pinos Git do M71, Global Worker, Outbox e Activation.
- `docs/aion/AION_P0_QUALITY_CANONICAL_85_CAUSAL_TRIAGE_NO_WAIVER_20261019.md`, commit `985a1b6c14f0f0c8de14c51a376c811eb5efe6c7`, blob **`335f62a99d5b3f1e5b62b0e9e9a20df9b55ae784`**, triagem e prioridades caso a caso.

| Arquivo de teste original | FAIL | ERROR | Causa/sinal observado |
|---|---:|---:|---|
| `test_atlasquant_aion_global_worker` | 21 | 0 | fixtures antigas esperam processamento de lease/retorno positivo, código bloqueia sem testemunha |
| `test_atlasquant_aion_global_worker_activation` | 15 | 0 | plano sintético exige `ACTIVATION_PLAN_READY`, readiness bloqueia por autoridade independente ausente |
| `test_atlasquant_aion_worker_runtime` | 6 | 0 | retorno/contagem de worker esperado, hardstop impede execução |
| `test_atlasquant_aion_global_worker_live_verification` | 5 | 0 | live evidence retorna `BLOCKED_UNVERIFIED_LIVE_EVIDENCE` |
| `test_atlasquant_aion_global_worker_readiness` | 2 | 0 | mocks esperam `PASS`, fonte independente não inscrita |
| `test_atlasquant_aion_global_worker_reactivation_gate` | 1 | 2 | `ACTIVATION_PLAN_READY` antigo recusado e dois `KeyError: 'plan'` secundários à recusa |
| `test_atlasquant_aion_execution_outbox` | 0 | 23 | `PermissionError: INDEPENDENT_PRODUCER_NOT_ENROLLED` |
| `test_atlasquant_aion_execution_saga` | 0 | 9 | `PermissionError` `INDEPENDENT_PRODUCER_RECEIPT_NOT_ENROLLED` e `INDEPENDENT_PRODUCER_NO_EFFECT_FENCE_NOT_ENROLLED` |
| `test_quality_workflow_coverage` | 1 | 0 | 15 root files de LAB adicionais fora da lista histórica canônica (em snapshot anterior) |
| **TOTAL** | **51** | **34** | **85 RED reais ainda abertos** |

Os grupos são classificação INICIAL. Mesmo quando o erro ocorre porque um guarda novo bloqueou o caminho, o caso originalmente também testava comportamento interno (CAS, saga, retry, cancelamento) que permanece sem validação end-to-end. **Não declarar essas 85 ocorrências sem importância** nem afrouxar a autorização externa para satisfazer o fixture.

## Diagnóstico causal novo: raiz da ativação realmente testada

A suite `test_aion_p0_quality_85_causal_inventory_lab.py` instancia fixtures reais e puramente locais de reactivation e activation com gate local `READY` e runtime ARMADO. Produz e agora exige os seguintes resultados imutáveis:
- `_runtime_armed_contract(...)` => `READY`.
- `validate_reactivation_gate_for_plan(...)` => `READY` na evidência sintética local.
- `_readiness_contract(...)` => **`BLOCKED / INDEPENDENT_ACTIVATION_AUTHORITY_NOT_ENROLLED`**.
- `prepare_global_worker_activation_plan(...)` => **`BLOCKED / INDEPENDENT_ACTIVATION_AUTHORITY_NOT_ENROLLED`**, `feature_flag_modified=false`, `global_worker_executed=false`, **sem objeto `plan`**. Esse é o motivo causal das 15 asserções antigas `BLOCKED != ACTIVATION_PLAN_READY` e dos dois `KeyError: 'plan'` derivados: os testes antigos assumiam planejamento positivo sem root independente. O M71, separadamente, devolve `BLOCKED / FRESH_INDEPENDENT_INCIDENT_SOURCE_NOT_ENROLLED` ao validar a execução final.
- Nenhuma das asserções na suite antiga foi modificada; não adicionar `mock_verified=True` ou `READY` artificial que bypassaria a trava.

## CI da rodada (e erro de inventário documentado)

A primeira CI [#39337219688](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39337219688) encontrou **erro do inventário novo**: tentativa de desduplicar os 85 blocos de erro por `(module,method)`, confundindo identidades de classes e parametrizações; resultou em `AssertionError: 85 != 73`. O log da Quality confirmou que duas funções de Outbox geravam cada uma dois `subTest(retryable=True/False)` independentes; o registro foi corrigido para guardar classe e contexto do `subTest`, e a asserção de causalidade foi reforçada para o código exato `INDEPENDENT_ACTIVATION_AUTHORITY_NOT_ENROLLED`. Isso NÃO foi erro de segurança do produto.

**[GitHub Actions #39337519687](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39337519687)**, head `aa06dc069d44e3df0b3467a16e020554599f5901`, **completed/success**:
- Ubuntu job `118350612028`: **12/12 inventory contracts PASS + 13/13 M71 PASS**.
- Windows job `118350611994`: **12/12 inventory contracts PASS + 13/13 M71 PASS**.
- Security canônica A74/A76 Ubuntu job `118350611896`: **365/365 PASS**.
- Total desta validação `12+13=25` casos distintos executados em dois SO (**50 execuções**), além de **365 execuções** de Security canônica em Ubuntu. Não somar o mesmo teste como novo caso em cada runner.
- Blobs de Worker/Outbox/Activation/M71 mantidos iguais; CI não toca fornecedor, flag, runtime produtivo ou gastos.

A CI VERDE é **da auditoria**, não da Quality: **Quality 51 FAIL/34 ERROR segue RED no último run completo**.

## Próxima prioridade por impacto em engenharia

1. **Quality 15 root files LAB fora da seleção**: desenhar um índice de cobertura que exija CI dedicated real para LAB e seleção Quality PROD completa, **sem simplesmente excluir `test_.*lab`** ou incluir o M71 negativo original num gate que deseja somente PASS. Preservar o teste de cobertura original RED até substituição comprovadamente mais rigorosa.
2. **32 Outbox/Saga erros**: restaurar cobertura da lógica de transições profundas em bancada sem acesso a fornecedor, preservando `INDEPENDENT_PRODUCER_NOT_ENROLLED` e `INDEPENDENT_PRODUCER_RECEIPT_NOT_ENROLLED`. Precisa de arquitetura de teste que separe puro estado de ato externo e nunca marque efeito autenticado com um fixture local.
3. **21 Global Worker e 6 worker runtime**: triagem de invariantes de leases/claim, retries e no-effect por paths onde writer NO-WITNESS impede entrar no estágio histórico, sem habilitar automação produtiva.
4. **P0 SQLite histórico**: continuam **dois IDs originais sem mapeamento exato**. Não classificar como fechados por passes LAB de thread/SQLite.
5. HUMAN_OWNER, produtor, H0 witness externo e terceira âncora continuam sem inscrição real, sem dinheiro/serviço novo e sem provas externas. Revisões de Quality, Security e auditoria independente continuam exigidas.

**VEREDITO FINAL: nenhum dos seis P0 homologado, Hard No-Go, Worker Off, Zero Auto Resend.**
