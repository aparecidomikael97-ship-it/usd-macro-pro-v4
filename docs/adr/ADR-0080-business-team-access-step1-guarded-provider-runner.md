# ADR-0080 — Business Team Access Step 1 Guarded Provider Runner

- Status: ACCEPTED
- Data: 2026-09-30
- Escopo: AtlasQuant / AION Business / Equipe & Acessos

## Contexto

ADR-0079 congela a operação Keycloak do Step 1 sem gerar comando executável.

A camada seguinte precisa ser capaz de realizar a mutação física somente quando
o operador local fornecer uma autorização específica e ainda assim manter
fail-closed, localhost-only, sandbox-only e sem append automático no ledger.

## Decisão

Criar um runner local Windows para o Step 1 com dois modos:

1. PLAN ONLY por padrão;
2. APPLY somente com -Apply e token físico exato.

O token físico é derivado do apply_plan_digest e do Step 1:

APPLY_SANDBOX_STEP1_CREATE_INDIVIDUAL_SANDBOX_ACCOUNT_<apply_plan_digest>

Mensagens genéricas como "vamos lá", "ok" ou "pode seguir" não satisfazem esse
token.

## Freshness

O execution envelope precisa ter no máximo 120 segundos no momento do runner
preflight.

Envelope expirado bloqueia tanto PLAN ONLY quanto APPLY.

## Provider

O runner só aceita:

- base URL http://127.0.0.1:<porta>;
- realm atlasquant-sandbox;
- POST /admin/realms/atlasquant-sandbox/users;
- expected status 201;
- username iniciado por sandbox.;
- apply plan íntegro e vinculado ao execution envelope.

## Autenticação

No modo APPLY, o runner obtém um access token efêmero do realm master usando o
client admin-cli e as credenciais bootstrap existentes apenas no env local.

O token:
- fica somente em memória;
- não é gravado no receipt;
- não é impresso;
- é limpo da variável ao final.

## Pre-write / post-write

Antes do POST:
- lookup exato do username;
- se a conta já existir, hard stop.

Depois de 201:
- lookup exato novamente;
- exatamente uma conta deve existir;
- username e enabled precisam coincidir;
- atributos sandbox/session/tenant/step precisam coincidir;
- provider user id precisa existir.

## Receipt

Após sucesso, o runner grava somente receipt sanitizado em LOCALAPPDATA.

O receipt não contém:
- access token;
- bootstrap password;
- authorization token físico.

O receipt também não autoriza append no ledger.

## Estado do preflight

PLAN ONLY:

STEP1_PROVIDER_RUNNER_PLAN_ONLY

APPLY autorizado:

READY_FOR_EXPLICIT_MANUAL_STEP1_PROVIDER_APPLY

## Segurança

Mesmo com APPLY válido:
- produção continua proibida;
- host externo continua proibido;
- ledger append continua separado;
- automatic execution permanece OFF;
- qualquer receipt anterior bloqueia novo apply;
- erro de lookup/status/readback interrompe o fluxo.

## Compatibilidade

Complementa ADR-0078 e ADR-0079.
