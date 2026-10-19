# Checkpoint Mestre — M71 replay de READY: RED→GREEN por HARD DENY LAB — 395 PASS por SO

**Data: 19/10/2026. Estado global INALTERADO: 0/6 P0 HOMOLOGADOS; HARD NO-GO; Global Worker OFF; ZERO_AUTO_RESEND. Sem merge, deploy, nova despesa, credencial, testemunha, envio, trading ou operação externa.**

## Problema REAL detectado e confirmado nos dois sistemas (antes do patch)

No A118 original, a função pública `validate_reactivation_gate_for_execution` aceitava um `gate READY` de antes da reabertura de um incidente, ainda dentro do TTL=300s, sem consultar nova fonte independente de incidentes. Runtime/ledger/feature flag podem permanecer iguais enquanto um incidente é REOPENED; o teste M71 demonstrava `READY` quando o resultado seguro é `BLOCKED`. A aprovação usada no teste era sintética; **nenhum writer, Worker ou produtor real foi acionado**, e o hard-stop `_independent_activation_authority_denial` anterior continuava bloqueando ativação em A118.

Baseline LAB RED nova branch `lab/aion-m71-postincident-fresh-source-deny-20261019`, criada do arquivo de auditoria canônica `ac437afdf0708211bfe54709304b737a406cb62f`.
- [**Actions RED #39335221061**](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39335221061), HEAD `a33a4a7030c59ef6852a8c4ca3638bd391050c19`. Ubuntu job `118342902000` e Windows job `118342902422`: ambos falharam em **mesma assertiva ORIGINAL** `M71_RED_STALE_READY_GATE_ACCEPTED_AFTER_REOPENED_INCIDENT`, com `AssertionError: 'READY' != 'BLOCKED'`. Fontes `activation`, `incident reconciliation`, `global worker` e `outbox` ainda tinham os blobs de segurança A118 esperados; nenhum estado real foi modificado.
- Não classificar o RED como ativação operacional; é lacuna de validador público cuja futura integração seria perigosa sem reparo.

## Patch M71 em LAB — somente execução antes da flag

Arquivo `atlasquant_aion_global_worker_reactivation_gate.py`, commit **`eb762dadb1d5a4914d3b34998457845345e2dfcb`**, blob **`d69e1ea42711610b2d36ec8274c32f7109fc96ee`**.
- Adicionada constante `INDEPENDENT_CURRENT_INCIDENT_SOURCE_MISSING = INDEPENDENT_POST_INCIDENT_CURRENT_STATE_NOT_ENROLLED`.
- `validate_reactivation_gate_for_execution` preserva checks antigos de estado/requirement, integridade, TTL, digest/sha runtime, ledger, closure ID, approval e flag. **Todos os caminhos que ANTES devolviam READY agora devolvem BLOCKED** por fonte independente NÃO matriculada — inclusive quando `gate_required=false` e o histórico local está vazio (vazio pode resultar de restore anterior).
- Respostas de bloqueio expõem `reactivation_authorized=false`, `feature_flag_modified=false`, `global_worker_executed=false`; não fazem I/O, chamadas a provider, lookup de conta, worker, assinatura nem retry.
- Checks negativos originais permanecem negativos com suas mensagens específicas (gate manipulado, expirado, escopo incorreto). Claims `independent_source_enrolled=true` em aprovação fornecida pelo caller nunca bypassam o bloqueio.
- **Limite fundamental:** a função **não lê de fato uma nova fonte de incidente**, não verifica assinatura, não realiza matrícula nem possui CAS externo. É um **guard deny-only temporário**, não a resolução completa de fonte/frescor nem P0 homologado. `validate_reactivation_gate_for_plan` é apenas função de planejamento e ainda pode produzir diagnósticos READY; a **fronteira de execução** pré-flag passa a bloquear. `activate_global_worker_feature_flag` segue com seu bloqueio adicional de autoridade externa A118.
- Não mexeu em `atlasquant_aion_global_worker_activation.py` (A118 blob `df43bb4371c784396069f4ede51205b0aa19cc0a`), `atlasquant_aion_global_worker_incident_reconciliation.py` (A118 `85541bb2d10f0b97b096df10b5184851160cfec9`), `atlasquant_aion_global_worker.py` (LAB `f4cd9f358aee285747321e96be3db82691e02fe8`) ou `atlasquant_aion_execution_outbox.py` (LAB `cd78ed43ad63888408eb599e28379c193c541de2`).

## Testes RED→GREEN SEM alterar assertiva de segurança original

- `test_aion_p0_m71_original_stale_gate_safety_negative_lab.py` do registro anterior permaneceu **intocado**: sempre exige `BLOCKED` mesmo quando caller repete `READY`. Estava RED antes do patch e passou GREEN depois.
- `test_aion_m71_unenrolled_current_incident_source_lab.py`, commit `373d930e89270cacd7a8cf335e64403c6799ff75`: dez novos testes de gate recente/antigo, incidente reaberto, `verified` autoafirmado, ausência de histórico, alteração de gate, TTL expirado, imutabilidade de input, approval divergente e alteração de requirement. Não usam conta ou fornecedor.
- `test_aion_p0_original_six_evidence_matrix_lab.py`, commit de revisão explícita `84e463c78537d78be35d75ae5d057092e9d46989`: manteve **seis P0 abertos**, mudou apenas auditoria M71 para verificar que a assertiva original *agora* passa com código patched. A evidência de RED anterior permanece no histórico e no commit da branch predecessora; não é `xfail`.
- `.github/workflows/aion-m71-fresh-incident-source-deny-lab.yml`, commit inicial `a33a4a7030c59ef6852a8c4ca3638bd391050c19`, reforçado com 365 Security canônicos em **`6c7b9e13fcbd7a3d652b9f5eb5fc566e0a0d8025`**. Read-only contents permission, runners Windows/Ubuntu, pinos de Writer/Outbox sem mudança.
- Documento com condições de implementação e limites em `docs/aion/AION_M71_STALE_READY_EXECUTION_DENY_ONLY_LAB_20261019.md`, commit `64ebc8796d357ed17311bec332779389713e23ce`.

## CI GREEN final confirmada via logs reais

[**Actions #39335923515**](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39335923515) — `completed/success`, HEAD `6c7b9e13fcbd7a3d652b9f5eb5fc566e0a0d8025`:
- Ubuntu job `118345276612`: original M71 **1/1 PASS**, novos M71 **10/10 PASS**, matriz seis P0 **10/10 PASS**, A73/A110 **9/9 PASS**, Security canônica A74/A76 **365/365 PASS**. **395/395**.
- Windows job `118345276222`: mesmas contagens e resultados **395/395 PASS**.
- TOTAL: **395 cenários por SO, 790 execuções PASS**. O marcador `M71_ORIGINAL_SAFETY_ASSERTION_NOW_GREEN_LAB_DENY_ONLY` e o pin `M71_A118_OTHER_HARDSTOPS_PINNED` aparecem em AMBOS os logs.

[CI #39335598159](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39335598159) antes da adição das 365 Security já mostrou 30/30 Ubuntu e Windows, com assertiva original M71 GREEN. Intermediate REDs em #39335403573 e #39335548354 ocorreram antes da atualização explícita da auditoria/teste de inventário para exigir GREEN; manter essas evidências acessíveis e não omitir o baseline #39335221061.

## Resultados que NÃO devem ser inflados

- **Quality canônica completa não foi reexecutada nesta branch de patch.** Último baseline verificável antes do patch: [#39334210568](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39334210568), 6.562 testes, **51 FAIL, 34 ERROR**, mais M71 original RED. Não dizer que Quality ficou GREEN por 790 testes focados. Parte dos testes legados de caminho positivo provavelmente precisará de migração de expectativas após esta postura deny-only — sem enfraquecer guardas nem xfail genérico.
- **M71 não se converteu em GO operacional.** Corrigiu-se uma decisão local perigosa por recusa padrão enquanto faltam testemunha independente, matrícula, verificação de fonte/incidente, monotonic epoch/sequence, verificação fresca imediatamente antes da escrita real e prova anti-TOCTOU. Realizar ensaios duas máquinas, reboot físico e incident reaberto concorrente só com infraestrutura e autoridade legítimas.
- **Nenhum dos seis P0 originais foi homologado**: HUMAN_OWNER real, recibos autênticos do produtor, primeira tentativa após resultado incerto, H0/restart antirollback e dois P0 históricos de SQLite (IDs originais ainda não reconciliados). Não declarar outros caminhos autorizados pelo simples fato de falha ser fail-closed.

## Próxima prioridade

1. Triar as **51 FAIL / 34 ERROR** Quality canônicas por clusters e confrontar contratos históricos com os hard-stops atuais, sem silenciar o RED.
2. Rastrear exatamente os DOIS IDs/falhas históricas de compatibilidade SQLite; não inferir que os guards de thread/tx são os dois P0 originais.
3. Tratar matrícula real da fonte de incidentes, owner e provedor **somente com autorização expressa do proprietário** e avaliação do orçamento/custódia externa. Não criar conta/serviço ou chave real para "provar" algo em LAB.

**ESTADO FINAL: M71 MITIGADO POR DENY-ONLY EM LAB; 0/6 P0 HOMOLOGADOS, HARD NO-GO, Worker OFF, ZERO_AUTO_RESEND, sem merge/deploy/gasto.**
