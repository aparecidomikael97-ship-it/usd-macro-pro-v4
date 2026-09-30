param(
    [string]$EnvFile = (Join-Path $env:LOCALAPPDATA "AtlasQuant\team-access-sandbox\team-access-sandbox.env"),
    [string]$BaselineFile = (Join-Path $env:LOCALAPPDATA "AtlasQuant\team-access-sandbox\evidence\team-access-baseline-evidence.json"),
    [string]$OutputDir = (Join-Path $env:LOCALAPPDATA "AtlasQuant\team-access-sandbox\operator"),
    [Parameter(Mandatory = $true)]
    [string]$ObservedBy
)

$ErrorActionPreference = "Stop"

if (-not $env:LOCALAPPDATA) {
    throw "LOCALAPPDATA is required for the default Step 1 observation paths."
}
if (-not (Test-Path -LiteralPath $EnvFile)) {
    throw "Sandbox env file not found: $EnvFile"
}
if (-not (Test-Path -LiteralPath $BaselineFile)) {
    throw "Baseline evidence file not found: $BaselineFile"
}
if ($EnvFile -match "(?i)prod" -or $BaselineFile -match "(?i)prod") {
    throw "Production-like paths are forbidden."
}
if (-not $ObservedBy -or $ObservedBy.Length -gt 120 -or $ObservedBy -match "[\r\n\x00]") {
    throw "ObservedBy is invalid."
}

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
$EnvResolved = (Resolve-Path -LiteralPath $EnvFile).Path
$BaselineResolved = (Resolve-Path -LiteralPath $BaselineFile).Path
$LocalRoot = [System.IO.Path]::GetFullPath(
    (Join-Path $env:LOCALAPPDATA "AtlasQuant\team-access-sandbox")
)
$LocalPrefix = $LocalRoot.TrimEnd("\") + "\"
$RepoPrefix = $RepoRoot.TrimEnd("\") + "\"
$OutputResolved = [System.IO.Path]::GetFullPath($OutputDir)

if (
    $EnvResolved.StartsWith($RepoPrefix, [System.StringComparison]::OrdinalIgnoreCase) -or
    $BaselineResolved.StartsWith($RepoPrefix, [System.StringComparison]::OrdinalIgnoreCase) -or
    $OutputResolved.StartsWith($RepoPrefix, [System.StringComparison]::OrdinalIgnoreCase)
) {
    throw "Step 1 operator artifacts must stay outside the repository tree."
}
if (-not $EnvResolved.StartsWith($LocalPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Sandbox env file must stay under the approved LOCALAPPDATA sandbox root."
}
if (-not $BaselineResolved.StartsWith($LocalPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Baseline evidence must stay under the approved LOCALAPPDATA sandbox root."
}
if (-not $OutputResolved.StartsWith($LocalPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Step 1 observation output must stay under the approved LOCALAPPDATA sandbox root."
}

$baseline = Get-Content -LiteralPath $BaselineFile -Raw | ConvertFrom-Json
$sessionId = [string]$baseline.operator_session_id
$baselineDigest = [string]$baseline.evidence_digest

if ($baseline.state -ne "READY_FOR_ADMIN_TEAM_ACCESS_SANDBOX_LIFECYCLE_TEST_REVIEW") {
    throw "Baseline evidence is not in the required review state."
}
if ($sessionId -notmatch "^[0-9a-f]{32}$") {
    throw "Baseline does not contain a valid operator_session_id."
}
if ($baselineDigest -notmatch "^[0-9a-f]{64}$") {
    throw "Baseline does not contain a valid evidence_digest."
}

$ComposeFile = Join-Path $PSScriptRoot "compose.yml"
$StopScript = Join-Path $PSScriptRoot "Stop-TeamAccessSandbox.ps1"
if (-not (Test-Path -LiteralPath $ComposeFile)) {
    throw "Sandbox compose file is missing."
}
if (-not (Test-Path -LiteralPath $StopScript)) {
    throw "Cleanup script is missing."
}

$composeText = Get-Content -LiteralPath $ComposeFile -Raw
if ($composeText -match "(?m)^\s*-?\s*0\.0\.0\.0:") {
    throw "Public bind detected in sandbox compose."
}
if ($composeText -notmatch "127\.0\.0\.1") {
    throw "Expected localhost-only bind was not found in sandbox compose."
}

# These two scripts perform read-only checks only:
# Docker status, OIDC discovery GET and PostgreSQL schema SELECT.
& "$PSScriptRoot\Test-TeamAccessSandbox.ps1" -EnvFile $EnvFile | Out-Null
& "$PSScriptRoot\Test-TeamAccessRegistry.ps1" -EnvFile $EnvFile | Out-Null

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$output = Join-Path $OutputDir "step1-readiness-observation.json"

$payload = [ordered]@{
    schema = "ATLASQUANT_AION_BUSINESS_TEAM_ACCESS_STEP1_READINESS_OBSERVATION_V1"
    version = "1"
    operator_session_id = $sessionId
    baseline_evidence_digest_observed = $baselineDigest
    observed_at = (Get-Date).ToUniversalTime().ToString("o")
    observed_by = $ObservedBy
    sandbox_health_verified = $true
    oidc_verified = $true
    registry_schema_verified = $true
    secrets_local = $true
    production_targets_absent = $true
    cleanup_path_ready = $true
    secret_material_included = $false
    production_targeted = $false
    external_mutations_executed = $false
}

$payload | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $output -Encoding UTF8
Write-Host "Step 1 readiness observation written to: $output"
Write-Host "Read-only checks completed. No lifecycle mutation was executed."
