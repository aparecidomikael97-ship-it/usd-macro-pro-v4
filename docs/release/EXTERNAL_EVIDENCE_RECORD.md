# AtlasQuant — Registro de Evidências Externas

Este arquivo é um registro manual de handoff. Ele **não** habilita lançamento, billing, TTS, lojas, broker ou ordens reais.

## Estado inicial

| Dependência | Estado | Evidência necessária |
|---|---|---|
| ADMIN de produção | PENDENTE | login, expiração e revogação validados; secret sem senha em texto puro |
| Jurídico e privacidade | PENDENTE | documentos finais aprovados, versionados e publicados |
| Licenciamento comercial de dados | PENDENTE | contrato/termos aplicáveis para cada fonte usada publicamente |
| Pagamento e assinatura | PENDENTE | sandbox, webhook assinado, idempotência, cancelamento e reembolso |
| TTS neural externo | PENDENTE | provedor/configuração, áudio real, custo, privacidade e fallback |
| Vídeos da Academy | PENDENTE | mídia final revisada, publicada e associada a cada aula |
| Google Play / Apple App Store | PENDENTE | pacote assinado e resultado da revisão/publicação |

## Como registrar uma conclusão

Para cada dependência concluída, registrar de forma revisável:

- data UTC;
- responsável pela validação;
- ambiente/provedor, sem credenciais;
- identificador ou referência da evidência;
- resultado dos testes aplicáveis;
- observações e limitações;
- aprovação humana final.

Nunca registrar senhas, tokens, chaves privadas, números completos de cartão ou outros segredos neste arquivo.

## Regra fail-closed

A ausência de evidência mantém o item como **PENDENTE**. Uma alteração neste documento, sozinha, não deve mudar `external_evidence_complete`, `public_launch_ready` ou permissões do produto. O código de readiness continua sendo a autoridade técnica fail-closed até uma integração externa explicitamente validada.

Broker e ordens reais permanecem fora desta release.
