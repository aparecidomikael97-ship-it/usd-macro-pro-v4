param(
    [string]$EnvFile = "$PSScriptRoot\sandbox.env.local"
)

$ErrorActionPreference = "Stop"
$ComposeFile = "$PSScriptRoot\compose.yml"

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
    throw "Sandbox-only marker missing."
}

$registryUser = $values["REGISTRY_DB_USERNAME"]
if (-not $registryUser -or $registryUser -notmatch "^[A-Za-z0-9_]+$") {
    throw "Invalid REGISTRY_DB_USERNAME."
}

$query = "SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename IN ('registry_revisions','team_memberships') ORDER BY tablename;"
$tables = docker compose --env-file $EnvFile -f $ComposeFile exec -T registry-db psql -U $registryUser -d atlasquant_registry -Atc $query
if ($LASTEXITCODE -ne 0) {
    throw "Registry schema query failed."
}

$rows = @($tables | Where-Object { $_ -and $_.Trim() })
if ($rows.Count -ne 2) {
    throw "Registry schema incomplete. Expected registry_revisions and team_memberships."
}

Write-Host "Registry schema OK: registry_revisions + team_memberships."
Write-Host "No registry row was inserted or changed by this verification."
