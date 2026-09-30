param(
    [string]$EnvFile = "$PSScriptRoot\sandbox.env.local",
    [string]$OutputDir = "$PSScriptRoot\.atlasquant_sandbox_evidence"
)

$ErrorActionPreference = "Stop"
$ComposeFile = "$PSScriptRoot\compose.yml"
$RealmFile = "$PSScriptRoot\realm\atlasquant-sandbox-realm.json"
$RegistrySchemaFile = "$PSScriptRoot\registry\init\001_registry_schema.sql"

if (-not (Test-Path -LiteralPath $EnvFile)) {
    throw "Sandbox env file not found: $EnvFile"
}
if ($EnvFile -match "(?i)prod") {
    throw "Production-like env file names are forbidden."
}

$values = @{}
Get-Content -LiteralPath $EnvFile | ForEach-Object {
    $line = $_.Trim()
    if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
        $pair = $line.Split("=", 2)
        $values[$pair[0].Trim()] = $pair[1].Trim()
    }
}
if ($values["ATLASQUANT_SANDBOX_ONLY"] -ne "true") {
    throw "ATLASQUANT_SANDBOX_ONLY=true is required."
}

$port = if ($values["KEYCLOAK_HTTP_PORT"]) { $values["KEYCLOAK_HTTP_PORT"] } else { "18080" }
if ($port -notmatch "^\d+$") {
    throw "Invalid KEYCLOAK_HTTP_PORT."
}

$registryUser = $values["REGISTRY_DB_USERNAME"]
if (-not $registryUser -or $registryUser -notmatch "^[A-Za-z0-9_]+$") {
    throw "Invalid REGISTRY_DB_USERNAME."
}

$services = @(
    docker compose --env-file $EnvFile -f $ComposeFile ps --services --status running
) | ForEach-Object { $_.Trim() } | Where-Object { $_ }
if ($LASTEXITCODE -ne 0) {
    throw "Could not read Docker Compose service state."
}

$issuerUrl = "http://127.0.0.1:$port/realms/atlasquant-sandbox/.well-known/openid-configuration"
$oidc = Invoke-RestMethod -Uri $issuerUrl -TimeoutSec 10
if (-not $oidc.issuer) {
    throw "OIDC discovery did not expose an issuer."
}

$query = "SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename IN ('registry_revisions','team_memberships') ORDER BY tablename;"
$tables = @(
    docker compose --env-file $EnvFile -f $ComposeFile exec -T registry-db psql -U $registryUser -d atlasquant_registry -Atc $query
) | ForEach-Object { $_.Trim() } | Where-Object { $_ }
if ($LASTEXITCODE -ne 0) {
    throw "Could not read registry schema."
}

$payload = [ordered]@{
    schema = "ATLASQUANT_AION_BUSINESS_TEAM_ACCESS_SANDBOX_EVIDENCE_V1"
    version = "1"
    environment = "SANDBOX"
    production_environment = $false
    captured_at = (Get-Date).ToUniversalTime().ToString("o")
    collector_executes_mutation = $false
    external_side_effects_executed = $false
    secrets_included = $false
    keycloak_image = "quay.io/keycloak/keycloak:26.7.5"
    postgres_image = "postgres:18.6"
    running_services = @($services)
    registry_tables = @($tables)
    oidc = [ordered]@{
        issuer = [string]$oidc.issuer
    }
    artifacts = [ordered]@{
        compose_sha256 = (Get-FileHash -LiteralPath $ComposeFile -Algorithm SHA256).Hash.ToLowerInvariant()
        realm_sha256 = (Get-FileHash -LiteralPath $RealmFile -Algorithm SHA256).Hash.ToLowerInvariant()
        registry_schema_sha256 = (Get-FileHash -LiteralPath $RegistrySchemaFile -Algorithm SHA256).Hash.ToLowerInvariant()
    }
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$outFile = Join-Path $OutputDir "team-access-baseline-evidence.json"
$payload | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $outFile -Encoding utf8

Write-Host "Sandbox baseline evidence collected:"
Write-Host "  $outFile"
Write-Host "No password, token or client secret was written by this collector."
Write-Host "No account, MFA, registry row or session was changed."
