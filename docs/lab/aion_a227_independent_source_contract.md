# A227 — Contrato mínimo para uma prova realmente independente

**Natureza:** laboratório sintético, sem autenticar fontes reais. **HARD NO-GO · P0 externo 0/6 · `UNCERTAIN=ZERO_AUTO_RESEND`.** Não há provedor escolhido, KMS/HSM provisionado, chave gerada, assinatura, contato, desafio em ambiente externo ou autorização formal do proprietário.

## Por que o A227 existe

O A226 demonstrou que duas declarações coerentes e nominalmente diferentes ainda podem vir de um único computador comprometido. O A227 traduz isso para **12 critérios mínimos de aceitação futura**. Cada linha fixa: prova exigida, fronteira de confiança externa, desafio negativo e quatro campos que permanecem em `NOT_OBTAINED`, `NOT_VERIFIED`, `NOT_EXECUTED` e `UNASSIGNED`.

**Preenchimento correto do formulário não equivale a prova aprovada.** O código aceita somente um **contrato de pesquisa**, sem testar chaves ou validar identidades.

| Requisito futuro | Evidência que precisará vir de fora do host | Tentativa adversarial a refutar |
|---|---|---|
| 1. Âncora de confiança do emissor | Origem da âncora autenticada fora do host | Substituição da chave-âncora |
| 2. Vínculo entre emissor e chave pública | Identidade/chave de emissor autenticada externamente | Troca do fingerprint pelo host |
| 3. Domínio de controle realmente separado | Administração que o host não consegue controlar | Dois nomes sob um administrador |
| 4. Segregação de assinante, administrador e aprovador | Permissões e principais revisados de forma independente | Escalada do host a papéis conflitantes |
| 5. Desafio nonce fora da banda | Nonce criado por desafiante independente | Reutilização de nonce escolhido pelo host |
| 6. Checkpoint anti-replay e anti-rollback | Histórico monotônico fora da custódia do host | Retrocesso de checkpoint |
| 7. Origem e consistência de auditoria | Inclusão, continuidade e custódia independente de logs | Reescrita do histórico |
| 8. Revogação e expiração | Estado de revogação consultável fora do host | Reuso de emissor revogado |
| 9. Autorização do proprietário no escopo | Canal separado e confirmação explícita, **ainda não solicitada** | Consentimento forjado pelo host |
| 10. Recibo final do provedor | Recibo emitido em canal controlado pelo provedor, **não por root local** | Substituição de recibo por assinatura local |
| 11. Incerteza e indisponibilidade sem reenvio | Resultado da falha analisado independentemente | Envio duplicado após perda de ACK |
| 12. Isolamento owner/tenant/workspace | Vínculo de escopo fiscalizável fora do host | Reaproveitamento entre tenants |

## Duas opções tecnológicas permanecem abertas

- **Raiz offline:** exigir testemunho de custódia fora do host, desafio de acesso negado, separação de responsáveis e âncora de confiança verificável.
- **KMS/HSM em laboratório:** exigir demonstração independente de permissões, de negação de assinatura e de mudanças IAM/política, sem aceitar a afirmação local do próprio host.
- **Em ambas:** nonce fora da banda, proteção contra replay, logs externos, revogação, escopo e recibo final do provedor. Nenhuma opção está selecionada.

Os 12 requisitos do A227 são **critérios transversais de independência**; os 13 controles específicos por arquitetura continuam documentados no A221/A224. Não são contagens de certificados nem de provas recebidas.

## Contrato de código e resultados

- `labs/a227_independence_acceptance_contract.py` verifica o formato estrito de um contrato com exatamente 12 linhas e vínculo ao digest textual não confiável do A226.
- O digest SHA-256 é **só identificador do texto local**, não assinatura, autenticação nem confirmação do emissor. A ordem das linhas não altera esse digest.
- A226 contendo fontes declaradamente compartilhadas ou digests divergentes não serve de base nem para esse contrato de pesquisa. Fontes distintas e coerentes continuam **sem independência comprovada**.
- Em cada linha, o host não pode escrever `VERIFIED`, `PASSED` ou `OBTAINED`. Qualquer promoção é recusada. Também são recusadas alterações de escopo, fornecedor escolhido, signoff imaginário, contato externo ou P0 maior que zero.
- Mesmo quando o formulário está íntegro: `actual_issuer_identity_verified=False`, `actual_domain_independence_verified=False`, `actual_external_challenges_executed=False`, `external_evidence_accepted=False`, `owner_signoff_valid=False`, `provider_final_effect_verified=False`. Todos os `may_*` são `False`.
- `labs/test_a227_independence_acceptance_contract.py`: **50 testes novos** sobre integridade, sobreposição, escopo, falsos aceites e fail-closed. Regressão de A202–A226: **705 anteriores + 50 novos = 755 por sistema operacional**, a confirmar no GitHub Actions Ubuntu e Windows.

## O que falta para sair do laboratório

O contrato não implementa coleta nem verificação real. Uma etapa externa exigirá, separadamente, definição de fonte de confiança e responsável, permissão formal do proprietário, escopo auditável, método de avaliação independente e execução autorizada. Tudo isso está **NOT_OBTAINED**. Um fornecedor citado como referência não foi escolhido ou contatado.

Referências de princípios (sem endosso de tecnologia): [NIST SP 800-57 Part 1 Rev. 5](https://csrc.nist.gov/pubs/sp/800/57/pt1/r5/final), [NIST — trust anchor](https://csrc.nist.gov/glossary/term/trust_anchor), [AWS KMS — segregação de responsabilidades](https://docs.aws.amazon.com/prescriptive-guidance/latest/encryption-best-practices/kms.html), [Google Cloud KMS — separação de funções](https://docs.cloud.google.com/kms/docs/separation-of-duties).

**Conclusão:** o A227 define **o que seria necessário provar**; ainda não apresenta **nenhuma prova externa**. HARD NO-GO.
