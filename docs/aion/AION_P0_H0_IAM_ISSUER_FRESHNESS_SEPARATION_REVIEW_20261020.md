# AION H0 P0 — IAM independente, identidade de emissor e frescor do high-water

**20/10/2026 — REVISÃO OFFLINE / HARD NO-GO.** Zero contas reais autenticadas, zero assinatura verificada, 0/6 P0 homologados. O programa `tests/test_aion_p0_h0_iam_issuer_freshness_separation_lab.py` contém somente dados sintéticos e **22 testes adversariais**. Um teste verde identifica propriedades do checklist, **não prova IAM, titularidade, high-water ou segurança produtiva**.

## Problema que continua bloqueando H0

A validação anterior [#1342](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1342) examinou a **forma** de `HeadObject`/`GetObject`/`GetObjectRetention` e a versão exata. Isto é necessário, **mas insuficiente**. Mesmo registros com COMPLIANCE, versão correta, nonce e digest podem ter sido obtidos ou construídos sob a **mesma administração que controla o executor e o custodiador**. Um replay/rollback coordenado pode aparentar coerência.

### Contrato de separação de funções (proposta, não configuração IAM)

| Domínio independente pretendido | Identidade administrativa | Permissão mínima proposta | Proibição relevante |
| --- | --- | --- | --- |
| Executor AION/Worker local | Owner+host sujeitos à autorização H0 | **Nenhuma permissão AWS** | Não deve ter segredo/role de âncora ou `kms:Sign` |
| Custodiador CAS Cloudflare | Admin/conta Cloudflare independente do executor | Sem permissão AWS direta nessa proposta | Não pode controlar terceiro root de confiança ou fazer retry |
| Escritor de âncora S3 | Admin da conta âncora | `s3:PutObject` no prefixo/versionamento pré-configurado | Não pode deletar, reduzir retenção ou ler como verificador |
| Leitor/verificador S3 | Conta/role de verificação **separada** | `s3:GetObjectVersion`, `s3:GetObjectRetention`, `s3:GetBucketObjectLockConfiguration`, `s3:ListBucketVersions` | Não pode dar `Put` nem administrar o bucket |
| Emissor da prova externa de último head | Raiz de assinatura e administração fora dos domínios suscetíveis ao mesmo PITR | Envelope autenticado de high-water, escopo, epoch, sequência, nonce e versão | Não pode ser autoassinado pelo executor nem revogado por ele |

A separação de **IDs de conta não comprova separação administrativa**. Os valores de `admin_digests` no teste são marcadores fictícios de separação e NÃO hashes verificados de identidades humanas. Isso exige uma auditoria real das pessoas/roles, MFA, contas root, federation, trust policies, chaves, pipelines de deploy, sessão STS, delegation chains e políticas de organização.

## Exigências de prova independente a coletar no futuro, SEM provisionar agora

- **Identidade**: fazer challenge por nonce imprevisível gerado fora do executor e verificar assinatura com chave pública **previamente matriculada por outro canal**, política de rotação/revogação, Account ID e ARNs exatos. `sts:GetCallerIdentity` identifica o chamador da sessão verificada, **não demonstra quem controla toda a organização nem que as contas são administradas independentemente**. Nunca usar `signed=True` fornecido pela aplicação.
- **IAM de duas pontas**: em acesso AWS entre contas, o lado solicitante precisa da política de identidade e o recurso da política de acesso. Falta de uma delas, denegação explícita em qualquer ponta, SCP/RCP/session policies ou concessões excessivas bloqueiam; simulação de políticas não substitui execução real. Referência: https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_evaluation-logic-cross-account.html ; https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_evaluation-logic.html .
- **Escopo, conta e isolamento**: comprovar que o emissor do head não pode alterar S3/Cloudflare ou compartilhar conta root, recuperação de MFA, credenciais ou administradores com ambos; preservar somente digests e IDs fictícios no LAB, não informações pessoais.
- **Frescor verificável**: confrontar sequência/epoch e versão com um head monotônico assinado independente. O nonce deve ser único, vinculado a escopo, digest, request e janela, com replay-cache fora do host. Um `observed_age_seconds=0` autoafirmado ou data local não constitui frescor.
- **Retenção**: confirmar por readback real da versão S3 COMPLIANCE com retenção mínima, listagem completa de versões/delete markers, proteção contra fork e prova de que o current head externo não foi omitido. [Object Lock AWS](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html) protege versões mas permite versões novas/delete markers.
- **Falhas**: tratar timeout, IAM 403/404, rotação não reconhecida, ausência de head, alteração de IAM, refresh expirado e fonte indisponível como `UNKNOWN/BLOCKED`. Não recriar um head 0 nem liberar FIFO/Worker/primeiro efeito. Conservação de `UNCERTAIN` e **ZERO_AUTO_RESEND**.
- **Efeito externo**: mesmo um head de intenção autenticado não comprova `COMMITTED_EFFECT` do fornecedor nem o `NO_EFFECT_FENCED` terminal. Os 32 erros históricos continuam abertos. O H0 humano/prova de owner precisa de seu próprio gate.

## Evidência objetiva da rodada

`tests/test_aion_p0_h0_iam_issuer_freshness_separation_lab.py` simula 22 cenários: contas repetidas, mesmo admin declarado em IDs diferentes, executor ou custodiador com AWS, escritor com delete, leitor com Put, ARN de outra conta, política somente de uma ponta, explicit deny, STS/MFA/signature claims hostis, pinned sequence antigo, version mismatch, nonce repetido, emissão stale, issuer errado, bool em epoch, lista de permissões com objetos hostis e preflight perfeito. **Todos** resultam `HARD_NO_GO`, com flags de titular autenticado, IAM real, highwater signed/nonce verified, WORM e execução sempre `False`. A correspondência de forma é apenas um parecer de checklist.

## Pendência de custo e decisão

O controle anterior `atlasquant_aion_p0_h0_iam_finops_preflight_lab.py` já fixa teto de referência de **R$200/mês**, projetado a partir de cotações externas ainda **não verificadas**. A exigência de **novos domínios e administração separada** pode aumentar custos com IAM, storage, CloudTrail, KMS, operações e retenção. Portanto, não criar contas, buckets, Object Lock COMPLIANCE, Cloudflare DO ou consumo em nome do AION sem orçamento atualizado/ aprovação explícita, nem assumir que criar contas distintas entrega independência.

**Próximo gate útil:** validação formal, por revisor independente, do mapa de confiança (quem controla cada segredo, pessoa, IAM role, backup, conta raiz e emissor), assinatura/nonce readback REAL e sincronização latest head real sob orçamento; só então considerar plano de integração H0. **Nenhuma credencial conectada, chamada de AWS, criptografia de produção ou merge ocorre neste LAB.**

**HARD NO-GO | Worker OFF | ZERO_AUTO_RESEND | 32 ERROR Outbox/Saga OPEN_NOT_WAIVED | 0/6 P0 homologados.**
