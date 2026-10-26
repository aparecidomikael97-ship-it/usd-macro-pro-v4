# AION — Contrato de homologação externa H0 / cinco exigências A184

**Data:** 2026-10-26. **Status:** especificação para futura prova REAL, não aprovação. Responsável pelo plano de ativação: HUMAN_OWNER. **Seis P0: 0/6 homologadas, HARD NO-GO.** Nenhuma alteração de produção/Worker/deploy/primeiro SEND autorizada.

## Princípio central

Um laboratório com chaves no mesmo processo ou dois SQLite no mesmo disco NÃO fornece custódia independente. Uma evidência assinada usando uma chave pública escolhida ou substituída pelo próprio chamador também não estabelece raiz de confiança. A primeira liberação exige prova guardada por uma autoridade que não possa ser rebootstrapada junto com o host AtlasQuant/AION.

## Exigência externa 1 — contador e custódia realmente monotônicos
- Custodiante em domínio de administração, armazenamento e credenciais independente do host, sem recurso host-controlled para apagar/recriar o registro de autoridade.
- Reserva atômica por **identidade imutável do evento de negócio**, com ordinal estritamente crescente, idempotência e durabilidade antes de responder.
- Relatório assinado de checkpoint com contador anterior, contador atual, compromisso do evento e nonce novo.
- Prova adversarial: fazer snapshot/restore/reboot do host + banco local + configurações; o mesmo efeito NÃO recebe uma nova autorização.
- Resposta ausente ou prazo expirado após possível COMMIT = **UNCERTAIN/SPENT**, jamais SEND automático.

## Exigência externa 2 — identidade original autenticada
- Identificador de evento de negócio recebido de fonte verificada fora do pedido operacional da IA.
- Vínculo comprovado com proprietário, empresa/tenant, workspace, ação, payload digest, autorização e política vigentes.
- Não derivar unicidade apenas do idempotency_key/request_id, nem apenas do digest de um payload recorrente: dois eventos legítimos idênticos podem existir.
- Prova adversarial: mudar aggregate_key, recriar host ou apresentar um novo ID técnico não redefine o evento original.

## Exigência externa 3 — raiz de confiança fixa fora do solicitante
- Identidade do atestador e impressão digital de chave pública com provisionamento protegido, rotação/revogação auditável e separação de funções.
- O operador que submete uma intenção não pode mudar o pin, a autoridade ou a chave e em seguida autovalidar sua própria prova.
- Challenge-response assinado com domínio, nonce único, janela de validade, versão/protocolo, operação, ordinal e issuer esperado; conferência da cadeia antes da reserva e depois de COMMIT.
- Prova adversarial: trocar chave+fingerprint local não libera SEND.

## Exigência externa 4 — versão SQLite nativa vinculada à instância viva
- Anexar o estado confiável a identidade de arquivo/hardware/VFS e snapshot/version **efetivamente usado** pela conexão aberta, não apenas path/hash/metadata fornecidos pelo host.
- Antes de permitir leitura de dados sensíveis, demonstrar que os bytes da instância viva pertencem à versão atestada.
- Prova adversarial A183: restaurar bytes antigos no MESMO inode mantendo conexão aberta e exigir StorageUnavailableError antes de qualquer leitura confiável.

## Exigência externa 5 — admissão nativa de escrita resistente a rollback
- Versão/contador externo confirmado + compare-and-swap no ponto de admissão real de gravação SQLite, antes de efeito persistente.
- O bloqueio não pode depender apenas de um wrapper Python, cache local ou callback opcional, que possam ser contornados.
- Prova adversarial A183: restauração same-inode no handle vivo deve negar `create_conversation` e quaisquer outras writers, sem criar uma autoridade nova.

## Fluxo mínimo de uma primeira operação

1. Obter identidade original e autorização do proprietário por meio verificável.
2. Validar pin externo pré-provisionado, política, versão do esquema, desafio novo, high-water e cadeia.
3. Reservar intenção pelo custódio independente, gravando-a **antes** de devolver a prova.
4. Exigir recibo autenticado de COMMIT com o mesmo evento, efeito, decisão, request ID, sequência e desafio pós-reserva.
5. Executar conferências de banco coerentes com o handle VFS nativo e atestação externa.
6. Se qualquer resposta estiver ausente/inconsistente: negar SEND, manter UNCERTAIN e reconciliar sem reenvio.
7. Autorizar execução com limites e observabilidade apenas depois de homologação separada do Worker/fornecedor e cerimônia humana de GO.

## Evidência aceitável / não aceitável

Aceitável: logs do custodiante realmente externo, fonte de tempo e chave provisionadas independentemente, resultados adversariais em Windows/Ubuntu após reinício/restauração, hashes exatos de artefatos e recibos verificáveis fora do host, aprovação humana do GO.

Não aceitável: screenshot de CI verde, assinaturas com chaves sintéticas A180-G111, testemunha em outro SQLite na mesma máquina, hash de arquivo informado pelo host, confirmação local do próprio AION, ou cinco testes RED convertidos em xfail/skip.

## Próxima implantação

Preparar uma arquitetura e orçamento por escrito antes de contratar/integrar serviço externo; respeitar teto operacional vigente e LGPD. Até aprovação explícita do proprietário, manter tudo em LAB/Draft, sem alocar recursos externos, contas, credenciais, custos, deploy ou SEND.

**HARD NO-GO até todas as evidências objetivas de P0 serem verificadas em um ambiente real autorizado.**
