# AION B2B — Owner Renewal Review V1

Status: **staging / owner-only / review-only**.

## Objetivo

Transformar o ciclo recorrente value-bound em um pacote de revisão do proprietário.

Nenhuma decisão comercial é executada automaticamente. O módulo apenas organiza a
evidência e apresenta alternativas de revisão compatíveis com o estado do serviço.

## Estados aceitos

- `HEALTHY / RENEWAL_REVIEW_CANDIDATE` → revisão de renovação;
- `REMEDIATION / REMEDIATE_REVIEW` → revisão de remediação;
- `CAPACITY_HOLD / CAPACITY_REVIEW` → revisão de capacidade;
- `INCIDENT_REVIEW` → revisão de incidente.

## Alternativas de revisão

As alternativas retornadas são rótulos de decisão humana, não comandos. Exemplos:

- renovar como está;
- renovar com mudanças;
- não renovar;
- revisar remediação;
- revisar capacidade;
- revisar preço;
- revisar pausa;
- revisar encerramento.

Nenhuma dessas opções é executada pelo módulo.

## Expansão e continuidade

O pacote preserva a linhagem da conversão value-bound:

- `EXPANSION_COMMERCIAL_REVIEW_CANDIDATE`;
- `CONTINUE_COMMERCIAL_REVIEW_CANDIDATE`.

Isso mantém expansão e continuidade como candidatas à revisão do proprietário,
sem autorização automática.

## Dados internos

O pacote é `owner_only=true` e `customer_visible=false`.

FinOps e custo operacional podem existir para decisão interna, mas não devem ser
repassados diretamente ao Portal do Cliente.

## Limite de autoridade

Permanecem bloqueados:

- escolha automática do proprietário;
- renovação;
- expansão;
- troca de pacote;
- pausa;
- encerramento;
- cobrança;
- repricing;
- aumento de quota;
- mudança de role;
- mudança de integração;
- contato com cliente;
- provisionamento;
- provider;
- CRM write;
- deploy;
- mutação de produção.
