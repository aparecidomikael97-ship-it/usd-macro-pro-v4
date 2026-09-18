$ErrorActionPreference = "Stop"

$configDir = Join-Path $env:LOCALAPPDATA "AtlasQuant"
$secretsPath = Join-Path $configDir "secrets.toml"

function Get-ExistingSecret {
    param([Parameter(Mandatory=$true)][string]$Name)

    if (-not (Test-Path $secretsPath)) {
        return ""
    }

    try {
        $line = Get-Content -LiteralPath $secretsPath | Where-Object {
            $_.TrimStart().StartsWith($Name + " =")
        } | Select-Object -Last 1

        if ([string]::IsNullOrWhiteSpace($line)) {
            return ""
        }

        $parts = $line -split "=", 2
        if ($parts.Count -ne 2) {
            return ""
        }

        $value = $parts[1].Trim()
        if ($value.Length -ge 2 -and $value.StartsWith('"') -and $value.EndsWith('"')) {
            return $value.Substring(1, $value.Length - 2)
        }

        return ""
    } catch {
        return ""
    }
}

function Read-SecretOrKeep {
    param(
        [Parameter(Mandatory=$true)][string]$Name,
        [Parameter(Mandatory=$true)][string]$Label
    )

    $existing = Get-ExistingSecret -Name $Name
    if ([string]::IsNullOrWhiteSpace($existing)) {
        Write-Host ("[PENDENTE] " + $Label)
    } else {
        Write-Host ("[OK] " + $Label + " ja configurada")
    }

    $secure = Read-Host ("Cole " + $Name + " ou deixe em branco para manter o valor atual") -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)

    try {
        $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
        if ([string]::IsNullOrWhiteSpace($plain)) {
            return $existing
        }
        return $plain.Trim()
    }
    finally {
        if ($bstr -ne [IntPtr]::Zero) {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
        }
        $plain = $null
    }
}

Write-Host ""
Write-Host "============================================================"
Write-Host "       ATLASQUANT - CONFIGURAR AS 4 APIS LOCAIS"
Write-Host "============================================================"
Write-Host ""
Write-Host "As chaves ficarao salvas somente neste usuario do Windows em:"
Write-Host $secretsPath
Write-Host ""
Write-Host "Nenhuma chave sera colocada no ZIP ou enviada ao GitHub."
Write-Host ""

New-Item -ItemType Directory -Force -Path $configDir | Out-Null

$fred = Read-SecretOrKeep -Name "CHAVE_FRED" -Label "FRED"
if (-not [string]::IsNullOrWhiteSpace($fred) -and $fred -notmatch '^[a-z0-9]{32}$') {
    throw "CHAVE_FRED invalida. A chave FRED deve ter 32 caracteres minusculos (letras e numeros)."
}

$twelve = Read-SecretOrKeep -Name "CHAVE_TWELVE_DATA" -Label "Twelve Data"
$eodhd = Read-SecretOrKeep -Name "CHAVE_EODHD" -Label "EODHD"
$newsapi = Read-SecretOrKeep -Name "CHAVE_NEWSAPI" -Label "NewsAPI"

$managedNames = @(
    "CHAVE_FRED",
    "CHAVE_TWELVE_DATA",
    "CHAVE_EODHD",
    "CHAVE_NEWSAPI"
)

$preserved = @()
if (Test-Path $secretsPath) {
    $preserved = Get-Content -LiteralPath $secretsPath | Where-Object {
        $line = $_
        -not ($managedNames | Where-Object { $line.TrimStart().StartsWith($_ + " =") })
    }
}

function Escape-TomlValue {
    param([string]$Value)
    if ($null -eq $Value) { return "" }
    return $Value.Replace("\", "\\").Replace('"', '\"')
}

$output = @($preserved)
if ($output.Count -gt 0 -and $output[-1].Trim() -ne "") {
    $output += ""
}

$values = [ordered]@{
    "CHAVE_FRED" = $fred
    "CHAVE_TWELVE_DATA" = $twelve
    "CHAVE_EODHD" = $eodhd
    "CHAVE_NEWSAPI" = $newsapi
}

foreach ($name in $values.Keys) {
    $value = [string]$values[$name]
    if (-not [string]::IsNullOrWhiteSpace($value)) {
        $escaped = Escape-TomlValue -Value $value
        $output += ($name + ' = "' + $escaped + '"')
    }
}

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllLines($secretsPath, [string[]]$output, $utf8NoBom)

Write-Host ""
Write-Host "[OK] Configuracao local das APIs salva."
Write-Host ""
Write-Host ("FRED: " + $(if ([string]::IsNullOrWhiteSpace($fred)) { "NAO CONFIGURADA" } else { "OK" }))
Write-Host ("Twelve Data: " + $(if ([string]::IsNullOrWhiteSpace($twelve)) { "NAO CONFIGURADA" } else { "OK" }))
Write-Host ("EODHD: " + $(if ([string]::IsNullOrWhiteSpace($eodhd)) { "NAO CONFIGURADA" } else { "OK" }))
Write-Host ("NewsAPI: " + $(if ([string]::IsNullOrWhiteSpace($newsapi)) { "NAO CONFIGURADA" } else { "OK" }))
Write-Host ""
Write-Host "Pare o AtlasQuant pela opcao 6 e inicie novamente pela opcao 2."
Write-Host ""
Read-Host "Pressione ENTER para voltar"
