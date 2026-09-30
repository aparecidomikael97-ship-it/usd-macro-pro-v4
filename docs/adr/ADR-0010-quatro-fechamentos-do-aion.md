# ADR-0010 — Quatro fechamentos obrigatórios antes de concluir um especialista

- Título: Quatro fechamentos obrigatórios antes de concluir um especialista
- Data: 2026-09-29
- Status: ACCEPTED

## Contexto

O Core já tem registry, papéis e memória de checkpoint. A reconciliação de 29/09 torna quatro fechamentos obrigatórios antes de chamar um especialista de concluído.

## Problema

Um especialista com leitura local pode ser anunciado como pronto sem router, permissão de domínio, memória isolada e certificação.

## Alternativas consideradas

Considerar o Skill/Plugin Certification V1 como a certificação dos especialistas de domínio foi rejeitado: aquele contrato é distinto e não executa skill. A alternativa aceita é uma Specialist Certification Gate ainda não implementada.

## Decisão

Nenhum especialista está concluído sem Specialist Router, permissões por domínio, memória e evidência isoladas por domínio, e AION Specialist Certification Gate.

## Consequências

A decisão está aceita e a implementação está pendente. Nenhum especialista atual é declarado certificado.

## Componentes afetados

Capability Registry, especialistas, Checkpoint Mestre e o futuro gate de certificação.

## Segurança

Certificação não autoriza execução, gasto, publicação ou trading. Memória de um domínio não vaza autoridade para outro.

## Compatibilidade

Os especialistas já registrados continuam existindo como leituras locais, sem mudança de permissão.

## Rollback/migração

Remover um fechamento exige ADR que substitua este e aponte o sucessor. Este arquivo não é apagado.

## PR/commit relacionado

Nenhum PR deste registro é citado como prova de produção. Evidência por caminho de arquivo, sem SHA de deploy.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
