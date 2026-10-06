[CmdletBinding()]
param(
    [Parameter()]
    [string]$CertificationTrustRoot = "",

    [Parameter()]
    [string]$OwnerTrustRoot = "",

    [Parameter()]
    [string]$ExpectedRuntimeSha = "020facc9991c5d2d4ce457e0840b04c875f8cfae",

    [Parameter()]
    [switch]$CheckRuntimeRead,

    [Parameter()]
    [switch]$RequireWriteReady,

    [Parameter()]
    [switch]$CiMode,

    [Parameter()]
    [string]$PythonCommand = "python"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Fail-ClosureLauncher {
    param([string]$Message)
    [Console]::Error.WriteLine($Message)
    exit 2
}

$ScriptDir = $PSScriptRoot
$Repo = (Resolve-Path (Join-Path $ScriptDir "..\..")).Path
$Packet = Join-Path $Repo "ops\aion-core-v1-formal-closure\unsigned_v220_evidence_packet.json"

if ($CiMode) {
    $TempRoot = [System.IO.Path]::GetTempPath()
    $Work = Join-Path $TempRoot "AtlasQuantAION-formal-closure-work"
    $NonceDb = Join-Path $TempRoot "AtlasQuantAION-formal-closure-nonce.sqlite3"
}
else {
    if (-not $env:LOCALAPPDATA) {
        Fail-ClosureLauncher "LOCALAPPDATA is required on the authorized Windows host."
    }
    $Work = Join-Path $env:LOCALAPPDATA "AtlasQuantAION\formal-closure\work"
    $NonceDb = Join-Path $env:LOCALAPPDATA "AtlasQuantAION\formal-closure\nonce_registry.sqlite3"
}

New-Item -ItemType Directory -Force -Path $Work | Out-Null

if (-not (Test-Path -LiteralPath $Packet -PathType Leaf)) {
    Fail-ClosureLauncher "Canonical unsigned V2.20 packet not found: $Packet"
}

if (-not $CiMode) {
    if (-not $CertificationTrustRoot) {
        Fail-ClosureLauncher "CertificationTrustRoot is required for the real ceremony and must point to a PUBLIC-ONLY trust-root JSON."
    }
    if (-not $OwnerTrustRoot) {
        Fail-ClosureLauncher "OwnerTrustRoot is required for the real ceremony and must point to a PUBLIC-ONLY HUMAN_OWNER trust-root JSON."
    }
    if (-not (Test-Path -LiteralPath $CertificationTrustRoot -PathType Leaf)) {
        Fail-ClosureLauncher "CertificationTrustRoot file not found."
    }
    if (-not (Test-Path -LiteralPath $OwnerTrustRoot -PathType Leaf)) {
        Fail-ClosureLauncher "OwnerTrustRoot file not found."
    }
}

$argsList = @(
    "-m",
    "ops.aion_core_v1_formal_closure.windows_readiness_preflight",
    "--repo-root", $Repo,
    "--packet", $Packet,
    "--work-dir", $Work,
    "--nonce-registry", $NonceDb,
    "--expected-runtime-sha", $ExpectedRuntimeSha
)

if ($CertificationTrustRoot) {
    $argsList += @("--certification-trust-root", (Resolve-Path $CertificationTrustRoot).Path)
}
if ($OwnerTrustRoot) {
    $argsList += @("--owner-trust-root", (Resolve-Path $OwnerTrustRoot).Path)
}
if ($CheckRuntimeRead) {
    $argsList += "--check-runtime-read"
}
if ($RequireWriteReady) {
    $argsList += "--require-write-ready"
}
if ($CiMode) {
    $argsList += "--allow-non-windows-ci"
}

$Mode = if ($CiMode) { "CI structural validation" } else { "AUTHORIZED WINDOWS PREFLIGHT" }
Write-Host "AION Core V1 formal closure launcher"
Write-Host "Formal target: 662eab4dc4f5bb009fa1ca89f87530df74d30ddf"
Write-Host "Mode: $Mode"
Write-Host "This launcher performs no signature, nonce claim, runtime write, merge, deploy, Worker arming or Core Freeze."

$raw = & $PythonCommand @argsList
$exitCode = $LASTEXITCODE
if ($null -eq $raw) {
    Fail-ClosureLauncher "Readiness preflight returned no output."
}

$lines = @($raw | ForEach-Object { "$_" } | Where-Object { $_.Trim() -ne "" })
$last = $lines[-1]
try {
    $result = $last | ConvertFrom-Json
}
catch {
    Write-Output $raw
    Fail-ClosureLauncher "Readiness preflight did not return valid JSON."
}

Write-Output $last

if ($exitCode -ne 0) {
    Write-Host "Formal closure remains BLOCKED. No authority action was executed."
    exit $exitCode
}

if ($CiMode) {
    if ($result.state -ne "STRUCTURAL_PREFLIGHT_PASS") {
        Fail-ClosureLauncher "CI launcher expected STRUCTURAL_PREFLIGHT_PASS but observed $($result.state)."
    }
    if ($result.executes_action -ne $false -or
        $result.signature_performed -ne $false -or
        $result.nonce_consumed -ne $false -or
        $result.runtime_write_performed -ne $false) {
        Fail-ClosureLauncher "CI launcher safety invariant failed."
    }
    Write-Host "CI LAUNCHER PASS: structural preflight only; zero authority action."
    exit 0
}

if (-not $CheckRuntimeRead) {
    Fail-ClosureLauncher "Real ceremony launcher requires -CheckRuntimeRead."
}
if (-not $RequireWriteReady) {
    Fail-ClosureLauncher "Real ceremony launcher requires -RequireWriteReady."
}
if ($result.state -ne "READY_FOR_FORMAL_CLOSURE_CEREMONY" -or $result.real_authority_ready -ne $true) {
    Fail-ClosureLauncher "Formal closure is not ready. Required state: READY_FOR_FORMAL_CLOSURE_CEREMONY."
}
if ($result.executes_action -ne $false -or
    $result.private_key_loaded -ne $false -or
    $result.signature_performed -ne $false -or
    $result.nonce_consumed -ne $false -or
    $result.runtime_write_performed -ne $false -or
    $result.merge_authorized -ne $false -or
    $result.deploy_authorized -ne $false -or
    $result.worker_armed -ne $false) {
    Fail-ClosureLauncher "Formal readiness safety invariant failed."
}

Write-Host ""
Write-Host "READY_FOR_FORMAL_CLOSURE_CEREMONY"
Write-Host "Passo 0 concluido. Pare aqui antes de qualquer assinatura."
Write-Host "Proximo gate: REAL V2.20 external certification signing."
Write-Host "Private Ed25519 keys must remain outside the repository, runtime JSON, logs and prompts."
exit 0
