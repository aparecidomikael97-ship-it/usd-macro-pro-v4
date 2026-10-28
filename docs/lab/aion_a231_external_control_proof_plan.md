# A231 — Exigências de prova fora do computador: 60 perguntas ainda sem resposta

**Estado:** contrato de pesquisa **não executado**. **HARD NO-GO · P0 externo 0/6 · `UNCERTAIN=ZERO_AUTO_RESEND`.** Nenhum fornecedor, pessoa, chave, corretora, KMS/HSM, infraestrutura ou identidade foi contratado, contatado, auditado, aprovado ou acionado.

## Por que não basta comparar nomes

O A230 mostra que um único computador pode renomear todas as supostas fontes e esconder até **66 sobreposições visíveis**. O A231 deliberadamente **não tenta inferir a verdade por novos nomes**. Em vez disso, define o que uma verificação independente teria de demonstrar, fora do host, antes de qualquer confiança operacional.

São **12 requisitos independentes A227 × 5 domínios de controle A229 = 60 perguntas não executadas**. Cada pergunta exige confirmação posterior por origem e testemunha fora da autoridade do host.

| Domínio de controle | Prova futura desejada, ainda não obtida |
|---|---|
| Administração | Quem realmente pode mudar políticas, usuários e privilégios; verificação de acesso fora do host |
| Autoridade superior | Quais contas, administradores ou organizações realmente controlam ou recuperam a fonte |
| Assinatura | Onde a chave é custodiada, quem consegue assinar e se a separação de papéis é real |
| Auditoria | Quem consegue apagar, reescrever ou validar um registro externamente |
| Recuperação | Quem tem capacidade de recuperação, rotação ou substituição de identidade |

Cada uma das 60 células nasce com `challenge_nonce_state=NOT_ISSUED`, `issuer_identity_state=NOT_VERIFIED`, `independent_witness_state=NOT_VERIFIED`, `external_acquisition_state=NOT_REQUESTED`, `evidence_state=NOT_OBTAINED`, `reviewer_state=NOT_ASSIGNED`. Nem um hash local, nem CI verde, nem um documento gerado pelo AION pode alterar esses estados para `VERIFIED` ou `OBTAINED`.

O vínculo de digest SHA-256 com o resultado A230 é **somente um compromisso local de texto**. Não equivale a assinatura do proprietário, identificação de fornecedor, confiança de PKI, IAM externo, testemunha independente ou recibo de efeito.

## Evidência realmente necessária numa etapa futura, separada e autorizada

Para cada controle deverão existir, conforme o caso e **sem presumir um fornecedor**: prova verificável de titularidade e identidade do emissor, auditoria administrativa independente, confirmação de cadeia de autoridade, verificação de separação entre administrador e assinante, desafio imprevisível originado fora do host e resposta autenticada, registro de revogação/recuperação e avaliação humana independente. A custódia offline e KMS/HSM continuam alternativas sob avaliação, não uma decisão.

**Limitação:** validar este formulário não autentica a realidade. Nenhuma das 60 perguntas foi feita a uma fonte real. O campo de forma completa significa **somente esquema consistente**, não avaliação positiva. Quando o JSON textual exceder 8.192 bytes, o parser estrito pode recusá-lo; não ampliar o limite para facilitar a ilusão de confiança. Objetos estruturados são usados para testes sintéticos.

## Segurança e entregáveis

O código só valida dados e devolve resultado imutável com `actual_control_domains_independent=False`, `external_evidence_accepted=False`, `owner_signoff_valid=False`, `provider_final_effect_verified=False`, 0/6 P0 e todos `may_*=False`. Recusa qualquer tentativa de declarar desafio executado, identidade verificada, testemunha atestada, revisão concluída, decisão do dono, `GO`, escolha tecnológica, contato, operação financeira ou reenvio automático.

- `labs/a231_external_control_proof_plan.py`: contrato estrito de 60 desafios **não executados**.
- `labs/test_a231_external_control_proof_plan.py`: 50 testes adversariais, integridade de escopo, vínculos A230 e recusa de prova inventada.
- `.github/workflows/aion-a231-external-control-proof-plan-readonly.yml`: regressão A202–A230 + A231 em Ubuntu/Windows, **955 testes por SO esperados**, a confirmar em logs.

**Conclusão A231:** agora há uma especificação de evidência a obter fora do host, não um aumento de confiança real. Só um futuro processo independente, com autorização apropriada, poderá produzir evidência submetida a verificação. Nenhum `GO` operacional decorre deste laboratório.
