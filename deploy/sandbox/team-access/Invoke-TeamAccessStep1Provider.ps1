param(
    [string]$EnvFile = (Join-Path $env:LOCALAPPDATA "AtlasQuant\team-access-sandbox\team-access-sandbox.env"),
    [string]$ExecutionEnvelopeFile = (Join-Path $env:LOCALAPPDATA "AtlasQuant\team-access-sandbox\operator\step1-execution-envelope.json"),
    [string]$ApplyPlanFile = (Join-Path $env:LOCALAPPDATA "AtlasQuant\team-access-sandbox\operator\step1-apply-plan.json"),
    [string]$OutputDir = (Join-Path $env:LOCALAPPDATA "AtlasQuant\team-access-sandbox\operator"),
    [switch]$Apply,
    [string]$AuthorizationToken = ""
)

$ErrorActionPreference = "Stop"

function Read-EnvFile {
    param([string]$Path)
    $result = @{}
    foreach ($line in Get-Content -LiteralPath $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) { continue }
        $parts = $trimmed -split "=", 2
        if ($parts.Count -ne 2) { continue }
        $result[$parts[0].Trim()] = $parts[1].Trim()
    }
    return $result
}

function Assert-UnderRoot {
    param(
        [string]$Path,
        [string]$ApprovedPrefix,
        [string]$RepoPrefix,
        [string]$Label
    )
    $full = [System.IO.Path]::GetFullPath($Path)
    if ($full.StartsWith($RepoPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "$Label must stay outside the repository tree."
    }
    if (-not $full.StartsWith($ApprovedPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "$Label must stay under the approved LOCALAPPDATA sandbox root."
    }
    return $full
}

if (-not $env:LOCALAPPDATA) { throw "LOCALAPPDATA is required." }

foreach ($path in @($EnvFile, $ExecutionEnvelopeFile, $ApplyPlanFile)) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Required local sandbox artifact not found: $path"
    }
    if ($path -match "(?i)prod") {
        throw "Production-like paths are forbidden."
    }
}

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
$LocalRoot = [System.IO.Path]::GetFullPath((Join-Path $env:LOCALAPPDATA "AtlasQuant\team-access-sandbox"))
$LocalPrefix = $LocalRoot.TrimEnd("\") + "\"
$RepoPrefix = $RepoRoot.TrimEnd("\") + "\"

$EnvResolved = Assert-UnderRoot -Path (Resolve-Path -LiteralPath $EnvFile).Path -ApprovedPrefix $LocalPrefix -RepoPrefix $RepoPrefix -Label "Sandbox env"
$EnvelopeResolved = Assert-UnderRoot -Path (Resolve-Path -LiteralPath $ExecutionEnvelopeFile).Path -ApprovedPrefix $LocalPrefix -RepoPrefix $RepoPrefix -Label "Execution envelope"
$PlanResolved = Assert-UnderRoot -Path (Resolve-Path -LiteralPath $ApplyPlanFile).Path -ApprovedPrefix $LocalPrefix -RepoPrefix $RepoPrefix -Label "Apply plan"
$OutputResolved = Assert-UnderRoot -Path $OutputDir -ApprovedPrefix $LocalPrefix -RepoPrefix $RepoPrefix -Label "Runner output"

$envMap = Read-EnvFile -Path $EnvResolved
if ($envMap["ATLASQUANT_SANDBOX_ONLY"] -ne "true") {
    throw "ATLASQUANT_SANDBOX_ONLY=true is required."
}
foreach ($key in @("KEYCLOAK_HTTP_PORT","KC_BOOTSTRAP_ADMIN_USERNAME","KC_BOOTSTRAP_ADMIN_PASSWORD")) {
    if (-not $envMap.ContainsKey($key) -or -not $envMap[$key]) {
        throw "Missing required sandbox env key: $key"
    }
    if ($envMap[$key] -match "(?i)CHANGE_ME|CHANGEME|PLACEHOLDER") {
        throw "Sandbox env still contains placeholder material for $key."
    }
}

[int]$keycloakPort = 0
if (-not [int]::TryParse($envMap["KEYCLOAK_HTTP_PORT"], [ref]$keycloakPort)) {
    throw "KEYCLOAK_HTTP_PORT must be numeric."
}
if ($keycloakPort -lt 1024 -or $keycloakPort -gt 65535) {
    throw "KEYCLOAK_HTTP_PORT is outside the allowed sandbox range."
}
$baseUrl = "http://127.0.0.1:$keycloakPort"

$validator = Join-Path $RepoRoot "validate_team_access_step1_provider_runner.py"
if (-not (Test-Path -LiteralPath $validator)) {
    throw "Runner validator CLI is missing."
}
$python = Get-Command python -ErrorAction Stop

New-Item -ItemType Directory -Force -Path $OutputResolved | Out-Null
$preflightFile = Join-Path $OutputResolved "step1-provider-runner-preflight.json"

$validatorArgs = @($validator,$EnvelopeResolved,$PlanResolved,"--base-url",$baseUrl,"--output",$preflightFile)
if ($Apply) {
    $validatorArgs += "--apply"
    $validatorArgs += "--authorization-token"
    $validatorArgs += $AuthorizationToken
}

& $python.Source @validatorArgs
if ($LASTEXITCODE -ne 0) { throw "Step 1 provider runner preflight failed." }

$preflight = Get-Content -LiteralPath $preflightFile -Raw | ConvertFrom-Json

if (-not $Apply) {
    if ($preflight.state -ne "STEP1_PROVIDER_RUNNER_PLAN_ONLY") {
        throw "Runner did not reach PLAN ONLY state."
    }
    Write-Host ""
    Write-Host "PLAN ONLY - no Keycloak mutation was executed."
    Write-Host "Provider: Keycloak sandbox on $baseUrl"
    Write-Host "Required physical apply token:"
    Write-Host ([string]$preflight.required_physical_apply_token)
    Write-Host ""
    Write-Host "To request the physical sandbox apply explicitly, rerun with:"
    Write-Host "  -Apply -AuthorizationToken <exact-token-above>"
    exit 0
}

if ($preflight.state -ne "READY_FOR_EXPLICIT_MANUAL_STEP1_PROVIDER_APPLY") {
    throw "Physical apply authorization preflight was not satisfied."
}
if (-not $AuthorizationToken) { throw "AuthorizationToken is required with -Apply." }

$probe = Join-Path $OutputResolved ".step1-runner-write-probe.tmp"
"probe" | Set-Content -LiteralPath $probe -Encoding UTF8
Remove-Item -LiteralPath $probe -Force

$plan = Get-Content -LiteralPath $PlanResolved -Raw | ConvertFrom-Json
$operation = $plan.provider_operation
if ($operation.provider -ne "KEYCLOAK") { throw "Only KEYCLOAK provider is allowed." }
if ($operation.realm -ne "atlasquant-sandbox") { throw "Only atlasquant-sandbox realm is allowed." }
if ($operation.method -ne "POST") { throw "Only POST is allowed for Step 1." }
if ($operation.relative_path -ne "/admin/realms/atlasquant-sandbox/users") { throw "Unexpected Keycloak Step 1 endpoint." }
if ([int]$operation.expected_http_status -ne 201) { throw "Expected Keycloak create-user status must be 201." }
if ($operation.authorization_header_included -ne $false -or $operation.access_token_included -ne $false -or $operation.secret_material_included -ne $false) {
    throw "Apply plan unexpectedly contains authorization or secret material."
}

$username = [string]$plan.target_username
if (-not $username.StartsWith("sandbox.")) { throw "Target username must use the sandbox. prefix." }

$tokenUri = "$baseUrl/realms/master/protocol/openid-connect/token"
$tokenBody = @{
    client_id = "admin-cli"
    username = $envMap["KC_BOOTSTRAP_ADMIN_USERNAME"]
    password = $envMap["KC_BOOTSTRAP_ADMIN_PASSWORD"]
    grant_type = "password"
}
$accessToken = $null
$tokenResponse = $null

try {
    $tokenResponse = Invoke-RestMethod -Method Post -Uri $tokenUri -ContentType "application/x-www-form-urlencoded" -Body $tokenBody
    $accessToken = [string]$tokenResponse.access_token
    if (-not $accessToken) { throw "Keycloak did not return an access token." }

    $headers = @{ Authorization = "Bearer $accessToken" }
    $encodedUsername = [System.Uri]::EscapeDataString($username)
    $lookupUri = "$baseUrl/admin/realms/atlasquant-sandbox/users?username=$encodedUsername&exact=true"

    $existing = @(Invoke-RestMethod -Method Get -Uri $lookupUri -Headers $headers)
    if ($existing.Count -ne 0) {
        throw "Target sandbox account already exists. Step 1 aborted before POST."
    }

    $bodyJson = $operation.body | ConvertTo-Json -Depth 12 -Compress
    $response = Invoke-WebRequest -UseBasicParsing -Method Post -Uri "$baseUrl$($operation.relative_path)" -Headers $headers -ContentType "application/json" -Body $bodyJson

    if ([int]$response.StatusCode -ne 201) {
        throw "Unexpected Keycloak create-user status: $($response.StatusCode)"
    }

    $created = @(Invoke-RestMethod -Method Get -Uri $lookupUri -Headers $headers)
    if ($created.Count -ne 1) {
        throw "Create-user POST returned 201 but exact readback did not return one user."
    }
    if ([string]$created[0].username -ne $username) {
        throw "Created user readback username mismatch."
    }
    if ($created[0].enabled -ne $true) {
        throw "Created user readback is not enabled."
    }

    $providerUserId = [string]$created[0].id
    if (-not $providerUserId) { throw "Created user readback did not expose a provider user id." }

    $receipt = [ordered]@{
        schema = "ATLASQUANT_AION_BUSINESS_TEAM_ACCESS_STEP1_PROVIDER_EXECUTION_RECEIPT_V1"
        version = "1"
        state = "STEP1_PROVIDER_APPLY_EXECUTED_PENDING_LEDGER_REVIEW"
        apply_plan_digest = [string]$plan.apply_plan_digest
        runner_preflight_digest = [string]$preflight.runner_preflight_digest
        execution_envelope_digest = [string]$plan.execution_envelope_digest
        operator_session_id = [string]$plan.operator_session_id
        baseline_evidence_digest = [string]$plan.baseline_evidence_digest
        target_step_order = 1
        target_step_id = [string]$plan.target_step_id
        target_username = $username
        provider = "KEYCLOAK"
        realm = "atlasquant-sandbox"
        provider_user_id = $providerUserId
        http_status = 201
        exact_readback_verified = $true
        executed_at = (Get-Date).ToUniversalTime().ToString("o")
        secret_material_included = $false
        access_token_included = $false
        authorization_token_included = $false
        ledger_append_authorized = $false
        automatic_ledger_append = $false
        production_targeted = $false
    }

    $receiptFile = Join-Path $OutputResolved "step1-provider-execution-receipt.json"
    $receipt | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $receiptFile -Encoding UTF8

    Write-Host "Sandbox Step 1 provider apply completed."
    Write-Host "Sanitized receipt written to: $receiptFile"
    Write-Host "Ledger append remains unauthorized pending receipt validation."
}
finally {
    $accessToken = $null
    $tokenResponse = $null
    $tokenBody["password"] = $null
}
