# A190 G11 — envelopes OFFLINE DynamoDB/Firestore com identidade semântica assinada

**Data local:** 23/10/2026, Cuiabá. **Missão A190 #1486**, sobre G10 Draft #1497. **Status: LAB somente documental. Não há integração externa funcional.**

## Problema específico atacado

G10 selecionou dois candidatos para **futura pesquisa**, não para uso real: escrita condicional AWS DynamoDB e precondição Firestore. Mesmo essas funções podem ser configuradas incorretamente. Na AWS, PutItem sem condição sobrescreve registro existente; no Firestore, patch sem currentDocument.exists=false pode alterar o documento já existente. Além disso, usar request_id como chave em vez do evento de negócio autenticado permitiria duplicação semântica.

G11 constrói apenas envelopes JSON de intenção, a partir de um **evento LAB assinado pela chave de origem do G8**. A chave nativa é SHA256 canônico de schema, tenant e semantic_digest validados pela assinatura da fonte. Não são incluídos ID autoalegado do cliente, request_id ou event_ref nessa chave, para que mudar rótulos não gere uma nova reserva.

## Regras por provedor — nenhum cliente SDK instalado

### AWS DynamoDB — contrato de tabela sintética

- Tabela presumida AION_A190_G11_LAB_ONLY: **apenas partition key PK**, sem sort key. Se a tabela real tiver chave composta, é necessário refazer o modelo e adversarial tests; UNIQUE depende da chave completa.
- PutItem precisa de ConditionExpression attribute_not_exists(#pk) com alias #pk -> PK, e ReturnValues NONE. Sem essa condição, PutItem poderá substituir registro. Item armazena tenant/semantic_digest/original_ref/request_id, com state RESERVED_STORAGE_ONLY e real_effect false.
- GetItem da PK derivada usa **ConsistentRead true**, já que default da API é eventual.
- DeleteItem, UpdateItem, BatchWriteItem, RestoreTableFromBackup, TransactWriteItems e qualquer operação não listada neste ensaio são NEGADOS pelo contrato documental. Essa allowlist NÃO equivale a policy IAM real ou garantia contra root da conta.
- FONTE PRIMÁRIA: https://docs.aws.amazon.com/amazondynamodb/latest/APIReference/API_PutItem.html
- FONTE PRIMÁRIA: https://docs.aws.amazon.com/amazondynamodb/latest/APIReference/API_GetItem.html
- FONTE PRIMÁRIA: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Expressions.ConditionExpressions.html

### Google Firestore Standard — contrato de documento sintético

- Documento tem ID nativo derivado da mesma identidade semântica, em coleção aion_g11_reservations de projeto **sintético**.
- PATCH v1 com precondition currentDocument.exists=false; uma reserva anterior não pode ser sobrescrita por nova requisição bem-formada, enquanto o documento continuar presente.
- GET do documento nativo em versão atual, sem readTime passado; segundo a API oficial, o GET usa consistência forte por padrão.
- DELETE, POST livre, BATCH_WRITE sem semântica condicional são NEGADOS no pré-flight, sem pretender que isso imponha controle IAM/Firestore real.
- FONTE PRIMÁRIA: https://docs.cloud.google.com/firestore/docs/reference/rest/v1/projects.databases.documents/patch
- FONTE PRIMÁRIA: https://docs.cloud.google.com/firestore/docs/reference/rest/v1/Precondition
- FONTE PRIMÁRIA: https://docs.cloud.google.com/firestore/docs/reference/rest/v1/projects.databases.documents/get

## Política de resultado (mesma para as duas interfaces)

| Resposta observada em um futuro provedor | Regra local que o G11 prepara | Confiança de efeito |
| --- | --- | --- |
| Falta de ACK, timeout, conexão quebrada | UNCERTAIN_ZERO_AUTO_RESEND | Zero; consulta posterior somente leitura |
| ConditionalCheckFailed (DynamoDB) ou ALREADY_EXISTS/FAILED_PRECONDITION (Firestore) | Duplicado: consultar chave nativa em modo somente leitura | Zero; não reenviar |
| HTTP sucesso em reserva | STORAGE_RESERVATION_ACK_NOT_EFFECT_PROOF | Prova no máximo reserva DB, não execução de fornecedor |
| HTTP sucesso em consulta | STORAGE_READ_ONLY_NOT_EFFECT_PROOF | Documento armazenado não equivale a recibo de corretora/banco/provedor |
| Body autoalega EFFECT_CONFIRMED ou contém assinatura inventada | Ignorar essa alegação para efeito | Requer assinatura de fornecedor verdadeiramente independente |
| Operação exclui/atualiza histórico ou tenta transação sem precondição | DENY no laboratório | IAM externo ainda PENDENTE |

Importante: o adaptador é um **gerador de formato de requisição**, nunca uma biblioteca de execução. Em cada retorno: execution_allowed=false, external_root_verified=false, vendor_effect_verified=false e HARD_NO_GO_NOT_AUTHORIZED_TO_EXECUTE.

## Threat model ainda NÃO satisfeito

1. A chave do emissor de evento é efêmera e auto-gerada pelo runner LAB; nenhum HUMAN_OWNER, autoridade real de evento ou vínculo externo foram comprovados.
2. Não há contas AWS/Google, IAM, KMS, chaves públicas externas, documentação de contrato assinado, limites de produção, quotas autorizadas ou testes com provedor real.
3. Condições de escrita impedem sobrescrita **somente enquanto o item e as permissões permanecerem intactos**. Admin cloud/root com Delete/Restore/SetPolicy ainda pode reabrir uma chave; a garantia de antirollback independente não foi demonstrada.
4. Não existe envio verdadeiro de efeito. Mesmo um ACK assinado do banco provaria armazenamento, nunca operação efetuada por um terceiro.
5. Sem energia, conta suspensa ou rede H0, negar novos efeitos; qualquer tentativa incerta mantém ZERO_AUTO_RESEND. Preços/custos e dados reais permanecem fora do escopo.
6. Ficam pendentes cinco external-RED por SO, 43 advisories, Quality/Security canônicas e os seis P0.

## Próximo gate verificável

Uma futura avaliação externa precisará de contas/sandboxes autorizados, papéis admin separados, execução do mesmo par de escritas reais com race/rollback/restore IAM, pin e identidade reais e evidência do fornecedor do EFEITO. Não registrar conta ou token em antecipação.

**0/6 P0 HOMOLOGADOS — HARD NO-GO — UNCERTAIN — ZERO_AUTO_RESEND.**

Sem merge, main, deploy, Worker, criação de conta, cartão, contratação, novo gasto, cliente, corretora, envio ou credencial externa.
