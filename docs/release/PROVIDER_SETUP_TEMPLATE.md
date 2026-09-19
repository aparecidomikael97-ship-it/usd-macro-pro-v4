# AtlasQuant — Provider Setup Template

Use este arquivo somente como checklist. **Nunca cole valores de secrets no repositório.**

| Integração | Identificador/configuração esperada | Valor no repositório |
|---|---|---|
| FRED | `CHAVE_FRED` | NUNCA |
| NewsAPI | `CHAVE_NEWSAPI` | NUNCA |
| EODHD | `CHAVE_EODHD` | NUNCA |
| Twelve Data | `CHAVE_TWELVE_DATA` | NUNCA |
| Usuários | `ATLASQUANT_USERS_JSON` | NUNCA |
| TTS futuro | secret definido pelo adaptador aprovado | NUNCA |
| Billing futuro | secret/webhook definido pelo provedor aprovado | NUNCA |
| Assinatura Android/iOS | keystore/certificados fora do repositório | NUNCA |

## Regras
- usar secret store do ambiente;
- menor privilégio possível;
- separar leitura de escrita/trading;
- rotacionar segredo comprometido;
- não exibir valor em log, suporte, screenshot ou commit;
- validar integração em sandbox/teste antes de produção.
