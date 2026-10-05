# ADR-0020 — Core Completion Review é separada de Core Freeze e do Checkpoint Save

- Título: Core Completion Review é separada de Core Freeze e do Checkpoint Save
- Data: 2026-10-04
- Status: ACCEPTED

## Contexto

A V2.20 fornece certificação criptográfica do AION Core, mas certificação técnica não
é decisão humana, freeze, merge, deploy ou persistência do Checkpoint Mestre.

## Problema

Sem uma camada explícita de revisão, um consumidor poderia tratar
`CERTIFICATION_CANDIDATE` como conclusão do núcleo ou transformar um registro de
checkpoint em autoridade operacional.

Também seria inseguro confiar em booleanos do manifesto V2.20 sem revalidar suas
evidências assinadas.

## Alternativas consideradas

Foram rejeitados:

- converter V2.20 verde diretamente em Core Complete;
- aceitar `core_frozen=True` vindo do payload;
- confiar apenas no manifest digest sem reverificar assinaturas;
- gravar automaticamente o resultado no Checkpoint Mestre;
- usar um store de conclusão paralelo;
- misturar review, freeze, merge, deploy e runtime activation.

## Decisão

V2.21 cria um Core Completion Review Gate read-only.

A camada:

- reconstrói o V2.20 a partir das evidências assinadas;
- reverifica Ed25519 contra o trust root fornecido pelo host;
- confere target SHA e manifest digest;
- rejeita campos inseguros promovidos;
- produz no máximo `READY_FOR_OWNER_REVIEW`;
- gera somente um patch candidate para o Checkpoint Mestre.

Nenhuma decisão do proprietário é criada automaticamente.

## Consequências

O histórico passa a distinguir de forma verificável:

1. código implementado;
2. CI estrutural verde;
3. V2.20 certification candidate;
4. V2.21 ready for owner review;
5. owner decision registrada;
6. eventual Core Freeze;
7. merge/deploy;
8. runtime activation.

Esses estados não são equivalentes.

## Componentes afetados

AION Core Certification, Checkpoint Mestre, CI, ADR registry e processo futuro de
Core Freeze.

## Segurança

- review não é authority;
- checkpoint staging não é persistence;
- checkpoint persistence não é freeze;
- freeze não é merge/deploy;
- nenhum campo unsafe pode ser promovido por payload;
- todas as evidências V2.20 são reverificadas;
- nenhuma chave privada real entra no repositório;
- nenhuma ação externa é executada.

## Compatibilidade

Compõe ADR-0007, ADR-0012 e ADR-0019 sem substituí-las.

## Rollback/migração

Qualquer futura automatização de owner review, freeze ou checkpoint save exige ADR
sucessor explícito.

## PR/commit relacionado

Branch `integration/aion-v221-core-completion-review-20261004`.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
