# AION Intelligence Core

## Visão

O AION é a camada de inteligência e orquestração do AtlasQuant. Ele organiza
capacidades existentes, evidências, memória, especialistas e políticas em uma
experiência simples. Não é uma AGI, não é autoridade autônoma e não transforma
análise em execução.

Princípio: **poderoso por dentro, simples por fora**.

## Inventário reutilizado

O Core evolui a base existente:

- `atlasquant_aion_core.py`: verdade básica, Guardian, custo e missões;
- `atlasquant_aion_cognitive_orchestrator.py`: decomposição, pesquisa e Critic;
- `atlasquant_aion_tool_hub.py`: ferramentas e preflight;
- `atlasquant_aion_fortress.py`: autoridade, autonomia e Proof of Safety;
- `atlasquant_aion_resilience.py`: agent firewall, circuit breaker e safe mode;
- `atlasquant_aion_provider.py`: provider externo fail-closed;
- `atlasquant_aion_dev_fusion.py`: segregação Builder/Reviewer/Breaker;
- `atlasquant_aion_memory.py`: Checkpoint Mestre e persistência;
- `atlasquant_aion_learning.py`: learning signals e promoção humana;
- `atlasquant_aion_observability.py`: eventos auditáveis com redação.

Os novos contratos conectam essas peças; não substituem os módulos de domínio.

## Fluxo central

```text
Interaction
  → AionContext / AionTask
  → Capability Registry
  → Router por metadata + contexto
  → Plano seletivo
  → Specialist Dispatch
  → Critic
  → Validator
  → Truth + Freshness + Safety Gate
  → Resposta / ação apenas proposta
  → memória, observabilidade e learning signal controlados
```

`atlasquant_aion_orchestrator.py` é deliberadamente não executor. Um estado
`READY` significa que o preflight não encontrou bloqueio; não significa que uma
ferramenta foi chamada.

Respostas locais e externas convergem em `ATLASQUANT_AION_RESULT_V1` por
`build_aion_result()`. O envelope preserva `request_id`, `task_id`, capability,
lane do provedor, contagem de evidências e o parecer do Validator/Truth Gate. Uma
resposta sem evidência confirmada permanece `REVISE`; o envelope nunca autoriza
ação externa, escrita automática de memória ou ordem real.

## Capability Registry

`atlasquant_aion_capabilities.py` registra:

- identificador e especialista;
- domínios, descrição e aliases;
- inputs e outputs;
- risco e modo de execução;
- ferramentas permitidas;
- roles permitidas;
- confirmação;
- custo estimado;
- disponibilidade.

O roteamento usa metadata declarada e `domain_hint`. Adicionar capability não
exige editar uma cadeia central de `if/elif`.

Especialistas atuais: Core, Dev, Research, Market, Macro, ICT, Risk, Lab,
Invest, Business, Studio e Admin. Eles compartilham infraestrutura e não ganham
permissões independentes.

## Truth Assessment

`atlasquant_aion_truth.py` preserva:

- `CONFIRMED`, `INFERENCE`, `HYPOTHESIS`, `UNKNOWN`;
- fonte e referência;
- tier da fonte;
- timestamp, TTL, idade, freshness e stale;
- confiança baseada na qualidade da evidência;
- conflito entre fontes.

`CONFIRMED` sem fonte ou timestamp exigido é rebaixado. Dado stale não parece
atual. Valores confirmados conflitantes produzem `CONFLICT`; o AION não escolhe
um silenciosamente. A explicação mostra conclusão operacional, evidências,
conflitos e lacunas, nunca chain-of-thought privado.

## Memória e Checkpoint Mestre

O Checkpoint Mestre v18 inclui `memory_layers`, mantendo compatibilidade com os
checkpoints anteriores e com `persona_memory`.

Camadas:

1. session;
2. working;
3. project;
4. decision;
5. knowledge;
6. user preference;
7. episodic;
8. checkpoint.

Cada entrada contém origem, data, confiança, validade, categoria, versão, tags,
status, `superseded_by`, estado de verdade, persona e referências. Conteúdo
idêntico é deduplicado; atualização preserva o registro anterior como
`SUPERSEDED`. Memória de persona exige correspondência exata para recuperação.
Payload incompatível recupera vazio e registra diagnóstico.

## Developer Engine

`atlasquant_aion_developer_engine.py` estrutura:

```text
REQUEST → PLAN → IMPLEMENT → TEST → REVIEW → RELEASE
```

O workflow exige ordem de fases, evidências, reviewer diferente do builder,
Critic adversarial independente, testes, rollback e documentação. A
autocorreção registra erro, hipótese, causa e evidências e para após três
tentativas. Definition of Done termina em `HUMAN_RELEASE_REVIEW`, nunca merge ou
deploy automático.

O Dev Fusion existente continua responsável pelos gates de Digital Twin,
Breaker e Evaluation Lab.

## Segurança e permissões

- autorização é aplicada na lógica, não somente na UI;
- Admin/Developer/Studio não são expostos a USER;
- Business aceita SALES/ADMIN;
- leitura de mercado/pesquisa pode ser usada por USER sem executar ações;
- ferramenta/capability desconhecida falha fechada;
- custo positivo exige política e aprovação;
- conteúdo externo é evidência, nunca autoridade;
- logs removem padrões de senha, token, chave e Bearer;
- `AION_EXTERNAL_ACTIONS_ENABLED` e `REAL_TRADING_ENABLED` são imutáveis em
  `False` nesta versão;
- real trading continua bloqueado mesmo com role, flag e aprovação.

## Observabilidade

Eventos correlacionam `request_id`, `task_id`, domínio, capability, ferramenta,
duração, resultado, risco, aprovação, fallback e confiança. Payloads de
requisição e credenciais não são registrados.

## Performance e fallback

O plano seleciona apenas capabilities relevantes. Especialista ou ferramenta
indisponível produz `DEGRADED_SAFE` e fallback local read-only que só resume
evidência existente. Providers externos permanecem opcionais, lazy e
desligados sem configuração, orçamento e aprovação.

## Interface

A Central AION mostra:

- AION ONLINE e gates ativos;
- memória em camadas;
- especialista/capability selecionada;
- estado de verdade;
- decisão e bloqueios;
- plano técnico apenas no modo Completo.

O modo Essencial usa o mesmo Core, mas reduz detalhes. A integração preserva o
redesign atual. A prévia também mostra a leitura local do especialista
selecionado.

## Leitura local dos especialistas

`read_specialist_evidence()` reutiliza funções puras já existentes. Ela descreve
somente o que a consulta local contém:

- contrato do universo Forex e fila sem pacote persistido;
- briefing macro sem linhas de entrada;
- matriz ICT/SMC sem evidência registrada, com PPR bloqueado;
- postura de risco quando a integridade não foi comprovada;
- evidência remota de laboratório não carregada, sem ler credencial;
- comparador de investimentos e catálogo de negócios vazios;
- providers de conteúdo não configurados;
- workflow de desenvolvimento incompleto e sem merge/deploy;
- plano de pesquisa não executado;
- inbox administrativa sem checkpoint;
- Guardian negando `real_trade` mesmo com aprovação.

`answer_truth` permanece `UNKNOWN`. Um contrato de código confirmado não vira
resposta da pergunta, cotação, recomendação ou ordem.

## Snapshot de sessão já carregado

`build_specialist_session_snapshot()` aceita somente evidência que o chamador
já tem em memória: scanner persistido, Radar, briefing macro, calendário da
sessão, pesquisa já carregada, backtest registrado, checkpoint administrativo
e estado local de Studio, Negócios ou Investimentos.

A leitura não busca web, feed, calendário remoto, GitHub, banco, API de mercado
nem modelo externo. Cada especialista distingue entrada ausente, presente porém
stale, conflitante ou válida. Snapshot ausente mantém `answer_truth=UNKNOWN`.
Dado stale não vira fato atual. Conflito permanece explícito, sem lado escolhido.

A Central mostra origem (`SESSION`, `CHECKPOINT`, `PERSISTED_SCANNER`,
`RESEARCH_EVIDENCE` ou equivalente), `observed_at`, freshness, `truth_state`,
conflicts e `answers_user_question`. O Guardian continua dono de `real_trade`.

## Limites atuais

- o Core planeja e valida; não é executor universal;
- a leitura local não consulta feed, calendário ao vivo nem store remoto;
- pesquisa web e modelos externos continuam condicionados a providers;
- métricas administrativas externas continuam desconhecidas sem integração;
- memória runtime só pode ser declarada persistida após confirmação do store;
- publicação, cobrança, merge, deploy, secrets e trading real permanecem fora
  da autonomia do AION.

## Specialist Router e certificação de domínio

O AION continua sendo um núcleo. Trader, Business e Investments selecionam,
respectivamente, AION Trader Expert, AION Business Expert e AION Investment
Expert. `AION/CORE` seleciona o AION completo. O contrato está em
`atlasquant_aion_specialist_router.py`. Esse roteador não executa ferramenta
e não transforma `BUSINESS_FUTURE`, `TRADER_FUTURE` ou `INVESTMENTS_FUTURE`
em capability disponível.

Domínio desconhecido permanece `UNKNOWN` / `DENIED_SAFE`. Domínio ambíguo pede
clarificação. Especialista ausente fica `DEGRADED_SAFE`, sem fallback silencioso.
Um perfil pode estar registrado e `NOT_CERTIFIED`. Até a certificação, a
autoridade de runtime não aumenta. O Core coordena e não herda trade, pagamento,
publicação ou deploy.

Memória com domínio não atravessa outro domínio sozinha. Leitura cruzada exige
o perfil `AION_CORE` e o domínio de origem explícito, e não promove `UNKNOWN`,
`STALE`, `CONFLICT` ou `INCOMPLETE`. A certificação desses especialistas é
`ATLASQUANT_AION_SPECIALIST_CERTIFICATION_V1`, descrita em
`docs/aion/AION_SPECIALIST_CERTIFICATION_V1.md`. Ela é distinta da certificação
de skill/plugin. `CERTIFIED` exige evidência explícita e `human_review_approved`
com o booleano `True`. Certificar não ativa o especialista.

ADR-0001, ADR-0005 e ADR-0010 continuam sendo as decisões. Este bloco fecha o
contrato que ADR-0010 deixou pendente de implementação; não substitui esses
registros.

## Architecture Decision Records

Decisões estruturais do Núcleo ficam em `docs/adr/`. O índice é
`docs/adr/README.md`. ADR, nesse registry, significa Architecture Decision
Record. Average Daily Range e American Depositary Receipts não são arquivos
desse diretório. Um ADR substituído não é apagado.

A reconciliação do Checkpoint Mestre de `2026-09-15` a `2026-09-29` está em
`docs/continuidade/CHECKPOINT_MESTRE_RECONCILIACAO_2026-09-29.md`. Ela
complementa `docs/continuidade/CHECKPOINT_MESTRE_ATLASQUANT_2026-09-22.md` e
não o apaga. O gate documental é
`CHECKPOINT_MESTRE_RECONCILIATION_2026_09_15_TO_2026_09_29`.
