# A182 — vínculo com intenção original e limites da confiança local (LAB)

**22/10/2026. HARD NO-GO. 0/6 P0 homologados. ZERO_AUTO_RESEND.**
Somente efeitos e chaves sintéticos; nenhum merge, deploy, Worker, operação real, serviço, cadastro, cobrança ou credencial de provedor.

## Base, isolamento e procedência
Inspecionada PR Draft #1471 (A181), aberta, não merged, base A180 `lab/aion-p0-preflight-witness-a180-20261022`. Head observado: `e58fd2b073f4eddb46d406da9b62e85bbe350aca`; código A181 anteriormente testado em `72fe8d7e033b1cc43d6ad144c9c554d12edbeb20`. Relatórios A176–A181 e matriz lidos nessa árvore, não presumidos presentes em main. A176 #1466 → A177 #1467 → A178 #1468 → A179 #1469 → A180 #1470 → A181 #1471 é a cadeia documentada; a base efetiva desta alteração é exclusivamente o head A181 acima.

Ramo remoto novo `lab/aion-p0-intent-binding-a182-20261022`, criado nesse SHA. Checkout preexistente /workspace/usd-macro-pro-v4 permaneceu no ramo work, limpo, commit `5744b2b`. Fetch bloqueado pelo proxy; ambiente também esteve temporariamente indisponível. Testes feitos em /workspace/work/a182-source, cópia parcial de 136 arquivos obtidos via conector GitHub no SHA fixo, com identidade de blob Git conferida individualmente. Não é checkout completo nem Quality canônica. Alterações remotas construídas sobre a árvore original via Git Data API, preservando arquivos não tocados.

## Fluxo, invariantes e fronteiras de confiança
1. Outbox.enqueue calcula chave por IDs técnicos, payload e escopo, persiste action_decisions/action_outbox numa transação. Idempotência pelo mesmo intent_ref não equivale a identidade de negócio autenticada.
2. claim_next usa BEGIN IMMEDIATE e lease. Somente PENDING/RETRY podem ser reclamados. Expiração de CLAIMED anterior ao dispatch pode gerar RETRY.
3. dispatch_claimed relê intenção/lease/autorização e orçamento; grava condicionalmente CLAIMED→UNCERTAIN **antes** da consulta à testemunha. Mudança concorrente de claim bloqueia. Incerteza de reserva não volta à fila.
4. A180 verifica desafio, assinatura, intenção completa, escopo, prazo e sequência; A181 lê custody_meta/first_attempts, faz BEGIN IMMEDIATE, insere reserva UNIQUE por digest e avança high_water; COMMIT precede assinatura e retorno. Perda de resposta/assinador após COMMIT mantém reserva, sem envio.
5. Somente guard literal True permite adapter.send. Recibo não verificável não confirma efeito nem autoriza retry. Reconciliação UNCERTAIN/SENT jamais retorna RETRY por flags do adaptador.
6. Saga.enqueue_next e enqueue_next_compensation usam o mesmo Outbox; sync_forward_outcome/sync_compensation_outcome propagam SENT/UNCERTAIN como incerteza e bloqueiam avanço/compensação indevida. Isso não prova auditoria de todos os callsites operacionais.

Chamador controla configuração de guard/verificador, decisão original, pins, relógio, revogações e checkpoint locais. Adaptador não é fonte de autoridade independente. Dois SQLite e duas assinaturas locais continuam sob o mesmo domínio de controle. Autoridade de bootstrap, identidade empresarial, proveniência de raiz e monotonicidade externa **não foram estabelecidas**.

## Contraexemplos antes dos controles
`before-controls.log` registra 19 execuções: 15 A181 carregadas pela importação original da classe fixture e quatro caracterizações A182. O carregamento duplicado foi corrigido com importação de módulo; os totais finais não incluem essa duplicação. Não foi uma suíte de proteção vermelha: asserts verdes documentam violações.
- A182UnresolvedRiskTests.test_altered_aggregate_same_adapter_effect_replayed_a181: mesmo payload/efeito do adaptador contador sintético, outro request e aggregate alias → novo digest → segunda chamada. O contador não prova equivalência de um provedor real.
- A181 test_06/test_07: wipe + bootstrap novo, ou restauração de snapshot da custódia, reabrem reserva.
- A181 test_14: guard injetado sempre True contorna testemunha.
- A180 test_14 e A178/A179: repinagem da raiz pelo chamador admite falsa autoridade.
- A181 test_01/test_02/test_03/test_10: perda/restauração apenas do host com custódia íntegra, resposta perdida e oito conexões concorrentes preservam bloqueio.

## Controle implementado, estritamente opt-in LAB
`aion_chat/intent_binding_a182_lab.py` adiciona BoundFirstAttemptWitnessLab, callback compatível com first_attempt_guard. Nenhuma ligação com Worker operacional nem substituição do caminho A181 histórico.
- Captura bytes canônicos da decisão **original fornecida antes do dispatch**. Somente intent_ref, decision_id, idempotency_key e aggregate_seq técnicos são excluídos. Payload, digest recalculado, escopo, alvo, ação, autorização, política, datas e demais campos ficam vinculados. Campos adicionais do candidato também divergem. Ordem de chaves JSON é canônica; não se presume equivalência de aliases, Unicode ou comportamento de provedor.
- Mutação posterior do dict original não altera os bytes capturados. Ausência/inconsistência do vínculo é negada; alterações no candidato são negadas antes de consultar/reservar custódia.
- Fingerprint esperado da configuração deve ser fornecido separadamente antes da verificação; mudança unilateral de chave/emissor/revogação é rejeitada. Configuração revogada nega mesmo com fingerprint correspondente.
- Checkpoint exige formato exato, inteiros não booleanos, count=high_water e ordinal não inferior ao mínimo retido. Ausência/ambiguidade/rollback abaixo desse mínimo bloqueiam. Isso é comparação local, **não atestação de monotonicidade**; restauração conjunta derrota o controle.
- Reserva/recibo continuam verificados pelo A180. Lock serializa o estado em memória deste guard; unicidade entre conexões segue na transação A181.
- Não há bootstrap automático, descoberta/aprendizado do vínculo pelo candidato nem autorização para reenvio.

Limitação deliberada: quem pode criar outro guard com outra decisão original, outro fingerprint e outro checkpoint pode reconfigurar todo o LAB. O objeto Python não resiste a um operador privilegiado, monkeypatch, substituição de código ou controle do host. O original local não é uma identidade empresarial comprovada; o digest A180 ainda pode bloquear recorrências legítimas idênticas. Tempo/revogação são snapshots de fixture, sem consulta dinâmica externa.

## Reproduções e execução
Da raiz do repositório:
```sh
python -B scripts/run_a182_lab.py regression
python -B scripts/run_a182_lab.py sqlite
python -B scripts/run_a182_lab.py external-red
```
Dependências de CI existentes e fixadas: cryptography==50.0.2, requests==2.34.2. Runner bloqueia conexões socket no processo de teste; não constitui firewall de SO nem prova de isolamento físico. Subprocessos SQLite temporários não herdam esses mocks.

Validação local:
- Regressão inicial A176–A181/Outbox/Saga: 110/110.
- Final: **132/132** (22 A182 + 110 históricos), in-process network guard. Dos 22 A182, 15 são proteção e sete são caracterizações de risco.
- SQLite: **93 executados, 92 aprovados, 1 ERROR** por requests ausente no teste que instala mocks de requests. Instalação bloqueada pelo proxy; teste não removido, resultado não chamado de verde.
- Ambiente local Python 3.12, cryptography 50.0.0 pré-instalado, diferente de 50.0.2 fixado em CI. Não foi possível instalar a versão fixada localmente.
- Primeira execução dos controles: um ERROR de fixture (store.connection inexistente), corrigido para out.db. Não era falha adicional de segurança.
- Qualidade canônica completa, VFS nativa, infraestrutura externa, disponibilidade H0, falhas de rede entre autoridades e identidade real não executadas.

## RED por desenho — sem mascaramento
`lab_a182_external_requirements_red.py`: **3 FAIL, 0 ERROR**, exit 1, sem expectedFailure/skip/continue-on-error:
1. Custódia e checkpoint restaurados juntos deveriam negar: aceitam.
2. Substituição da intenção original por outra inscrição deveria ser detectada: aceita.
3. Substituição conjunta de raiz e fingerprint deveria ser detectada: construtor aceita.
São requisitos externos não resolvidos, não regressões inadvertidas. Workflow novo executa regression, sqlite e external-red em Ubuntu/Windows. Os dois jobs external-red devem falhar e manter CI global vermelho enquanto essas garantias faltarem. Jobs verdes de regressão não homologam produção.

## Contrato externo verificável necessário
| Requisito | Evidência objetiva para revisão humana |
|---|---|
| Identidade original imutável | emissão de ID por autoridade autenticada, vínculo assinado ao proprietário/escopo/intenção original e regras de equivalência/recorrência; ensaio de aliases e novos IDs sem nova autoridade |
| Reserva anterior ao efeito | protocolo documentado de reserva linearizável, unicidade por evento autêntico e COMMIT durável antes da autorização; corrida multiprocessos/máquinas e perda de ACK |
| Custódia monotônica independente | domínios administrativos/físicos distintos, journal/quórum não restaurável junto ao host; apagar/restaurar host, custódio e snapshots antigos sem reabrir efeito |
| Bootstrap/recovery | gênese/epoch autenticados, reinscrição somente por cerimônia revisada, impedimento de substituição silenciosa; recuperação de perda total preserva tombstones |
| Raiz e revogação | origem de chave autenticada fora do adaptador/host, rotação/revogação auditáveis, anti-rollback de versão e fail-closed para estado desconhecido/antigo |
| Recibos e consulta H0 | assinatura da fonte externa, vínculo a intenção e efeito, completude de consulta, sequência/checkpoint verificáveis, disponibilidade/recuperação testadas na infraestrutura-alvo |
| Não reenvio | timeout/partição/ACK perdido/recibo inválido → quarentena; nenhuma nova tentativa por novo ID, reconciliação negativa ou bootstrap local |

Esses requisitos não autorizam contratação, provisão, cadastro, uso de chaves reais ou decisão de autoridade. Esse trecho fica bloqueado para revisão humana. Nenhum serviço foi criado/contatado para produzir efeito real.

**0/6 P0 homologados. HARD NO-GO. ZERO_AUTO_RESEND.**

