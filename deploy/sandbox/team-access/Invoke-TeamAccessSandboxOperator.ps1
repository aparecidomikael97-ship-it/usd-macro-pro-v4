param(
    [string]$EnvFile = (Join-Path $env:LOCALAPPDATA "AtlasQuant\team-access-sandbox\team-access-sandbox.env"),
    [string]$OperatorDir = (Join-Path $env:LOCALAPPDATA "AtlasQuant\team-access-sandbox\operator"),
    [string]$EvidenceDir = (Join-Path $env:LOCALAPPDATA "AtlasQuant\team-access-sandbox\evidence"),
    [switch]$ApplyStart,
    [switch]$CollectBaseline
)

$ErrorActionPreference = "Stop"
if (-not $env:LOCALAPPDATA) {
    throw "LOCALAPPDATA is required for the default operator paths."
}
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path

Write-Host "AtlasQuant Team Access Sandbox Operator"
Write-Host "--------------------------------------"

& "$PSScriptRoot\Get-TeamAccessSandboxReadiness.ps1" -EnvFile $EnvFile -OutputDir $OperatorDir
if ($LASTEXITCODE -ne 0) {
    throw "Operator readiness command failed."
}

$readinessFile = Join-Path $OperatorDir "windows-operator-readiness.json"
if (-not (Test-Path -LiteralPath $readinessFile)) {
    throw "Readiness report not found."
}
$readiness = Get-Content -LiteralPath $readinessFile -Raw | ConvertFrom-Json
$operatorSessionId = [string]$readiness.operator_session_id
if ($operatorSessionId -notmatch "^[0-9a-f]{32}$") {
    throw "Readiness report does not contain a valid operator session id."
}
if ($readiness.state -ne "READY_FOR_ADMIN_TEAM_ACCESS_WINDOWS_SANDBOX_START_DECISION") {
    throw "Sandbox operator readiness is blocked. Resolve the reported checks first."
}

if (-not $ApplyStart) {
    Write-Host ""
    Write-Host "PLAN ONLY - readiness passed, but no container was started."
    Write-Host "To start the LOCAL sandbox explicitly:"
    Write-Host "  .\Invoke-TeamAccessSandboxOperator.ps1 -ApplyStart"
    Write-Host "To start, verify and collect baseline:"
    Write-Host "  .\Invoke-TeamAccessSandboxOperator.ps1 -ApplyStart -CollectBaseline"
    exit 0
}

Write-Host ""
Write-Host "Explicit -ApplyStart received. Starting LOCAL SANDBOX only."
& "$PSScriptRoot\Start-TeamAccessSandbox.ps1" -EnvFile $EnvFile -Apply

Write-Host ""
Write-Host "Running read-only sandbox verification..."
& "$PSScriptRoot\Test-TeamAccessSandbox.ps1" -EnvFile $EnvFile
& "$PSScriptRoot\Test-TeamAccessRegistry.ps1" -EnvFile $EnvFile

if (-not $CollectBaseline) {
    Write-Host ""
    Write-Host "Sandbox verified. Baseline was not collected because -CollectBaseline was not supplied."
    exit 0
}

Write-Host ""
Write-Host "Collecting sanitized baseline evidence..."
& "$PSScriptRoot\Collect-TeamAccessSandboxEvidence.ps1" -EnvFile $EnvFile -OutputDir $EvidenceDir -OperatorSessionId $operatorSessionId

$evidenceFile = Join-Path $EvidenceDir "team-access-baseline-evidence.json"
if (-not (Test-Path -LiteralPath $evidenceFile)) {
    throw "Baseline evidence file was not produced."
}

Push-Location $RepoRoot
try {
    python validate_team_access_sandbox_evidence.py $evidenceFile
    if ($LASTEXITCODE -ne 0) {
        throw "Baseline evidence validation failed."
    }
}
finally {
    Pop-Location
}

Write-Host ""
Write-Host "Sandbox baseline flow completed."
Write-Host "No lifecycle account/MFA/registry/session step was executed."
Write-Host "Production was not targeted."
