# ADR-0072 — Business Team Access Windows Operator Baseline Handoff

- Status: ACCEPTED
- Data: 2026-09-30
- Escopo: AtlasQuant / AION Business / Equipe & Acessos

## Contexto

O Windows Operator Kit produz dois artefatos separados: readiness e baseline.
Eles não podem ser combinados livremente, pois isso permitiria misturar um
readiness antigo com um baseline de outra execução.

## Decisão

Adicionar um operator_session_id não sensível e aleatório ao readiness local.

O mesmo ID é propagado pelo Operator Kit para a coleta do baseline.

O handoff só pode avançar quando:
- readiness validado;
- baseline validado;
- ambos possuem operator_session_id válido;
- os IDs são idênticos;
- baseline não é anterior ao readiness;
- digests são válidos;
- ambos permanecem não autorizadores;
- reviewer é explícito.

## Estado máximo

READY_FOR_ADMIN_TEAM_ACCESS_REAL_BASELINE_ACCEPTANCE_REVIEW

Esse estado não aceita o baseline automaticamente. Ele apenas forma um pacote
coerente para revisão administrativa.

## Segurança

O operator_session_id:
- não é secret;
- não contém credencial;
- não identifica usuário do sistema operacional;
- serve apenas para binding entre artefatos da mesma execução lógica.

O handoff:
- não inicia Docker;
- não cria conta;
- não habilita MFA;
- não grava registry;
- não revoga sessão;
- não autoriza lifecycle;
- não autoriza produção/deploy/runtime.

## Compatibilidade

Complementa ADR-0066, ADR-0071 e o fluxo ADR-0067 até ADR-0070.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
