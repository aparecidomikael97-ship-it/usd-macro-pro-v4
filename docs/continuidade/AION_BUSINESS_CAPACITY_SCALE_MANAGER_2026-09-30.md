# Continuidade — AION BUSINESS Capacity & Scale Manager V1

Data: 2026-09-30

## Ponto de partida

Empilhado sobre a camada de Equipe & Acessos / RBAC.

## Bloco

Criado o Gestor de Capacidade & Escala:

- valida digest exato do plano de quotas;
- mede custo por tenant;
- inclui custo compartilhado da plataforma;
- respeita teto inicial de R$200;
- mede suporte disponível;
- mede headroom de infraestrutura;
- verifica margem;
- bloqueia crescimento com tenant sobrecarregado;
- bloqueia crescimento com incidente grave;
- calcula quantidade segura de novos tenants;
- prepara apenas review de admissão;
- nenhuma admissão é automática.

## Estado

Draft PR #437 — AION BUSINESS: capacity and scale manager V1.

IMPLEMENTADO / EM VALIDAÇÃO.

Ainda pendente:
- binding com métricas reais de produção;
- leitura real de custos de providers;
- leitura real de fila/incidentes;
- decisão/aprovação física de onboarding.
