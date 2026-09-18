$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$streamlitDir = Join-Path $root ".streamlit"
$secretsPath = Join-Path $streamlitDir "secrets.toml"

Write-Host ""
Write-Host "============================================================"
Write-Host "       ATLASQUANT - CONFIGURAR TWELVE DATA LOCAL"
Write-Host "============================================================"
Write-Host ""
Write-Host "A chave ficara salva SOMENTE neste computador em:"
Write-Host $secretsPath
Write-Host ""

$secure = Read-Host "Cole sua CHAVE_TWELVE_DATA" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)

try {
    $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    if ([string]::IsNullOrWhiteSpace($plain)) {
        throw "A chave foi deixada em branco."
    }

    New-Item -ItemType Directory -Force -Path $streamlitDir | Out-Null

    $existing = @()
    if (Test-Path $secretsPath) {
        $existing = Get-Content $secretsPath | Where-Object {
            $_ -notmatch '^\s*CHAVE_TWELVE_DATA\s*='
        }
    }

    $escaped = $plain.Replace("\", "\\").Replace('"', '\"')
    $line = 'CHAVE_TWELVE_DATA = "' + $escaped + '"'

    $output = @($existing)
    if ($output.Count -gt 0 -and $output[-1].Trim() -ne "") {
        $output += ""
    }
    $output += $line

    Set-Content -Path $secretsPath -Value $output -Encoding UTF8

    Write-Host ""
    Write-Host "[OK] CHAVE_TWELVE_DATA configurada localmente."
    Write-Host "Feche o AtlasQuant que estiver aberto e inicie novamente pelo launcher."
    Write-Host "Depois, no Painel Mestre, recarregue a leitura."
}
finally {
    if ($bstr -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
    $plain = $null
}

Write-Host ""
Read-Host "Pressione ENTER para voltar"
