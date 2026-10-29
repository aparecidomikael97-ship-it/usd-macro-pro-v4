# A218 — Pacote de decisão de fontes externas de confiança (SEM ESCOLHA AUTOMÁTICA)

**Status:** PR Draft de laboratório, 0/6 obrigações P0 externas homologadas, HARD NO-GO, UNCERTAIN=ZERO_AUTO_RESEND.

## Objetivo

A202–A217 demonstraram controles locais e resultados sintéticos, **não a execução financeira real nem custódia externa independente**. O A218 prepara uma decisão de arquitetura, sem escolher fornecedor, contratar, provisionar credenciais, registrar chaves ou ativar a execução.

Há **três funções diferentes**. Nenhum produto isolado prova as três:

| Função | Alternativas a avaliar | Evidência que realmente importa | Risco se o host for comprometido |
|---|---|---|---|
| **1. Raiz e assinatura** | Chave do proprietário mantida offline com cerimônia auditável; ou serviço de chaves/HSM administrado por domínio de controle realmente separado | Identidade do custodiante, autorização out-of-band, pública chave obtida fora do host, registro de emissão/rotação/revogação e testes de negação | Um KMS usado com as mesmas permissões do host pode assinar declarações forjadas: assinatura matemática sozinha não basta |
| **2. Efeito do provedor** | API/sandbox do provedor escolhido que ofereça recibo assinado, ID idempotente, consulta autoritativa de efeito e processo de reconciliação | Documentação contratual + sandbox: qual campo comprova efeito final, consulta independente após perda de ACK, ocorrência e unicidade por ID | Uma resposta enviada pelo adapter do host pode alegar CONFIRMED mesmo sem efeito |
| **3. Testemunha e antirollback** | Log externo verificável com prova de inclusão/consistência e observador de outra organização; checkpoint mantido fora do host | Inclusão criptograficamente verificável, checkpoint anterior independente, detecção de fork e histórico monotônico contra replay/rollback | Duas cópias assinadas pelo mesmo host podem fingir consenso |

**Notas sobre tecnologias:** AWS KMS e Google Cloud KMS documentam chaves assimétricas e mecanismos de assinatura/verificação; isso é capacidade de gestão de chaves, não prova de efeito em corretora, nem independência automática do administrador. Sigstore Rekor é exemplo de log de transparência para assinaturas de software: pode inspirar verificações de inclusão, mas **não é automaticamente um ledger de trades ou recibos financeiros**. Não existe fornecedor selecionado.

Referências oficiais consultadas:
- AWS KMS GetPublicKey: https://docs.aws.amazon.com/kms/latest/developerguide/download-public-key.html
- AWS KMS Verify: https://docs.aws.amazon.com/kms/latest/APIReference/API_Verify.html
- Google Cloud KMS Creating and validating digital signatures: https://docs.cloud.google.com/kms/docs/create-validate-signatures
- Sigstore Rekor: https://docs.sigstore.dev/logging/overview/
- RFC 9162, log de certificados, provas de inclusão e consistência: https://www.rfc-editor.org/rfc/rfc9162.html
- NIST SP 800-57 Part 1 Rev. 5, gestão de chaves: https://csrc.nist.gov/pubs/sp/800/57/pt1/r5/final

## Decisões a tomar com o proprietário

1. **Modelo de custódia:** raiz do proprietário em dispositivo offline, ou serviço de custódia com administração realmente separada do host? Quem paga, aprova e pode revogar?
2. **Provedor de operações:** qual corretora/serviço e qual ambiente SANDBOX podem fornecer prova verificável de um efeito e consulta autoritativa sem depender do adapter?
3. **Testemunha externa:** instituição/serviço e mecanismo de checkpoint imutável fora do host; como detectar replay, fork e rollback se o host desaparecer?
4. **Segregação operacional:** quem controla usuários, políticas, acesso de emergência, rotação e custos; qual a janela de revisão por um humano?
5. **Teste adversarial obrigatório:** simular perda de ACK, assinatura sob chave intrusa, recibo duplicado, reorg/fork, outage, revogação e host comprometido; só homologar com prova auditável adquirida fora dele.

Essas escolhas não são autorizadas por um simples "vamos lá" para implementação de laboratório. **O usuário deverá aprovar fornecedor, custos e escopo separadamente antes de qualquer conexão externa.**

## Checklist de evidências antes de qualquer alegação de origem independente

- [ ] Identidade e posse da raiz verificadas por canal externo sob controle conhecido.
- [ ] Mecanismo de assinatura com política de uso e revogação comprovados independentemente.
- [ ] Recibo de efeito real do provedor e consulta autoritativa validada em sandbox.
- [ ] Testemunhas/log independentes com inclusão e consistência verificadas.
- [ ] Estado antirollback/nonce/sequence observado fora do host e protegido contra replay.
- [ ] Resultados de testes adversariais com documentação, responsabilidade e aceite explícito do responsável de risco.

**Importante:** esses seis itens são uma proposta de checklist A218 e não substituem, renomeiam ou homologam os seis P0 existentes. O estado oficial continua **0/6 P0 externos homologados** até auditoria e aceite próprios.

## Condições de aceitação do A218

- Módulo de laboratório de portfólio de opções: sem decisão real e com resultado may_connect=False, may_activate=False, may_confirm=False em todos os casos.
- Testes garantem que tentativas de marcar fornecedor escolhido, P0 já homologado, chave "independently_verified", credenciais e efeitos operacionais por texto do host sejam rejeitadas.
- Nenhum arquivo de configuração de produção, segredo, IAM, KMS, network, despesa, PR merge ou deploy.
- PR isolado em Draft.

**Decisão atual: AWAITING_OWNER_SOURCE_CHOICE. HARD NO-GO.**
