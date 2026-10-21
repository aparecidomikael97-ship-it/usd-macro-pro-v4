# AION P0 — recuperação do Checkpoint: recusar resumos de trace inconsistentes (LAB)

**Data:** 21/10/2026. **Base:** PR Draft #1408; branch LAB empilhada, sem merge/deploy/restore real. **HARD NO-GO · Worker OFF · ZERO_AUTO_RESEND · 0/6 P0 homologados.**

## Falha real reproduzida antes da correção

`atlasquant_aion_recovery_traceability_gate.py` recebe `current_runtime`, `candidate` e uma projeção de rastreabilidade gerada em condições normais por `build_local_traceability`. A função `recovery_traceability_readiness` verifica os rótulos `SAFE_LOCAL`, `contract_consistent`, `record_count`, `execution_refs` e `source_keys` diretamente, sem recalculá-los a partir dos registros individuais. A projeção é **evidência local, não testemunha independente**, mas o gate permitia apresentar o estado `READY_FOR_ADMIN_REVIEW` com resumos falsos.

Em casos mais graves, `int(trace["record_count"])`, `dict(trace["security"])` e `dict(row)` podiam gerar exceções para entradas não confiáveis. Isso **não chegou a autorizar restauração real**, porque o retorno do gate original já tinha `recovery_authorized=false`, `automatic_restore=false` e `automatic_retry=false`. Ainda assim, uma revisão incorretamente classificada como pronta e um erro não controlado violam o contrato fail-closed de retomada.

**RED-first verificável:** [CI #39647122823](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39647122823), SHA `79adb5cd5e89d92cae403ced0a18b34421f9b0d3` (antes do patch): **19 FAIL e 4 ERROR entre 26 testes novos em Ubuntu**. A suíte usa o mesmo gerador real de `build_local_traceability`, `default_checkpoint` e `recovery_preflight`, com mutações no objeto de rastreabilidade local. Sem chamadas de GitHub Runtime, save, restore, provedor ou Worker.

## Patch mínimo no gate

- `_trace_projection_coherent` exige `records` como lista limitada e `record_count` como inteiro exato, sem aceitar `bool` como contador. Recalcula `execution_refs`, `confirmed_content_refs`, `unknown_refs`, `conflict_refs`, `source_keys` e `contract_fingerprints` a partir dos registros; exige igualdade estrita com os resumos declarados.
- Identidades `tool_id/source_key/source_path` devem corresponder ao catálogo estático de fontes locais do AION. O trace legítimo `aion.checkpoint.inspect` continua reconhecido; uma origem falsificada ou um registro `local_only=false` bloqueia prontidão.
- Controles `SAFE_LOCAL`, `network_called=false`, `connector_called=false`, `external_side_effects=false`, `security_issues=[]`, marcadores de autoridade e inclusão de conteúdo bruto devem ser coerentes; o rótulo `SAFE_LOCAL` sozinho não vale como prova.
- Entradas de tipos incorretos devolvem `BLOCKED` e bloqueador `TRACEABILITY_RECORD_PROJECTION_MISMATCH` ou `TRACEABILITY_SECURITY_BLOCK`, em vez de exceção. Projeções inválidas também não contaminam o digest de recibo com dados dinâmicos arbitrários.
- O gate continua marcando `READY_FOR_ADMIN_REVIEW` **somente para traços locais coerentes e candidato de recovery preflight elegível**. O retorno ainda exige aprovação administrativa separada e **não grava checkpoint, não restaura, não reexecuta operação**.
- `local_contract_fingerprint` e hashes/traces internos não criam testemunho externo; um atacante com acesso completo à produção local ainda pode reconstruir um trace coerente. O patch restringe adulterações parciais e dados malformados, **não** representa proteção criptográfica externa contra rollback.

## Aprendizado de validação

O primeiro patch rejeitou por engano também o traço legítimo, devido a barras duplas em `re.compile(r"...\\Z")`, erro encontrado pela CI #39647418048, onde **25 dos 26 testes passaram e o único FAIL foi o caminho positivo legítimo**. A regex foi corrigida; o SHA definitivo deve provar ambos os requisitos — recusa de falsificação e preservação do review local esperado — em Windows e Ubuntu.

Suíte nova: `tests/test_aion_p0_checkpoint_recovery_trace_shape_coherence_lab.py` (26 cenários), mais suites originais `test_atlasquant_aion_recovery_traceability_gate`, `test_atlasquant_aion_recovery_review`, `test_atlasquant_aion_local_traceability` e H0 A79 64. Workflow específico `.github/workflows/aion-p0-checkpoint-recovery-trace-coherence-lab.yml` e Quality/Security original 588 módulos/6.895 testes, Security A74 365 sem waivers.

## Limites de homologação

Os seis P0 permanecem abertos. Não existe emissor externo com chave independentemente matriculada, recibo causal do produtor, reserva de nonce fora do host, head monotônico fora do controle do administrador, prova `NO_EFFECT_FENCED` nem autorização real do HUMAN_OWNER. **HARD NO-GO · Worker OFF · ZERO_AUTO_RESEND · 0/6 P0 homologados.** Nenhum merge, deploy, Worker, restore real, API externa ou gasto foi permitido.
