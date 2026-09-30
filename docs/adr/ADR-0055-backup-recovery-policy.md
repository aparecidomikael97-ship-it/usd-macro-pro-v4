# ADR-0055 — Backup e recuperação exigem integridade, múltiplas camadas e restore não automático

Título: Backup e recuperação exigem integridade, múltiplas camadas e restore não automático  
Data: 2026-09-30  
Status: ACCEPTED

## Contexto

O AION cresce em código, documentação, Checkpoint Mestre, runtime e histórico.
Perder continuidade ou restaurar conteúdo corrompido comprometeria todo o ecossistema.

## Problema

Já existem peças de backup e recovery, mas faltava uma política única que
diferenciasse backup de código, histórico de checkpoint e cópia secundária, além
de exigir verificação de integridade antes de qualquer restauração.

## Alternativas consideradas

1. Confiar apenas no histórico Git.
2. Confiar apenas no ZIP de source backup.
3. Política em camadas com integridade, checkpoint versionado e cópia secundária.

## Decisão

Adotar a alternativa 3.

Camadas mínimas:
- source archive com SHA256;
- histórico versionado de checkpoint/runtime;
- cópia secundária distinta da referência primária.

O source backup deve:
- gerar SHA256;
- validar o SHA256;
- testar o ZIP;
- verificar arquivos críticos de continuidade;
- manter ATLASQUANT_REAL_EXECUTION=0.

O runtime checkpoint permanece separado do source archive.

RPO e RTO não são inventados pelo sistema; precisam ser definidos pelo
administrador como metas internas.

## Consequências

Backup passa a ser considerado confiável somente quando as evidências mínimas
estiverem presentes. Restore automático continua proibido.

## Segurança

Nenhum módulo desta ADR:
- apaga dados;
- restaura produção;
- escreve runtime;
- chama provider;
- executa deploy;
- movimenta dinheiro;
- opera Trade.

## Compatibilidade

Reutiliza o source backup workflow existente, o Checkpoint Mestre e
`atlasquant_aion_recovery.py`.

## Rollback/migração

A política é read-only; o endurecimento do workflow pode ser revertido sem tocar
nos dados de runtime.

## PR/commit relacionado

Draft PR AION Backup & Recovery Policy V1.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
