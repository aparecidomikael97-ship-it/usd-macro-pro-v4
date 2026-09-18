$ErrorActionPreference = "Stop"

$configDir = Join-Path $env:LOCALAPPDATA "AtlasQuant"
$secretsPath = Join-Path $configDir "secrets.toml"

Write-Host ""
Write-Host "============================================================"
Write-Host "          ATLASQUANT - CONFIGURAR FRED LOCAL"
Write-Host "============================================================"
Write-Host ""
Write-Host "A FRED exige uma chave gratuita para a API oficial."
Write-Host "Crie ou consulte sua chave em:"
Write-Host "https://fredaccount.stlouisfed.org/apikeys"
Write-Host ""
Write-Host "A chave ficara salva SOMENTE neste computador em:"
Write-Host $secretsPath
Write-Host ""

$secure = Read-Host "Cole sua CHAVE_FRED (32 caracteres)" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)

try {
    $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    if ([string]::IsNullOrWhiteSpace($plain)) {
        throw "A chave foi deixada em branco."
    }

    $plain = $plain.Trim()
    if ($plain -notmatch '^[a-z0-9]{32}$') {
        throw "CHAVE_FRED invalida. A FRED usa uma chave de 32 caracteres minusculos (letras e numeros)."
    }

    New-Item -ItemType Directory -Force -Path $configDir | Out-Null

    $existing = @()
    if (Test-Path $secretsPath) {
        $existing = Get-Content $secretsPath | Where-Object {
            $_ -notmatch '^\s*CHAVE_FRED\s*='
        }
    }

    $escaped = $plain.Replace("\", "\\").Replace('"', '\"')
    $line = 'CHAVE_FRED = "' + $escaped + '"'

    $output = @($existing)
    if ($output.Count -gt 0 -and $output[-1].Trim() -ne "") {
        $output += ""
    }
    $output += $line

    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllLines($secretsPath, [string[]]$output, $utf8NoBom)

    Write-Host ""
    Write-Host "[OK] CHAVE_FRED configurada localmente."
    Write-Host "A chave nao foi exibida nem enviada ao GitHub."
    Write-Host "Pare o AtlasQuant pela opcao 6 e depois inicie novamente pela opcao 2."
}
finally {
    if ($bstr -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
    $plain = $null
}

Write-Host ""
Read-Host "Pressione ENTER para voltar"
