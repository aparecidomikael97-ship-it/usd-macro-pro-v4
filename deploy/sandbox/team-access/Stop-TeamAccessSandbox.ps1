param(
    [string]$EnvFile = "$PSScriptRoot\sandbox.env.local",
    [switch]$Apply,
    [switch]$DestroyData,
    [switch]$ConfirmDestroy
)

$ErrorActionPreference = "Stop"
$ComposeFile = "$PSScriptRoot\compose.yml"

if (-not (Test-Path -LiteralPath $EnvFile)) {
    throw "Sandbox env file not found: $EnvFile"
}
if ($EnvFile -match "(?i)prod") {
    throw "Production-like env file names are forbidden."
}

if (-not $Apply) {
    Write-Host "PLAN ONLY - no container or volume was changed."
    Write-Host "Use -Apply to stop the local sandbox."
    Write-Host "Use -Apply -DestroyData -ConfirmDestroy to remove local sandbox volumes."
    exit 0
}

if ($DestroyData) {
    if (-not $ConfirmDestroy) {
        throw "DestroyData requires -ConfirmDestroy."
    }
    docker compose --env-file $EnvFile -f $ComposeFile down -v
    Write-Host "Local sandbox containers and sandbox volumes removed."
    exit 0
}

docker compose --env-file $EnvFile -f $ComposeFile down
Write-Host "Local sandbox containers stopped. Sandbox volumes preserved."
