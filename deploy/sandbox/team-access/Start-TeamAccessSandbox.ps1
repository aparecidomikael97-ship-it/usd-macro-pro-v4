param(
    [string]$EnvFile = "$PSScriptRoot\sandbox.env.local",
    [switch]$Apply
)

$ErrorActionPreference = "Stop"
$ComposeFile = "$PSScriptRoot\compose.yml"

if (-not (Test-Path -LiteralPath $EnvFile)) {
    throw "Sandbox env file not found: $EnvFile. Copy sandbox.env.example to sandbox.env.local and replace placeholders."
}

$raw = Get-Content -LiteralPath $EnvFile -Raw
if ($raw -match "(?i)CHANGE_ME|CHANGEME|PLACEHOLDER") {
    throw "Sandbox env still contains placeholder secrets."
}
if ($raw -notmatch "(?m)^ATLASQUANT_SANDBOX_ONLY=true\s*$") {
    throw "ATLASQUANT_SANDBOX_ONLY=true is required."
}
if ($EnvFile -match "(?i)prod") {
    throw "Production-like env file names are forbidden for this sandbox launcher."
}

docker --version | Out-Null
docker compose version | Out-Null

Write-Host "Validating isolated team-access sandbox configuration..."
docker compose --env-file $EnvFile -f $ComposeFile config --quiet

if (-not $Apply) {
    Write-Host ""
    Write-Host "PLAN ONLY - no container was started."
    Write-Host "Keycloak: 127.0.0.1:18080 (or KEYCLOAK_HTTP_PORT from env)"
    Write-Host "Registry PostgreSQL: 127.0.0.1:15432 (or REGISTRY_DB_PORT from env)"
    Write-Host ""
    Write-Host "To start the sandbox explicitly:"
    Write-Host "  .\Start-TeamAccessSandbox.ps1 -Apply"
    exit 0
}

Write-Host "Starting LOCAL SANDBOX only..."
docker compose --env-file $EnvFile -f $ComposeFile up -d
docker compose --env-file $EnvFile -f $ComposeFile ps

Write-Host ""
Write-Host "Sandbox start requested. Production was not targeted."
Write-Host "Run .\Test-TeamAccessSandbox.ps1 to verify OIDC discovery and container state."
