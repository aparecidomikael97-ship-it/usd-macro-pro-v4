# AION — Portable Core + Vault + Entrada Única

Data: 2026-09-25

## Objetivo

Implementar a primeira base real para o AION existir como núcleo independente
do AtlasQuant sem criar um novo site pago nesta etapa.

## Checkpoint Mestre V10

O Checkpoint Mestre passa a persistir:

- `portable_core`;
- `vault`.

Ambos possuem digest próprio e entram no relatório de integridade. Checkpoints
antigos migram em memória para V10 antes de uma escrita condicional autorizada.

## Portable Core

O AION passa a ter identidade própria e um registro de workspaces.

Workspaces iniciais:

- AION Central;
- AtlasQuant;
- Studio;
- Negócios;
- Desenvolvimento;
- Administração.

AtlasQuant é um workspace do ecossistema, não a identidade inteira do AION.

Conectores suportam contratos NATIVE/API/MCP/FILE/WEBHOOK. Conector externo
começa desabilitado e não pode ampliar a própria permissão.

## Entrada única

O mesmo aplicativo privado aceita `?aion=1`.

A rota:

- só é consumida quando a sessão já é ADMIN;
- não pula login;
- não muda role;
- não contorna Guardian;
- não liga feature flag;
- não ativa conector;
- não habilita trading.

A PWA existente usa a mesma rota. Assim, nesta etapa, não é necessário comprar
outro domínio ou manter um segundo site.

## AION Vault

O Vault desta etapa é um cofre de **metadados, referências, versões e integridade**.

Ele não implementa criptografia própria e não salva valor de:

- senha;
- token;
- API key;
- private key;
- credential.

Para segredo, guarda somente a referência ao slot em backend aprovado, por
exemplo:

- variável de ambiente;
- Render Secret;
- GitHub Actions Secret;
- OS keychain;
- vault externo.

Backups de Checkpoint, políticas, identidade, configurações e artefatos também
podem ser referenciados/versionados.

## Proteções

- plaintext secret proibido;
- AION não pode apagar o Vault sozinho;
- AION não pode ampliar a própria permissão;
- mudança sensível continua dependente de Guardian;
- Proof of Safety permanece obrigatório para ação sensível;
- trading real permanece bloqueado.

## Estado honesto

Esta etapa implementa os contratos, a persistência no Checkpoint, a entrada
única e a visualização administrativa.

Ainda NÃO afirma:

- backend de Vault externo conectado;
- domínio próprio comprado;
- aplicativo nativo publicado em loja;
- todos os conectores externos ativos;
- persistência runtime do Checkpoint já criada no branch de dados;
- infraestrutura independente do AtlasQuant já hospedada em produção.

Essas etapas futuras devem ser comprovadas individualmente.
