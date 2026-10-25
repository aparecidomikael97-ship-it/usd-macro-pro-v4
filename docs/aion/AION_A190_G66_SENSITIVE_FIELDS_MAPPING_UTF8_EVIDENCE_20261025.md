# AtlasQuant / AION A190 — G66 sensitive fields, Mapping and exact UTF-8 contract

**Data:** 2026-10-25. **LAB branch:** `lab/aion-a190-g66-sensitive-fields-mapping-utf8-20261025`. **Draft PR:** [#1552](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1552), based on G65 Draft #1551, **not main**.

## Scope, not operational certification

G65 refused sensitive-looking names of JSON keys and bounded 4096 traversals / 262144 encoded UTF-8 bytes, but the shared `aion_chat.privacy.redact` function had incomplete exact field names: `authorization`, `access_token`, `client_secret`, `api-key`, `apiKey`, `accessToken`. Plain fake marker values under those fields were left in synthetic `action_decisions.data` or `action_effects.data`, particularly nested tuples. A custom `collections.UserDict` was treated as opaque and serialized via `default=str`, which could persist its fake sensitive values. Numeric/non-string keys had no stable fail-closed error.

The labels are **synthetic**, not genuine credentials or customer data. No provider SEND, Worker or financial effect was executed.

## Independent Codex review before patch

Windows Codex CLI v0.164.0-alpha.11.1 session `01a174a6-0d38-7173-a769-5d6142707290`, read-only/ephemeral, inspected G65 code, privacy helper and test contracts. Confirmed the three defects in static inspection and recommended extending exact field-name matching, `Mapping`-to-dict redaction, and stable rejection of non-string keys before BEGIN. It also noted `redact` is shared with chat/store, not just Outbox. Codex did not edit files, execute tests, use network or contact provider.

## RED first, before runtime changes

Created `labs/a190/test_g66_sensitive_fields_mapping_utf8_lab.py` on G65 at test-only SHA **`5e4be24726ba68af8450f3c01a2b71797e0e811d`**. Actual isolated Windows disposable SQLite run:
- **12 tests, 6 PASS / 5 FAIL / 1 ERROR**.
- FAIL 01–04: field-name variants leaked fake marker values, and nested `UserDict` serialized its `repr` instead of a redacted structure (including inside confirmation).
- ERROR 05: non-string nested JSON key raised incidental `TypeError` from `re.fullmatch`, rather than stable pre-BEGIN denial; FAIL 06: a non-string UserDict key in confirmation was accepted.
- GREEN 07–11 demonstrated the **existing** G65 controls: exact ASCII 262144 accepted / 262145 denied before BEGIN, multibyte UTF-8 boundary allowed and exceeded refused, plus post-reservation decision-envelope overflow causing transaction rollback with no decisions/outbox/lock/effect. GREEN 12 confirmed existing standard `password`/`secret` redaction.

## Narrow G66 runtime corrections

1. `aion_chat/privacy.py` SHA **`36f685cd6486f561615b7c6666f91c47d8b6dea7`**: use `collections.abc.Mapping` instead of `dict` alone for recursive redaction; convert mappings into redacted plain dicts. Extend exact sensitive-name match to field variants listed above. Ordinary non-sensitive text stays ordinary text; names of sensitive fields remain as key labels and associated values become `[REDACTED]`. G65 pattern-matching secret-looking *key content* still rejects.
2. `atlasquant_aion_execution_outbox.py` SHA **`008630f172b49abc560ad58d4a485c3de6cb67f5`**: reject non-string keys in any traversed `Mapping` with `G66_NONSTRING_JSON_KEY_DENY` before recursive redaction and before BEGIN. No silent stringification/key coercion and no provider SEND enabling.
3. No changes to G65 UTF-8 byte budgeting, G63 immutable serialized payload validation, COMMIT/rollback, external authority or retry.

After patch: **G66 12/12 PASS** on Windows; G65 19/19, G64 16/16, G63 13/13 pass as immediate inherited regression.

## Full focused regression and CI provenance

- Full isolated Windows G30–G66 regression at SOURCE SHA **`008630f172b49abc560ad58d4a485c3de6cb67f5`**: **619/619 PASS**, exit 0, clean detached checkout `C:\Users\apare\AtlasQuant-G66-Privacy-LAB-20261025`. G51 tests consolidated into G50.
- Matrix GitHub Actions workflow `.github/workflows/aion-a190-g66-field-mapping-utf8-lab.yml` committed with unchanged source at SHA **`c258d1e0fba66ff7a68df395aaef39f2d57bcc99`**, Ubuntu and Windows, **619 focused synthetic cases per OS**. The final job logs and markers MUST be observed before cross-OS approval is claimed.
- Any subsequent evidence-document-only commit is NOT a retest of source/workflow SHA.

## Segunda revisão independente Codex pós-patch (limites reais e não demonstrados)

Codex CLI Windows somente leitura/efêmero, sessão `01a174ab-3f2e-7a11-b59c-78004aa4b5da`, revisou o código G66 no checkout local, sem editar ou executar testes, rede, GitHub ou provider. Confirmou pela leitura que a política de `Mapping`/nomes sensíveis e a recusa de chaves não-string estão presentes, que a checagem ocorre antes de BEGIN nos caminhos usuais e que os limites G65 de UTF-8 permanecem. A sessão **não** validou resultados de testes nem comprovou diferenças de diff: inspecionou o estado atualmente montado.

**Ainda ABERTO, não corrigido pela G66:**
- `aion_chat.privacy.redact` também atua no chat/store. Um `Mapping` com chave não-string pode produzir `TypeError` ao passar diretamente no redator, sem a checagem específica da Outbox. Em alguns caminhos de store, a chamada de redaction ocorre depois de BEGIN.
- Um `Mapping.items()` personalizado pode mudar de conteúdo entre a inspeção e a redação; G66 não faz snapshot autenticado único nem limita efeitos colaterais de código Python arbitrário.
- Campos `refresh_token`, `private_key`, `authorization ` com espaço e variantes com caracteres invisíveis/Unicode não estão todos no matcher; não se pode inferir DLP universal.
- Nenhuma migração para linhas antigas. Alterar a redaction muda digests/IDs de intents repetidos; leituras históricas que verificam hashes locais não provam ausência de dados antes persistidos em claro.
- Surrogate Unicode isolado ainda pode gerar `UnicodeEncodeError` no `ensure_ascii=False` + UTF-8. A cota 256 KiB é de JSON *admitido*, não de pico de memória da serialização.

**Próximos candidatos G67**, somente com testes RED independentes: Mapping variável em duas visitas; comportamento explícito de `redact` em chat/store com chaves não-string; matriz adicional de nomes e Unicode; regressão histórica pré-G66; exceção e controle de memória para texto excessivo. Nenhum desses problemas foi contado como fechado nesta G66.

## Deliberate limitations / gate

This is pattern redaction, not DLP universal. The shared redactor modifies behavior for chat/store and historic digests, so some previously admitted intents may fail closed on replay. Custom mappings may execute methods with side effects or mutate during iteration; unsupported values may still be stringified via `default=str`. Input materialization and first JSON serialization can consume memory before byte cap. Physical rollback, H0 restart, unknown result after real supplier SEND, true owner identity/authentication and external signed receipts/custody are not verified. No merge, deploy, Worker, provider, real customers/credentials, funds or paid resources.

**0/6 P0 HOMOLOGADOS — HARD NO-GO — UNCERTAIN — ZERO_AUTO_RESEND.**
