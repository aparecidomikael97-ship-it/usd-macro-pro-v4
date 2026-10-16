# A122 — Avaliação documental de custódia independente do AION

**Data:** 16/10/2026 | **Classificação:** DESIGN / RESEARCH / HARD NO-GO | **Base:** A121 `30ff8b28a2977418e770ea012cfae65eb085aa63`

**Decisão:** Selecionar **AWS DynamoDB regional transacional + diário protegido por S3 Object Lock Compliance + assinatura AWS KMS assimétrica**, em **conta AWS com administração separada da conta/runtime AION**, **apenas como candidato para uma futura prova de conceito**, NÃO para implantação ou contratação. **Google Cloud Firestore + Cloud Storage Bucket Lock** fica como alternativa comparável. **Cloudflare Durable Objects, sem testemunha WORM separada, não atende** ao requisito de antirollback demonstrado pela A120/A121. Nenhuma opção está homologada.

## 1. Fronteira de ameaça e afirmações que não faremos

- A121 mostrou que o SQLite do AION e outro SQLite chamado de "custodiante" sob a mesma conta/admin podem ser revertidos juntos; o teste #23 reproduz **segundo FakeSender após rollback do custodiante**. O fato de 23/23 testes terem passado inclui um contraexemplo positivo; não são 23 garantias.
- F1/T1 = atestar **origem, titularidade e monotonicidade do checkpoint** por âncora fora do restore do AION. H0 = provar a emissão e a semântica causal de **efeitos externos**. F2 = consentimento físico do HUMAN_OWNER. **Uma função não substitui a outra**.
- Um armazenamento WORM não é CAS nem prova que o provedor SMS não enviará tardiamente. Um banco CAS não cria imutabilidade administrativa. Assinar um hash não atesta que os fatos correspondam ao mundo real.
- Modelo de adversário: comprometimento completo do AION local, de seus backups e credenciais de aplicação. Custodiante e auditor precisam ser administrativamente independentes desse comprometimento. O controle exclusivo do administrador de custódia ou da conta cloud **não** está demonstrado imune: exigir trilha, separação de funções, monitoramento, proteção de contas e evidências externas adicionais.

## 2. Comparação das opções (pesquisa oficial em 16/10/2026)

| Opção | Capacidade documental | Falha que permanece | Decisão |
|---|---|---|---|
| **A. AWS DynamoDB (única região de escrita) + S3 Object Lock Compliance + KMS Sign** | DynamoDB `attribute_not_exists()` e transações atômicas regionalmente; leitura forte em tabela (não em GSI); S3 WORM protege cada versão até o fim da retenção; AWS KMS assimétrico assina e pode ser verificado fora da AWS | **Não há transação distribuída DynamoDB→S3→KMS→fornecedor**, mesmo sob duas contas. S3 admite novas versões e delete markers; consultar apenas "latest" é inseguro. Restaurar tabela pode apagar CAS: verificar ancoragem antes de autorizar qualquer nova intenção. Administrador da custódia ainda exige governança e testes. | **CANDIDATO A ESTUDO CONTROLADO; NO-GO** |
| **B. Google Firestore + Cloud Storage Bucket Lock** | Firestore oferece isolamento serializável por tempo de commit; Cloud Storage permite bloquear uma política de retenção, irreversivelmente | Transação Firestore e gravação Cloud Storage são dois sistemas separados; política de retenção tem efeitos operacionais irreversíveis e custos. Identidade, papéis, verificador e falha/rollback ainda não provados. | **ALTERNATIVA DOCUMENTAL; NO-GO** |
| **C. Cloudflare Durable Objects (SQLite)** | Armazenamento transacional e consistente; há plano Free e limites de armazenamento documentados | API PITR restaura SQLite embutido até 30 dias; **sozinho reproduz classe de rollback** A121. Worker/DO na mesma conta/admin não equivale a testemunha independente. Precisaria segunda custódia imutável/admin externa. | **REPROVADO COMO SOLUÇÃO ISOLADA; NÃO É REPROVAÇÃO GLOBAL DO FORNECEDOR** |
| **D. GitHub branch/SQLite local/SQS FIFO** | Úteis para desenvolvimento, transporte e rastreio convencional | Mesmo domínio de administração ou deduplicação/TTL sem H0; não resolvem antirollback externo permanente. | **NÃO ACEITOS COMO CUSTODIANTE H0/F1-T1 AUTÔNOMO** |

### Alertas técnicos que invalidam soluções aparentemente fáceis

1. DynamoDB MREC (Global Tables multi-region eventual) usa resolução de conflito por *last-writer-wins*; não tratar múltiplos escritores regionais como CAS global. MRSC existe, porém **não suporta as transações `TransactWriteItems`** requeridas pelo desenho composto. Nesta etapa: **um escritor autoritativo numa região; indisponibilidade => UNKNOWN/BLOCKED**.
2. S3 Object Lock Compliance impede editar/excluir **uma versão protegida**, mas permite criar **outras versões e delete markers**. Exigir auditoria de **todas as versões relevantes** e âncora verificada fora do controle AION; não confiar em leitura de última versão ou simples objeto `HEAD`.
3. Sem commit atômico DynamoDB↔S3: orfandade do ledger ou do WORM após crash pode ocorrer. **Não liberar adaptador externo** enquanto não houver evidência durável, coerente e autenticada. Se qualquer parte perder resposta: **UNKNOWN**, operador humano, **NUNCA retry automático**. As garantias dessa sequência exigem testes de falhas cross-service e desenho de reconciliação; não estão demonstradas.
4. Nem o certificado de assinatura KMS, nem S3 WORM, nem Firestore garantem a propriedade H0 `NO_EFFECT_FENCED` **após** um provedor aceitar a mensagem. Até prova causal do próprio provedor: **HARD NO-GO**.
5. Retenção WORM deve conter **IDs/digests mínimos**, sem telefone, mensagem, CPF ou conteúdo pessoal. Antes de retenção imutável: LGPD, política de retenção, legal basis e resposta a direitos do titular avaliadas juridicamente. Não configurar Compliance ou Bucket Lock sem aprovação específica — ações difíceis/impossíveis de reverter.

## 3. Contrato de custódia alvo — PROPOSTA SEM CÓDIGO PRODUTIVO

```text
AION host / checkpoint (sem credenciais de custódia/admin/fornecedor)
  -> requisição autenticada, nonce novo, digests, owner+tenant+workspace+scope+action
  -> API do custodiante em conta/admin separados
     -> controle de matrícula/assinatura/política fora do checkpoint do AION
     -> verificação monotônica de âncora WORM externa e da ledger atual
     -> CAS regional atômico PREPARE | PRE_FENCE | ISSUE_ONCE
     -> evidência WORM/assinatura em fluxo com tratamento explícito de escrita parcial
     -> apenas quando TODOS gates de emissão estiverem coerentes, FakeSender em sandbox
  -> sem ACK causal verificável: UNKNOWN, preservação e zero repetição
```

Requisitos não negociáveis: source binding exato e out-of-band; permissão IAM AION somente `request/status` com limite, não `delete/restore/PutObjectRetention/Sign`; chaves de fornecedor exclusivas do emissor; logging de contas e verificador externo; antirollback de alta-water + eventos + nonces + id/epoch/tenant; key rotation e revogação; não reutilização após retenção/TTL; plano de incidente e fail-closed sem relógio confiável; orçamento limite firme.

## 4. Critérios de aceite ANTES de qualquer POC externa

| Gate | Evidência exigida | Situação |
|---|---|---|
| G01 | Aprovação explícita do HUMAN_OWNER para custo/conta/sandbox, após termo de risco | **NÃO AUTORIZADO** |
| G02 | Prova de duas contas/identidades administrativamente separadas e IAM AION sem restore/delete/admin/sign | **NÃO EXECUTADO** |
| G03 | Matriculação owner/tenant/workspace/recurso vinculada a fonte externa, assinada | **NÃO EXECUTADO** |
| G04 | Prova de uma única emissão com 32+ concorrentes reais em dois hosts | **NÃO EXECUTADO** |
| G05 | Restore do AION + tentativa de reemissão negada por testemunha independente | **NÃO EXECUTADO** |
| G06 | Tentativa AION de restore/remoção do custodiante bloqueada, log de IAM verificável | **NÃO EXECUTADO** |
| G07 | Restore/split-brain/failover do custodiante com high-water preservado ou fail-closed | **NÃO EXECUTADO** |
| G08 | Retenção WORM/versões/nonce/auditoria e assinaturas em um verificador independente | **NÃO EXECUTADO** |
| G09 | Crash entre CAS, prova WORM, assinatura, adapter, recibo: sem segundo efeito | **NÃO EXECUTADO** |
| G10 | Timeout, 429, 5xx, resposta sem ID, callbacks fora de ordem => UNKNOWN sem reenvio | **NÃO EXECUTADO** |
| G11 | Provedor H0 qualificado para efeito positivo e limite real de NO_EFFECT_FENCED | **NÃO EXECUTADO** |
| G12 | Aprovação LGPD/retenção/dados mínimos + revisão contratual | **NÃO EXECUTADO** |
| G13 | Orçamento completo com limites e alertas: moeda/tributo/FX, logs, KMS, storage, API, transferência, suporte | **NÃO COTADO** |
| G14 | Execução CI/Linux+Windows e autorização F2 física HUMAN_OWNER separadas | **NÃO EXECUTADO** |

Todos os gates continuam abertos. `HARD NO-GO`, `ZERO_AUTO_RESEND`, Worker OFF.

## 5. FinOps: não usar preço inicial isolado como orçamento total

**Orçamento de referência do projeto:** R$200/mês para infraestrutura **total** (inclui Render existente), nenhuma nova despesa sem autorização; eventual aumento somente por necessidade extrema e aprovação. **Despesa contratual atual não verificada nesta rodada; folga = DESCONHECIDA**.

- AWS DynamoDB Free Tier documenta 25 WCU/25 RCU e 25 GB **no modo provisionado**; on-demand é cobrado por requisição. Não considerar a oferta gratuita garantida para a arquitetura nem para todo recurso.
- AWS KMS lista **US$1/mês por chave criada**, além de requisições e eventuais outros serviços. Mesmo valor baixo não é aprovação de despesa.
- Firestore Standard lista cota gratuita de **50 mil leituras e 20 mil gravações/dia, 1 GiB** para um banco elegível; backup/PITR/restores não entram na cota. Bucket Lock/storage, funções, logs, tráfego e outros recursos podem ser cobrados.
- Cloudflare Durable Objects inclui opção Free com limite de **5 GiB por conta SQLite** segundo documentação; preço zero não satisfaz segurança independente.
- A cotação futura deve indicar região, requests por intenção (CAS/leituras/transações), tamanho e número de objetos WORM, retenção, KMS assinaturas, rede egress, logs/CloudTrail, API gateway/compute, alarmes, impostos e câmbio, com cenário normal, pico e incidente e limite firme. Sem orçamento confirmado, **não provisionar**.

## 6. Próximas ações SEGURAS (independentes de cloud)

1. Elaborar contrato JSON/IDL dos recibos e da cadeia WORM, incluindo versões, ID de custódia, issuer, key IDs, nonce, epoch, previous hash e detalhes exatos de intenção.
2. Produzir apenas **testes sintéticos NEGATIVOS** para crash entre DynamoDB↔WORM, indisponibilidade do verificador, bifurcação de cabeçalho WORM, replay, versão nova contraditória, conta A→B, custo desconhecido.
3. Encerrar design review de responsabilidades IAM sem gerar políticas ativas.
4. Preparar a matriz de orçamento de estimativas condicionais, **sem criar recursos ou habilitar billing**.
5. Solicitar autorização separada **somente depois** do relatório de design, riscos, custo mensal máximo e plano de rollback/disable.

## 7. Fontes oficiais consultadas em 16/10/2026

- AWS DynamoDB conditional writes: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Expressions.ConditionExpressions.html
- AWS DynamoDB transactions: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/transaction-apis.html
- DynamoDB global tables MREC/MRSC: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/V2globaltables_HowItWorks.html
- DynamoDB read consistency / GSI: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/HowItWorks.ReadConsistency.html
- AWS S3 Object Lock: https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html
- S3 Object Lock management: https://docs.aws.amazon.com/us_en/AmazonS3/latest/userguide/object-lock-managing.html
- AWS KMS Sign: https://docs.aws.amazon.com/kms/latest/APIReference/API_Sign.html
- AWS KMS pricing: https://aws.amazon.com/kms/pricing/
- AWS DynamoDB pricing: https://aws.amazon.com/dynamodb/pricing/
- Google Firestore transaction isolation: https://docs.cloud.google.com/firestore/native/docs/transaction-data-contention
- Google Cloud Storage Bucket Lock: https://docs.cloud.google.com/storage/docs/bucket-lock
- Google Firestore quotas/pricing: https://docs.cloud.google.com/firestore/quotas ; https://cloud.google.com/firestore/pricing
- Cloudflare Durable Objects transactional storage and PITR: https://developers.cloudflare.com/durable-objects/best-practices/access-durable-objects-storage/ ; https://developers.cloudflare.com/durable-objects/api/sqlite-storage-api/
- Cloudflare limits: https://developers.cloudflare.com/durable-objects/platform/limits/

## 8. Status do projeto

- Base A121 verificada `30ff8b28a2977418e770ea012cfae65eb085aa63`; `main` previamente verificada `5744b2b7b17c84331e6f27c569064993ff587782`.
- A118 PR #1326 Draft/unmerged, 84 diagnósticos históricos Quality A118 (50 FAIL/34 ERROR) OPEN sem rerun; 23 Outbox + 9 Saga ainda dependem do produtor H0. Matriz A115 (#1323) é corte histórico 89 casos, não deve ser somada/substituída.
- 0/6 P0 homologados, 20/20 FIRST_INSTALL bloqueados. **A122 é só decisão de estudo; não há software cloud, CI novo, compra, conta, deploy ou contrato H0 homologado.**
