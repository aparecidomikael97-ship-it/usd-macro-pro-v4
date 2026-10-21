# AION P0-H0 — triagem de garantias reais do fornecedor (21/10/2026)

**Estado:** laboratório, somente avaliação negativa. Sem fornecedor vinculado, sem compra, sem credencial, sem Worker, sem envio, sem merge e sem deploy. **HARD NO-GO · 0/6 P0 homologados · ZERO_AUTO_RESEND.**

## Decisão arquitetural

O SQLite local consegue perder ou restaurar o histórico de uma primeira tentativa. Em testes existentes do `ExecutionOutbox` real, um snapshot antigo pode fazer `PENDING` parecer novamente elegível a um claim — isso NÃO atravessa a barreira efetiva de envio porque `dispatch_claimed` segue bloqueado antes de acessar o adaptador. **A ausência de prova local é diferente de uma prova independente de ausência de efeito.** Nenhum recibo sintético adicional, mesmo com sete assinaturas Ed25519 matematicamente coerentes sob chaves do chamador, resolve a custódia real.

É necessário separar quatro contratos, de domínios independentes:

1. **Reserva da primeira tentativa, previamente durável e externa ao executor:** request/intent/nonce/operação, escopo, hash canônico, contador monotônico, época e proof-of-consumption. Em indisponibilidade, negar primeira emissão e reenvio.
2. **Fornecedor real:** origem autenticada da chave/conta, sem que o chamador possa substituí-la; prova causal para aquela primeira operação, não apenas um `2xx` ou estado local `CONFIRMED`.
3. **Frescor e no-effect fence:** readback exaustivo por tentativa e versão mais recente independente; se `NO_EFFECT_FENCED`, fence real que impeça efeito tardio da primeira chamada. Falta de resultado em `GET` ou listagem não basta.
4. **Proprietário, aprovações, governança:** HUMAN_OWNER autenticado, contas e domínios administrativos separados, rotação/revogação atualizadas, Quality/Security completas verdes e teste de recuperação com falha injetada. Sem qualquer um, o Worker permanece desligado.

## Entrega deste bloco

O arquivo `atlasquant_aion_p0_h0_provider_capability_review_lab.py` recebe um manifesto de **alegações**, não um certificado. Examina nove capacidades declaradas: idempotência no servidor, escopo e retenção, deduplicação após timeout, consulta exata da tentativa, consulta exaustiva de efeitos tardios, fencing de não execução, recibo originário, última cabeça autenticada e custódia atômica off-host.

Cada capacidade pode ser declarada `CLAIMED_SUPPORTED`, `DECLARED_UNSUPPORTED` ou `UNKNOWN`. Nenhuma delas passa a "verificada" mediante texto, links HTTPS, hashes, recibos do chamador ou a alegação de um atendente. O algoritmo sinaliza lacunas para futura diligência; **todos os resultados** têm:

- `state=HARD_NO_GO`, `allowed=False`, `external_truth=UNKNOWN`, `reconciliation_state=UNKNOWN_BLOCKED`;
- `automatic_retry_allowed=False`, `manual_resend_allowed=False`, `worker_arming_allowed=False`, `outbox_terminal_transition_allowed=False`;
- nenhum efeito, consulta de rede, alteração de Outbox, validação independente ou custo externo.

A rota `SUPERVISED_RECONCILIATION_NO_RESEND` significa **investigar humanamente**, não aprovar reenvio manual. Até documentos oficiais exigem verificação de versão, contrato da conta, escopo, latência, retenção, concorrência e fornecedor real em um ambiente futuro autorizado.

## Observações sobre Twilio — sem equiparar superfícies diferentes

- **Programmable Messaging clássico:** `POST /2010-04-01/Accounts/{AccountSid}/Messages.json` cria um recurso de mensagem. Em resposta de suporte encaminhada ao projeto, foi informado que o recurso não oferece token de idempotência e que, após falha da chamada, a busca é por destino/origem/data. A declaração de suporte não é teste de protocolo nem garante ausência de mensagem.
- **Twilio Comms API v1:** é uma superfície de API **distinta**. Sua documentação de listagem descreve filtros por `operationId`, canal, datas e paginação e alerta que dados anteriores a **sete dias** podem estar incompletos. Essas consultas não constituem por si só readback exaustivo ou fence.
- **Mensagem agendada:** a documentação descreve cancelamento de mensagem **agendada**; não se deve generalizar isso para qualquer envio já aceito na fila.

Fontes de revisão documental:
- https://www.twilio.com/docs/messaging/api/message-resource
- https://docs.comms.twilio.com/comms-api-reference/messages/list
- https://www.twilio.com/docs/messaging/features/message-scheduling

Nenhuma chamada à API da Twilio foi realizada neste bloco, e nenhuma capacidade idempotente é presumida para a Comms v1. Antes de qualquer integração real, é indispensável confirmar diretamente com a Twilio **qual produto/API contratado** está em uso e quais garantias contratuais existem.

## Matriz adversarial

`tests/test_aion_p0_h0_provider_capability_review_lab.py` contém 44 métodos: afirmações de todas as capacidades suportadas, declarações de lacunas críticas, respostas 2xx/404/timeout, paginação incompleta, agendamento cancelado, links falsamente invocados como autoridade, entradas hostis, chaves extras `authorized=True`, tipos não canônicos e combinação de sintomas. Mesmo quando os 44 passarem, **a conclusão continua NO-GO**: só valida a classificação negativa em LAB.

O workflow paralelo Ubuntu/Windows roda os 44 testes novos e regressões selecionadas do Outbox real. A comprovação de PASS depende de execução finalizada no SHA exato; a Quality completa histórica (52 FAIL + 34 ERROR na última referência) segue sem dispensa.

## Próxima decisão que realmente destrava H0

Obter especificação oficial e evidência operacional de um fornecedor/custodiador **independente**, com garantia contra a primeira tentativa incerta e rollback físico, antes de implementar qualquer integração real. Se nenhum fornecedor cumprir o contrato, manter operações com resultado incerto em **reconciliação humana sem reenvio**, ou redesignar o protocolo. O alvo não é aumentar o número de assinaturas locais: é estabelecer uma fronteira de verdade externa comprovável.

**Nenhum P0 homologado. Não liberar o Worker.**
