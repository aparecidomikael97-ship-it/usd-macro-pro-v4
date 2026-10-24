# A190 G11 — evidência CI e limites dos adaptadores condicionais OFFLINE

**Data local:** 23/10/2026, Cuiabá (AMT). **PR Draft #1498**, empilhada sobre G10 #1497. **Código/workflow/testes efetivamente executados:** SHA 5e96e35180b82bfb6f1745333f5ceabca9304e8d.

## Resultado CI confirmado

- [GitHub Actions run #40050961568](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40050961568): completed / **success**.
- **Ubuntu** job 120743307692: **20 tests, OK**.
- **Windows** job 120743307943: **20 tests, OK**.
- Total: **40 execuções de testes de formato e lógica local**, não testes funcionais dos serviços remotos.
- Python 3.12, cryptography 50.0.2 para assinatura Ed25519 LAB da origem do evento. Não houve AWS SDK, Google SDK, credencial, token, HTTP a terceiros, conta, Worker ou efeito.

## Evidências principais presentes nos dois logs

| Critério | Marcador / verificação | Qualificação |
| --- | --- | --- |
| Dois formatos usam mesma chave semântica original assinada | A190_G11_SIGNED_NATIVE_KEY_CROSS_PROVIDER=STABLE | PASS laboratório de código |
| Requisições com request ID diferente não criam chave nova | A190_G11_CALLER_REQUEST_ID_CANNOT_CHANGE_NATIVE_KEY | PASS laboratório de código |
| Eventos de origem com refs alternativas, mesma intenção | A190_G11_SIGNED_EVENT_ALIASES_SAME_SEMANTIC=ONE_KEY | PASS laboratório de código |
| Origem falsificada/alterada | A190_G11_ATTACKER_SELF_PINNED_EVENT=DENIED; A190_G11_TAMPERED_SEMANTIC_AFTER_SIGN=DENIED | PASS sob pin sintético retido |
| Tenant assinado participa da identidade | A190_G11_TENANT_IN_SIGNED_NATIVE_KEY=TRUE | PASS laboratório de código |
| DynamoDB PutItem com condição | A190_G11_DDB_ATOMIC_CONDITIONAL_PUT_SHAPE=DOCUMENTARY | Alinhado à documentação; NENHUMA escrita AWS real |
| DynamoDB GetItem com ConsistentRead | A190_G11_DDB_STRONG_GET_SHAPE=DOCUMENTARY | Alinhado à documentação; NENHUMA leitura AWS real |
| Firestore PATCH currentDocument.exists=false | A190_G11_FIRESTORE_EXISTS_FALSE_PATCH_SHAPE=DOCUMENTARY | Alinhado à documentação; NENHUMA chamada Google real |
| Firestore GET padrão sem snapshot antigo | A190_G11_FIRESTORE_DEFAULT_STRONG_GET_SHAPE=DOCUMENTARY | Alinhado à documentação; NENHUMA leitura Google real |
| Remoção, restauração e mutações não condicionais fora da allowlist | A190_G11_DELETE_UPDATE_RESTORE_NONCONDITIONAL_MUTATION=DENIED | **Apenas guarda local**, NÃO IAM real |
| ACK de storage desconhecido e duplicata condicional | A190_G11_UNKNOWN_STORAGE_ACK=UNCERTAIN_ZERO_AUTO_RESEND; A190_G11_PROVIDER_ALREADY_EXISTS=READ_ONLY_NO_RETRY | Fail closed, sem reenvio |
| Resposta OK do banco não confirma efeito de terceiro | A190_G11_CLOUD_DB_COMMIT_IS_NOT_VENDOR_EFFECT=ENFORCED | Sem fornecedor real |
| Resposta falsa dizendo que efeito foi confirmado | A190_G11_FORGED_DB_RESPONSE_EFFECT_FIELD=NO_GO | Fail closed |
| IDs de projeto/request perigosos; evento expirado | A190_G11_PATH_TRAVERSAL_AND_UNSAFE_IDS=DENIED; A190_G11_EXPIRED_ORIGINAL_ISSUER_EVENT=DENIED | Fail closed |
| Envelope permanece não executável | A190_G11_OFFLINE_ENVELOPES_EXECUTION_ALLOWED=FALSE | **HARD NO-GO** |

## Primeira execução com falha preservada

[Run #40050925349](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40050925349), SHA 1fd5a23ab6f9f81e089b3e064e846c33e7a22da6: **FAIL** em Ubuntu e Windows (19 testes passaram e 1 erro de teste por OS). O auxiliar do teste de caminho hostil não recebia o argumento de nome de projeto, lançando TypeError antes de chegar à função sob teste. Corrigido exclusivamente o encaminhamento **options do auxiliar em 5e96e35180b82bfb6f1745333f5ceabca9304e8d**; verificação do caminho perigoso permaneceu ativa e passou nos dois SOs. Não apresentar primeira CI como sucesso, nem somar seus testes ao 40/40 da segunda execução.

## Exatamente o que ainda NÃO existe

- Nenhum IAM/SDK/token, serviço DynamoDB/Firestore real, região, conta, fatura ou custo.
- Nenhum teste de conditional overwrite real em cloud, consistency real, operador de conta, revogação, restauração de backup, cruzamento de domínios administrativos ou evidence receipt assinada externamente.
- Nenhuma prova de fonte independente do HUMAN_OWNER ou de provedor de efeito.
- Nenhuma prova de H0 pós power loss real, backups genuínos, clock, SLA, LGPD, custo mensal e P0. Cinco external-RED por SO, 43 advisories e Quality/Security canônicas seguem pendentes.

**0/6 P0 HOMOLOGADOS — HARD NO-GO — UNCERTAIN — ZERO_AUTO_RESEND.** Somente LAB Draft, sem merge/main, deploy, Worker, fornecedor, conta, cartão, assinatura, credenciais operacionais ou efeito real.
