# A190 G10 — decisão de custódia externa: critérios, opções oficiais e custo (SEM CONTRATAÇÃO)

**Data local da pesquisa:** 23/10/2026, horário de Cuiabá/AMT. **Missão:** issue #1486. **Base:** G9 Draft #1496. **Resultado decisório:** NENHUM candidato homologado, NENHUMA escolha operacional/fornecedor, NENHUM acesso externo provisionado.

## Resultado de segurança

G0–G9 demonstraram, por testes Windows/Ubuntu e contraexemplos, que principal local diferente, assinatura Ed25519 e processo fornecedor simulado **não** resistem ao rollback conjunto por administrador/root do mesmo domínio de controle. Há duas autoridades distintas a comprovar:

1. **Reserva de primeira tentativa:** fonte original autenticada, unicidade de intenção, histórico monotônico fora do poder de restauração do administrador do host AION.
2. **Efeito do fornecedor:** contrato REAL de idempotência e recibo/consulta REAL autenticados por terceiro. Gravação em Cloud DB NÃO prova execução da ordem, pagamento, mensagem ou outro efeito externo.

A escolha técnica deve suportar indisponibilidade H0 com NEGATIVA de novos efeitos, mantendo leitura local rotulada NÃO VERIFICADA. Sem reconciliação autenticada, ACK incerto implica UNCERTAIN / ZERO_AUTO_RESEND.

## Fontes oficiais verificadas em 23/10/2026 e triagem

| Alternativa | Evidência documentada de capacidade | Limite / principal ataque remanescente | FinOps oficial e decisão |
| --- | --- | --- | --- |
| A: serviço dedicado SO no próprio PC | G1/G2/G7: UID/SID e ACL reais isolam aplicativo de menor privilégio | Root/admin local substitui chave e banco; G7 RED | Sem novo serviço. **NÃO serve como raiz independente** |
| B1: Cloudflare Durable Objects SQLite | API de storage transacional fortemente consistente, isolamento por objeto. Workers Free: 100 mil requisições/dia; SQLite free: 100 mil linhas gravadas/dia, 5 milhões lidas/dia, até 5 GB de armazenamento incluído | **PITR pode restaurar até 30 dias**; Durable Objects não possui papel separado do Worker e Editor consegue modificar dados do Data Studio. O dono/admin do Worker pode afetar estado e pin. Sem raiz externa adicional, NÃO fornece monotonicidade antirollback exigida | Gratuito **somente dentro das cotas**, operações excedentes no plano Free falham; plano Paid possui cobrança mínima de Workers e consumo. **CANDIDATO PARA ESTUDO, NÃO GO** |
| C1: AWS DynamoDB com escrita condicional por chave semântica | PutItem/UpdateItem condicional; condição de inexistência previne sobrescrita enquanto item íntegro. IAM possui controle de ações de backup/restore. Modo on-demand cobra leitura/escrita sob demanda; free tier do provisionado oferece 25 WCUs/RCUs e 25 GB segundo o provedor | Admin da conta, credenciais com DeleteItem/DeleteTable/restore/alteração de política, escolha errada de partition key, chave de assinatura externa e recibo REAL continuam pendentes. Não confundir ConditionalWrite com efeito de terceiro ou retenção imutável | **CANDIDATO A PROVA DE CONTROLE ADMINISTRATIVO SEPARADO**, sem cotação final de região/carga/tráfego |
| C2: Google Firestore Standard | Create-document/precondition exists=false; transações atômicas. Free tier para um banco padrão: 20 mil writes/dia, 50 mil reads/dia e 1 GiB armazenado, com limites adicionais de egress | Conta com privilégio de deleção/restore pode substituir fonte; regras de segurança, origem autenticada, recibo do efeito, IAM/quorum e rollback extremo não provados. Documentação diz que transações falham offline, coerente com fail closed | **CANDIDATO A PROVA DE CAMPO**, preço exato além das cotas e zona NÃO cotados |
| C3: Supabase Postgres hospedado | Banco Postgres com índices únicos/transaction em serviço gerenciado, útil a CRM, não implica custódia monotônica de efeito | Free pausa após 1 semana sem atividade, sem backups automáticos ou SLA de uptime do plano Free. Pro é no mínimo US$25/mês antes de acréscimos/efetivo câmbio. Acesso admin e função privilegiada ainda podem mudar dados | **NÃO PRIORIZAR PARA CUSTÓDIA H0/P0**, dado orçamento restrito e falta de prova independente |

### Links primários (revalidar antes de qualquer autorização financeira)

- Cloudflare DO pricing (atualizado oficialmente em outubro/2026): https://developers.cloudflare.com/durable-objects/platform/pricing/
- Cloudflare DO SQLite/PITR: https://developers.cloudflare.com/durable-objects/api/sqlite-storage-api/
- Cloudflare DO roles: https://developers.cloudflare.com/workers/authorization/durable-objects/
- AWS DynamoDB pricing/free tier: https://aws.amazon.com/dynamodb/pricing/
- AWS conditional idempotent writes: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/WorkingWithItems.html
- AWS IAM backup/restore: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/backuprestore_IAM.html
- Firestore free quotas: https://docs.cloud.google.com/firestore/quotas
- Firestore precondition exists=false: https://docs.cloud.google.com/firestore/docs/reference/rest/v1/Precondition
- Firestore transactions offline: https://docs.cloud.google.com/firestore/native/docs/manage-data/transactions
- Supabase pricing Free/Pro/pausing/backups: https://supabase.com/pricing

Valores e cotas são referências de páginas oficiais em data específica, NÃO orçamento formal, preço final em reais ou garantia de elegibilidade. A quantidade de operações do AION ainda é DESCONHECIDA.

## FinOps conservador e condição de compra

**Teto confirmado pelo proprietário:** R$200/mês regra geral; excepcionalmente R$250 somente mediante justificativa e aprovação pontual. Render (~US$19 + US$7) é referência HISTÓRICA informada pelo usuário, **não fatura atual verificada**. Não temos neste ponto câmbio, tributos, franquias, faturas consolidadas nem projeção de carga, portanto a margem real é DESCONHECIDA.

Condição calculável para futura proposta, sem ocultar egress/backup/assinatura:

- custo_total_BRL = serviços_existentes_BRL + (custo_novo_USD + APIs_auxiliares_USD + rede_USD + retenção_USD) * câmbio_efetivo + tributos_BRL;
- budget_room = 200 - custo_total_BRL;
- gate FINOPS = PASS somente com orçamento de região/carga, faturas reais, conta segura, hard limit/alerta e **aprovação expressa Mikael**; nunca inferir que faixa gratuita torna o serviço gratuito ou seguro em produção.

**Não ativar plano pago, cadastrar cartão, abrir conta, criar Worker, elevar quota ou armazenar credencial agora.**

## Contrato de prova externa — nenhuma linha autoatestada conta como fechamento

Exigir evidência independente para CADA gate (não basta marcar Boolean):

1. Provador HUMAN_OWNER autenticado por canal fora do host AION, escopo, revogação e confirmação de efeito.
2. Original_event com emissor confiável, semântica original estável, canonicalização, nonce, tenant, contexto e versionamento.
3. Credencial do aplicativo de escopo somente invocação controlada; AION/root comprometido NÃO pode listar/alterar backup ou mexer na raiz pública, KMS, política, logs e conta cloud administrativa.
4. Monotonicidade após restore conjunto do host e reinício H0; terceiro que detém o piso deve provar que houve sequência maior e recusar rollback.
5. Teste com conta/papel administrativo adversarial configurado conforme threat model; privilégio efetivo verificado por logs nativos, não simulado.
6. Conditional reservation concorrente por idempotency key emitida/autenticada por terceiro; IDs alternativos com mesmo significado devem colidir.
7. Sender apenas após autorização válida, journal-first e não antes; camada de rede não deve permitir bypass por callback Python autoatestado.
8. Recibo de efeito realmente vindo do fornecedor do efeito, com chave de assinatura/precondição ligada a fonte independente e acesso de leitura pós-ACK incerto.
9. Falta de autoridade, revogação, clocks conflitantes, conta suspensa, timeout e erro retornam **DENY** ou **UNCERTAIN**, jamais reenviar automaticamente.
10. Chave externa/pin publicados e revogados por canal não controlado pelo mesmo admin de host, com evidência imutável auditável.
11. Evidência por Windows e Ubuntu com SHA/logs, incluindo rollback de ambos os lados e downtime; dados sintéticos primeiro, sem Worker em produção.
12. Cobertura de custo, alertas e travas de orçamento, termos de retenção, SLA, LGPD, região de dados e acesso do proprietário.

A prova de idempotência da reserva NÃO substitui prova de idempotência do fornecedor. Um Banco remoto sem raiz/custódia independente **não satisfaz** o problema G7–G9.

## Escolha provisória e próximo bloco

- **A local:** descartada como autoridade final, pode permanecer mecanismo de defesa em profundidade.
- **B1 Cloudflare:** preço atrativo para estudo, mas PITR e permissão Editor exigem piso independente adicional; NÃO privilegiar custo em detrimento da raiz.
- **C1 DynamoDB / C2 Firestore:** candidatos a **ensaio adversarial futuro mediante autorização de conta/sandbox sem efeitos**, com papéis de IAM separados e demonstração externa.
- **C3 Supabase:** não priorizar para P0/H0 por pausa e custo/propriedade.
- **Decisão final:** NÃO ESCOLHIDO / HARD NO-GO até prova de divisão REAL dos domínios administrativos e contrato do fornecedor do efeito. Evidência sintética dos blocos anteriores permanece útil ao protocolo, não à homologação.

**0/6 P0 — HARD NO-GO — UNCERTAIN — ZERO_AUTO_RESEND.** Sem merge/main, deploy, Worker, conta/serviço, contrato ou gasto.
