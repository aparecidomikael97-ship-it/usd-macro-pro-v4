# AION — Persistência Runtime Prioridade 1

Data: 2026-09-25

## Objetivo

Fechar a primeira prioridade da hierarquia técnica aprovada: tornar o
Checkpoint Mestre um documento runtime real, verificável e recuperável, sem
confundir código mesclado com persistência.

## Mudanças

### Leitura e escrita separadas

A configuração runtime agora distingue:

- READ_ONLY_PUBLIC: repo/branch conhecidos, sem credencial de escrita;
- READ_WRITE: repo/branch + credencial de escrita;
- UNAVAILABLE: configuração insuficiente ou branch inseguro.

Como o repositório do projeto é público, leitura do Checkpoint pode ocorrer sem
token. Escrita continua exigindo credencial e aprovação explícita.

Nenhum token é retornado por `runtime_configuration_status`.

### Bootstrap idempotente

O workflow `AION Runtime Checkpoint Bootstrap`:

1. gera o Checkpoint canônico a partir do código atual;
2. verifica integridade local;
3. garante o branch dedicado `atlasquant-runtime`;
4. se o arquivo já existir, verifica e NÃO sobrescreve;
5. se não existir, cria `dados/aion/checkpoint_master.json`;
6. lê novamente;
7. valida integridade, versão e trading real desligado.

O workflow usa o token efêmero do próprio GitHub Actions e não grava esse token
no Checkpoint.

### Fundação consolidada

O bootstrap inclui as decisões aprovadas mais recentes, entre elas:

- Memory Fabric;
- confiabilidade de memória;
- Epistemic Core;
- Resolução Científica de Problemas;
- kernel de soberania/resiliência;
- firewall de agentes/sandbox/watchdogs/circuit breakers;
- Data & Event Fabric e Decision Engine;
- observabilidade/autodiagnóstico;
- Creative Fusion com prioridade local/gratuita;
- Cofre Pessoal de Documentos;
- replay cognitivo de trading;
- pós-trade RCA;
- regra mestre de stop/alvo/liquidez;
- hierarquia técnica oficial por dependência/importância.

## Travas

- runtime nunca grava em `main` ou `atlasquant-dev`;
- bootstrap não sobrescreve Checkpoint existente;
- digest divergente bloqueia;
- versão antiga/integridade inválida bloqueia;
- trading real permanece desligado;
- gravação interativa do app continua exigindo credencial + aprovação.

## Verdade operacional

A existência do workflow na main não prova que o arquivo runtime foi criado.
Somente o readback confirmado de
`atlasquant-runtime:dados/aion/checkpoint_master.json` permite declarar a
persistência inicial concluída.

