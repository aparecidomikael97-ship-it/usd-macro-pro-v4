# AION P0 — revisão restritiva dos testes legados M71/A74
Data: 21/10/2026 · somente LAB · sem autorização operacional

## Evidência e diagnóstico

A Quality completa da PR #1388 (execução https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39592498502, commit `81f6bbf064e705c6327c893ef956672bbbb2cd65`) exercitou **6.895 testes** e reportou **51 FAIL + 34 ERROR**. Os dois `ERROR` de `test_atlasquant_aion_global_worker_reactivation_gate` foram `KeyError: 'plan'`: os testes antigos presumiam que `prepare_global_worker_activation_plan` produziria `ACTIVATION_PLAN_READY`. Isso não é mais verdadeiro. O código de produto bloqueia com `INDEPENDENT_ACTIVATION_AUTHORITY_NOT_ENROLLED` e nem cria um campo `plan`.

Um terceiro teste dessa mesma classe ainda tinha a expectativa antiga `ACTIVATION_PLAN_READY` (1 FAIL). Esses três casos são **contratos positivos obsoletos no estado HARD NO-GO**, não prova de falha operacional. Uma passagem direta para READY seria perigosa. Nenhum código de produção deve ser revertido para satisfazê-los.

## Migração rigorosa, sem skip nem falso GO

Nesta branch alteramos somente os três métodos de teste (renomeados para refletir precisamente o veto), mais documentação/CI:

1. `test_activation_plan_binds_green_post_incident_gate` → `test_green_local_gate_cannot_mint_activation_plan_without_external_source`: o gate local pode ser READY estruturalmente, mas **não** cria plan, não muda feature flag, não executa Worker e exige autoridade de ativação independente.
2. `test_final_activation_execution_requires_fresh_gate` → `test_missing_fresh_gate_and_untrusted_ticket_never_write_flag`: não há plano real; mesmo com confirmação explícita e ticket inventado, o validador recusa gate ausente e o writer injetado **não é chamado**.
3. `test_execution_validation_rejects_reopened_gate` → `test_execution_validation_rejects_reopened_gate_without_synthetic_approval`: gate de reativação local fresco não autoriza a execução por si só, e incidente reaberto permanece bloqueado; não sintetiza prova de proprietário nem approver.

**A fronteira mantida é mais restritiva do que a expectativa antiga.** Isso não valida a capacidade de ativar: transforma três testes de cenários não operacionais em asserts explícitos de que a ativação está proibida. O controle positivo de um futuro ambiente homologado precisa de um novo conjunto de testes com evidência independente e revisão apropriada; esse fluxo não existe hoje.

O workflow dedicado executa esses três métodos em Windows/Ubuntu junto com os controles já existentes de A74 e H0 A79, com Worker OFF; a Quality completa é disparada nesta branch, sem exclusões nem dispensa das outras **82** ocorrências esperadas após eventual aprovação. Não declarar 82 até verificar as execuções completas, individuais e no mesmo HEAD.

## Segurança

- Sem mudança de `atlasquant_aion_global_worker_activation.py`, `atlasquant_aion_global_worker_reactivation_gate.py`, Outbox, Saga ou Worker.
- Sem chaves reais, fornecedor, conta nova, envio, retry, rollback terminal, merge nem deploy.
- Continuam ausentes identidade HUMAN_OWNER realmente homologada, primeira tentativa off-host, readback atual de fornecedor, evidência independente de reativação e seis P0 fechados.
- `HARD NO-GO`, `0/6 P0`, `ZERO_AUTO_RESEND`, feature flag de Worker desligada.

**Critério de aceitação:** 3 testes transformados PASS e nenhum novo FAIL/ERROR na Quality completa no HEAD final; manter catálogo completo dos restantes. A aprovação desta PR não significa homologação nem liberação do núcleo.
