# AION H0 — Matriz de permissões, custo global e evidências de uma futura experiência

19/10/2026 — PROPOSTA OFFLINE. 0/6 P0 HOMOLOGADOS; HARD NO-GO; GLOBAL WORKER OFF; ZERO_AUTO_RESEND. Nenhum deploy, merge, fornecedor, conta, credencial ou custo adicional.

## 1. Escopo: três domínios separados

Arquitetura candidata: AION local → Cloudflare Durable Objects SQLite para serialização/CAS → Amazon S3 Object Lock COMPLIANCE numa conta e administração distintas, como âncora de versões. NÃO está implementada; faltam identidade, trust anchors, assinatura externa, autorização do dono, alta-water real, certificado do fornecedor, testes em nuvem, Quality/Security e aprovação. Cloudflare DO admite PITR; S3 Object Lock COMPLIANCE retém versões individuais, mas novas versões e delete markers continuam possíveis. VersionID exato e descoberta de forks são obrigatórios.

## 2. Matriz de permissões mínima (proposta, NÃO policy IAM)

| Ator | Permissões propostas | Não deve ter |
|---|---|---|
| AION Executor / Global Worker | Nenhuma credencial/permissão AWS | s3:*, IAM, KMS, S3 delete, admin de buckets ou Cloudflare; Worker segue desligado |
| Cloudflare CAS runtime | Nenhuma permissão AWS direta neste contrato | Chave AWS no PC/Worker; auto-retry; capacidade de reescrever uma reserva já reconhecida |
| AWS gravador de âncoras | s3:PutObject, limitado por bucket/prefixo e default Object Lock COMPLIANCE configurado por outro papel | s3:DeleteObject, s3:DeleteObjectVersion, s3:PutObjectRetention, s3:PutBucketObjectLockConfiguration, s3:PutBucketVersioning, s3:PutLifecycleConfiguration, s3:PutBucketPolicy, s3:BypassGovernanceRetention |
| AWS leitor/verificador | s3:GetObjectVersion, s3:GetObjectRetention, s3:GetBucketObjectLockConfiguration, s3:ListBucketVersions no escopo fixado | PUT, DELETE, IAM, bucket admin, uso de GET sem VersionID para selecionar latest |
| Administrador de segurança AWS | Configuração/renovação de retenção e IAM fora dos papéis de serviço | Não fornecer root/credenciais administrativas ao executor. Admin separado com MFA e recuperação revisada |
| FinOps | Consulta a custos, limites e faturas conforme permissões futuras | Nenhuma permissão para liberar Worker, alterar WORM ou autorizar efeitos |

A matriz é apenas uma allowlist para revisão de proposta. NÃO implementa nem prova enforcement de IAM, bucket policy, SCP, key policy ou MFA. A API S3 exige direitos distintos conforme operações; condições e recursos precisam de simulação/teste real antes de implantação. Este desenho presume retenção COMPLIANCE configurada no bucket. Uso de retenção por objeto ou SSE-KMS customer-managed exige outra revisão IAM específica, não coberta por esta allowlist.

## 3. FinOps — teto GLOBAL R$200/mês

- Teto financeiro do ecossistema INTEIRO: R$200/mês. R$250 não é um novo teto automático; requer justificativa e aprovação expressa fora deste LAB.
- Gate preventivo de revisão: projeção total estritamente abaixo de R$160/mês (80% do teto); é uma margem administrativa voluntária, não limite de faturamento garantido.
- Valores necessários: custo real atual do ecossistema (Render e demais serviços), câmbio USD/BRL sob estresse, preços regionais S3 Standard em sa-east-1, PUT/GET, KMS e logging, plano/cotas Cloudflare, impostos e outros custos em nuvem. Todos estão como null no template enquanto não forem verificados.
- Modelo de 31 dias e capacidade constante: GiB-mês retidos = âncoras/dia × dias de retenção × versões/âncora × bytes/versão / 2^30. S3 USD = armazenamento + preço de PUT e GET × operações/mês + chamadas KMS + chave KMS + logs + outros custos de nuvem. R$ projetados = R$ base existente + US$ projetado × câmbio sob estresse × (1 + margem de incerteza). Inclui versões retidas, mas ainda não precifica automaticamente retenção longa inicial, tráfego de saída, impostos reais nem todas as operações de CloudTrail; exige validação com AWS Pricing Calculator e faturas.
- Cloudflare Workers Free DO SQLite: totais da CONTA abaixo de 80% dos limites diários de 100 mil requests, 13 mil GB-s, 5 milhões de linhas lidas, 100 mil linhas escritas e 5 GB de armazenamento, além do limite de Workers Free. Exceder o Free provoca falha, nunca fallback permitindo efeito. O sistema deve parar de reservar antes da cota.
- AWS Budgets não é disjuntor: a atualização de fatura pode atrasar, e alertas não garantem parada automática antes de superar o teto. Exigir quotas da aplicação, acompanhamento real e bloqueio de novas reservas.
- Uma chave customer-managed KMS, se aprovada, normalmente custa US$1/mês antes de uso e eventuais rotações; não presumir custo zero nem criar uma chave agora.

## 4. Fases de evidência que AINDA NÃO EXISTEM

| Fase | Evidência indispensável | Estado |
|---|---|---|
| E0 — Financeira | Faturas atuais, cotação sa-east-1 AWS datada, volume de eventos, câmbio sob estresse, custos KMS/logs/Cloudflare, estimativa da calculadora AWS | AUSENTE |
| E1 — IAM | Duas administrações separadas, IAM policy e bucket policy verificadas no IAM simulator, MFA e contas autorizadas, prova de negações a delete, lifecycle e admin | AUSENTE |
| E2 — WORM | Bucket S3 real com default COMPLIANCE, VersionID, metadata de retenção, GetObjectVersion, readback de versão exata, teste de delete marker/fork | AUSENTE |
| E3 — High-water | Issuer/key independente matriculado, nonce single-use, seq/epoch/CAS remoto e prova de assinatura/chave, confronto com cabeçalho WORM | AUSENTE |
| E4 — Recuperação | CAS confirmado e resposta perdida, S3 PUT incerto, dois clientes, rollback de SQLite e DO PITR, reboot físico, no-auto-resend | AUSENTE |
| E5 — Homologação | HUMAN_OWNER real, recibos terminais do produtor, caminho obrigatório H0/Outbox/Worker, Quality/Security canônicas, auditoria independente | AUSENTE |

Mesmo proposta completa e barata nunca se torna GO por meio deste documento. E0–E4 não dispensam E5.

## 5. Artefatos executáveis offline

- atlasquant_aion_p0_h0_iam_finops_preflight_lab.py: lê proposta JSON sem acessar contas nem redes; calcula cenário quando dados estão preenchidos e compara matriz declarada com allowlist. Sempre retorna state=HARD_NO_GO, com todos os campos de verificação externa/efeito falsos. CLI retorna exit code 2 mesmo se a matemática estiver completa.
- docs/aion/AION_P0_H0_IAM_FINOPS_UNPRICED_PROPOSAL_TEMPLATE_20261019.json: preços, contas, consumo e projeções desconhecidos permanecem null; controles não auditados permanecem false. Não substituir null por zero para passar.
- test_aion_p0_h0_iam_finops_preflight_lab.py: testes adversariais de permissão excessiva, falta de valores, teto alterado, cota Free, FX, estresse e valores falsamente declarados. Os preços ilustrativos usados nesses testes NÃO são cotações reais.
- Execução local após checkout: python -B atlasquant_aion_p0_h0_iam_finops_preflight_lab.py docs/aion/AION_P0_H0_IAM_FINOPS_UNPRICED_PROPOSAL_TEMPLATE_20261019.json — sempre retorna HARD_NO_GO e código 2, sem modificar arquivos.

## Fontes oficiais (revisadas em outubro/2026)

- https://aws.amazon.com/pt/s3/pricing/
- https://aws.amazon.com/aws-cost-management/aws-pricing-calculator/
- https://aws.amazon.com/kms/pricing/
- https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock-managing.html
- https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-with-s3-policy-actions.html
- https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html
- https://developers.cloudflare.com/durable-objects/platform/pricing/
- https://docs.aws.amazon.com/cost-management/latest/userguide/bcm-lite-use-budget.html

## Próxima prioridade

Não multiplicar simuladores para substituir custódia real. Auditar os IDs canônicos dos P0 SQLite e plano H0, fechar a matriz de orçamento/identidade até o ponto de futura decisão explícita e preservar hard stops já existentes. Sem confirmação do proprietário, NÃO criar AWS/Cloudflare ou iniciar retenção COMPLIANCE que não pode ser reduzida.

Status: 0/6 P0 homologados, HARD NO-GO, Worker OFF, ZERO_AUTO_RESEND, nenhum gasto/merge/deploy.
