param(
    [string]$EnvFile = "$PSScriptRoot\sandbox.env.local"
)

$ErrorActionPreference = "Stop"
$ComposeFile = "$PSScriptRoot\compose.yml"

if (-not (Test-Path -LiteralPath $EnvFile)) {
    throw "Sandbox env file not found: $EnvFile"
}

$tables = docker compose --env-file $EnvFile -f $ComposeFile exec -T registry-db sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "SELECT tablename FROM pg_tables WHERE schemaname = '\''public'\'' AND tablename IN ('\''registry_revisions'\'','\''team_memberships'\'') ORDER BY tablename;"'
if ($LASTEXITCODE -ne 0) {
    throw "Registry schema query failed."
}

$rows = @($tables | Where-Object { $_ -and $_.Trim() })
if ($rows.Count -ne 2) {
    throw "Registry schema incomplete. Expected registry_revisions and team_memberships."
}

Write-Host "Registry schema OK: registry_revisions + team_memberships."
Write-Host "No registry row was inserted or changed by this verification."
