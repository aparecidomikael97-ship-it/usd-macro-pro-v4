# AION P0/H0 — suspeitas de regressão e recuperação read-only (LAB)

Data: 21/10/2026. Base: PR Draft #1385, commit `6dfbc54767fcbf7fc785dd1ffe56ccab9805083c`.

## Propósito e limites

Melhorar apenas o **diagnóstico de inconsistência local** do `ExecutionOutbox` sobre SQLite. O verificador **não impede** o rollback físico, não valida fonte externa, não confere identidade do HUMAN_OWNER, não chama provider, não autoriza reenvio (manual ou automático) nem fecha uma operação. A saída continua incondicionalmente `HARD_NO_GO`, `allowed=False`, `UNKNOWN_BLOCKED`, flags de autoridade falsas.

## Novas classes de suspeita

1. Uma pista de estado local **terminal** (`CONFIRMED`, `REVOKED`, `FAILED` ou `BLOCKED_REAPPROVAL`) diverge do estado encontrado para o mesmo `idempotency_key`, inclusive terminal→outro terminal.
2. Uma linha aparentemente reutilizável (`PENDING`/`RETRY`) ainda contém início de despacho, carimbo de envio/confirmação ou `effect_ref`. Mesmo que essa combinação seja anômala, ela não comprova resultado externo.
3. Uma linha `CLAIMED` contém envio, confirmação ou `effect_ref` anterior. **Apenas** `dispatch_started_at` em `CLAIMED` pode representar operação em curso e, isoladamente, não prova regressão.
4. Uma pista histórica de início de despacho tem timestamp diferente do observado: indício local suspeito, não prova independente.
5. Um carimbo local malformado ou quantidade de tentativas fora do limite de diagnóstico é classificado como registro ilegível, sem exceção que conceda autoridade.

Os novos cenários são **adversariais e negativos**. Existem 11 novos métodos na suíte `test_aion_p0_h0_recovery_triage_readonly_lab.py` (total documental de 55). Eles exercitam `ExecutionOutbox` REAL em SQLite temporário, inclusive mutações feitas **somente na preparação do teste** e observação posterior sem escritas; nenhuma ação externa é disparada.

## Limite arquitetural

Uma restauração simultânea de pistas históricas e do banco continua potencialmente invisível. Falta atestação externa de versão/cabeça, matrícula independente do fornecedor, nonce consumido atomicamente em custódia externa e recibo originário/fence de provedor. Não concluir P0-H0, não permitir primeira emissão, reenvio, reconciliação terminal, Worker, merge ou deploy.

## Evidência exigida

- Executar CI específica em Ubuntu e Windows sobre o HEAD exato; **não presumir PASS** pela simples criação de workflow.
- Rodar novamente Quality/Security canônicas antes de qualquer avaliação de integração; não dispensar falhas históricas.
- Zero violação de `allowed=False`, `HARD_NO_GO`, `UNKNOWN_BLOCKED`, `automatic_retry_allowed=False`.
- Registrar qualquer teste falho ou cancelado, sem mascarar RED como GREEN.

**0/6 P0 homologados; HARD NO-GO permanente neste LAB; Worker desligado; ZERO_AUTO_RESEND.**
