# ADR-0071 — Business Team Access Windows Operator Kit

- Status: ACCEPTED
- Data: 2026-09-30
- Escopo: AtlasQuant / AION Business / Equipe & Acessos

## Contexto

O sandbox físico já possui compose, verificações e coleta de baseline. Para uso
no ambiente Windows do administrador, o fluxo precisa reduzir erro operacional
sem transformar o AION em executor automático.

## Decisão

Adicionar um Operator Kit local com quatro fronteiras explícitas:

1. geração local de sandbox.env.local;
2. readiness read-only;
3. start manual com switch dedicado;
4. coleta de baseline com switch separado.

## Secrets

Prepare-TeamAccessSandboxEnv.ps1:

- PLAN ONLY por padrão;
- exige -Apply para gravar sandbox.env.local;
- não sobrescreve arquivo existente sem -ReplaceExisting;
- gera três secrets criptograficamente aleatórios e distintos;
- não imprime valores;
- não inicia containers.

## Readiness

Get-TeamAccessSandboxReadiness.ps1 verifica:

- arquivo local existente;
- marcador ATLASQUANT_SANDBOX_ONLY=true;
- ausência de placeholders;
- Docker CLI;
- Docker Compose;
- compose config válido;
- ausência de nome de produção.

O relatório não contém secrets e não inicia containers.

## Operador

Invoke-TeamAccessSandboxOperator.ps1:

- PLAN ONLY por padrão;
- exige -ApplyStart para subir o sandbox local;
- exige -CollectBaseline separadamente para coletar/validar baseline;
- não executa lifecycle de conta, MFA, registry ou revogação.

## Estado máximo automático

READY_FOR_ADMIN_TEAM_ACCESS_WINDOWS_SANDBOX_START_DECISION

O estado não autoriza start. O start continua dependente do switch manual
-ApplyStart executado na máquina autorizada.

## Segurança

O kit não:
- toca produção;
- publica secrets;
- habilita executor do AION;
- cria usuários;
- habilita MFA;
- grava membership;
- revoga sessões;
- autoriza deploy/runtime.

## Compatibilidade

Complementa ADR-0065, ADR-0066 e ADR-0067 até ADR-0070.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
