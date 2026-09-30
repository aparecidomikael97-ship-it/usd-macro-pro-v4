param(
    [string]$EnvFile = "$PSScriptRoot\sandbox.env.local"
)

$ErrorActionPreference = "Stop"
$ComposeFile = "$PSScriptRoot\compose.yml"

if (-not (Test-Path -LiteralPath $EnvFile)) {
    throw "Sandbox env file not found: $EnvFile"
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

$port = if ($values["KEYCLOAK_HTTP_PORT"]) { $values["KEYCLOAK_HTTP_PORT"] } else { "18080" }
if ($port -notmatch "^\d+$") {
    throw "Invalid KEYCLOAK_HTTP_PORT."
}

docker compose --env-file $EnvFile -f $ComposeFile ps

$oidc = "http://127.0.0.1:$port/realms/atlasquant-sandbox/.well-known/openid-configuration"
Write-Host "Checking OIDC discovery: $oidc"
$response = Invoke-WebRequest -UseBasicParsing -Uri $oidc -TimeoutSec 10
if ($response.StatusCode -ne 200) {
    throw "OIDC discovery did not return HTTP 200."
}

$payload = $response.Content | ConvertFrom-Json
if ($payload.issuer -notmatch "/realms/atlasquant-sandbox$") {
    throw "OIDC issuer does not match atlasquant-sandbox realm."
}

Write-Host "OIDC discovery OK."
Write-Host "This verification does not authorize production, account provisioning, registry writes or session revocation."
