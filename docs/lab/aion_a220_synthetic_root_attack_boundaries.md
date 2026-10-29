# A220 — Simulador adversarial de fronteiras da raiz: offline e KMS/HSM

**Status:** somente laboratório, sem credenciais, dispositivo, serviço, chaves, rede, IAM, assinatura, recibo financeiro, contato externo, custo ou deploy. **HARD NO-GO · 0/6 P0 externos homologados · UNCERTAIN=ZERO_AUTO_RESEND**.

O A219 documentou os trade-offs dos dois modelos. O A220 faz **testes de mesa codificados** de 13 ataques de um host comprometido. O modelo recebe hipóteses booleanas **fornecidas pelo próprio host**, não uma política IAM real. Seu trabalho é expor o que aconteceria **se** a hipótese fosse verdadeira ou falsa; não demonstra que um controle realmente existe.

## Modelo de interpretação — essencial

| Resposta do simulador | Interpretação exata | O que **não** significa |
|---|---|---|
| `SYNTHETIC_ASSUMPTION_BLOCKS_SCENARIO_NOT_PROOF` | O campo fictício de controle para aquele ataque foi marcado `true`. Sob essa hipótese, o ataque seria barrado no **modelo de papel**. | Não valida chave, hardware, isolamento de rede, permissão, identidade, aprovação, logs ou segurança externa. |
| `SYNTHETIC_ATTACK_REVEALS_ASSUMED_CONTROL_GAP` | O campo relevante foi marcado `false`, revelando que a própria hipótese não contém o controle exigido. | Não confirma que o ataque aconteceu em cloud, dispositivo ou corretora reais. |
| Qualquer erro de envelope/escopo | Entrada ausente, alterada, ambígua, de escopo incorreto ou tentando se promover a autoridade. | Não permite continuar com um modelo incompleto ou supostamente homologado. |

**Nenhum resultado** permite criar/importar chave, assinar, provisionar, conectar, confirmar ou reenviar automaticamente. Nenhum resultado comprova independência de raiz ou escolhe fornecedor. SHA-256 do cenário é apenas checksum local de hipótese controlada pelo host.

## Cenários A220 e barreiras hipotéticas a auditar

| Cenário hostil | Modelo | Hipótese testada |
|---|---|---|
| `HOST_READS_OFFLINE_PRIVATE_MATERIAL` | Offline | Material privado, backups e seed fora do host |
| `HOST_IMPERSONATES_OFFLINE_CUSTODIAN` | Offline | Custodiante inacessível ao host |
| `HOST_INVOKES_KMS_SIGN` | KMS/HSM | Host sem permissão `Sign` |
| `HOST_CHANGES_KMS_KEY_POLICY` | KMS/HSM | Host sem permissão de alterar a política da chave |
| `HOST_ASSUMES_SIGNER_ROLE` | KMS/HSM | Host sem poder assumir/delegar identidade assinante |
| `HOST_FORGES_OWNER_APPROVAL` | Ambos | Aprovação real fora do host |
| `ADMIN_SIGNER_APPROVER_COLLUSION` | Ambos | Papéis de administrador, assinante e aprovador segregados |
| `HOST_REPLAYS_OLD_NONCE` | Ambos | Nonce/checkpoint independente anti-replay |
| `HOST_REUSES_REVOKED_ROOT` | Ambos | Estado da revogação independente e monotônico |
| `HOST_ERASES_AUDIT_TRAIL` | Ambos | Auditoria com testemunha fora do host |
| `OUTAGE_FORCES_AUTOMATIC_RESEND` | Ambos | Falha fechada e `ZERO_AUTO_RESEND` durante incerteza |
| `ROOT_SIGNATURE_FORGES_BROKER_EFFECT` | Ambos | Recibo do provedor não substituído por assinatura da raiz |
| `HOST_SUBSTITUTES_OTHER_TENANT` | Ambos | Vinculação de owner/tenant/workspace por canal confiável |

Os riscos não são independentes: um host com acesso `kms:Sign` pode forjar mensagens mesmo se a chave for não exportável. Também não basta negar `Sign` se o host puder editar a política, assumir outro papel, suplantar o aprovador ou adulterar o log. No offline, a chave realmente só está fora do host se **todo o material, backups e mecanismo de aprovação** estiverem inacessíveis a ele. **Essas são hipóteses a testar externamente no futuro**, não afirmações de configuração atual.

## Entrada e saídas do laboratório

Arquivo: `labs/a220_synthetic_root_attack_boundaries.py`. Função `simulate_untrusted_root_attack`:

- Recebe exatamente: schema versionado, owner/tenant/workspace, modelo, ataque, origem do atacante `HOST_CONTROLLED`, estado `FICTIONAL_UNVERIFIED_ONLY`, aprovação `NOT_REQUESTED`, P0 `0` e um mapa completo de 13 controles booleanos.
- Nunca aceita segredo, private key, credential, nome de fornecedor, identidade aprovada ou campo extra. Recusa chaves JSON duplicadas e entrada acima do limite.
- Uma única hipótese correspondente é testada por ataque. Os demais campos continuam parte do rascunho, sem promoção de confiança.
- Resultado imutável: `independently_verified=False`, `owner_approval_valid=False`, `external_p0_homologated=0`, `may_generate_key=False`, `may_sign=False`, `may_provision=False`, `may_connect=False`, `may_confirm=False`, `may_auto_resend=False`.

Exemplo mental: no cenário `HOST_INVOKES_KMS_SIGN`, se `kms_host_sign_denied` estiver `false`, há lacuna simulada; se estiver `true`, há bloqueio **apenas assumido**. Nem o segundo caso prova política IAM real. A transição para uma verificação real depende de autorização específica do proprietário, auditoria independente e ambiente separado — não de um campo de texto.

## Testes e isolamento

- `labs/test_a220_synthetic_root_attack_boundaries.py`: 40 testes específicos, incluindo todos os 13 cenários, diferenças offline/KMS, negação de falsos P0, IDs fora de escopo, campos de credencial, mutação de políticas, replays e `ZERO_AUTO_RESEND`.
- Workflow `.github/workflows/aion-a220-synthetic-root-attacks-readonly.yml`: SHA-pinned, Ubuntu e Windows, 40 testes A220 + 390 regressões A202–A219 = **430 por sistema operacional**.
- CLI para reproduzir somente o laboratório: `python -B -m unittest -v labs.test_a220_synthetic_root_attack_boundaries`. Não chama APIs, serviços ou dispositivos reais.
- Sem integração com execução financeira, sem atestar uma raiz verdadeira, sem alterações de produção.

## Próxima decisão, não automatizada

A221 poderá **especificar o protocolo de evidência independente** para auditar os controles críticos offline/KMS em ambiente autorizado, ainda sem conectar nada por padrão. Antes de qualquer projeto/conta/custo/teste externo, o proprietário deverá delimitar o escopo e aprovar o procedimento separadamente.

Fontes oficiais de referência:
- AWS KMS `kms:Sign` e controles por política: https://docs.aws.amazon.com/kms/latest/developerguide/kms-api-permissions-reference.html
- AWS KMS política da chave e permissões: https://docs.aws.amazon.com/kms/latest/developerguide/key-policies.html
- AWS Prescriptive Guidance, separação entre administração e uso da chave: https://docs.aws.amazon.com/prescriptive-guidance/latest/encryption-best-practices/kms.html
- Google Cloud KMS separação de deveres: https://docs.cloud.google.com/kms/docs/separation-of-duties

**Fim do A220 = fim de uma simulação controlada, não homologação. O status de produção permanece HARD NO-GO, P0 0/6.**
