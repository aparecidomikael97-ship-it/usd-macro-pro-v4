# G128 — ephemeral Windows hosted-runner principal separation, LAB ONLY.
# Creates a disposable LOCAL standard account ONLY on GitHub-hosted Windows CI.
# No personal PC, customer, production account, provider or paid cloud access.
# Failure to launch the separate token is NOT_EXERCISED/CI failure, never PASS.

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repoProbe = Join-Path $env:GITHUB_WORKSPACE 'labs/a190/g128_os_principal_probe_lab.py'
if (!(Test-Path -LiteralPath $repoProbe)) {
    throw 'G128_PROBE_SOURCE_MISSING'
}
$pythonExe = (Get-Command python -ErrorAction Stop).Source
$token = [Guid]::NewGuid().ToString('N')
$accountName = 'g128a' + $token.Substring(0, 8)
$privateDir = Join-Path $env:RUNNER_TEMP ('g128-private-' + $token)
$publicDir = Join-Path $env:PUBLIC ('g128-public-' + $token)
$probeCopy = Join-Path $publicDir 'g128_probe.py'
$dbPath = Join-Path $privateDir 'synthetic-probe.db'
$ownerName = ((whoami).Trim() -split [regex]::Escape([string][char]92))[-1]
$ownerSid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value

$randomBytes = New-Object byte[] 24
[System.Security.Cryptography.RandomNumberGenerator]::Fill($randomBytes)
$passwordPlain = 'G128!' + [Convert]::ToBase64String($randomBytes) + 'x7A!'
$passwordSecure = ConvertTo-SecureString -String $passwordPlain -AsPlainText -Force
$passwordPlain = $null

New-Item -ItemType Directory -Path $privateDir -ErrorAction Stop | Out-Null
New-Item -ItemType Directory -Path $publicDir -ErrorAction Stop | Out-Null
Copy-Item -LiteralPath $repoProbe -Destination $probeCopy -ErrorAction Stop

& icacls.exe $privateDir '/inheritance:r' | Out-Host
if ($LASTEXITCODE -ne 0) { throw 'G128_WINDOWS_REMOVE_INHERITANCE_FAILED' }
& icacls.exe $privateDir '/grant:r' ('*' + $ownerSid + ':(OI)(CI)F') | Out-Host
if ($LASTEXITCODE -ne 0) { throw 'G128_WINDOWS_OWNER_ACL_FAILED' }
& icacls.exe $privateDir '/grant:r' '*S-1-5-18:(OI)(CI)F' | Out-Host
if ($LASTEXITCODE -ne 0) { throw 'G128_WINDOWS_SYSTEM_ACL_FAILED' }

$acl = Get-Acl -LiteralPath $privateDir
if (!$acl.AreAccessRulesProtected) { throw 'G128_WINDOWS_INHERITANCE_STILL_ON' }

& $pythonExe -B $probeCopy owner-init $dbPath $ownerName
if ($LASTEXITCODE -ne 0) { throw 'G128_WINDOWS_OWNER_INIT_FAILED' }

New-LocalUser -Name $accountName -Password $passwordSecure -PasswordNeverExpires -Description 'Disposable G128 restricted app principal on ephemeral GitHub runner only' | Out-Null
try {
    $credential = New-Object System.Management.Automation.PSCredential(
        ($env:COMPUTERNAME + [char]92 + $accountName), $passwordSecure
    )
    $appStdout = Join-Path $publicDir 'app-stdout.txt'
    $appStderr = Join-Path $publicDir 'app-stderr.txt'
    $arguments = @(
        '-B',
        ('"' + $probeCopy + '"'),
        'app',
        ('"' + $dbPath + '"'),
        $accountName
    )
    $startArguments = @{
        FilePath = $pythonExe
        ArgumentList = $arguments
        Credential = $credential
        WorkingDirectory = $publicDir
        Wait = $true
        PassThru = $true
        RedirectStandardOutput = $appStdout
        RedirectStandardError = $appStderr
        ErrorAction = 'Stop'
    }
    try {
        $appProcess = Start-Process @startArguments
    }
    catch {
        Write-Host 'G128_WINDOWS_SEPARATE_USER_PROCESS=NOT_EXERCISED'
        throw
    }
    if (Test-Path -LiteralPath $appStdout) {
        Get-Content -LiteralPath $appStdout | ForEach-Object { Write-Host $_ }
    }
    if (Test-Path -LiteralPath $appStderr) {
        Get-Content -LiteralPath $appStderr | ForEach-Object { Write-Host $_ }
    }
    if ($appProcess.ExitCode -ne 0) {
        throw ('G128_WINDOWS_SEPARATE_USER_PROBE_FAILED exit=' + $appProcess.ExitCode)
    }
    $output = Get-Content -LiteralPath $appStdout -Raw
    @(
        'G128_APP_RAW_READ=OS_DENIED',
        'G128_APP_RAW_WRITE=OS_DENIED',
        'G128_APP_SQLITE_READ=OS_DENIED',
        'G128_APP_SQLITE_WRITE=OS_DENIED',
        'G128_SEPARATE_LOW_PRIVILEGE_OS_PRINCIPAL=PROVEN_ONLY'
    ) | ForEach-Object {
        if (!$output.Contains($_)) { throw ('G128_WINDOWS_EXPECTED_MARKER_MISSING: ' + $_) }
    }

    & $pythonExe -B $probeCopy owner-check $dbPath $ownerName
    if ($LASTEXITCODE -ne 0) { throw 'G128_WINDOWS_OWNER_CONTROL_FAILED' }

    $windowsPrincipal = New-Object System.Security.Principal.WindowsPrincipal(
        [System.Security.Principal.WindowsIdentity]::GetCurrent()
    )
    if (!$windowsPrincipal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'G128_WINDOWS_ADMIN_OVERRIDE_NOT_TESTABLE'
    }
    Write-Host 'G128_WINDOWS_STANDARD_USER_NATIVE_SQLITE=OS_DENIED'
    Write-Host 'G128_WINDOWS_LOCAL_ADMIN_CONTROL=STILL_VULNERABLE_NOT_P0'
}
finally {
    Remove-LocalUser -Name $accountName -ErrorAction Stop
}
