# AION V2.13 — Real Trust Root & Authority Verification

**Base:** V2.12 head `0552d5b359024eb4e518c6283ac2f4fc7a87cf41`

## Objetivo

Transformar a fronteira fail-closed do V2.12 em uma capacidade criptográfica real de
**verificar autoridade**, sem ainda ligar essa verificação diretamente a execução.

O V2.13 adota Ed25519 por biblioteca criptográfica mantida externamente. O projeto
não implementa algoritmo criptográfico próprio e não armazena chave privada no
repositório.

## Componentes

- `atlasquant_aion_trust_root.py`
  - registry local de chaves públicas;
  - key id + key version;
  - janelas de validade;
  - ACTIVE / RETIRED / REVOKED;
  - revogação explícita;
  - rejeição de arquivo symlink e JSON ambíguo;
  - nenhuma chave privada.

- `atlasquant_aion_nonce_registry.py`
  - SQLite local;
  - unicidade por scope + nonce;
  - transação `BEGIN IMMEDIATE`;
  - persistência entre reinícios;
  - limpeza de nonces expirados;
  - replay protection concorrente.

- `atlasquant_aion_authority_verifier.py`
  - canonicalização determinística do statement;
  - verificação Ed25519;
  - binding obrigatório de subject / tenant / domain / policy;
  - validade temporal;
  - key version;
  - rotação/revogação;
  - nonce persistente;
  - capability grant assinado.

## Separação de autoridade

Um statement assinado e validado pode produzir:

- `authority_verified=True`
- `execution_authority_granted=True`

Mas permanece:

- `execution_allowed=False`
- `approval_implied=False`
- `executes_action=False`

Portanto:

**assinatura válida != aprovação humana != readiness operacional != execução.**

O gate final de execução será responsável por compor, no mínimo, autoridade
criptográfica + policy kernel + approval aplicável + capability scope + runtime
health + tenant/domain isolation + kill-switch state.

## Trust root

O trust root contém somente material público. O provisionamento do arquivo de
trust root é uma responsabilidade administrativa/control-plane e não pode ser feito
por LLM, agente ou payload externo.

A chave privada deve existir fora do código e fora do repositório. O módulo de
produção V2.13 não possui função de geração de chave privada.

## Replay

O nonce é consumido apenas **depois** de:

1. shape válido;
2. janela temporal válida;
3. binding válido;
4. chave conhecida/ativa/não revogada;
5. assinatura válida.

Tentativas inválidas não podem queimar nonce legítimo.

## Rotação e revogação

- uma versão RETIRED não assina nova autoridade;
- uma versão REVOKED é rejeitada;
- uma key id em `revoked_key_ids` é rejeitada;
- versões novas podem coexistir no registry durante migração;
- o statement carrega `key_id` + `key_version` e a assinatura cobre ambos.

## Limites atuais do V2.13

Este bloco **não**:
- ativa Global Worker;
- executa ferramenta externa;
- faz trading;
- autoriza gasto;
- publica/deploya;
- gera chave privada de produção;
- implementa HSM/KMS;
- substitui Windows Hello/FIDO2 para aprovação crítica;
- torna V2.12 automaticamente READY.

Esses limites são deliberados para preservar a separação entre confiança,
aprovação e execução.

## Critério de fechamento V2.13

V2.13 só é considerado tecnicamente validado quando:
- testes de assinatura/tamper/binding/replay/rotation/revocation passam;
- nonce permanece persistente após reopen;
- concorrência permite uma única claim do mesmo nonce/scope;
- nenhum private key material entra no trust-root contract;
- Security / Unified / Quality permanecem verdes;
- supply-chain audit aceita a dependência criptográfica;
- nenhum caminho de execução externa é ativado.
