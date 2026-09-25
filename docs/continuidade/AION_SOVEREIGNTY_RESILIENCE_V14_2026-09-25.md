# AION — Sovereignty & Resilience Core · Checkpoint V14

Data: 2026-09-25

## Objetivo

Implementar a segunda prioridade da hierarquia técnica oficial: soberania e
resiliência do AION.

O objetivo é impedir que outra IA, agente, tool, documento ou origem externa
ganhe autoridade sobre o AION, e reduzir risco de loop, travamento, consumo
excessivo ou falha em cascata.

## Checkpoint Mestre V14

O Checkpoint passa a persistir a seção:

- `resilience`.

Ela contém, de forma auditável:

- delegações limitadas;
- watchdogs;
- circuit breakers;
- resource governors;
- postura de safe mode;
- digest próprio.

A integridade da seção entra no relatório global do Checkpoint.

## Authority Kernel

Princípios:

- SYSTEM_POLICY autenticada pode impor limites;
- ADMIN autenticado pode emitir intenção, ainda sujeita ao Guardian;
- AION_CORE não possui autoridade raiz independente;
- AGENT só opera por delegação limitada;
- EXTERNAL_AI nunca possui autoridade raiz;
- nenhuma entidade pode ampliar a própria permissão;
- nenhuma delegação altera política.

## Delegação

AION pode orquestrar workers/agentes dentro de capacidade herdada.

Capacidades não delegáveis:

- REAL_TRADING;
- WRITE_SECRET;
- CHARGE_CUSTOMER;
- MERGE_MAIN;
- DEPLOY_PRODUCTION;
- CHANGE_POLICY;
- EXPAND_PERMISSIONS;
- DISABLE_SECURITY.

Mesmo uma capacidade delegável ainda precisa passar pelo Guardian e, quando
aplicável, Proof of Safety.

## Agent Firewall

O firewall verifica:

- tipo da origem;
- capability solicitada;
- workspace;
- delegação válida;
- escopo.

IA externa pode fornecer conteúdo como worker, mas não controla diretamente
tools.

## Watchdog

Sinais:

- heartbeat stale;
- repetição de ação/loop;
- excesso de erros não tratados.

Estados:

- HEALTHY;
- DEGRADED;
- ISOLATE_RECOMMENDED.

O watchdog não mata processo, não deleta dado e não desativa segurança.

## Circuit Breaker

Abre quando há, por exemplo:

- sinal crítico;
- três ou mais falhas consecutivas;
- taxa de erro >= 50%.

Estados:

- CLOSED;
- OPEN;
- HALF_OPEN.

Não existe restart destrutivo automático.

## Resource Governor

Monitora orçamento de:

- chamadas;
- tokens;
- tempo de execução;
- memória.

Estados:

- WITHIN_BUDGET;
- THROTTLE;
- CIRCUIT_BREAK.

Não compra upgrade, não amplia quota paga e não amplia permissão.

## Safe Mode

Estados:

- NORMAL;
- DEGRADED_READ_ONLY;
- EMERGENCY_STOP_RECOMMENDED.

Falha de integridade de autoridade/política ou exposição de segredo leva a
recomendação de parada emergencial. Circuitos abertos/isolamento recomendado
levam a modo degradado somente leitura.

O kill switch real continua dependente de controlador independente.

## Persistência confiável

A partir do V14 também existe migração runtime condicional:

1. lê o Checkpoint atual no `atlasquant-runtime`;
2. verifica integridade;
3. bloqueia se estiver dirty ou corrompido;
4. aplica `ensure_operating_checkpoint` preservando dados;
5. valida integridade da versão nova;
6. grava com SHA condicional;
7. faz readback;
8. verifica novamente.

Não há sobrescrita silenciosa.

## Estado honesto

Implementado:

- contratos determinísticos de autoridade/delegação;
- Agent Firewall;
- Watchdog;
- Circuit Breaker;
- Resource Governor;
- Safe Mode;
- persistência V14;
- migração condicional;
- painel read-only;
- testes adversariais.

Ainda não significa:

- sandbox de sistema operacional ativo;
- kill switch externo fisicamente conectado;
- quarentena real de processo/rede;
- restart automático;
- agente externo com permissão de tool;
- deploy automático;
- trading real.

Esses componentes futuros devem usar este núcleo como gate, não substituí-lo.
