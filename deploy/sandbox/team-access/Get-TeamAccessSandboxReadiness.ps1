param(
    [string]$EnvFile = (Join-Path $env:LOCALAPPDATA "AtlasQuant\team-access-sandbox\team-access-sandbox.env"),
    [string]$OutputDir = (Join-Path $env:LOCALAPPDATA "AtlasQuant\team-access-sandbox\operator")
)

$ErrorActionPreference = "Stop"
if (-not $env:LOCALAPPDATA) {
    throw "LOCALAPPDATA is required for the default operator paths."
}
$ComposeFile = "$PSScriptRoot\compose.yml"

$checks = [ordered]@{
    env_file_exists = $false
    sandbox_marker = $false
    placeholders_absent = $false
    docker_cli = $false
    docker_compose = $false
    compose_config_valid = $false
    production_name_absent = $false
}

$checks.production_name_absent = ($EnvFile -notmatch "(?i)prod")

if (Test-Path -LiteralPath $EnvFile) {
    $checks.env_file_exists = $true
    $raw = Get-Content -LiteralPath $EnvFile -Raw
    $checks.sandbox_marker = ($raw -match "(?m)^ATLASQUANT_SANDBOX_ONLY=true\s*$")
    $checks.placeholders_absent = ($raw -notmatch "(?i)CHANGE_ME|CHANGEME|PLACEHOLDER")
}

try {
    docker --version | Out-Null
    if ($LASTEXITCODE -eq 0) { $checks.docker_cli = $true }
}
catch {}

try {
    docker compose version | Out-Null
    if ($LASTEXITCODE -eq 0) { $checks.docker_compose = $true }
}
catch {}

if (
    $checks.env_file_exists -and
    $checks.sandbox_marker -and
    $checks.placeholders_absent -and
    $checks.docker_cli -and
    $checks.docker_compose -and
    $checks.production_name_absent
) {
    try {
        docker compose --env-file $EnvFile -f $ComposeFile config --quiet
        if ($LASTEXITCODE -eq 0) { $checks.compose_config_valid = $true }
    }
    catch {}
}

$ready = -not ($checks.Values -contains $false)
$payload = [ordered]@{
    schema = "ATLASQUANT_AION_BUSINESS_TEAM_ACCESS_WINDOWS_OPERATOR_READINESS_V1"
    version = "1"
    state = if ($ready) {
        "READY_FOR_ADMIN_TEAM_ACCESS_WINDOWS_SANDBOX_START_DECISION"
    }
    else {
        "TEAM_ACCESS_WINDOWS_OPERATOR_READINESS_BLOCKED"
    }
    captured_at = (Get-Date).ToUniversalTime().ToString("o")
    checks = $checks
    secrets_included = $false
    container_started = $false
    production_targeted = $false
    external_side_effects_executed = $false
    local_report_written = $true
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$outFile = Join-Path $OutputDir "windows-operator-readiness.json"
$payload | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $outFile -Encoding utf8

Write-Host "Operator readiness: $($payload.state)"
Write-Host "Report: $outFile"
Write-Host "No secret value was written to the report."
Write-Host "No container was started."
