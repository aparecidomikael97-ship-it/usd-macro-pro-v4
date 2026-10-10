# AION P0 — plano de matrícula real e decisão de serviços externos

**Data:** 10/10/2026. **Base:** Draft #1184 SHA `8d0284eeb44a7f6a8c7cf3b15b7933c01e76e858`. **Issue:** #1178. **Prioridade:** Núcleo + AION.

**ESTADO:** `PRE-ENROLLMENT / NO CLOUD CREATED / HARD NO-GO`. Esta PR especifica o contrato de decisão e rastreamento de prova. **Nenhum campo de status deste documento ou JSON pode liberar um Worker de produção.** Só matrícula real independente, validações físicas, auditoria e decisões HUMAN_OWNER separadas podem conduzir a uma proposta de integração posterior.

## Opção técnica investigada, sem escolha final

**Coordenador transacional candidato:** Cloudflare SQLite-backed Durable Objects, 1 objeto por owner+tenant/workspace, CAS sequencial sem operação remota intermediária, e readback/receipts duráveis. Documentação oficial: https://developers.cloudflare.com/durable-objects/platform/pricing/ e https://developers.cloudflare.com/durable-objects/api/sqlite-storage-api/. DOs estão no Workers Free com limites: 100.000 requests/dia, 13.000 GB-s/dia, 5.000.000 linhas lidas/dia, 100.000 linhas escritas/dia, 5 GB total de dados; limites Free excedidos interrompem operações. Workers Paid possui mínimo de US$5/mês mais uso extra. Custos de Workers chamadores também contam. **PITR permite restaurar o banco até estados anteriores em até 30 dias**; um DO sozinho não prova antirollback administrativo. O status de Free não equivale a zero custo integral de todo o sistema.

**Âncora secundária candidata:** Amazon S3 Object Lock em modo COMPLIANCE **numa conta e domínio administrativo independentes**, com retenção por versão e histórico de cabeças assinadas. Documentação oficial: https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html e https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock-managing.html. A AWS confirma que novas versões e delete markers podem ser criados mesmo quando versões anteriores são WORM. Uma operação GET comum da chave ou assinatura antiga **não** prova o HEAD mais recente. O serviço de matrícula e o cliente precisarão provar enumeração/completude de versões, epoch e sequência atual, sem aceitar o head que o solicitante escolheu. O próprio root da AWS não pode apagar uma versão em COMPLIANCE durante a retenção, porém **a exclusão da conta associada é uma exceção importante no modelo de ameaça**; separar root/custódia de forma verificável. Valor e região do S3 ainda não cotados: https://aws.amazon.com/s3/pricing/.

**Alternativas examinadas:** SQLite somente no PC, Docker no mesmo host, GitHub repository + branch, DO + cabeça assinada armazenada no mesmo DO ou S3 com o mesmo administrador: **inadequadas como testemunha independente contra restauração conjunta**. Segundo domínio é necessário; não afirmar que dois endereços de e-mail no controle da mesma credencial provam independência.

## Contrato de implementação futura, sem deployment

1. **Autoridade antes de rede:** registrar o vínculo OWNER → TENANT → WORKSPACE → `repo/branch/path` em registro auditado e protegido fora do arquivo checkpoint/GitHub/sessão. Aprovação do HUMAN_OWNER e autenticação física com fator resistente a phishing. Os pins públicos de source/coordinator/anchor devem vir de canal out-of-band verificado, não de argumento `trusted` injetável pelo caller.
2. **Leitura atual da âncora:** serviço autenticado recebe desafio nonce imprevisível e único gerado pelo verificador, consulta sua **própria** cabeça persistida e provas de cadeia/versionamento sob retenção, e assina scope/epoch/sequence/SHA/nonce/time. Nunca apenas ecoar um head ou timestamp solicitado. Proteção a rollback/descoberta incompleta, delete markers e paginação; acesso sem prova = nenhum GET do checkpoint.
3. **Consistência de commit:** CAS serializado no coordenador; commit/retention no segundo domínio é OUTRA transação. Não há commit atômico Cloudflare↔AWS por padrão. Perda de resposta, timeout, rejeição 403, derrubada de S3/CF ou fork deixam `UNKNOWN_OUTCOME`; nenhuma repetição de escrita/transação de efeito externo antes de reconciliar remotamente por evidência independente.
4. **Revalidação antes de executor:** após GET exato e CAS/lease, revalidar challenge/head atual, segredo no domínio correto, revogação e fencing. Com witness offline, head divergente, clock inconfiável ou proof revogada: `HARD NO-GO`; nunca fallback para GitHub/local.
5. **Plano de recovery:** procedimento de restauração assinado pelo proprietário e verificador independente, saltar epoch monotonicamente sem reset arbitrário, bloquear todas as ações até reconciliar ambos os domínios e os registros `UNKNOWN_OUTCOME`. Não deletar o histórico legado.

## Custo e capacidade — portas de aprovação, não valores simulados

- Teto de infraestrutura definido: **R$200/mês**, incluindo todos os serviços já existentes, e não somente o novo witness. Ainda **não** há fatura/projeção completa de Cloudflare, AWS, requisições, retenção WORM, logs, backups, região, imposto, variação cambial ou margem de pico. Portanto, `FULL_BRL_BUDGET_QUOTE=BLOCKED`.
- **Orçamento real precisa incluir:** Workers + DO Free/Paid + rows/storage/duration, S3 GB-mês de versões retidas, número de PUT/GET/LIST/LIST VERSIONS e respostas, KMS ou outro custodiante se aplicável, egress/interprovedor, observabilidade, incidências tributárias e câmbio. Plano Paid da Cloudflare não é custo de infraestrutura total.
- **Medição pré-compra:** estimar frequência de proof/nonce por tenant (login, leitura de checkpoint, claim, pre-execução), tamanho de receipt, retenção e crescimento por mês; checar máximos diários/free e comportamento quando atingir cota. Alterar tamanho de lote/frequência só após validar freshness, riscos de stale e replays. Fazer 3 cenários (baixo/esperado/pico) com orçamento detalhado e reserva; não afirmar projeção sem tarifas válidas para região/conta.
- **Dados/LGPD:** confirmar região física e contratual, transferências internacionais, operadores, data minimization, retenção, direitos e incident response. Preferir testemunhar apenas hashes/metadata mínimos, não dados privados do cliente. Decisão separada para criação de contas e aceite de termos.

## Próximas etapas operacionais com critério verificável

| Marco | O que muda | Prova exigida | Pode executar agora? |
|---|---|---|---|
| **0. Inventário e CI** | Ler repositório, estudar APIs públicas, manter Worker bloqueado | Doc + manifest + testes Win/Linux | **Sim**, sem nuvem |
| **1. Decisão financeira/jurídica** | Selecionar provedores, contas e região | Orçamento total em BRL, checklist LGPD e aceite do proprietário | **Não**, depende de informações/cotações/decisão |
| **2. Matrícula física** | Chaves públicas raiz e owner/tenant binding em domínios externos | Verificação de identidade/custódia/rotações e cerimônia HUMAN_OWNER | **Não**, requer aprovação e PC/acesso real |
| **3. Sandbox externo seguro** | Criar namespaces/bucket/chaves de teste, sem dados de clientes | Autorizações específicas, quotas, URLs/canal autenticado, sem deploy de Worker real | **Não** |
| **4. Teste adversarial externo** | CAS simultâneo, PITR, delete markers, falha interdomínios e replay | Receipts reais, endpoints atestados, testes Win/Linux e físicos, quarentena | **Não** |
| **5. Liberação separada** | Integrar provider e candidato a merge/deploy/Worker | nova auditoria P0 + aprovação separada + todos required checks | **Não** |

## Manifest de evidências

`docs/aion/evidence/AION_WITNESS_EXTERNAL_ENROLLMENT_GATE_V1.json` lista **20 gates BLOCKED**, incluindo IAM/admin, proteção WORM, latest-head, inscrição de chaves, custos completos e aprovações específicas. Os campos `evidence_uri`/`evidence_sha256` são nulos porque **nenhuma prova real foi coletada**. O documento não contém secrets e **não é lido pelo Worker como política**. O script de teste verifica que nenhum desses campos vira autorização acidental.

## Reutilização verificada no repo

- `atlasquant_aion_trust_root.py`: suporte a registro local de **chaves públicas Ed25519** com validade/revogação. **Um arquivo local escolhido pelo mesmo caller não é pin externo atestado**; matrícula física e domínio de confiança diferente seguem pendentes.
- `atlasquant_aion_v2_authenticated_witness_read_cas_reference.py`, `..._external_witness_rollback_reference.py`, `..._isolated_sqlite_witness_cas_reference.py`: matemática nonce/CAS/rollback, **sem provider real**.
- #1179, #1184: source binding e resposta de desafio sob **chaves sintéticas**, sem matrícula.
- #1180–#1182: runner fail-closed, readiness `BLOCKED` e **sem GET de dados privados sem prova**. Nenhum caminho de aprovação pode vir deste ADR.

**Status final:** `PARTIALLY_CLOSED / HARD NO-GO`. Não criar contas, contratar plano, iniciar billing, gerar chaves reais, executar Worker/Render, instalar, migrar ou mergear sem novas autorizações do proprietário.


## Novo P0 operacional: rota Fail Closed e armazenamento por objeto (10/10/2026)

A documentação oficial da Cloudflare [Workers Limits](https://developers.cloudflare.com/workers/platform/limits/) explica que, ao atingir **100 mil requests/dia no Workers Free**, a rota em modo **Fail Open** pode contornar o Worker completamente, deixando o origin processar sem o código de segurança. Para uma testemunha AION que aplique autenticação/source binding, **isso pode anular toda a política**. É obrigatório comprovar **Fail Closed** na rota efetiva (ou arquitetura equivalente que nunca tenha caminho de bypass ao origin); quota 1027 deve negar acessos, nunca servir dados protegidos. A configuração de rota no Dashboard/API e teste adversarial físico devem fornecer evidência independente: um campo de JSON, workflow verde ou simulação não provam o estado publicado. O tipo real de endpoint (Route, Custom Domain, workers.dev) deve ser verificado antes de aplicar esse controle; não declarar automaticamente que todas as topologias usam a mesma opção de rota.

Conforme [Durable Objects Limits](https://developers.cloudflare.com/durable-objects/platform/limits/), o SQLite-backed DO em Workers Free suporta até **1 GB por Durable Object** e **5 GB por conta**; quando o objeto atinge o limite, operações de escrita falham com SQLITE_FULL, mesmo que a conta inteira ainda esteja abaixo de 5 GB. Falha de gravação do head/witness tem de virar UNKNOWN_OUTCOME/NO-GO com reconciliação independente, não retry cego. Medir maior objeto, total de conta, quotas e margem de crescimento.

O manifest agora contém **20 gates BLOCKED** (incluindo `CLOUDFLARE_SECURITY_ROUTE_NO_BYPASS` e `CLOUDFLARE_DO_SINGLE_OBJECT_STORAGE_HEADROOM`), todos sem evidência de implantação. Não existe endpoint, rota, domínio ou conta Cloudflare criada por este trabalho.
