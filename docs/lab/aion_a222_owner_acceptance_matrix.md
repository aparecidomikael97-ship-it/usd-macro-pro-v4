# A222 — Matriz de aceite do proprietário (SEM DECISÃO EMITIDA)

**Status:** Draft de laboratório, somente perguntas e controles; **HARD NO-GO · P0 externo 0/6 · UNCERTAIN=ZERO_AUTO_RESEND**.

O A221 definiu o formato de 13 provas que ainda precisamos adquirir de fontes externas. A222 é um formulário seguro para **Mikael decidir em outra etapa** se prefere priorizar raiz offline, KMS/HSM com gestão separada, ou manter os dois em avaliação. Não preenche escolhas, notas, custos, fornecedores, equipes nem aprovações por conta própria.

## Decisão em linguagem simples

| Pergunta para você | Offline (sob seu controle) | KMS/HSM (domínio externo separado) |
|---|---|---|
| **1. Independência:** o computador não consegue usar a chave sozinho? | Verificar custódia física e aprovação fora do host | Verificar negação de `Sign`, mutação de política e escalada do host |
| **2. Recuperação:** se perder chave ou acesso, como voltar? | Procedimento de cópias, quórum, guarda e restauração | Procedimento de lockout, disable/destruição, recuperação e incidentes |
| **3. Continuidade:** se alguém faltar ou o serviço cair? | Sem custodiante, cerimônia não ocorre | Dependência de IAM, região, rede e serviço |
| **4. Trabalho de custódia:** quem executa a rotina? | Pessoal, dispositivo e cerimônias físicas | Políticas, permissões, reconciliação, logs e administração |
| **5. Auditoria:** alguém independente detecta fraude e rollback? | Testemunha e checkpoint fora do host | Audit log e checkpoint fora das permissões comprometíveis |
| **6. Revogação/rotação:** como desativar chave antiga? | Cerimônia, troca e publicação independente da revogação | Estados/versões e negações efetivas verificadas em outro domínio |
| **7. Custo contínuo:** quem paga e aprova? | Equipamento, armazenamento, backup, pessoal: **não cotado** | Chaves, operações, serviço, logging, equipe: **não cotado** |
| **8. Adequação:** atende ao seu ritmo de uso? | Mais controle manual, possível atrito operacional | Mais automação possível, exige governança de permissões |

**Nenhuma coluna ganhou nota de segurança.** O critério que pesa mais é uma escolha sua; valores e disponibilidade precisam de evidência real. O sistema não deve tratar uma preferência de interface como assinatura jurídica, contratação, credencial ou homologação P0.

## Responsabilidades a definir por aceite explícito

| Função | Responsabilidade futura |
|---|---|
| `OWNER_DECISION_MAKER` | Definir prioridades e autorizar ou rejeitar a arquitetura e escopos |
| `OFFLINE_KEY_CUSTODIAN` | Guarda física e recuperação da raiz, se esse modelo for adotado |
| `KMS_POLICY_ADMIN` | Administrar ciclo e permissões das chaves com segregação real |
| `KMS_SIGN_OPERATOR` | Operar assinatura sob autorização separada do administrador |
| `INDEPENDENT_WITNESS` | Registrar checkpoints e detectar adulteração independentemente |
| `RISK_REVIEWER` | Aprovar procedimentos adversariais, outage, recuperação e risco |
| `PROVIDER_RECEIPT_AUDITOR` | Confrontar recibos financeiros e consultas autoritativas do provedor |

**Todos os nomes, contatos, identidades e autorizações estão `UNASSIGNED/NOT_OBTAINED/NOT_CONTACTED/NO_AUTHORITY_GRANTED`.** Esse é o estado honesto enquanto não houver designação externa e aprovação específica. A escolha de uma função não autoriza o host a exercê-la.

## Portões antes de qualquer homologação externa

Os 13 controles do A221 permanecem no estado:
- `review_state=NOT_STARTED`;
- `external_evidence_state=NOT_OBTAINED`;
- `acceptance_state=NOT_REQUESTED`.

Isso inclui custódia offline, negação `Sign` e de alteração de política KMS, aprovação independente, separação de papéis, nonce, revogação, logs, falha fechada, recibo externo real e isolamento de tenant. **Ter 13 itens escritos não significa aprovar 13 itens** nem altera os seis P0 oficiais, que continuam em **0/6**.

## Protocolo de aceite proposto, em duas etapas separadas

**Etapa A222 (agora, somente pesquisa):**
1. Publicar perguntas, categorias, responsáveis e gates em Draft.
2. Testar que o host não consegue escolher preferências, dar nota, designar pessoas, fabricar prova ou aprovar orçamento.
3. Rodar regressões, sem gastar, contratar, criar chaves, enviar mensagens ou abrir acesso.

**Uma etapa futura, se Mikael solicitar separadamente:**
1. Ouvir prioridades reais do proprietário e registrar um formulário de intenção **que não é autorização operacional**.
2. Submeter custos/fornecedores/procedimentos e identidades a nova revisão humana.
3. Se e somente se houver autorização explícita separada, estudar eventual sandbox com auditoria independente.
4. A homologação P0 exigirá prova externa real e critérios próprios; não virá de um formulário assinado pelo host.

## Código e limites

- `labs/a222_owner_acceptance_matrix.py`: esquema estrito, escopo owner/tenant/workspace, 8 critérios `UNRANKED`, 7 papéis `UNASSIGNED` e 13 gates `NOT_STARTED`.
- `labs/test_a222_owner_acceptance_matrix.py`: 40 testes de negação de seleção de modelo, score inventado, aceite do host, orçamento, identidades, P0 falso, credenciais e JSON ambíguo.
- Workflow A222: 40 testes próprios + 470 regressões A202–A221 = **510 testes por sistema operacional** em Ubuntu/Windows, actions pinadas.
- Hash SHA-256 do formulário = identificação local do rascunho, **não é assinatura, aceite nem prova externa**.
- Resultado invariável: `owner_preferences_recorded=False`, `responsibilities_assigned=False`, `external_proof_accepted=False`, `owner_signoff_valid=False`, `external_p0_homologated=0`, `may_select_model=False`, `may_commit_budget=False`, `may_contact_provider=False`, `may_provision=False`, `may_sign=False`, `may_connect=False`, `may_confirm=False`.

Referências técnicas primárias:
- NIST SP 800-57 Part 1 Rev. 5 (final), ciclo de vida de chaves: https://csrc.nist.gov/pubs/sp/800/57/pt1/r5/final
- AWS KMS, segregação entre administradores e usuários: https://docs.aws.amazon.com/prescriptive-guidance/latest/encryption-best-practices/kms.html
- Google Cloud KMS, separação de funções: https://docs.cloud.google.com/kms/docs/separation-of-duties

**Decisão A222 atual: `AWAITING_OWNER_PRIORITIES`. Nenhum modelo escolhido, nenhum orçamento autorizado, nenhuma raiz homologada. HARD NO-GO.**
