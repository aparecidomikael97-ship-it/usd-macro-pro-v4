# AION B2B — Terminal Certificate Read Model UI Runtime Binding Offline V1

Status: **offline-only / read-only / fail-closed / Draft**.

## Objetivo

Transformar o Terminal Certificate Read Model Runtime Projection em um view-model
de painel seguro, sem permitir que a camada de apresentação consulte banco,
provider, rede ou reconstrua verdade operacional.

## Fonte única

A entrada é exclusivamente a projeção formal de runtime do Read Model.

A UI binding não conhece DurableExecutionStore e não chama o Runtime Reader
diretamente.

## Estados visuais

- VERIFIED -> POSITIVE_EVIDENCE_ONLY
- MISMATCH -> FAIL_CLOSED
- UNAVAILABLE -> EVIDENCE_UNAVAILABLE
- STALE -> REFRESH_REQUIRED

A aparência positiva não cria autoridade. VERIFIED continua significando somente
evidência consistente e fresca.

## Seções

O view-model contém exatamente:

1. certificate_status
2. execution_identity
3. terminal_state
4. terminal_revision
5. certificate_digest
6. finalization_evidence
7. audit_seal_evidence
8. finops_evidence
9. observability_trace
10. scope_boundary

## Controles

A coleção de controles é vazia.

Não existem botões de execução, retry, reopen, reconciliação, rollback,
compensação, emissão/assinatura de certificado, billing, CRM, provisionamento,
deploy ou mutação de produção.

## Material sensível

Qualquer credencial, secret, token, private key, authorization header, payload
bruto, resposta bruta de provider, mensagem bruta de cliente ou comando de shell
faz a projeção falhar fechado.

## Limite

Esta etapa gera apenas um view-model Python offline. Não renderiza Streamlit/HTML
e não toca produção.

Próximo passo permitido:
IMPLEMENT_TERMINAL_CERTIFICATE_PANEL_COMPONENT_OFFLINE_ONLY
