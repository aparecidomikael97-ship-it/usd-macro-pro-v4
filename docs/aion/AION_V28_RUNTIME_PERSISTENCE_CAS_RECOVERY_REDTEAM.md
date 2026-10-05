# AION Core V2.8 — Runtime Persistence, CAS and Recovery Red-Team

Base: `f48434977a76daf0865da9881d4f7439ef3d5485`.

## Resultado

A auditoria confirmou três falhas reais em `load_runtime_checkpoint`:

1. JSON com chaves duplicadas era aceito pelo parser padrão.
2. Base64 com caracteres inválidos era aceito por `b64decode` não estrito.
3. O campo `encoding` era ignorado, permitindo valores explicitamente incompatíveis.

A correção alinha o runtime loader ao hardening já existente em `load_checkpoint_revision`:

- resposta deve ser Mapping;
- `content` deve ser string;
- encoding explicitamente incompatível é rejeitado;
- ausência de encoding preserva o default `base64` por compatibilidade;
- whitespace externo no base64 é normalizado;
- tamanho encoded é limitado antes do decode;
- decode usa `validate=True`;
- tamanho decoded continua limitado por `MAX_RUNTIME_BYTES`;
- JSON usa duplicate-key rejection.

## Bugs reproduzidos

### Duplicate JSON keys

Antes: last-key-wins silencioso.

Depois: `ERROR / ValueError`.

### Base64 não estrito

Antes: caracteres como `@@@` podiam ser ignorados.

Depois: decode estrito falha fechado.

### Encoding incompatível

Antes: `encoding="utf-8"` era processado como base64.

Depois: somente base64 canônico é aceito; ausência preserva o default compatível.

## Hipóteses que permaneceram fail-closed

- encoded size bound;
- receipt target/intent tampering;
- lost-response reconciliation;
- CAS/write SHA conflict;
- recovery candidate revalidation.

## Lost response

`reconcile_runtime_write` distingue:

- `CONTENT_CONFIRMED`: conteúdo bate, mas não é possível atribuir unicamente o write;
- `CONFIRMED`: write aceito e SHA/digest batem;
- `CONFLICT`: conteúdo ou SHA divergem;
- `WAITING`: runtime ainda não pode confirmar o estado.

`automatic_retry` nunca é promovido a verdadeiro por essa reconciliação.

## Recovery

`restore_checkpoint_revision` faz novo load da revisão histórica e novo preflight antes de salvar. Um candidate alterado após o primeiro preflight não recebe passe permanente.

## Rede e efeitos externos

Os testes V2.8 usam mocks de transporte. Nenhuma chamada real de provider, billing, broker ou ordem é necessária para provar os contratos desta branch.

## Limitações

Ainda não provados nesta entrega:

- matriz HTTP completa de PUT/readback;
- concorrência CAS com writers independentes;
- multiprocess do durable store;
- TOCTOU determinístico de symlink;
- todos os caminhos de global worker arming;
- execução de rede real, deliberadamente proibida.

## Política de segurança

Recovery/persistence não concede autorização operacional. Persistência confirmada não equivale a approval nem execução.

ZERO MERGE. ZERO DEPLOY. ZERO PROVIDER. ZERO BILLING. ZERO PAID API. ZERO REAL ORDER. ZERO EXTERNAL EXECUTION.
