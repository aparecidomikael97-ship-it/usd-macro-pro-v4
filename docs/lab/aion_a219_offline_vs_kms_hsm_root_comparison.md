# A219 — Comparação de raiz offline versus KMS/HSM externo (somente pesquisa)

**Estado:** laboratório, PR Draft, escolha não feita. **HARD NO-GO · P0 externo homologado 0/6 · UNCERTAIN=ZERO_AUTO_RESEND.**

O A218 organizou as opções de origens externas. O A219 compara exclusivamente **dois modelos hipotéticos de custódia da raiz**, sem gerar/importar chaves, criar conta, contratar, executar comando KMS/HSM, registrar identidade, ativar assinaturas, mudar IAM, emitir recibo financeiro ou contatar terceiros. **Nenhum fornecedor foi selecionado.**

## Comparação de arquitetura — sem pontuação ou vencedor inventado

| Critério | Raiz offline sob custódia do proprietário | KMS/HSM com domínio separado | Prova necessária antes de qualquer decisão |
|---|---|---|---|
| **Controle e independência** | Chave desconectada do host; proprietário/custodiante conduz cerimônia presencial. Ainda exige controle físico e separação de papéis. | HSM/KMS administra chave e operação remota; só é independente se acesso de assinatura, administração, políticas e aprovação estiverem segregados do host. | Identidade e domínio de controle constatados por canal independente; host e seus operadores incapazes de usar/gerenciar a raiz por conta própria. |
| **Host comprometido** | Malware remoto não deve alcançar material privado, backup, dispositivo ou aprovador; verificar isso, não presumir. | Se o host possui permissão de `Sign` direta ou pode assumir papel que a possua, o atacante pode assinar declarações falsas mesmo sem exportar a chave. | Teste adversarial de abuso com conta host comprometida, negações auditadas fora dele. |
| **Assinatura / operação** | Cerimônia manual ou interface air-gapped aumenta atrito e evita assinar eventos de alta frequência automaticamente. | Assinatura remota é mais automatizável; automatização não substitui aprovação independente por intenção/nonce/política. | Verificação independente de public key, finalidade, nonce, versão, replay, autorização e legitimidade do conteúdo. |
| **Segregação de funções** | Custodiante, autorizador, testemunha e recuperador devem ser papéis demonstráveis e não concentrados no host. | Admin de chave/política, operador criptográfico, aprovador e auditor devem ter identidades/políticas separadas. | Provas negativas de escalonamento e colusão simulada; logs fora do domínio controlado pelo host. |
| **Revogação/rotação** | Cerimônia física e publicação externa de novo fingerprint/revogação. | Disable/revoke/rotate dependem de controles e versões de fornecedor; identificar semântica efetiva. | Histórico da raiz e checkpoint antirollback fora do host; rejeição de assinatura antiga/revogada. |
| **Perda/recuperação** | Risco físico: perda, roubo, dano, backups e quórum para restauração. | Risco de bloqueio, exclusão/disable de chave, permissões, conta e recuperação dependente de provedor. | Exercício de recuperação sem vazar raiz, sem bypass, documentando responsabilidade. |
| **Disponibilidade** | Ausência de responsável/dispositivo impede cerimônia. | Depende de IAM, rede, serviço e eventualmente região/contrato. | Outage simulada com fail-closed; nenhuma operação reenviada automaticamente sob incerteza. |
| **Auditoria** | Atas, coassinaturas/observadores e logs físicos auditáveis fora do host. | Logs API podem ser auditados, mas ficam inseguros se host ou seu administrador puder apagá-los/alterar controles. | Cópias independentes, integridade, inclusão/consistência e testemunhas externas de checkpoint. |
| **Custos e dependências** | Custo real de equipamento, guarda, cerimônias, pessoal, backup e resposta a incidentes **não cotado**. | Custo real de chaves, operações, HSM, registro/auditoria, região e governança **não cotado**. | Orçamento e contrato explícitos submetidos ao proprietário em etapa separada; nenhuma cifra presumida. |
| **P0/efeito financeiro** | Assinatura de raiz não prova que uma ordem foi executada pela corretora. | Assinatura do KMS/HSM também não comprova efeito financeiro. | Recibo assinado pela instituição e consulta autoritativa independente continuam obrigações separadas. |

**Importante:** “chave não exportável” ou “hardware HSM” não basta para autonomia: quem pode solicitar uso, alterar permissões, rotacionar, revogar ou aprovar a mensagem assinada é parte do limite de confiança. O administrador na mesma conta/projeto/organização do host pode destruir essa separação.

## Oito hipóteses adversariais, ambas abertas

O laboratório `labs/a219_root_custody_comparison.py` fornece perguntas específicas para ambos os modelos nas oito situações; não executa ataques reais nem marca prova como obtida:

1. `HOST_COMPROMISE`: malware no host tenta usar material offline ou chamar `Sign` remotamente.
2. `SIGNER_ADMIN_COLLUSION`: um único ator acumula aprovação, gestão de política e assinatura.
3. `ROOT_KEY_LOSS`: perda de dispositivo, backup, conta, chave ou destruição.
4. `OUTAGE_OR_CUSTODIAN_ABSENCE`: falha de rede/serviço ou custódia humana indisponível.
5. `REVOKED_KEY_REPLAY`: assinatura antiga/revogada reutilizada contra estado local revertido.
6. `AUDIT_ROLLBACK_OR_FORK`: host ou administrador apaga logs ou apresenta dois históricos.
7. `UNVERIFIED_BROKER_RECEIPT`: host usa assinatura válida como substituta de recibo real da corretora.
8. `LIFECYCLE_COST_AND_LIABILITY`: responsabilidade de custódia, cobrança e incidente indefinida.

**Nenhum cenário é marcado como mitigado**. Cada hipótese aponta a evidência a ser solicitada e ensaiada fora do host após autorização separada.

## Condições negativas codificadas no A219

- O envelope aceita exatamente dois modelos `OWNER_OFFLINE_ROOT` e `SEPARATE_DOMAIN_KMS_HSM`, ambos no estado `HYPOTHETICAL_ONLY`, sem vencedor, com escopo owner/tenant/workspace vinculado.
- Campos de segredo/credential/fornecedor, identidade supostamente verificada, domínio atribuído, chave gerada, política aprovada, segregação/auditoria demonstrada, revogação/recuperação testada ou custo cotado **invalidam** o pacote de pesquisa.
- JSON ambíguo com chaves repetidas ou tamanho acima do limite falha fechado.
- Todo resultado conserva `independent_root_verified=False`, `owner_choice_approved=False`, `external_p0_homologated=0`, `may_generate_or_import_key=False`, `may_sign=False`, `may_provision=False`, `may_connect=False`, `may_confirm=False`.
- SHA-256 do catálogo é **somente integridade local do rascunho**, não assinatura, atestado, consentimento ou comprovação externa.
- 40 testes A219 mais toda a regressão A202–A218 em Ubuntu e Windows. Este laboratório nunca faz chamadas à nuvem.

## Decisões reservadas ao Mikael

1. Validar depois quem seria custodiante/aprovador/testemunha de cada alternativa, com pessoas e domínios distintos do host.
2. Informar prioridades relativas: uso manual, continuidade, recuperação, autonomia, segregação, auditoria e orçamento.
3. Autorizar, em etapa futura e separada, pesquisa de preço/contrato ou prova de sandbox se desejar. Um “vamos lá” para testes **não** autoriza essas ações.
4. Só após provas reais externas, revisões humanas e aceites formais discutir homologação P0; os seis P0 atuais **permanecem 0/6**.

## Referências técnicas oficiais consultadas (não constituem endosso)

- AWS KMS key policies: https://docs.aws.amazon.com/kms/latest/developerguide/key-policies.html
- AWS Prescriptive Guidance: separation of duties, least privilege and CloudTrail: https://docs.aws.amazon.com/prescriptive-guidance/latest/encryption-best-practices/kms.html
- Google Cloud KMS separation of duties, administração vs. uso: https://docs.cloud.google.com/kms/docs/separation-of-duties
- Google Cloud KMS key destruction and recovery: https://docs.cloud.google.com/kms/docs/destroy-restore
- NIST SP 800-57 Part 1 Rev. 5 (final): https://csrc.nist.gov/pubs/sp/800/57/pt1/r5/final

**Decisão de saída A219: `AWAITING_OWNER_COMPARISON_REVIEW`. Nenhuma raiz escolhida, criada ou homologada. HARD NO-GO.**
