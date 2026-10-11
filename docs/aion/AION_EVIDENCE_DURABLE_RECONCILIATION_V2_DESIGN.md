# AION — reconciliação durável de evidências V2: projeto, sem ativação

Status: DESIGN / REFERENCE_ONLY / HARD NO-GO (#1117).
Nenhum adaptador de produção, serviço, credencial, testemunha ou autorização real.
O contrato atlasquant_aion_v2_evidence_reconciliation_contract.py não é importado
pelo Autopilot e não pode liberar seu bloqueio incondicional.

## Reuso de mecanismos reais existentes

| Código / símbolo lido | Reuso previsto / limite real |
|---|---|
| atlasquant_aion_core_intelligence/context.py / Context.key | binding de tenant/workspace/actor/task/domain; o objeto fornecido pelo caller não autentica esses valores. Arquivo congelado intacto. |
| atlasquant_aion_v2_one_shot_unknown_outcome_journal_reference.py / ReferenceOneShotUnknownOutcomeJournal.prepare_reference_only, claim_reference_only, mark_unknown_reference_only | intenção antes do claim; BEGIN IMMEDIATE; sequência e integridade locais; replay negado. SQLite local não é testemunha independente. Seu schema é provider/budget específico: não fabricar campos de orçamento para encaixar Shadow/Flight. Reusar os mecanismos mediante adaptação de propósito revisada, sem um CAS concorrente. |
| atlasquant_aion_v2_isolated_sqlite_witness_cas_reference.py / mecanismo CAS SQLite existente | concorrência/conexões e perda de resposta como referência; continua restaurável junto com o journal. Não instalar outro SQLite como suposta segunda autoridade. |
| atlasquant_aion_v2_authenticated_witness_read_cas_reference.py / review_reference_witness_cas_preconditions | verifica matemática de desafios/head/generation. Pins e desafios do caller não são enrollment nem leitura independentemente confiável. |
| atlasquant_aion_v2_dispatch_journal_dual_witness_reference.py / review_dual_witnessed_journal, review_one_step_claim_fence_preflight | comparar head/sequence/snapshot e fence entre duas referências; restaurar journal e ambos os heads antigos ainda pode passar matemática. |
| atlasquant_aion_v2_unknown_outcome_reconciliation_reference.py / review_provider_outcome_observation, review_manual_reconciliation_candidate | separar observação e revisão humana; assinaturas sintéticas não provam vendor billing, presença do proprietário ou autorização. Não reutilizar purpose de provider como recibo de GitHub. |
| atlasquant_aion_v2_legacy_github_contents_readback.py / decode_verified_github_contents, verify_legacy_jsonl_readback | bytes, blob SHA, PUT receipt e GET correspondente. Não prova sozinho qual operação causou o conteúdo nem origem independente/durabilidade. |

## Contrato implementado nesta fase, somente referência

build_reference_intent vincula bytes exatos (máximo 1 MiB, bytes estritos), SHA256,
Git blob SHA, tamanho, nonce não zero e scope fechado: tenant, workspace, actor,
task, domain, repo, branch, sink, path e policy_generation. Shadow/Flight usam
os caminhos reais dos stores; branches de código e rotas inválidas são recusadas.
operation_id é o hash de domínio do descritor completo; semantic_id exclui o nonce
para identificar o mesmo conteúdo reembrulhado com nonce novo. O nonce da fixture
não é geração segura de challenge; produção requer fonte autenticada apropriada.

review_reference_observation exige descritores idênticos, scope/content binding,
state DISPATCH_CLAIMED ou UNKNOWN_OUTCOME, generation coerente e bytes idênticos.
O semantic_id não fecha sozinho a troca de task/policy/scope. O journal futuro
precisa manter todas as pendências por destino e scope autenticado estável;
novo task_id, generation ou nonce nunca pode ignorar uma operação antiga incerta.
Correspondência resulta em PENDING_RECONCILIATION, nunca SAVED/ALREADY_PRESENT.
Falha resulta em HARD_DENY ou pendência de leitura; todas as permissões ficam false.
Não há argumentos approved/admin/test bypass e não há clear de quarentena.

## Protocolo futuro obrigatório, ainda NÃO implementado em produção

1. **Escopo autenticado:** tenant/workspace/actor/task/domain fornecidos pela
   fronteira autenticada, não por browser ou flag. Destination repo/branch/path,
   credencial/identidade do writer e geração de policy também vinculados.
   Não ler nem mesclar cache de outro scope; contexto desconhecido bloqueia.
2. **Registro antes da escrita:** persistir intenção exata e hash do payload,
   preimage/blob esperado, operação/semantic_id/nonce e parent/revision esperados
   em journal validado. Resultado da transação precisa ser conhecido antes do send.
   Falha/ACK perdido na preparação exige read-only reconcile, nunca tentar enviar.
3. **Claim externo:** CAS global por identidade semântica/nonce sob generation e
   revision esperadas. Registrar fencing token/sequence antes de qualquer possível
   envio; dois hosts/escritores devem disputar o mesmo registro, não cópias locais.
   Reabrir journal não concede outro claim. SQLite de referência não fecha isso.
4. **Monotonicidade:** head protegido fora do domínio restaurável do journal,
   challenge fresco, geração/epoch e high-watermark independentes. Divergência,
   head faltante, comunicação perdida ou recuperação de backup mantêm PENDING.
   Sem comprovação independente de freshness, match de hashes não libera nada.
5. **Envio único:** o vínculo claim/intenção/writer deve ser irreutilizável. Após
   DISPATCH_CLAIMED, assumir possível envio mesmo se a queda antecedeu HTTP.
   Não existe transação atômica SQLite + GitHub + duas testemunhas: projetar
   protocolo de crash/commit explícito, sem chamar essa composição de atomicidade.
6. **Observação somente por leitura:** GET autenticado, sem redirect, status e
   bytes verificados; observar commit/parent/autor e recibo exato por operação,
   conteúdo/scope/fence/geração. Presença de um ID ou GET 404 não prova que o
   write anterior não ocorreu. Conteúdo igual não prova causalidade do PUT.
   Exigir origem/evidência independente; mismatch de conteúdo ou SHA bloqueia.
7. **Queda/reinício:** PREPARED órfão não permite send automático; CLAIMED sem
   resultado vira UNKNOWN/PENDING; readback perdido preserva incerteza; corrupção
   bloqueia sem reset/migração permissiva. Reconciliar o journal contra os heads
   antes de qualquer ação; manter ambos os registros históricos se houver conflito.
8. **Revisão humana distinta:** decisão assinada/autenticada e challenge fresco,
   vinculada ao operation_id, conteúdo, scope, evidência, heads, geração e decisão.
   Reconhecer resultado é diferente de conceder nova ação. Nem ACK nem confirmação
   antiga podem gerar retry. Uma retomada requer nova autorização específica,
   novo claim validado e regra explícita para a operação antiga não ser repetida.
9. **Dois escritores e resposta perdida:** um único vencedor do CAS pode continuar
   a fase permitida; perdedor reconcilia por leitura. Lost ACK depois de commit não
   refaz CAS com outro nonce. Novo nonce para o mesmo semantic_id não é bypass.
   Timeout/409/422 não concedem outra escrita; todas as fontes de erro são redigidas.
10. **Revogação/rollback:** invalidar autorizações antigas por epoch/policy/fence;
    consultar autoridade independente após reinício. Não aceitar um head antigo
    apenas porque journal/assinatura também foram restaurados. Sem autoridade
    disponível, operações antigas permanecem UNKNOWN e Autopilot HARD_DENY.

## Estados e ausência de autorização implícita

| Situação | Estado seguro |
|---|---|
| Autopilot atual, qualquer sessão/processo | HARD_DENY / DURABLE_CLAIM_REQUIRED; nenhum builder/writer executado |
| Pendência conhecida no consumidor atual | UNKNOWN_OUTCOME / reconciliation_required=True; apenas captura local |
| Readback de referência correspondente | PENDING_RECONCILIATION; content_match_reference_only=True |
| Ausência de GET, 404 ou ACK perdido | UNKNOWN/PENDING; ausência observada não comprova não execução |
| Escopo/geração/content/SHA corrompido | HARD_DENY; sem inferir estado forte |
| CAS local, assinatura de fixture ou aprovação bool | referência não confiável; execution_authorized=False |

## Isolamento e limites de segurança

Sessões Streamlit independentes usam session_state distintos; teste não mostrou
mistura de dados/marcadores entre duas sessões sintéticas. Isso NÃO comprova
separação autenticada de empresas dentro da mesma sessão ou do mesmo repo de dados.
Os consumidores legados não recebem Context autenticado e usam arquivos comuns
por repo/branch. O novo contrato separa scopes por hash, mas ainda não está conectado
à UI/store. Essa lacuna permanece HIGH; o sistema não está pronto para multi-tenant.
Não fabricar tenant default nem tratar um campo do pedido como identidade aprovada.

A quarentena dos consumidores é RAM por sessão: restart/new session pode perdê-la;
check e write não têm claim global. O bloqueio do Autopilot fecha novas escritas
nesse caller mesmo em processo novo, mas não resolve operações antigas, writers
diretos fora desse caller, testemunhas ausentes ou persistência real. Não liberar
uma pendência limpando session_state, trocando branch ou ativando uma flag.

Critérios futuros de aceite: scope autenticado/isolado; intenção persistida;
CAS/fence externo verificável; fresh heads sob custódia independente; crash matrix
sem segundo send; reconciliação com evidência e revisão humana distintas; nenhuma
reutilização de nonce/semantic_id; testes locais, entre processos e entre máquinas
mais provas físicas separadamente autorizadas. Até lá: PARTIALLY_CLOSED/HARD NO-GO.
