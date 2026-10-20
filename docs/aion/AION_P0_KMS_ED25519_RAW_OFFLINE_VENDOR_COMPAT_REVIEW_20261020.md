# AION P0 — assinatura externa: compatibilidade Ed25519 × AWS KMS, sem contratação

**20/10/2026 | proposta de decisão, não implantação | HARD NO-GO | 0/6 P0.**

## Descoberta verificável que evita refazer a criptografia

Na documentação oficial consultada em outubro de 2026, a AWS KMS oferece a especificação assimétrica **`ECC_NIST_EDWARDS25519`** para assinatura e verificação. Para a assinatura Ed25519 comum que o laboratório AION já verifica com `cryptography`, a AWS exige o algoritmo **`ED25519_SHA_512`** com **`MessageType=RAW`**. A alternativa **`ED25519_PH_SHA_512`** usa **`MessageType=DIGEST`**, não é intercambiável com o contrato de bytes atual e **não deve ser selecionada por conveniência**. Fontes: [Key spec AWS KMS](https://docs.aws.amazon.com/kms/latest/developerguide/symm-asymm-choose-key-spec.html), [API Sign](https://docs.aws.amazon.com/kms/latest/APIReference/API_Sign.html), [AWS CLI Sign](https://docs.aws.amazon.com/cli/latest/reference/kms/sign.html).

**Contrato de interoperabilidade candidato (offline apenas):**

| Campo | Condição para compatibilidade criptográfica LAB | Autoridade |
| --- | --- | --- |
| KeySpec | `ECC_NIST_EDWARDS25519` | Ainda não há chave KMS criada |
| KeyUsage | `SIGN_VERIFY` | Não prova quem controla a conta |
| SigningAlgorithm | `ED25519_SHA_512` | Não escolher variante prehash |
| MessageType | `RAW` | Não converter `DOMAIN+JSON` em digest |
| Message | bytes exatos `ATLASQUANT:AION:P0:INCIDENT_WITNESS:LAB:V1\0 + JSON canônico` | Até 4.096 bytes; envelope + prefixo |
| KeyId | identificador esperado, previamente matriculado em canal independente | ID digitado no AION não constitui matrícula |
| Public key | `GetPublicKey` comparado ao fingerprint matriculado *fora* do executor | Comparar só dois valores autodeclarados não atesta a raiz |
| Sequence/head/replay | leitura de head e cache externos, verificador independente | Chave KMS sozinha **não** comprova último evento nem não repetição |

A API Sign documenta o limite de **4.096 bytes** no campo Message; o prefixo de domínio faz parte dos bytes assinados. **Nenhuma requisição Sign/Verify/GetPublicKey/CreateKey será enviada nesta etapa.**

## Custo — evitar supor que o serviço é grátis

A [página oficial de preços AWS KMS](https://aws.amazon.com/kms/pricing/) informa **US$ 1/mês por chave KMS criada**, além do preço das requisições; `Sign`, `Verify`, `GetPublicKey` e outras operações com chaves assimétricas **não entram na franquia gratuita** indicada para outras operações. Rotação e outros recursos podem acrescentar custos. Também será preciso orçar separadamente logs, versionamento, retenção, consulta externa, IAM/monitoramento e taxas da região. Esses números são apenas referência de documentação pública, **não cotação operacional do AtlasQuant** nem compromisso de despesa. Teto do projeto: **R$200/mês**, até R$250 somente com justificativa e autorização.

## Não confundir Object Lock com last-head infalsificável

A documentação oficial de [S3 Object Lock](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html) afirma que a retenção protege **uma versão específica**: ela não impede adicionar **novas versões** ou **delete markers**. Portanto, mesmo se uma versão antiga estiver protegida, isso **não prova que ela é o estado mais recente**. Não basta fazer `HEAD` na versão informada pelo próprio executor. A evidência tem de vir de um verificador com credenciais, custódia e política independentes, capaz de detectar fork/omissão e rollback. O sistema permanece bloqueado sem esse verificador.

## Alternativas futuras e decisão

1. **KMS em conta administrativamente segregada:** matematicamente compatível, possibilita chave privada não exportável, mas tem custos e exige análise de recuperação de conta, permissões, trilhas de auditoria e IAM. Não dá independência se o mesmo responsável puder alterar simultaneamente executor, custódia, verificador e emissor.
2. **Chave de teste/offline em máquina separada:** útil para avaliar assinatura e protocolos sem mensalidade nova, mas não é por si só um emissor confiável, verificador permanente, replay cache ou H0 disponível após reinício.
3. **Fornecedor de assinatura/verificação especializado:** somente avaliar com contrato técnico verificável, preços atuais, responsabilidade administrativa e provas de recuperação/último head. Não há fornecedor contratado.

**Decisão nesta rodada:** especificação **KMS-compatível em LAB**, não seleção definitiva ou conta criada. A solução positiva exige termos de matrícula, credencial humana, custódia, antirollback externo, nonce único e recipiência causal do fornecedor; nenhum desses itens deve ser preenchido com `verified=true` local.

## Evidência executável desta branch

O novo `atlasquant_aion_p0_kms_ed25519_raw_interop_lab.py` é um *validador negativo de configuração*: não usa boto3, não consulta AWS, não cria chave e sempre retorna `BLOCKED`, incluindo assinaturas matematicamente verificadas por chaves efêmeras de teste. `tests/test_aion_p0_kms_ed25519_raw_interop_lab.py` adiciona **18 testes** sobre RAW vs DIGEST, `Ed25519ph`, tamanho da mensagem, assinatura/digest alterados, troca da chave+fingerprint, escopo, head e material malformado. A CI Ubuntu/Windows repete os **31 testes de matrícula negativa #1360, 34 de envelope #1359, 30 de testemunha #1358, A53/A76/A74/M71, H0 e 23 módulos LAB raiz**, sem modificar Quality ou Security originais.

**Situação histórica não dispensada:** Quality canônica **6.562 testes / 52 FAIL +34 ERROR (86)**, Security adversarial A53 **RED**, 32 Outbox/Saga ERROR `OPEN_NOT_WAIVED`, 0/6 P0 homologados. Worker OFF, ZERO_AUTO_RESEND, sem merge/deploy/recebimento de cliente real/compra.
