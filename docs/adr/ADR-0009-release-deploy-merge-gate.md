# ADR-0009 — Release, deploy e merge exigem gate

- Título: Release, deploy e merge exigem gate
- Data: 2026-09-29
- Status: ACCEPTED

## Contexto

O handoff de 15/09 proíbe merge para main, promoção e mudança de secrets sem autorização. O release guard existe para impedir promoção automática. O checkpoint de 22/09 separa health 200 de prova de build.

## Problema

CI verde ou health check podem ser tratados como deploy concluído.

## Alternativas consideradas

Promoção automática foi rejeitada. A alternativa aceita é gate explícito, rollback e prova do artefato servido.

## Decisão

Release, deploy e merge exigem o gate apropriado e revisão humana. Ausência de prova do SHA servido fica UNVERIFIED, não como sucesso de deploy.

## Consequências

O guard local não prova o ambiente de produção. Dependência externa de hook, credencial e conta continua registrada à parte.

## Componentes afetados

atlasquant_release_guard.py; workflows de release; Checkpoint Mestre.

## Segurança

Secrets não são alterados por documentação. Worker e provider não são ativados por um merge de registro.

## Compatibilidade

Main não é reescrita por esta decisão. Branches de trabalho continuam abrindo PR.

## Rollback/migração

Automatizar merge ou deploy exigiria ADR posterior. Este arquivo permanece.

## PR/commit relacionado

Nenhum PR deste registro é citado como prova de produção. Evidência por caminho de arquivo, sem SHA de deploy.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
