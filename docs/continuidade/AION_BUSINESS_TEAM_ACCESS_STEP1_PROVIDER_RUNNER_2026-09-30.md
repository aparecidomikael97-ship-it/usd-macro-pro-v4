# Continuidade — Step 1 Guarded Provider Runner — 30/09/2026

## Estado

Implementado / em validação sobre a Draft PR #467.

## Entrega

- runner preflight read-only;
- PLAN ONLY por padrão;
- token físico exato derivado do apply_plan_digest;
- execution envelope freshness de 120 s;
- localhost-only;
- sandbox-only;
- script PowerShell com -Apply separado;
- token Keycloak efêmero em memória;
- lookup exato pré-write;
- POST somente para o endpoint congelado do Step 1;
- 201 obrigatório;
- readback exato pós-write;
- atributos sandbox/session/tenant/step conferidos;
- bloqueio se receipt anterior já existir;
- receipt sanitizado;
- zero ledger append automático;
- ADR-0080.

## Estado real

Nenhum runner APPLY foi executado por esta PR.

Nenhuma conta real foi criada.

Nenhum receipt real foi produzido.

Produção/deploy/runtime continuam OFF.

## Próximo gate

Após um apply físico real e receipt válido, validar o receipt contra
apply_plan_digest + runner_preflight_digest + provider readback e somente então
preparar o append manual do Step 1 no lifecycle ledger.
