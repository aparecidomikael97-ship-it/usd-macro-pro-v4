# AtlasQuant — Política de Branches

## Objetivo

Evitar que código estável, evidência operacional mutável e experimentos sejam misturados.

## Branches principais

### `main`
Fonte estável/release atual.

Regras:
- somente mudanças revisadas;
- Quality obrigatoriamente verde;
- UI Smoke para mudanças sensíveis de interface;
- Health e Browser Smoke pós-merge;
- sem dados operacionais mutáveis;
- sem ordens reais.

### `atlasquant-runtime`
Estado/evidência operacional mutável.

Regras:
- pode acumular snapshots, diagnósticos e artefatos do runtime;
- não deve ser usado para sobrescrever `main` por merge cego;
- mudanças de código devem ser reconciliadas explicitamente;
- runtime/evidence não é aprovação de release.

### branches de feature/release
Usadas para mudanças isoladas e revisáveis.

Fluxo:
1. criar a partir da `main` atual;
2. alterar escopo mínimo;
3. executar Quality;
4. executar UI Smoke quando aplicável;
5. revisar diff;
6. PR limpa para `main`;
7. merge apenas após checks verdes;
8. validar produção pós-merge.

## Backups

Branches `backup/*` e snapshots de runtime são pontos de recuperação/evidência. Não devem substituir política de release.

## Proibições

- não force-push em `main`;
- não copiar secrets para branches;
- não mesclar runtime inteiro sobre `main`;
- não habilitar trading real em branch de acabamento;
- não considerar branch antiga como release atual sem comparar com `main`.

## Regra de verdade

Quando houver dúvida sobre a versão corrente, a referência é a `main` validada e seus checks pós-merge.
