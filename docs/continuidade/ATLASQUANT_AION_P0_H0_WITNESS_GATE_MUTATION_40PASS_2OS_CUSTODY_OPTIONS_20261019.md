# Checkpoint Mestre — H0 externo: travas contra regressão + seleção de custodiante, 40/40 por SO

**Data 19/10/2026. ESTADO: 0/6 P0 homologados, HARD NO-GO, Worker OFF, ZERO_AUTO_RESEND.** Nada foi mesclado em main, implantado em Render/PC, provisionado ou pago. Nenhuma testemunha foi inscrita, nenhuma credencial real consultada, nenhum produtor acionado, nenhuma mensagem enviada.

## Onde retomamos

Rodada precedente `lab/aion-p0-h0-boot-first-effect-readonly-20261019` demonstrou com SQLite concreto e restore manual: após perda da transição `UNCERTAIN`, um banco antigo pode reaparecer coerente como `PENDING`. Um diagnóstico exclusivamente local NÃO pode comprovar ou excluir rollback. H0 observador foi validado 45/45 por SO no [workflow #39323959715](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39323959715). Ele não está integrado ao boot do produto e continua bloqueando tudo.

Nesta rodada, confirmei a proteção estrutural **já existente**:
- `atlasquant_aion_global_worker.py`: `run_global_worker_once` tem bloqueio `INDEPENDENT_SOURCE_WITNESS_NOT_ENROLLED` ANTES da tentativa de lease CAS/executor, e o escritor diretamente invocável `_persist_runtime_checkpoint_cas` retorna bloqueio sem I/O. Um GET de leitura/validação de checkpoint anterior ao gate NÃO autentica a fonte.
- `atlasquant_aion_execution_outbox.py`: `dispatch_claimed` e `reconcile` não chegam ao fornecedor sem `INDEPENDENT_PRODUCER_NOT_ENROLLED`.
- `aion_chat/store.py`: caminho genérico de restore da branch LAB barra banco de origem/destino contendo tabelas de execução; backup só de chat continua.
- `atlasquant_aion_global_worker_readiness.py`: independent witness obrigatório no painel de readiness.
- `atlasquant_aion_p0_h0_sqlite_startup_observer_lab.py`: H0 diagnóstico inicia `BLOCKED`, flags de autoridade false, CLI return=2.

## Implementação verificável (somente AST, sem runtime de efeitos)

- Branch isolada `lab/aion-p0-h0-external-custody-gate-drift-20261019`, a partir de `437ed74011f570d8d77587e676fa57292dd9bc4e` (observador H0 e documentação).
- `atlasquant_aion_p0_h0_boundary_drift_sentinel_lab.py`, commits `5abf4cb33b39a60f2cf5258bc1efd44413878e48` e revisão para docstring `dac0b1ade3ad75576abf7de0ab67c4c6e7f257e4`. Analisa AST do código local, sem importar módulos de execução. Confronta travas hard-stop, posição antes de primeira chamada CAS/executor, checagens source/target restore e flags falsos do H0. Saída `SOURCE_INVARIANTS_OBSERVED_NOT_AUTHORITY` (não READY), `external_witness_enrolled=false`, `highwater_authenticated=false`, `first_effect_authorized=false`. Em caso de desvio sai 2.
- `test_aion_p0_h0_boundary_drift_mutations_lab.py`, commit `fc69893d7f065d18cc12510f7725e2c61a9d8a71`: 15 testes, incluindo exclusão/movimento em memória de bloqueio do Worker, exclusão das duas barreiras Outbox, retirada de checagens source/target restore, perda do blocker de readiness, flip de flags falsos do H0 e mudança indevida do exit code 2 para 0.
- Workflow read-only `.github/workflows/aion-p0-h0-boundary-drift-mutation-lab.yml`, commit `9ad36611349ec099361a1207070a68d70ed35502`, depois inclusão de instalação de dependências históricas `ee90b6f47f916f57c56f8b1dadb0c2712f2bd64f`. Blobs das quatro fontes anteriores fixados no CI. Os testes de mutação são **em memória e não modificam os arquivos do repositório**.
- Documento de decisão arquitetural e avaliação de custodiantes em `docs/aion/AION_P0_H0_INDEPENDENT_HIGHWATER_CUSTODIAN_OPTIONS_NO_GO_20261019.md`, commit `40b1d27827ca1840b37c67437d1d76f37630f7bf`. Sem provisionamento, sem assinatura, sem escolha contratual.

## CI — preservar falha de infraestrutura e GREEN real

- [Actions #39325290345](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39325290345): os 15 testes de mutação e 16 do H0 já passaram, mas o histórico A73 não importou por `ModuleNotFoundError: No module named 'requests'` na CI mínima que não instalava `requirements.txt`. **Esse RED inicial é uma falha de ambiente, não bypass encontrado.**
- Após incluir instalação das dependências `requirements.txt` já fixadas no repo, [Actions **#39325439437**](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39325439437) concluiu **completed/success** nos DOIS runners:
  - Ubuntu job `118309941140`: **15/15** testes de mutação + **16/16** H0 SQLite + **9/9** A73 witness/A110 sem efeito = **40/40 PASS**.
  - Windows job `118309941254`: mesmas contagens **40/40 PASS**.
  - Total **40 cenários distintos, 80 execuções PASS**; pinos `P0_H0_FOUR_SAFETY_SOURCES_PINNED` nos dois logs.
- **Atenção à semântica do teste:** `PASS` em teste de mutação significa que a estrutura alterada foi **detectada como regressão**, não que o teste autorizou Worker ou provou independência externa. Uma AST estática pode não reconhecer bypasses semânticos, de runtime, dependências, código dinâmico ou mudanças adversariais simultâneas no próprio sentinel. Isto é *regression tripwire*, não verificação formal nem uma barreira produtiva nova.

## Opções externas realmente pesquisadas (NENHUMA selecionada)

1. **Cloudflare Durable Objects com SQLite:** docs públicas de outubro de 2026 confirmam armazenamento fortemente consistente e transacional, DO SQLite compatível com Workers Free e limites de armazenamento gratuitos. A possibilidade de PITR/rollback **do próprio custodiador** exige governança/admin separados, uma trilha imutável sob terceiro domínio e key custody independente; uma conta Cloudflare compartilhada com o executor é INSUFICIENTE.
   - https://developers.cloudflare.com/durable-objects/api/sqlite-storage-api/
   - https://developers.cloudflare.com/durable-objects/platform/limits/
   - https://developers.cloudflare.com/workers/platform/pricing/
2. **AWS DynamoDB em conta separada:** `UpdateItem(ConditionExpression)` dá atualização condicional com disputa CAS; `GetItem(ConsistentRead=true)` dá leitura fortemente consistente do item; IAM e custo precisam de desenho/estimativa e proibição de `DeleteItem`, restore e poderes de administração no executor. Chave assinante/verificação/alta-water fora do domínio de ataque ainda não existem.
   - https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/WorkingWithItems.html
   - https://docs.aws.amazon.com/amazondynamodb/latest/APIReference/API_GetItem.html
- Critério comum: não é suficiente só ter outro banco. Precisa **conta/controle distintos, autenticidade do emissor com chave PINNED, epoch e sequência monotônicos, CAS de primeira tentativa, nonce single-use, resposta vinculada a owner/tenant/host/intenção e readback forte**. O custodiador NÃO é o produtor externo, não comprova SMS entregue nem prova no-effect terminal, não habilita reenvio.
- Orçamento: preservar R$200/mês, sem novas contas/contratações, sem Worker da Cloudflare nem Redis/Render/AWS reais sem aprovação. Trabalharemos em opções documentadas, sem custos.

## Pendência / próxima barreira

Para um verdadeiro P0 H0 ser superado, faltam a **escolha e matrícula autenticada de um custodiante com autoridade administrativa separada**, assinatura de registro, monotonic CAS remoto, witness fresco no boot/antes de primeira tentativa e testes de duas máquinas, perda de resposta, replay/rollback do custodiador, crash físico e revisão Security/Quality integral. Se o custodiador não responde, nenhuma primeira ação pode ser admitida. Mesmo isso não substitui prova do produtor, HUMAN_OWNER ou os outros P0.

**Decisão operacional mantida:** 0/6 P0 homologados. HARD NO-GO. ZERO_AUTO_RESEND. Worker desligado. Nenhum merge/deploy/gasto, nenhuma ação externa executada.
