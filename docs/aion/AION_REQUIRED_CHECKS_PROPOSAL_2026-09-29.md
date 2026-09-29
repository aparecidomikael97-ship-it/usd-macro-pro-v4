# AION — Required Checks / Ruleset Proposal — 2026-09-29

Status: **PROPOSTA SOMENTE LEITURA — NÃO APLICADA**.

Esta página prepara a decisão administrativa sem alterar branch protection, rulesets, permissões ou produção.

## Evidência observada

Leitura do endpoint de rulesets do repositório retornou uma coleção vazia no momento da inspeção.

A leitura direta de `branches/main/protection` retornou `403 Resource not accessible by integration`, portanto **branch protection permanece NOT_VERIFIED** por esta conexão. A ausência de rulesets visíveis não deve ser convertida em afirmação de que toda proteção de branch está desligada.

Uma PR histórica baseada em `main` (#326) executou com sucesso estes workflows:

- **Quality tests** → job `test`;
- **AION Core Security Gate** → jobs `AION adversarial contracts` e `Supply-chain audit`;
- **AION Global Worker Activation Readiness** → job `readiness`;
- **AtlasQuant - Release Readiness** → job `readiness`;
- **AtlasQuant Integration UI Smoke** → job `ui-smoke`.

## Correções CI realizadas na ponta #359

A varredura encontrou dois problemas de cobertura/continuação que poderiam enfraquecer uma futura política de required checks:

1. `aion-core-security-gate.yml` tinha comandos shell sem `\` antes do último teste, podendo tratar o arquivo seguinte como comando separado;
2. `quality-tests.yml` não listava três testes AION já existentes e, depois do hardening atual, também precisava registrar o novo teste residual.

Na ponta #359, o gate foi corrigido e agora inclui explicitamente:

- Critical Review;
- Global Worker inflight reconciliation;
- Global Worker inflight resolution;
- resource bounds base;
- resource bounds residual;
- supply-chain pinning.

A Quality Suite foi reconciliada contra a árvore atual: **331 arquivos root `test_*.py`, 331 registrados, zero ausentes e zero extras** na ponta #359.

A trilha visual #358 também foi reconciliada: **331/331 root tests registrados**, incluindo o contrato do cockpit.

## Conjunto proposto de checks obrigatórios

### Núcleo mínimo recomendado

Para qualquer PR destinada a `main` que toque o AION/Núcleo:

1. `Quality tests / test`
2. `AION Core Security Gate / AION adversarial contracts`
3. `AION Core Security Gate / Supply-chain audit`
4. `AION Global Worker Activation Readiness / readiness`

### Camada de release

Antes de uma integração destinada à publicação/produção:

5. `AtlasQuant - Release Readiness / readiness`
6. `AtlasQuant Integration UI Smoke / ui-smoke`

Os nomes acima foram observados em execução real do GitHub Actions; não foram inventados.

## Política sugerida

- bloquear merge se qualquer check obrigatório estiver ausente, falhando ou cancelado;
- não aceitar `UNKNOWN` como sucesso;
- required checks devem apontar para nomes estáveis de job/workflow;
- nenhuma exceção automática para administrador;
- mudanças de ruleset devem exigir revisão humana;
- não habilitar auto-merge/deploy como consequência destes checks;
- Worker Readiness continua read-only e não equivale a ativação do worker;
- Release Readiness não equivale a autorização de deploy;
- UI Smoke não substitui testes de segurança.

## Ação administrativa pendente

**NÃO EXECUTAR automaticamente.**

A próxima decisão humana é escolher/aplicar a proteção administrativa do repositório usando o conjunto acima, depois confirmar por leitura que os contexts exigidos ficaram ativos.

Até essa confirmação:

- `RULESET_STATE = NOT_VERIFIED`
- `BRANCH_PROTECTION_STATE = NOT_VERIFIED`
- nenhuma resposta do AION deve afirmar que `main` está protegida por required checks.

