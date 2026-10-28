# A223 — Preferência de pesquisa: 1 · Segurança e controle máximo

**Estado:** anotação de preferência conversacional, sem autenticação ou assinatura do proprietário. **HARD NO-GO · P0 externo 0/6 · `UNCERTAIN=ZERO_AUTO_RESEND`.**

Mikael respondeu **“1”** à escolha entre (1) segurança e controle máximo, (2) facilidade de operação, (3) recuperação/continuidade e (4) custo. Este laboratório **anota apenas a prioridade geral para organizar a pesquisa**. A escolha não significa escolher raiz offline ou KMS/HSM, aprovar investimento, nomear custodiantes, demonstrar evidência, assinar documentos ou liberar funcionamento real.

## Como aplicar a prioridade sem escolher uma tecnologia

1. **Segurança primeiro:** perguntar se a máquina comprometida poderia acessar a raiz, assinar, mudar política, simular a autorização do dono ou apagar a auditoria. A resposta precisa ser comprovada depois por fonte independente; diagramas e testes sintéticos não provam a separação.
2. **Recuperação sem atalho:** estudar perda/roubo de chave, ausência de custodiante, lockout e indisponibilidade. Nenhuma falta de acesso deve justificar bypass, chave guardada no host ou reenvio automático de operação incerta.
3. **Comparar duas opções ainda abertas**, sem notas inventadas ou vencedor automático.
4. **Decidir em outra etapa:** pedir autorização explícita e separada para qualquer decisão de arquitetura ou mudança operacional. Mesmo uma decisão humana não substitui validação externa P0.

| Pergunta prioritária de segurança | Raiz offline sob custódia humana | KMS/HSM em domínio separado |
|---|---|---|
| Computador comprometido consegue assinar sozinho? | Só seria seguro se mídia, backups e cerimônia fossem inacessíveis ao host — **não provado** | Só seria seguro se `Sign`, edição de política e escalada de papéis fossem efetivamente negados ao host — **não provado** |
| Quem aprova e quem pode revogar? | Custodiante, aprovador e testemunha independentes — **não designados** | Admin, operador de assinatura, aprovador e auditor segregados — **não designados** |
| Dá para detectar replay, auditoria apagada ou rollback? | Checkpoint e testemunha fora do host — **não obtidos** | Logs/checkpoint fora de permissões comprometíveis — **não obtidos** |
| Como falha quando alguém/serviço está indisponível? | Não assina e não reenvia automaticamente — **regra de estudo, não ensaio externo** | Não assina e não reenvia automaticamente — **regra de estudo, não ensaio externo** |
| Qual o custo e trabalho de guarda? | Não cotado, sem compra nem instalação | Não cotado, sem contratação nem provisionamento |

**Nenhuma alternativa é declarada mais segura**: faltam provas externas equivalentes e contexto operacional real. A preferência por segurança não é sinônimo de preferência por “offline” nem por “HSM”.

## 13 questões obrigatórias ligadas ao A221

Mantemos todos os controles `OPEN/NOT_OBTAINED/NOT_REQUESTED`:

- Material offline inacessível ao host.
- Custodiante offline inalcançável/impersonável pelo host.
- Negação de operação KMS `Sign` pelo host.
- Negação de edição de política KMS pelo host.
- Negação de escalada/assunção de papel de assinatura.
- Aprovação externa e inequívoca do proprietário.
- Separação efetiva entre assinatura, administração e aprovação.
- Nonce e checkpoint anti-replay fora do host.
- Revogação e checkpoint fora do host.
- Auditoria/testemunha contra adulteração ou rollback fora do host.
- Indisponibilidade falha fechada, sem reenvio automático incerto.
- Recibo real do provedor distinto de assinatura da raiz.
- Isolamento estrito entre owner/tenant/workspace.

Os controles específicos de offline ou KMS/HSM são avaliados no modelo correspondente; os controles comuns valem para ambos. Ter 13 perguntas **não** significa 13 proteções verificadas.

## Fronteira de autoridade

O A223 exige uma matriz **A222 inalterada e ainda não preenchida**, usando o SHA-256 canônico da matriz para manter a ligação local owner/tenant/workspace. O hash apenas detecta diferenças entre rascunhos; não autentica usuário, não é uma assinatura e não impede um host comprometido de produzir um novo rascunho falso.

O código marca `conversational_security_priority_noted=True` apenas quando o formulário é estruturalmente válido; mantém sempre:

- `identity_verified=False`, `owner_signoff_valid=False`, `root_model_selected=False`, `independent_evidence_verified=False`;
- `may_select_model=False`, `may_commit_budget=False`, `may_contact_provider=False`, `may_provision=False`;
- `may_generate_key=False`, `may_sign=False`, `may_connect=False`, `may_confirm=False`, `may_auto_resend=False`;
- `external_p0_homologated=0`.

Input autoafirmado como “assinatura”, seleção offline/KMS, fornecedor, P0 aprovado, prova externa ou orçamento é recusado. Não há nuvem, chave, credencial, aparelho, conta financeira, envio de mensagem, agendamento ou operação live.

## Arquivos e validação esperada

- `labs/a223_owner_security_priority.py`: validador puro com campos exatos, digests canônicos e travas incondicionais.
- `labs/test_a223_owner_security_priority.py`: 45 verificações contra escopo trocado, preferências falsas, pontuação, assinatura, seleção, orçamento, duplicidade, JSON ambíguo e reenvio automático.
- Workflow em Ubuntu e Windows: **45 novos + 510 regressões A202–A222 = 555 testes por SO**.

Referências técnicas, não aprovação de fornecedor:

- NIST SP 800-57 Part 1 Rev. 5: https://csrc.nist.gov/pubs/sp/800/57/pt1/r5/final
- AWS KMS, segregação entre administração e uso: https://docs.aws.amazon.com/prescriptive-guidance/latest/encryption-best-practices/kms.html
- Google Cloud KMS, segregação de funções: https://docs.cloud.google.com/kms/docs/separation-of-duties

**A223 encerra apenas o registro da preferência de pesquisa nº 1. Arquitetura indefinida, evidências externas não obtidas, P0 0/6, HARD NO-GO.**
