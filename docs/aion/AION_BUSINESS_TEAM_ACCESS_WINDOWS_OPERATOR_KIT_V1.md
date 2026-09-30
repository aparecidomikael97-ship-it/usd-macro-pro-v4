# AION BUSINESS — Equipe & Acessos · Windows Operator Kit V1

## Objetivo

Deixar o sandbox pronto para execução local controlada no Windows sem exigir que
o administrador monte manualmente cada comando e sem abrir uma rota automática
para produção.

## Fluxo recomendado

### 1. Preparar secrets

Plan only:

    .\Prepare-TeamAccessSandboxEnv.ps1

Criar o arquivo local:

    .\Prepare-TeamAccessSandboxEnv.ps1 -Apply

O script gera secrets localmente, não mostra os valores e não inicia Docker.

### 2. Verificar readiness

    .\Get-TeamAccessSandboxReadiness.ps1

O resultado é gravado, por padrão, fora do repositório em:

    %LOCALAPPDATA%\AtlasQuant\team-access-sandbox\operator\windows-operator-readiness.json

O secret env e o baseline também usam a árvore
%LOCALAPPDATA%\AtlasQuant\team-access-sandbox por padrão. O relatório contém
apenas checks booleanos e timestamp.

### 3. Revisar o operador

    .\Invoke-TeamAccessSandboxOperator.ps1

Sem switches, nenhuma mutação acontece.

### 4. Start explícito

    .\Invoke-TeamAccessSandboxOperator.ps1 -ApplyStart

Isso sobe somente o sandbox local e executa as verificações read-only.

### 5. Baseline explícito

    .\Invoke-TeamAccessSandboxOperator.ps1 -ApplyStart -CollectBaseline

Além do start e healthcheck, o comando coleta a evidência sanitizada e chama o
validador Python do baseline.

## Fronteira

Mesmo após baseline válido, o Operator Kit termina antes do lifecycle.

Conta, MFA, registry write, disable e revogação continuam sob ADR-0068,
ADR-0069 e ADR-0070.

## Estado máximo

READY_FOR_ADMIN_TEAM_ACCESS_WINDOWS_SANDBOX_START_DECISION

Esse estado significa apenas que o ambiente local está pronto para uma decisão
manual de start.
