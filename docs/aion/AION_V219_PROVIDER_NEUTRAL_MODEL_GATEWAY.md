# AION V2.19 — Provider-Neutral Model Gateway & Local Fallback

**Base:** V2.18 head `9dda9de36986d63e722c427b907ddee3d432ec02`

## Objetivo

Remover qualquer dependência arquitetural do AION Core em um fornecedor específico
de modelo.

O V2.19 cria uma fronteira provider-neutral para registry, health, routing, budget e
fallback. Adapters concretos permanecem substituíveis e ficam abaixo dessa fronteira.

O módulo V2.19 não chama provedor, não lê chave, não executa billing e não executa
ação externa.

## Relação com a infraestrutura existente

O repositório já possui:
- Model Registry;
- Model Router;
- Registry-aware routing bridge;
- gateway local;
- adapter externo OpenAI;
- budget policy;
- fallback local determinístico.

O V2.19 não apaga essas peças.

A decisão arquitetural passa a ser:
- o **Core** depende apenas do contrato provider-neutral;
- `atlasquant_aion_provider.py` continua como adapter concreto/legado compatível;
- OpenAI não é identidade do núcleo;
- novos providers podem ser adicionados por adapters sem alterar o Policy Kernel.

## Registry provider-neutral

`ProviderNeutralModelRegistry` aceita endpoints com:
- provider_id;
- model_id;
- lane;
- health state;
- local/external;
- zero-cost flag;
- enabled;
- priority;
- capability set;
- estimated request cost.

Não há lista hardcoded de fornecedores válidos.

## Lanes

- LOCAL_DETERMINISTIC
- EXTERNAL_FAST
- EXTERNAL_REASONING

Endpoints locais precisam ser:
- LOCAL_DETERMINISTIC;
- zero cost;
- cost = 0.

Endpoints externos não podem fingir ser lane local.

## Local/offline fallback

Uma configuração de produção do Core deve ter fallback local/offline saudável.

`provider_independence_audit` bloqueia quando:
- não existe endpoint local;
- não existe endpoint local HEALTHY.

Um endpoint local DEGRADED pode ser usado como fallback degradado no plano de rota,
mas não satisfaz a certificação de independência.

## Endpoint health

`evaluate_endpoint_health` usa evidência explícita:
- success count;
- failure count;
- consecutive failures;
- heartbeat age.

Sem request evidence, o endpoint fica DEGRADED, nunca HEALTHY por suposição.

Heartbeat stale ou limite de falhas consecutivas => UNAVAILABLE.

## Routing

`route_model_request` considera:
- task class;
- required capabilities;
- privacy sensitivity;
- offline requirement;
- external-model feature posture;
- remaining budget;
- max request cost;
- preferred provider;
- excluded providers;
- health;
- priority.

Task classes:
- GENERAL;
- FAST;
- REASONING;
- PRIVATE;
- OFFLINE.

PRIVATE, OFFLINE ou external disabled forçam lane local.

## Provider failover

Quando o provider preferencial está indisponível:
1. outro endpoint saudável da mesma lane pode assumir;
2. se não houver, rota pode cair para fallback local saudável;
3. se só houver local degradado, o estado é DEGRADED_LOCAL_FALLBACK;
4. sem endpoint elegível, BLOCKED.

Nenhum retry de provider é realizado pelo gateway.

## Budget

Endpoint externo só é elegível se:
- custo estimado <= max_request_cost_usd;
- custo estimado <= budget_remaining_usd.

Se o externo sair do orçamento, o gateway tenta fallback local.

Nenhum billing é feito.

## Privacidade

`privacy_sensitive=True` força rota local.

O gateway não envia payload nem conteúdo para provider. Ele apenas produz uma decisão
de rota.

## Separação entre planejamento e execução

Uma rota pronta contém apenas referência do endpoint.

Mesmo quando externo é escolhido:
- `provider_called=False`;
- `billing_executed=False`;
- `execution_allowed=False`;
- `executes_action=False`.

O adapter concreto só poderá ser chamado por um Execution Gate posterior que componha
Constitution, authority, capability, durable execution, approval e operational posture.

## Independência

A certificação V2.19 exige que:
- nomes arbitrários de providers funcionem no registry;
- pelo menos dois providers externos possam coexistir;
- provider indisponível possa ser substituído;
- fallback local saudável exista;
- Core routing não importe adapter concreto;
- nenhum provider seja autoridade.

## Critério de fechamento

- registry provider-neutral;
- endpoint identity estrita;
- health fail-closed;
- no fabricated health sem evidence;
- task-class routing;
- capability filtering;
- privacy/offline local route;
- budget/cost ceilings;
- preferred/excluded provider;
- external failover;
- local fallback;
- all-unavailable => BLOCKED;
- no provider call inside routing;
- all canonical gates green.
