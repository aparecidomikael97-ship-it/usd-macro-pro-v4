# AION V2.17 — Multi-Agent Governor & Memory Governance

**Base:** V2.16 head `a094d9ce0381854f6361eef58194f8afccbd8097`

## Objetivo

Fechar a governança de coordenação multiagente e uso operacional da memória sem
transformar supervisor, agente ou memória em fonte de autoridade.

O V2.17 reaproveita:
- Loop Governor;
- Autonomy Budget;
- Resource Governor;
- Memory Contract V2.3;
- Memory Architecture;
- V2.15 Capability Isolation;
- V2.16 Operational Resilience.

## Governor multiagente

`govern_multiagent_session` adiciona ao Loop Governor existente:

- supervisor canônico;
- raiz única ligada ao supervisor;
- linhagem `delegated_by -> parent_id`;
- capability request limitada pelo teto recebido do host;
- deadline global da sessão;
- deadline por nó;
- custo já consumido + custo planejado;
- limite de custo;
- profundidade;
- fan-out;
- limite de nós;
- calls/tokens/wall time/memory budget;
- detecção de ciclo e parent dangling herdadas do Loop Governor.

### Supervisor

O supervisor/orquestrador coordena, mas não vira root authority.

Resultado positivo significa apenas:

`state=WITHIN_GOVERNANCE`

Ainda permanece:
- `grants_permission=False`;
- `execution_allowed=False`;
- `starts_agent=False`;
- `starts_worker=False`;
- `executes_action=False`.

### Delegação

Cada filho precisa declarar `delegated_by` igual ao parent real do plano.

Isso bloqueia:
- cadeia de delegação adulterada;
- root alegando ter sido delegado por outro agente;
- capability fora do teto;
- loops;
- profundidade/fan-out excessivos;
- orçamento estourado;
- deadline inválido.

O V2.17 não substitui a verificação criptográfica V2.15 no execution gate. O teto
recebido pelo governor serve para planejamento; execução futura deve revalidar o
scope assinado.

## Memory Governance

`govern_memory_use` recebe um `MemoryContractRecord` tipado e combina:

- validation state;
- provenance/evidence;
- tenant scope;
- persona scope;
- confidence;
- valid_from;
- expires_at;
- retention;
- sensitivity;
- tombstone state.

### Memória operacional

Para ser `USABLE`, a memória precisa:
- estar VALIDATED;
- ter evidência/provenance;
- corresponder ao tenant confiável;
- corresponder à persona confiável quando aplicável;
- atingir confidence mínima;
- estar dentro da janela temporal;
- não estar tombstoned;
- não estar conflicting/outdated/doubtful/quarantined/rejected/unverified.

Mesmo `USABLE`:
- `grants_permission=False`;
- `grants_authority=False`;
- `changes_policy=False`;
- `execution_allowed=False`.

Flags escritas dentro de metadata não alteram isso.

## TTL e retenção

SESSION e PROJECT exigem `expires_at`.

LONG_TERM e UNTIL_SUPERSEDED podem permanecer sem expiry explícita, desde que todo
o restante esteja válido.

LEGAL_HOLD nunca recebe tombstone automático por expiração.

## Expiração sem apagar auditoria

`build_expiry_tombstone` cria somente uma proposta de tombstone versionado:

- versão = versão anterior + 1;
- previous_version aponta para o memory_id anterior;
- rollback_pointer preserva referência;
- digest do registro anterior fica na metadata;
- original não é apagado;
- persistência não é automática.

Portanto esquecer/expirar conteúdo operacional não destrói a trilha auditável.

## Relação com as camadas anteriores

- V2.13: authority criptográfica;
- V2.14: durable execution;
- V2.15: capability/tenant/workspace/domain scope;
- V2.16: postura operacional;
- V2.17: coordenação multiagente + governança temporal/escopo da memória.

A execução real continua posterior e deve compor todas as evidências necessárias.

## Critério de fechamento V2.17

- supervisor raiz canônico;
- delegation lineage validada;
- ciclos/dangling/depth/fan-out bloqueados;
- capability escalation de planejamento bloqueada;
- deadline global e por agente;
- call/token/wall/memory budget;
- cost budget;
- tenant/persona memory isolation;
- validation/provenance/conflict governance;
- confidence mínima;
- TTL/validity window;
- retention;
- legal hold;
- tombstone auditável e não destrutivo;
- memória não concede permission/authority;
- plano multiagente não inicia agente/worker;
- gates canônicos verdes.
