# Decisão técnica candidata — witness independente do checkpoint AION

**Data da pesquisa:** 10/10/2026. **Issue:** #1178. **Base:** Draft #1182, SHA `b030132888d5f7ea5256c33ffabb2831d75436f3`.

**ESTADO: SOMENTE PESQUISA/REFERÊNCIA — NÃO APROVADO, NÃO MATRICULADO, NÃO IMPLANTADO.**

## Objetivo e decisão preliminar

Para a primeira avaliação técnica, priorizar uma arquitetura **de dois domínios administrativos efetivamente independentes**:

- **Coordenador de operações/tenant:** Cloudflare Workers + SQLite-backed Durable Object (DO) exclusivo por escopo, mantendo cabeça sequencial transacional e CAS sem `await` entre comparação e atualização.
- **Segunda fronteira, não restaurável junto com o coordenador:** histórico assinado de cabeças em **outra conta e outro provedor**, candidato AWS S3 com Object Lock **COMPLIANCE**, retenção e versionamento, com canal separado que devolva a **cabeça realmente mais recente** de forma autenticada, desafiada por nonce e verificável; somente armazenar uma assinatura antiga num bucket **não** prova atualidade.
- **Identidade/assinatura:** matrícula de owner/tenant/workspace e chaves públicas do emissor e witness ancoradas fora do GitHub, app e sessão; duas pessoas/principais/custódias de acesso separadas. A função de estudo não confia em booleans fornecidos pelo app. Enrolar chaves privadas, contas e MFA exigirá decisão e autorização específicas.

É um **candidato para revisão de segurança**, não uma recomendação para contratar ou um desenho operacional concluído. O valor real do DO é coordenar CAS; sua restauração administrativa/PITR torna necessária uma segunda fronteira.

## Evidências verificadas na documentação primária (10/10/2026)

1. [Cloudflare Durable Objects pricing](https://developers.cloudflare.com/durable-objects/platform/pricing/), atualizada em 30/09/2026: Workers Free permite DO com SQLite. Limites informados: 100 mil requisições/dia, 13 mil GB-s/dia, 5 milhões de leituras de linhas/dia, 100 mil gravações de linhas/dia, 5 GB armazenados; ao superar limite Free, operações excedentes falham. Plano Paid tem base mínima de US$5/mês, **fora** armazenamento/uso adicional, imposto e câmbio; falta orçamento da cadeia inteira.
2. [Cloudflare SQLite-backed Durable Object storage](https://developers.cloudflare.com/durable-objects/api/sqlite-storage-api/): consistência forte e transações dentro de um objeto, mas **PITR restaura a base de dados inteira a pontos anteriores em até 30 dias**. Um objeto sozinho não resiste a administrador com capacidade de restaurar sua cópia. Não assumir inviolabilidade/antirollback só com assinatura local.
3. [AWS S3 Object Lock](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html): modo COMPLIANCE evita substituir/remover **uma versão protegida** durante retenção, inclusive por root. Não proíbe criar outras versões ou delete markers; proteção de versão **não equivale à autoridade do 'último head'**. Modo GOVERNANCE permite bypass privilegiado e foi rejeitado como único segundo controle.
4. [AWS S3 Object Lock configuration](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock-configure.html): ativação, retenção, custos e consequências operacionais requerem avaliação e confirmação humanas. Nenhuma conta, bucket, Object Lock ou chave foi criada.

## Reutilização no AtlasQuant — evitar trabalho repetido

| Artefato existente no repositório | Capacidades de referência | O que NÃO prova |
|---|---|---|
| `atlasquant_aion_v2_authenticated_witness_read_cas_reference.py` / ADR V2 Signed Witness | leitura assinada com desafio fresco e pré-condições CAS | trusted pin remoto, matrícula, escrita transacional externa |
| `atlasquant_aion_v2_external_witness_rollback_reference.py` | compara cabeça externa e snapshot, inclusive restauração/rollback | atualidade se atacante fornece cabeça stale consistente |
| `atlasquant_aion_v2_isolated_sqlite_witness_cas_reference.py` | CAS persistente SQLite, reopen, operação idempotente simulada | domínio de falha independente quando as duas bases podem ser restauradas |
| `atlasquant_aion_runtime_source_boundary_ref_v1.py` (#1179) | binding matemático owner/tenant/resource, assinaturas source + witness | chaves reais inscritas, challenge genuíno e witness atual comprovado |
| `atlasquant_aion_global_worker_source_gate_v1.py` (#1180) | bloqueia execução/GET real sem fonte verificada | autorização positiva |
| Readiness #1181/#1182 | status BLOCKED honesto, sem GET para fonte sem vínculo | operação liberada |

Não adaptar nenhum simulador para produção sem provedor de origem independemente autenticado.

## Modelo de duas etapas contra rollback e ambiguidade

1. **Enrollment aprovado do proprietário** cria documento de recurso `owner → tenant → workspace → (repo, branch, path)` e pins do emissor/witness com canal de verificação fora do GitHub e equipamento autenticado. Capacidade de revogação, rotação e recuperação real.
2. **READ fresco**: app gera nonce criptográfico de uso único, desafio de escopo/epoch/sequence. Um endpoint witness autenticado por chave inscrita assina nonce e **head atual obtido pelo próprio servidor**, não ecoa um `head` fornecido pelo caller. Retenção assinada numa segunda administração e leitura da sequência mais recente são ambas obrigatórias.
3. **Checkpoint GET** somente após prova de origem e cabeça atuais. Validar SHA exato, payload integrity, resource binding e revogação. Caso contrário, zero dados privados/zero executor.
4. **CAS de claim/append**: serializável no coordenador; publicar prova durável no domínio separado. **Não há atomicidade automática entre DO e S3**. Se apenas um lado avançou, ou resposta se perdeu, congelar operação em `UNKNOWN_OUTCOME` e reconciliar as duas fontes por leitura autenticada antes de qualquer retry, nunca assumir sucesso/falha.
5. **Revalidação final** da cabeça assinada e tenant antes de executor, respeitando fence, kill switch e autorização HUMAN_OWNER. Se witness cair, clock falhar, aparecer fork, sequência recuar ou houver suspensão/revogação, permanecer `HARD NO-GO`.
6. **Recovery**: não restaurar cabeça remota a partir do checkpoint local; procedimento de break-glass com prova separada do proprietário, revogação controlada, publicação de novo epoch e auditoria. Validar restauração parcial/fork/backup antes de operação.

## Comparação e custo (sem contratar)

| Alternativa | Vantagem | Risco bloqueante | Estado financeiro |
|---|---|---|---|
| Cloudflare DO isolado | CAS por objeto; plano Free comporta **pesquisa de baixo tráfego** | PITR/admin pode voltar cabeça; sem segundo domínio | piloto teórico dentro Free, **sem conta/deploy** |
| CF DO + S3 Object Lock Compliance em conta independente | domínios de operação distintos; retenção de versões | precisa provar 'latest' por fonte autenticada, isolamento administrativo, recover/UNKNOWN_OUTCOME e seleção segura de políticas | CF Free é possível; **AWS/egresso/ops/FX/impostos não cotados** |
| Witness local SQLite/mesmo PC/GitHub | protótipo sem contratação | rollback conjunto; não fornece testemunha externa | custo adicional zero, **reprovado para produção** |
| S3 Object Lock apenas | versões WORM protegidas | não tem CAS de cabeça + fresh READ autêntico completo | custos não cotados; insuficiente sozinho |

**Teto já estabelecido:** R$200/mês para infraestrutura. **Não foi estimado custo total em reais, nem consultada fatura, nem contratada ou provisionada conta.** A opção preferida pode exceder o teto quando agregados AWS, tráfego, armazenagem, tributação, monitoramento, logs e câmbio. Exigir cotações e orçamento aprovado antes de qualquer teste externo.

## Aprovações e evidências pendentes (gates P0)

- [ ] Decisão HUMAN_OWNER específica sobre fornecedores/contas independentes, política de LGPD e orçamento.
- [ ] Fonte de verdade de owner/tenant inscrita e assinada fora do GitHub, avaliação de IAM e segregação de administradores.
- [ ] Enrollment de chaves reais e recuperação/rotação/revogação com confirmação física autorizada.
- [ ] Serviço de testemunha realmente implantado e autenticado; challenge-response com nonce único, latest head e prova de monotonicidade protegida.
- [ ] Testes realistas contra PITR, rollback conjunto, replay dentro de 300s, head falso, fork, conta A→B, S3 delete marker, perda de resposta CAS, queda, ataque de relógio, revogação e restore.
- [ ] CI Windows/Linux, E2E proprietário Windows, auditoria independente e autorização separada para merge/deploy/Worker/instalação.

## Entrega da próxima Draft

`atlasquant_aion_witness_architecture_review_reference_v1.py` confere SOMENTE invariantes autodeclaradas do plano (dois domínios, modo Compliance, desafio fresco, CAS, recovery, separação de chaves/contas, custo não cotado e ausência de autorização). Até um plano que satisfaz tudo retorna `RESEARCH_CANDIDATE_UNTRUSTED`, `production_no_go=true`, `worker_authorized=false`. Não é um gate de produção nem evidência de trust real. A CI reprova dados ambíguos e confirma que os gates reais permanecem bloqueados.

**Status:** `PARTIALLY_CLOSED / HARD NO-GO`, #1178 e #1169 abertas, Core V1 congelado, nenhuma compra, novo serviço, Worker, deploy, merge, instalação, migração ou alteração de chaves.
