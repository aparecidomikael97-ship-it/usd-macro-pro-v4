<#
AION Local-First Hardware Read-Only Probe V1

Outputs only numerical resource sizing and broad GPU vendor class to STDOUT.
Does not export usernames, device names, IDs, serials, network, process lists,
driver paths, installed apps, secrets or personal account information.

Owner workstation: must be EXPLICITLY launched by user with
  -OwnerReadOnlyConsent
CI runner: -CIProbe is allowed only inside GitHub pull_request Windows runner.

No disk writes, no admin, no installs, no model downloads, no cloud/network,
no package build, no paid API call, no startup or Registry changes.
#>
[CmdletBinding()]
param(
    [switch]$OwnerReadOnlyConsent,
    [switch]$CIProbe
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if ($CIProbe -and $OwnerReadOnlyConsent) {
    throw 'CI_AND_OWNER_MODES_MUTUALLY_EXCLUSIVE'
}
if ($CIProbe) {
    if ($env:GITHUB_ACTIONS -ne 'true' -or
        $env:GITHUB_EVENT_NAME -ne 'pull_request' -or
        $env:RUNNER_OS -ne 'Windows') {
        throw 'CI_MODE_REQUIRES_GITHUB_WINDOWS_PR_RUNNER'
    }
    $reportSource = 'CI_EPHEMERAL'
}
elseif ($OwnerReadOnlyConsent) {
    $reportSource = 'OWNER_EXPLICIT_READ_ONLY'
}
else {
    throw 'EXPLICIT_READ_ONLY_CONSENT_REQUIRED'
}

$computer = Get-CimInstance -ClassName Win32_ComputerSystem
$processors = @(Get-CimInstance -ClassName Win32_Processor)
$videos = @(Get-CimInstance -ClassName Win32_VideoController)
$systemDisk = Get-CimInstance -ClassName Win32_LogicalDisk -Filter "DeviceID='$($env:SystemDrive)'"

if ($null -eq $computer -or $processors.Count -lt 1 -or $null -eq $systemDisk) {
    throw 'CORE_HARDWARE_METRICS_UNAVAILABLE'
}

$ramBytes = [double]$computer.TotalPhysicalMemory
$logical = 0
foreach ($cpu in $processors) {
    if ($null -ne $cpu.NumberOfLogicalProcessors) {
        $logical += [int]$cpu.NumberOfLogicalProcessors
    }
}
$ramGiB = [math]::Round($ramBytes / 1GB, 2)
$diskGiB = [math]::Round(([double]$systemDisk.FreeSpace) / 1GB, 2)
if ($ramGiB -le 0 -or $logical -lt 1 -or $diskGiB -lt 0) {
    throw 'HARDWARE_MEASUREMENT_INVALID'
}

$vendors = @()
foreach ($video in $videos) {
    $label = [string]$video.Name
    $vendor = 'OTHER_OR_UNKNOWN'
    if ($label -match 'NVIDIA|GeForce|Quadro|RTX|GTX') {
        $vendor = 'NVIDIA'
    }
    elseif ($label -match 'AMD|Radeon|ATI') {
        $vendor = 'AMD'
    }
    elseif ($label -match 'Intel') {
        $vendor = 'INTEL'
    }
    $vendors += $vendor
}
$vendors = @($vendors | Sort-Object -Unique)
if ($vendors.Count -eq 0) {
    $vendors = @('OTHER_OR_UNKNOWN')
}

$report = [ordered]@{
    schema = 'ATLASQUANT_AION_LOCAL_AI_HARDWARE_READONLY_V1'
    source = $reportSource
    ram_total_gib = $ramGiB
    cpu_logical_processors = $logical
    system_disk_free_gib = $diskGiB
    gpu_vendor_classes = @($vendors)
    dedicated_gpu_vram_verified = $false
    local_model_execution_tested = $false
    model_speed_measured = $false
    api_usage_charge_read = $false
    data_uploaded = $false
    device_modified = $false
    owner_install_approved = $false
    production_ready = $false
}
$report | ConvertTo-Json -Compress -Depth 4
