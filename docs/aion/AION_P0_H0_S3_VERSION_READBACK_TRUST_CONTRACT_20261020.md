# AION P0 H0 — contrato de leitura de versão e retenção (S3 Object Lock), SEM matrícula

**20/10/2026 | DRAFT LAB | HARD NO-GO | 0/6 P0 homologados.**  
**Escopo:** examinar *somente a coerência* de um pacote de metadados S3 simulado. Não autentica AWS nem emite recibo, não realiza `HEAD`, `GET`, `ListObjectVersions` ou `GetObjectRetention` reais, não confere relógio de confiança, IAM, retenção COMPLIANCE real, assinatura, Account ID, custódia externa ou efeito do produtor. Todas as saídas ficam `BLOCKED`.

## Evidência oficial para desenhar um futuro protocolo

- **S3 Object Lock COMPLIANCE** protege uma **versão específica** contra exclusão e sobrescrita durante a retenção, mas **não impede novas versões nem delete markers**. Uma leitura só do nome lógico da chave, ETag, `latest` ou um `versionId` entregue pelo mesmo emissor que pode causar o rollback **não prova qual é o último estado verdadeiro**. Referência: https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html .
- **`HeadObject`** com `versionId` exato pode devolver `x-amz-object-lock-mode` e `x-amz-object-lock-retain-until-date`; esses metadados **podem estar ausentes se o leitor não tiver `s3:GetObjectRetention`**. Não considerar campo ausente como COMPLIANCE por padrão. Conferir também `GetObjectRetention`, `GetObject` da mesma versão e digest/corpo. https://docs.aws.amazon.com/AmazonS3/latest/API/API_HeadObject.html e https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock-managing.html .
- **`ListObjectVersions`** ajuda a observar versões concorrentes/delete markers, sujeito a paginação e permissão. Uma listagem incompleta, obsoleta ou obtida de credencial comprometida não é certificado de último head; o pin de versão precisa ser vinculado a trilha *autenticada independentemente* e a um high-water monotônico fora dos administradores que controlam executor + custodiador.
- **S3 Inventory pode levar até 48 horas** e não serve como confirmação fresca H0 antes de primeiro efeito. `GetObjectRetention` ou `HeadObject` expõem estado mais atual, mas apenas dentro do limite das permissões e domínio de confiança da AWS. https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock-managing.html .
- **CloudTrail S3 data events** pode registrar `GetObject`, `HeadObject`, `ListObjectVersions`, `PutObjectRetention` etc., *se configurado e administrado de forma realmente independente*. Um evento entregue à mesma conta não substitui uma assinatura atestada nem prova que nenhuma versão posterior foi omitida. https://docs.aws.amazon.com/AmazonS3/latest/userguide/cloudtrail-logging-s3-info.html .

## Ordem candidata de verificação produtiva — **NÃO IMPLEMENTADA**

1. Consultar identidade do proprietário/host/tenant por canal aprovado e distinto; determinar key/policy PINNED fora do banco que pode ser restaurado. Negar claims `verified=true` fornecidos pela própria execução.
2. Confirmar custodiador CAS remoto em conta e administração distintas, head/epoch/nonce e existência da reserva; timeout ou readback inconsistente deixa operação em `UNKNOWN`, nunca repete o envio.
3. Obter por **leitor com IAM independente e credenciais segregadas** uma âncora S3 com `versionId` esperado, `GetObject` e `GetObjectRetention` da **mesma versão**, comparar digest/escopo/epoch/seq/payload e garantir COMPLIANCE até além da janela definida de recuperação.
4. Confrontar `ListObjectVersions` com paginação completa e delete markers, incluindo `HEAD` atual e versões concorrentes. Não presumir que uma versão retida antiga ainda seja *o último head*; uma nova versão pode ser criada mantendo a antiga imutável.
5. Comparar com um **high-water mais recente assinado/atestado por identidade fora dos três domínios de rollback**, sujeito a pinning/rotação/revogação de chaves e política de anti-replay/freshness. Se a fonte confiável do head atual não está disponível, **BLOCKED**, mesmo com metadados íntegros.
6. Ainda exigir **recibo de efeito do fornecedor autenticado** ou prova terminal de ausência de efeito; uma âncora de intenção não prova que SMS, pagamento ou trade realmente aconteceram ou deixaram de acontecer. **ZERO_AUTO_RESEND**.

## O que o laboratório realmente verifica

`tests/test_aion_p0_h0_s3_version_readback_evidence_lab.py` implementa um classificador de **forma sintética** com **22 testes de abuso**: pin de versão ausente ou divergente entre `HeadObject`/`GetObject`/`GetObjectRetention`; retenção inexistente, em GOVERNANCE ou expirada; cabeçalho de retenção ausente (IAM); versões antigas/novas, delete markers, paginação incompleta; scope/epoch/sequence conflitantes; digest de payload divergente; objetos hostis e falsos `signed=true`; headers aparentemente perfeitos ainda sem autoridade. As `22` saídas sempre têm `state=BLOCKED` e TODAS as flags de produtor, issuer, frescor, WORM, primeiro efeito, Worker e retry `False`. **PASS = formato inspecionado, NÃO AWS autenticada ou P0 fechado**.

Completa os modelos anteriores de [duas custodias](AION_P0_H0_CLOUDFLARE_DO_CUSTODY_GATE_PROPOSAL_20261019.md) e [três domínios simulados](AION_P0_H0_THREE_DOMAIN_ROLLBACK_ADVERSARIAL_REVIEW_20261020.md). Não substitui os 32 ERROR Outbox/Saga, a Quality canônica RED ou Security 365.

## Gates reais que faltam e decisão de custo

- Conta AWS + custodiador/cloud *realmente separados*, MFA/RBAC mínimos e emissor de assinatura matriculado por canal diferente da execução;
- S3 Object Lock COMPLIANCE, versioning, retenção e `versionId` reais, readback independente e trilha antirollback externa, teste de delete marker/PITR/rotação;
- Owner/H0, recibo COMMITTED_EFFECT e eventual `NO_EFFECT_FENCED` continuam bloqueados;
- **Não contratar/provisionar AWS, Cloudflare, KMS, CloudTrail nem armazenamento WORM sem orçamento aprovado**. Retenção COMPLIANCE não pode ser simplesmente encurtada, e custos de versões, operações, chave e logs devem caber no teto operacional antes de criação;
- Não usar telefones, dados de clientes ou chaves no LAB. Worker OFF, HARD NO-GO, ZERO_AUTO_RESEND.

**Veredito:** este é um contrato de auditoria e falsificação de alegações. Não pode ser ligado ao pipeline produtivo como `READY` nem aceitar nenhum callback/assinatura fabricada.