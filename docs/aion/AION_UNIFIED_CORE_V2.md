# AION Unified Core V2 — integração segura sobre a main de 2026-10-03

## Escopo

Esta etapa consolida as duas lacunas identificadas pela auditoria de duplicação:

1. fundação de chat persistente da PR #543, portada de forma aditiva sobre a main atual;
2. fachada unificada `AionRequest -> AionResponse` sobre os módulos existentes.

Ela **não cria um quarto orquestrador** e não substitui os módulos maduros de verdade, memória, checkpoint, autorização, model routing, receipts, tenant ou recovery.

## Reuso deliberado

A fachada `atlasquant_aion_unified_runtime.py` compõe:

- `atlasquant_aion_orchestrator.orchestrate`;
- `atlasquant_aion_cognitive_orchestrator.route_specialists`;
- `atlasquant_aion_truth.assess_truth`;
- `aion_chat.authorization.classify_action`;
- `atlasquant_aion_model_router.route_intelligence`;
- `atlasquant_aion_action_receipt.seal_action_receipt`;
- `atlasquant_aion_internal_roles.internal_roles_snapshot`.

O runtime não chama provider e não executa ferramentas.

## 8 papéis oficiais

A fachada expõe os oito papéis oficiais:

1. Orquestrador / Núcleo;
2. Arquiteto / Estrategista;
3. Guardião / Auditor;
4. Prime / Execução;
5. Shadow / Pesquisa e Triagem;
6. Sentinel / Monitoramento;
7. Comercial / Leads e CRM;
8. Educador / Treinamento.

Os IDs antigos permanecem legíveis por compatibilidade. Isso evita migrar ou quebrar dados existentes durante esta etapa. Papéis são responsabilidades dentro de **um único AION Core**.

## Chat e Checkpoint Mestre

Os checkpoints de conversa continuam separados do Checkpoint Mestre.

A integração oferece duas operações explícitas:

- `prepare_checkpoint_export`: prepara candidato scoped e nunca salva;
- `save_approved_checkpoint`: exige `explicit_approval=True` e receipt de aprovação não vazio, delegando a persistência ao `CheckpointMasterAdapter` injetado.

Não existe promoção automática de conversa para memória oficial.

Eventos de memória recebidos no `source_context` saem como `PROPOSED_ONLY` e exigem validação de verdade + política de checkpoint.

## Provider e custo

O runtime apenas usa o roteador de modelo para planejar lane.

- padrão: `ZERO_COST_LOCAL`;
- external feature desligada por padrão;
- provider não pronto + external feature ligado => `PROVIDER_UNAVAILABLE`;
- nenhuma chamada externa é feita;
- nenhum billing é executado.

## Segurança

A fachada:

- valida owner/tenant/workspace do contexto fornecido;
- bloqueia `source_context` cross-tenant/cross-workspace;
- não executa ação externa;
- não habilita ordem real;
- ações desconhecidas permanecem `BLOCKED`;
- ações sensíveis permanecem `REQUIRES_APPROVAL`;
- emite action receipt com fingerprint canônico, explicitamente não tratado como assinatura.

## Port da PR #543

A branch antiga da #543 não foi mergeada nem rebased.

Os 16 arquivos novos da fundação foram copiados de seu head validado para a branch criada da main atual. Isso evita carregar a base antiga e preserva o histórico da PR original para auditoria.

O arquivo `atlasquant_aion_chat_ui.py` foi portado, mas **não foi ligado à aplicação principal nesta etapa**, preservando a fronteira com o trabalho de interface em paralelo.

## Fora de escopo nesta etapa

- ligar Chat AION à UI de produção;
- provider real;
- execução de ferramentas;
- e-mail/publicação/merge/deploy;
- trade real;
- migração destrutiva dos IDs de papéis antigos;
- persistência automática no Checkpoint Mestre;
- alteração do shell/interface em trabalho paralelo.

## Próximas integrações

Após validação desta Draft PR:

1. adapter concreto Chat -> Checkpoint Mestre;
2. adapter Chat -> Biblioteca para anexos explicitamente enviados à análise;
3. journal genérico de request/task do runtime unificado;
4. recovery de tarefas do chat nos estados duráveis existentes;
5. provider real apenas atrás dos gates, orçamento e aprovação já existentes.
