# AION Windows basic inventory reference. READ-ONLY only with a separate
# owner approval specifying the exact machine, commands and output audience.
# No PIN, secrets, biometrics, TPM, FIDO2 keys, license IDs, network or files.
# CI invokes plan-only. This script is not an installer or authority decision.
[CmdletBinding()]
param(
    [switch]$AuthorizeReadOnlyInventory
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# Executing the script without the explicit switch reads no Windows registry,
# host properties, hardware, user identifiers, credentials or environment.
if (-not $AuthorizeReadOnlyInventory.IsPresent) {
    Write-Output 'PLAN_ONLY_NO_WINDOWS_READ'
    Write-Output 'Scope after separate owner approval: registry ProductName, EditionID, DisplayVersion, CurrentBuildNumber, UBR; runtime architecture.'
    Write-Output 'Excluded: account name, hostname, serial number, product keys, TPM, FIDO2, biometrics, BitLocker keys, certificates, secrets, network, installation.'
    Write-Output 'FIRST_INSTALL_HARD_NO_GO'
    return
}

if (-not [Runtime.InteropServices.RuntimeInformation]::IsOSPlatform(
    [Runtime.InteropServices.OSPlatform]::Windows
)) {
    throw 'WINDOWS_PLATFORM_REQUIRED'
}

# A single allowlisted read of publicly describable OS edition/version keys.
# It does not query device ownership, hardware identity or Windows Security.
$cv = Get-ItemProperty -LiteralPath 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion' -ErrorAction Stop

# Only specifically named non-identifying properties can appear in the output.
# Any missing property fails rather than broadening to a wildcard registry dump.
$report = [ordered]@{
    schema = 'AION_WINDOWS_BASIC_INVENTORY_READONLY_V1'
    mode = 'APPROVED_OBSERVATION_ONLY_NOT_INSTALLATION'
    first_install_status = 'HARD_NO_GO'
    owner_identity_verified = $false
    hardware_attestation_verified = $false
    signed_installer_verified = $false
    independent_witness_verified = $false
    installation_authorized = $false
    worker_authorized = $false
    product_name = [string]$cv.ProductName
    edition_id = [string]$cv.EditionID
    display_version = [string]$cv.DisplayVersion
    os_build = [string]$cv.CurrentBuildNumber
    update_build_revision = [int]$cv.UBR
    os_architecture = [string][Runtime.InteropServices.RuntimeInformation]::OSArchitecture
    process_architecture = [string][Runtime.InteropServices.RuntimeInformation]::ProcessArchitecture
    security_capabilities = 'NOT_INSPECTED'
    windows_hello = 'NOT_INSPECTED'
    tpm = 'NOT_INSPECTED'
    bitlocker = 'NOT_INSPECTED'
    fido2 = 'NOT_INSPECTED'
    network_access_performed = $false
    files_written = $false
}

# No export file and no side effects. Results must be kept private.
$report | ConvertTo-Json -Depth 2 | Write-Output
