param(
    [string]$EnvFile = (Join-Path $env:LOCALAPPDATA "AtlasQuant\team-access-sandbox\team-access-sandbox.env"),
    [switch]$Apply,
    [switch]$ReplaceExisting
)

$ErrorActionPreference = "Stop"

if (-not $env:LOCALAPPDATA) {
    throw "LOCALAPPDATA is required for the default local secret path."
}

function New-LocalSecret {
    param([int]$Bytes = 32)

    $buffer = New-Object byte[] $Bytes
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($buffer)
    }
    finally {
        $rng.Dispose()
    }

    $encoded = [Convert]::ToBase64String($buffer)
    return $encoded.TrimEnd("=").Replace("+", "-").Replace("/", "_")
}

if ($EnvFile -match "(?i)prod") {
    throw "Production-like env file names are forbidden."
}

if ((Test-Path -LiteralPath $EnvFile) -and -not $ReplaceExisting) {
    Write-Host "Local sandbox env already exists. No change made."
    Write-Host "Use -ReplaceExisting together with -Apply only if rotation is intentionally required."
    exit 0
}

if (-not $Apply) {
    Write-Host "PLAN ONLY - no secret file was created."
    Write-Host "Target: $EnvFile"
    Write-Host "The apply path creates three distinct cryptographic random secrets locally."
    Write-Host "Secret values are never printed."
    exit 0
}

if ((Test-Path -LiteralPath $EnvFile) -and -not $ReplaceExisting) {
    throw "Existing sandbox env will not be overwritten without -ReplaceExisting."
}

$adminPassword = New-LocalSecret
$keycloakDbPassword = New-LocalSecret
$registryDbPassword = New-LocalSecret

if (
    $adminPassword -eq $keycloakDbPassword -or
    $adminPassword -eq $registryDbPassword -or
    $keycloakDbPassword -eq $registryDbPassword
) {
    throw "Generated secrets were not distinct. Refusing to write the env file."
}

$payload = @"
# Local AtlasQuant Team Access sandbox secrets.
# Generated locally. Never commit this file.
ATLASQUANT_SANDBOX_ONLY=true

KEYCLOAK_HTTP_PORT=18080
REGISTRY_DB_PORT=15432

KC_BOOTSTRAP_ADMIN_USERNAME=atlasquant-sandbox-admin
KC_BOOTSTRAP_ADMIN_PASSWORD=$adminPassword

KC_DB_USERNAME=keycloak_sandbox
KC_DB_PASSWORD=$keycloakDbPassword

REGISTRY_DB_USERNAME=atlasquant_registry_sandbox
REGISTRY_DB_PASSWORD=$registryDbPassword
"@

$directory = Split-Path -Parent $EnvFile
if ($directory -and -not (Test-Path -LiteralPath $directory)) {
    New-Item -ItemType Directory -Force -Path $directory | Out-Null
}

Set-Content -LiteralPath $EnvFile -Value $payload -Encoding utf8 -NoNewline

Write-Host "Local sandbox env created."
Write-Host "Path: $EnvFile"
Write-Host "Secret values were not displayed."
Write-Host "No container was started."
