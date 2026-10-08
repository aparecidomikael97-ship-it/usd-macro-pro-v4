# CI-only read-only Authenticode inspection and modified-copy negative control.
# Writes JSON and tampered inert file ONLY to ephemeral GitHub RUNNER_TEMP.
# Never executes the tampered copy or changes Registry/ACL/startup/install.
$ErrorActionPreference = 'Stop'
if (
    $env:GITHUB_ACTIONS -ne 'true' -or
    $env:RUNNER_OS -ne 'Windows' -or
    $env:GITHUB_EVENT_NAME -ne 'pull_request' -or
    $env:AION_CI_AUTHENTICODE_FIXTURE -ne '1' -or
    -not (Test-Path -LiteralPath $env:RUNNER_TEMP -PathType Container)
) {
    throw 'EPHEMERAL_WINDOWS_GITHUB_PR_RUNNER_REQUIRED'
}
$systemExecutable = Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'
if (-not (Test-Path -LiteralPath $systemExecutable -PathType Leaf)) {
    throw 'WINDOWS_SIGNED_SYSTEM_BINARY_MISSING'
}
$root = Join-Path $env:RUNNER_TEMP ('aion-wintrust-ci-' + [Guid]::NewGuid().ToString('N'))
$null = New-Item -ItemType Directory -Path $root -Force
$fixturePath = Join-Path $root 'signature-fixture.json'
$tamperedPath = Join-Path $root 'modified-copy-not-executed.exe'
$bytes = [System.IO.File]::ReadAllBytes($systemExecutable)
if ($bytes.Length -lt 8192 -or $bytes[0] -ne 0x4D -or $bytes[1] -ne 0x5A) {
    throw 'WINDOWS_PE_BASELINE_INVALID'
}
[System.IO.File]::WriteAllBytes($tamperedPath, $bytes)
$modified = [System.IO.File]::ReadAllBytes($tamperedPath)
$position = [Math]::Min(8192, $modified.Length - 1024)
$modified[$position] = $modified[$position] -bxor 0x01
[System.IO.File]::WriteAllBytes($tamperedPath, $modified)

function Get-CertSha256([object]$cert) {
    if ($null -eq $cert) { return '' }
    $certificateBytes = $cert.RawData
    return ('sha256:' + [Convert]::ToHexString(
        [System.Security.Cryptography.SHA256]::HashData($certificateBytes)
    ).ToLowerInvariant())
}
function Get-SafeSignatureRow([string]$path, [string]$role) {
    $sig = Get-AuthenticodeSignature -LiteralPath $path -ErrorAction Stop
    $hash = Get-FileHash -LiteralPath $path -Algorithm SHA256 -ErrorAction Stop
    $header = [System.IO.File]::ReadAllBytes($path)
    return @{
        role = $role
        binary_sha256 = 'sha256:' + $hash.Hash.ToLowerInvariant()
        byte_count = [int]$header.Length
        pe_magic_mz = ($header[0] -eq 0x4D -and $header[1] -eq 0x5A)
        signature_status = $sig.Status.ToString()
        signer_cert_sha256 = Get-CertSha256 $sig.SignerCertificate
        signer_cert_present = ($null -ne $sig.SignerCertificate)
    }
}
$baseline = Get-SafeSignatureRow $systemExecutable 'WINDOWS_SYSTEM_POWERSHELL_EXE'
$tampered = Get-SafeSignatureRow $tamperedPath 'MUTATED_CI_SCRATCH_COPY'
$fixture = @{
    schema = 'ATLASQUANT_AION_WINDOWS_CI_AUTHENTICODE_INTEGRITY_V1'
    ci_scope = 'EPHEMERAL_WINDOWS_GITHUB_PR_RUNNER'
    artifact_role = 'CI_SIGNED_WINDOWS_SYSTEM_POWERSHELL'
    challenge_digest = 'sha256:' + ('a' * 64)
    policy_digest = 'sha256:' + ('b' * 64)
    verifier_source_digest = 'sha256:' + ('c' * 64)
    baseline = $baseline
    tampered = $tampered
    tamper_operation = 'ONE_BYTE_XOR_CI_SCRATCH_NOT_EXECUTED'
    tampered_copy_executed = $false
    owner_device_accessed = $false
    aion_binary_examined = $false
    aion_release_signer_verified = $false
    signed_artifact_installed = $false
}
$fixture | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $fixturePath -Encoding utf8NoBOM
if ($baseline.signature_status -ne 'Valid' -or -not $baseline.signer_cert_present) {
    throw 'WINDOWS_CI_BASELINE_SIGNATURE_NOT_VALID'
}
if ($tampered.signature_status -eq 'Valid') {
    throw 'TAMPERED_CI_COPY_SIGNATURE_WAS_VALID'
}
if ($baseline.binary_sha256 -eq $tampered.binary_sha256) {
    throw 'SYNTHETIC_SINGLE_BYTE_CHANGE_NOT_DETECTED'
}
# GITHUB_ENV is an isolated CI runner mechanism; no physical owner device.
"AION_AUTHENTICODE_FIXTURE_FILE=$fixturePath" | Out-File -FilePath $env:GITHUB_ENV -Append -Encoding utf8
"AION_AUTHENTICODE_FIXTURE_ROOT=$root" | Out-File -FilePath $env:GITHUB_ENV -Append -Encoding utf8
Write-Host 'CI Authenticode baseline valid, modified-copy rejected. Private fixture in runner temp only.'
