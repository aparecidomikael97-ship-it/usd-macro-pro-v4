# AION B2B — Terminal Certificate Read Model Runtime Projection Offline V1

Status: **offline-only / read-only / fail-closed / Draft**.

## Objetivo

Normalizar o resultado já seguro do Terminal Certificate Runtime Reader Offline V1
para o conjunto formal de campos do Terminal Certificate Read Model.

Esta camada não conhece o DurableExecutionStore, não abre banco e não consulta
provider ou rede.

## Cadeia

Durable store autorizado -> store projection adapter -> runtime reader offline ->
read-model runtime projection.

A projeção continua sendo evidência observacional. Ela não cria autoridade.

## Estados

A camada preserva exatamente:

- VERIFIED
- MISMATCH
- UNAVAILABLE
- STALE

Estado desconhecido vira MISMATCH.

## Revalidações

Para VERIFIED e STALE, a camada exige:

- owner exato;
- tenant exato;
- workspace exato;
- marcador explícito de evidência sem autoridade;
- campos/digests obrigatórios presentes;
- valores de freshness coerentes;
- ausência de material sensível;
- todas as flags de autoridade do reader em false.

VERIFIED acima da janela de freshness é inválido.

STALE dentro da janela de freshness é inválido.

## Mapeamento formal

A saída inclui o conjunto lógico esperado pelo Read Model, incluindo:

- schema_version;
- tenant/workspace/execution;
- final execution state;
- terminal revision;
- certificate status;
- certificate manifest digest;
- certificate digest;
- certificate persistence record digest;
- finalization record digest;
- audit seal manifest digest;
- audit seal persistence record digest;
- terminal evidence set digest;
- FinOps observation digest;
- observability trace;
- pre-terminal audit chain digest;
- observed_at;
- SHA256;
- UTF8_CANONICAL_JSON.

## Segurança

Nunca cria execução, retry, reopen, reconciliação, rollback, compensação,
efeito externo, billing, contato com cliente, escrita CRM, provisionamento,
deploy ou mutação de produção.

Credenciais, secrets, tokens, chaves privadas, authorization headers, payload
bruto, resposta bruta de provider, mensagem bruta de cliente e comando de shell
são proibidos.

## Próximo limite

O próximo passo permitido é somente o desenho/implementação offline do binding
da UI ao read model runtime, ainda read-only e sem controles de ação.

Sem merge. Sem deploy. Sem produção.
