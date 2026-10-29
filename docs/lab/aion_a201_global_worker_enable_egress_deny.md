# AION A201 — contenção de ativação externa do Global Worker (LAB)

**27/10/2026 · PR DRAFT · 0/6 P0 homologadas · HARD NO-GO.**

## Falha concreta no código-fonte da base A200

`atlasquant_aion_global_worker_activation.write_repository_feature_flag_enabled(config, prior_state)` é uma **função pública e exportada** que aceitava `RuntimeConfig.repo` + `RuntimeConfig.token` e estado anterior `UNSET`/`DISABLED` passado pelo chamador e fazia `requests.post` ou `requests.patch` no GitHub para definir `AION_GLOBAL_WORKER_ENABLED=1`, sem vínculo independente da identidade original do proprietário, da reserva durável da primeira tentativa ou da custódia contra rollback. Embora `activate_global_worker_feature_flag` tenha um cerimonial local de confirmação e aprovação, a função de baixo nível pode ser chamada diretamente, ou alcançada pelo cerimonial com tickets autoatestados. **A presença de token e confirmação local não constitui aceite P0.**

Risco específico: mudança remota do recurso de ativação do Worker por um caminho ainda não ancorado externamente. Não foi demonstrado que isso já tenha ocorrido em produção ou que um atacante externo possua token; não realizamos nenhuma chamada real.

## Alteração real em código, somente laboratório

- Em `write_repository_feature_flag_enabled`: manter a validação de ausência de token e estado inseguro, mas recusar `UNSET` e `DISABLED` com `status=BLOCKED`, `reason=EXTERNAL_ENABLE_CUSTODY_NOT_HOMOLOGATED`, `modified=false` **antes de montar headers ou alcançar POST/PATCH**.
- Em `activate_global_worker_feature_flag`: quando o writer padrão retorna a negativa de custódia, propagar `status=BLOCKED`, sem reler ou tentar retry de rede, sem afirmar ativação.
- Manter `force_disable_repository_feature_flag` e `deactivate_global_worker_feature_flag` **inalterados**. A desativação segura de uma flag já ligada deve continuar possível, com POST/ PATCH de valor `0` somente após suas proteções existentes. Isso não demonstra disponibilidade em todo cenário real.
- O transporte anterior de enable permanece atrás de `return` incondicional, somente para histórico de revisão. Não há flag runtime, parâmetro `force`, approve=true nem token fornecido pelo chamador que ultrapasse o bloqueio.

## Testes e histórico de regressão

O teste antigo `test_writer_creates_when_unset_and_updates_when_disabled` fazia mock de POST/PATCH e exigia `WRITE_ACCEPTED`. **Esse contrato tornou-se inseguro** no atual HARD NO-GO. Renomeamos e migramos explicitamente esse método, exigindo `BLOCKED` e zero chamadas HTTP. O original e sua expectativa estão preservados integralmente no commit pai A200 `ece53349fa30cf603ea78fe758059cafccb1e460`, e a alteração é visível no diff. Nenhum `skip` ou `xfail`.

A nova suíte `labs/test_a201_global_worker_enable_egress_deny.py` com 11 testes verifica: UNSET/DISABLED, bypass por grafia/prior-state, condição insegura, 64 tentativas concorrentes, falta de token, cerimonial com ticket sintético aprovado mas writer real bloqueado, ausência de confirmação, desativação PATCH=0 e fallback 404/POST=0, parada ADMIN simulada e ausência de autoridade HUMAN_OWNER independente. Todos os transportes são substituídos por mocks, **nunca GitHub real**. Workflow Linux e Windows com dependências pinadas; Quality geral, segurança e navegador também obrigatórios. O CI decidirá, não declarar verde antecipadamente.

## Limites fundamentais

Este bloco contém somente a ativação da variável Global Worker, e não bloqueia todos os caminhos de mutação do GitHub/Outbox/memória nem cria testemunha de custódia. Qualquer alteração futura para permitir enable exige revisão de código e evidência de admissão original independente, irrevogável e vinculada ao efeito. Contratos ainda RED: raiz HUMAN_OWNER independente, intenção semântica CAS externa, anti-rollback de histórico/chave, provider receipt H0/NO_EFFECT_FENCED, native same-inode e testes nativos Windows/Linux. `UNCERTAIN=ZERO_AUTO_RESEND`.

**FinOps:** Negócios congelado. Nenhuma contratação/custo extra até 05/11; a partir de 06/11 só sob autorização explícita. Proibidos AWS/KMS, Worker, SEND real, trades, merge, deploy, mudança de chave/token e cobrança.
