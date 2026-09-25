# AION — Memory Reliability + Epistemic Core — Checkpoint V15

Data: 2026-09-25

## Objetivo

Fechar a prioridade técnica nº 3 da hierarquia:

**Confiabilidade de Memória + Epistemic Core**

Persistência runtime e soberania/resiliência já foram confirmadas antes deste
bloco. V15 acrescenta uma camada determinística para decidir quando uma memória
pode ser usada como evidência atual, quando precisa de ressalva e quando deve ser
bloqueada/reverificada.

## Memory Reliability

Cada revisão de memória pode registrar:

- referência e tipo de memória;
- versão;
- estado de verdade;
- fontes/proveniência;
- referências de evidência;
- digest do conteúdo;
- data observada/revisada;
- validade;
- contradições;
- supersessão;
- confiança de conhecimento;
- revisor.

### Regras fail-closed

- CONFIRMED sem proveniência ou digest -> VERIFY_REQUIRED;
- memória contraditória -> CONFLICT/BLOCKED;
- memória superseded -> BLOCKED;
- memória CONFIRMED expirada -> rebaixada para INFERENCE;
- ação sensível exige memória CURRENT + CONFIRMED + proveniência + digest;
- memória nunca autoriza ação;
- memória nunca amplia permissão;
- memória histórica nunca confirma mercado atual sozinha;
- confiança de conhecimento não é probabilidade de lucro.

## Epistemic Core

O núcleo classifica o estado da evidência como:

- SUPPORTED;
- PARTIAL;
- RESEARCH_REQUIRED;
- VERIFY_REQUIRED;
- CONFLICT;
- INSUFFICIENT_EVIDENCE.

Ele pode exigir pesquisa/reverificação ou reduzir força da resposta.

Ele **não** pode:

- executar ferramenta;
- autorizar publicação/gasto/deploy;
- expandir autoridade;
- habilitar trading real.

## Decision Snapshot / Replay Receipt

V15 inclui recibos de decisão para reconstruir:

- contexto;
- evidências;
- checklist;
- regime;
- tese;
- stop;
- alvo;
- versão do modelo;
- estado de verdade;
- momento/data dos dados.

Isso permite RCA e replay posterior sem reescrever o que o AION sabia na hora.

## Integração

O gate epistemológico entra em:

- Checkpoint Mestre V15;
- integridade/digest;
- migração runtime;
- AION Gateway local;
- prompt do provedor externo.

Memória recuperada entra como conteúdo/evidência, nunca autoridade.

## Runtime

A mudança em `atlasquant_aion_memory.py` aciona o workflow de migração do
runtime. A conclusão só deve ser declarada depois de:

1. PR verde;
2. merge na main;
3. workflow de migração verde;
4. readback direto do `atlasquant-runtime` mostrando V15 e
   `memory_reliability`.

## Restrições preservadas

- custo zero padrão;
- nenhum serviço pago ativado;
- nenhuma publicação automática;
- nenhum deploy automático por este núcleo;
- trading real permanece bloqueado.
