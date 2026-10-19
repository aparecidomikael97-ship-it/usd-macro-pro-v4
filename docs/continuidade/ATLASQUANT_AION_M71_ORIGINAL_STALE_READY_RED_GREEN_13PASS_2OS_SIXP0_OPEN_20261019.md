# CHECKPOINT MESTRE — AION M71: gate READY obsoleto não passa na validação final (RED→GREEN LAB)

**Data: 19/10/2026. Estado operacional imutável: 0/6 P0 HOMOLOGADOS, HARD NO-GO, Worker OFF, ZERO_AUTO_RESEND.** Nenhum merge, deploy, conta, credencial, fornecedor, mensagem, execução externa ou gasto adicional. O M71 é uma lacuna TRANSVERSAL aos seis P0, não um sétimo P0 nem homologação H0.

## Reproduzimos a falha real ANTES do remendo

- Repo: `aparecidomikael97-ship-it/usd-macro-pro-v4`.
- Código A118 original `atlasquant_aion_global_worker_reactivation_gate.py` Git blob `8412ada82761de37a72a8f29af7f8672cfb5b082` em commit `c62fab663c6349d7320f7843c8d09587c514426b`.
- Branch LAB `lab/aion-m71-fresh-incident-execution-hardstop-20261019`, base `44a4de01817d896e056810025d6c68ec8e34112f` (auditoria original seis P0).
- `test_aion_m71_execution_fresh_source_denial_lab.py`: 12 contratos congelados em commit `ee8004ef18531e67187c5c116ba5198884d78a52` **antes de editar o validador**. O original `test_aion_p0_m71_original_stale_gate_safety_negative_lab.py` foi mantido sem mudanças (hash Git `4808449a673dbcd3e930940f383c622fb5fbcb81`).
- [Actions **RED #39335321672**](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39335321672): seis dos 12 casos novos falharam, pois `validate_reactivation_gate_for_execution()` retornava `READY` para gate antigo dentro do TTL, alegações autofirmadas de freshness no gate/approval ou ausência de histórico local. O M71 negativo original também falhou, marcador `M71_RED_STALE_READY_GATE_ACCEPTED_AFTER_REOPENED_INCIDENT`. Os testes mostram violação do contrato do **validador isolado**, NÃO acionamento de Worker/feature flag. No original, a autoridade final independente continuava bloqueando o writer.

## Causa e correção localizada

O A118 calculava `gate_digest`, verificava escopo, validade de até 300s padrão, runtime SHA, ledger/closure e aprovação, mas **não tinha consulta confiável ao estado de incidentes depois da geração do gate**. Em uma reabertura 10s depois, a avaliação FRESCA produzia `BLOCKED`, mas a chamada final com o gate antigo ainda produzia `READY`. Como um rollback local pode inclusive omitir história de incidentes, a ausência de `gate_required` não era prova de limpeza.

- **Fix LAB** commit `c78b0f2a783040bd981c895aff9436642f6f48ae`, `atlasquant_aion_global_worker_reactivation_gate.py` blob `8533ae3c1720d4230dace6478a40f9f11b9677d4`.
- `validate_reactivation_gate_for_execution` mantém todos os erros negativos existentes (digest, TTL, runtime, ledger, flag, approval), mas **nunca retorna execução `READY` sem fonte independente de incidentes autenticada e monotônica**. Como não existe essa fonte, todo caminho final de execução retorna `BLOCKED`; motivo específico para estrutura válida: `FRESH_INDEPENDENT_INCIDENT_SOURCE_NOT_ENROLLED`.
- Se `gate_required=False` por ausência de histórico local (possivelmente rollback), também retorna `BLOCKED`, antes sem prova.
- `assess_post_incident_reactivation_gate` e `validate_reactivation_gate_for_plan` permanecem intactos: `READY` significa possível planejamento baseado no snapshot, **não habilitação**.
- Nenhum sinal `verified=true`, `signed=true`, callback do mesmo caller ou gate local tem exceção para contornar. Só real enrollment/reconciliação de fonte independente, com prova e auditoria futura, poderá abrir o limite por outra versão homologada.
- `atlasquant_aion_global_worker_activation.py` permaneceu blob `df43bb4371c784396069f4ede51205b0aa19cc0a`; `atlasquant_aion_global_worker.py` `f4cd9f358aee285747321e96be3db82691e02fe8`; Outbox `cd78ed43ad63888408eb599e28379c193c541de2`. Worker real, mensagens e código produtivo NÃO foram alterados.

## Evidência GREEN foco e continuidade do inventário

- [Actions #39335459200](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39335459200) pós-fix: Ubuntu **12/12 novos PASS** e **1/1 M71 original PASS**; Windows mesmos **12+1 PASS**. O workflow MAIS AMPLO permaneceu `FAILURE` devido a testes históricos de reactivation (**1 FAIL, 2 ERROR**) e activation (**15 FAIL**) — **totais idênticos ANTES do patch** em #39335321672. Não esconder esse resultado nem classificá-lo como GREEN total.
- Criado workflow focado de CI `.github/workflows/aion-m71-exact-original-replay-focused-lab.yml`, commit `2e3d5b8d9a7e855bb9589493df74c26eaa24739e`; [**Actions #39335745839**](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39335745839), **completed/success**: Ubuntu job `118344696597` **13/13 PASS**, Windows job `118344696337` **13/13 PASS** (12 novos + 1 negativo original sem alteração). Pinos A118/patch/Activation/Worker/Outbox confirmados em ambos OS. É um GREEN LIMITADO ao contrato M71 do validador, não Quality canônica.
- Documento técnico de análise em `docs/aion/AION_M71_POST_INCIDENT_STALE_GATE_HARDSTOP_RED_GREEN_LAB_20261019.md`, commit `f13dcdc3a1ab113166f7fc88567ec151c154a32b`.

## Registro dos seis P0 conciliado, sem perder RED histórico

- O JSON anterior `docs/aion/AION_P0_SIX_BLOCKERS_CANONICAL_EVIDENCE_REGISTER_20261019.json` dizia M71 `RED_ORIGINAL_RECONFIRM_PENDING`. Essa descrição ficou obsoleta APÓS fix. Atualizado em commit `76adabd85194efd6bebc19d12438e6980f93677c` para `LAB_DIRECT_VALIDATOR_HARDSTOP_GREEN_CANONICAL_HOMOLOGATION_PENDING`, incluindo links do RED original e do GREEN focado; os **seis P0 continuam `OPEN_*`, independent_evidence_obtained=false, canonical_tracker_id=null e p0_homologated=0**.
- `test_aion_p0_original_six_evidence_matrix_lab.py`, atualizado em `f9ac34a89c3227cbb94616581a53abd346976a45`: pin do A118 original via `git rev-parse c62...:...`, pin do remendo LAB atual via `git hash-object` e reexecução da **mesma afirmação negativa M71** esperando agora saída 0 e `BLOCKED`; o RED anterior permanece documentado por Actions #39335321672. Nenhuma asserção de segurança M71 foi afrouxada, descartada ou transformada em `xfail`.
- `.github/workflows/aion-m71-six-p0-inventory-reconciliation-lab.yml`, commit `25ea40d30c2873b915340116782bad008328fd3a`, [**Actions #39336162918**](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39336162918) `completed/success`: Ubuntu job `118346068473` **10/10 auditoria + 13/13 M71 PASS**, Windows job `118346069015` **10/10 auditoria + 13/13 M71 PASS**. Os 23 casos distintos foram executados 2 vezes = **46 execuções**. Não somar os 13 já vistos em #39335745839 como se fossem novos cenários.

## Regressões não superadas / próxima prioridade

1. **Quality canônica integral segue historicamente RED** na última execução completa [#39334210568](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39334210568): 6.562 testes, 51 FAIL, 34 ERROR. Essa suíte NÃO foi reexecutada neste ramo de patch M71. O Security subset anterior: 365 PASS limitado; NÃO igual a sistema homologado.
2. O workflow M71 amplo verificou que historicamente os 13 testes originais de reactivation continham 1 FAIL/2 ERROR, e activation continha 15 FAIL, ANTES e DEPOIS. Precisam de triagem por causalidade, sem `xfail` genérico ou relaxamento da expectativa BLOCKED. A correção M71 deliberadamente reduz disponibilidade de execução enquanto não há fonte externa; qualquer compatibilidade que faça retornar READY por dados locais é regressão de segurança.
3. **Nenhuma fonte independente matriculada de incidente atual**, sem timestamp/epoch remoto, key ID trust root, readback assinado ou dois hosts. O remendo é um HARDSTOP local. Não há pronta reativação operacional.
4. Os seis P0 permanecem abertos: HUMAN_OWNER real, emissor de recibos, primeira operação incerta, H0 após reboot, compatibilidade SQLite leitura/escrita (dois IDs canônicos originais ainda UNMAPPED).
5. Outros bloqueios: Quality CI coverage de 15 root files LAB, rollback manual do sqlite externo, custódia S3/Cloudflare não provisionada, M71 live incident source sem custódia. Não há autoridade para ativar Worker, merge, deploy ou gastos.

## Próxima ação

Fazer triagem causal da **Quality histórica do módulo activation/reactivation**, preservando RED antigo e separando expectativa de plan READY de execução READY (agora proibido), reconciliar os 15 arquivos LAB fora da seleção canônica, e mapear os dois SQLite P0 ao erro original. Dar prioridade a contratos de falha de segurança, não a contadores de mini-testes. Integração de witness externo exigirá autorização humana específica, conta separada e orçamentos validados.

**HARD NO-GO; Worker OFF; ZERO_AUTO_RESEND; 0/6 P0 homologados.**
