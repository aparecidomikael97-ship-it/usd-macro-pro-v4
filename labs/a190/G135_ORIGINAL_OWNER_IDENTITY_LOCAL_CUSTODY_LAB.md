# G135 — assinatura da identidade original antes da custódia local (LAB, NÃO P0)

**G135 está empilhado sobre G134 #1626. 0/6 P0 HOMOLOGADAS. HARD NO-GO.**

## Lacuna escolhida

G134 demonstra que o mesmo `tenant/event_id` não deve ser reservado duas vezes quando a custódia local está intacta, mas permite `event_id` rotulado arbitrariamente pelo chamador. Esta variação de laboratório exige que o mesmo registro original, o mesmo hash SHA-256 **canônico da operação econômica** e um documento sintético de identidade com **duas assinaturas Ed25519** (`owner` + `identity_authority`) sejam válidos *antes* de obter a reserva de G134 e de chamar a `ExecutionOutbox` real.

Em nenhum momento a assinatura LAB, o hash, o status `ADMITTED` ou o `lab_verified` permitem SEND. A recuperação após ACK perdido continua `UNCERTAIN/ZERO_AUTO_RESEND`.

## Contrato executável

- Registro original retido: `{event_id, original_sha256, owner_id, tenant_id, workspace_id}`. A igualdade exata é necessária. `request_ref` técnico pode mudar; o identificador original não.
- Operação econômica canônica imutável em LAB: `{action, kind, target, amount_minor, currency}`; hash SHA-256 com serialização canônica da AION. Substituição de conta/valor/moeda é negada.
- Uso do verificador já existente `ExternalAuthorityContractLab` A183: challenge aleatório, instante e validade, epoch, sequência, snapshot das 4 roles, assinaturas específicas `owner` e `identity_authority`. Nenhuma chave privada integrada no código de aplicação; chaves geradas somente no teste.
- Somente após aprovação **sintética** chamar G134: transação `BEGIN IMMEDIATE`, `UNIQUE(tenant,event_id)`, sequência local. Somente após reserva admitir `ExecutionOutbox.enqueue` local; o Outbox padrão mantém a quarentena de SEND.
- Ambos `G135` e `G134` são camadas de teste. O gate G135 existe **fora** de `ExecutionOutbox.enqueue`, então um chamador que pule o bridge ainda consegue fazer *staging local*. Isso não prova SEND.

## 14 provas/contraexemplos

1. Duas assinaturas sintéticas para manifesto imutável: staging LAB elegível, **não** autorização de SEND.
2. `event_id` rebatizado com chave antiga: negado.
3. Alvo, valor ou moeda alterados: negado.
4. Assinatura sob nova chave, raiz retida antiga: negada.
5. Falta assinatura da autoridade de identidade: negado.
6. Desafio alterado ou prova expirada: negado.
7. Falha do provedor simulado de prova, reenvio da mesma prova: negado.
8. Hash do manifesto incorreto ou valor malformado: negado.
9. **RED:** atacante substitui juntamente manifesto original e raiz local: reautorreinscrição passa.
10. Mutação de `dict` do chamador após construção não muda o original retido.
11. Outbox real, restauração somente do banco AION, custódia separada intacta: tentativa repetida é recusada.
12. Outbox real, tentativa com novo evento e manifesto original intacto: recusa antes da reserva.
13. **RED:** nova raiz sintética + falso original no mesmo host permitem duas admissões do mesmo conteúdo econômico.
14. **RED:** chamada direta a `ExecutionOutbox.enqueue` não exige o bridge voluntário; staging local não é envio.

## O que impede homologar

As **raízes**, o **manifesto original**, a **identidade HUMAN_OWNER**, o **relógio** e a **sequência monotônica** ainda são todos fornecidos pelo chamador e/ou mantidos localmente em LAB. A raiz verdadeira teria de ser provisionada independentemente e mantida fora do domínio de rollback do host. Sem isso, assinaturas sob chaves substituídas provam somente consistência matemática. O exemplo contrafactual de self-repin é deliberadamente **RED**. A quebra de identidade original, recibos de provedor e SQLite nativo live same-inode seguem não homologadas em G122.

**Sem Worker, provider real, SEND, deploy, PR merge, custos, credenciais, dados de clientes.** G125 é a bateria canônica inalterada; G122 deve manter os cinco assertions RED até prova genuína. Não desabilitar ou maquiar o G122.
