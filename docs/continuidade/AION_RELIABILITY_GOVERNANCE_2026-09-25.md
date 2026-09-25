# AION — Reliability & Governance

Data de consolidação: 2026-09-25

## Objetivo

Garantir que o AION continue útil quando fontes, APIs, memória, produção ou
orçamento estiverem parciais, divergentes ou indisponíveis, sem inventar saúde
e sem executar contenção sozinho.

## Data Guardian e reconciliação de fontes

Cada observação pode registrar:

- fonte/provedor;
- afirmação ou métrica;
- valor;
- estado de verdade;
- disponibilidade;
- saúde;
- idade e idade máxima;
- criticidade;
- quota/custo quando disponível.

Estados de fonte:

- OK
- DEGRADED
- STALE
- CONFLICT
- UNAVAILABLE
- UNKNOWN

Quando duas ou mais fontes frescas e confirmadas discordarem sobre a mesma
afirmação, o estado permanece CONFLICT. O AION não escolhe uma fonte
silenciosamente.

## Modo degradado

Estados:

- NORMAL
- DEGRADED_SAFE
- FAIL_CLOSED

Em modo degradado o AION pode explicar, organizar evidências e orientar
revalidação. Capacidades dependentes de evidência ausente não podem ser
apresentadas como saudáveis.

FAIL_CLOSED é acionado para condições críticas, como conflito crítico de fonte,
incidente crítico, conflito do Checkpoint ou divergência de integridade.

Trading real permanece sempre bloqueado nesta fundação.

## Cost Guardian

Regras:

- custo zero é o padrão;
- nenhuma cobrança ou upgrade automático;
- nenhuma troca silenciosa para fonte/provedor pago;
- consumo estimado próximo ao teto gera WARNING;
- teto atingido gera BLOCKED_LIMIT;
- rota gratuita/local deve ser preferida quando puder cumprir a tarefa.

## Proteção da memória

O Checkpoint Mestre é protegido por:

- digest de integridade;
- SHA do runtime;
- escrita condicional;
- detecção de conflito entre runtime e alterações locais;
- aprovação explícita para persistência;
- bloqueio de sobrescrita quando há conflito ou mismatch.

## Incidentes

Conflitos críticos de fonte entram no Centro de Incidentes.
Limite de custo também pode gerar incidente administrativo de governança.

Nenhum incidente executa:

- contenção automática;
- rotação automática de segredo;
- correção automática de conta;
- rollback automático;
- deploy automático.

## Rollback

Rollback é advisory-only.

O sistema pode recomendar revisão de rollback quando houver evidência explícita,
mas a execução depende de processo autorizado e revisão humana.

## Respostas do AION

A resposta local e o prompt para modelo externo recebem:

- Reliability posture;
- modo degradado;
- quantidade de conflitos de fonte.

Se houver conflito, o AION deve descrevê-lo e pedir/recomendar reconciliação,
nunca escolher uma versão escondido.

## Travas permanentes

- Failover automático: DESATIVADO.
- Reparo automático: DESATIVADO.
- Rollback automático: DESATIVADO.
- Fallback pago automático: DESATIVADO.
- Trading real: BLOQUEADO.
