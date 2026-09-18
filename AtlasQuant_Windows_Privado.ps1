$ErrorActionPreference = "Stop"
Set-Location -LiteralPath (Split-Path -Parent $MyInvocation.MyCommand.Path)

function Pause-AtlasQuant {
    Write-Host ""
    [void](Read-Host "Pressione ENTER para continuar")
}

function Get-PythonLauncher {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        return @{ Exe = "py"; Args = @("-3") }
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        return @{ Exe = "python"; Args = @() }
    }
    throw "Python 3 nao foi encontrado. Instale o Python 3 e marque Add Python to PATH."
}


function Read-AtlasQuantLocalSecret {
    param([Parameter(Mandatory=$true)][string]$Name)

    $secretsPath = Join-Path (Get-Location).Path ".streamlit\secrets.toml"
    if (-not (Test-Path $secretsPath)) {
        return ""
    }

    try {
        $escapedName = [regex]::Escape($Name)
        $line = Get-Content -LiteralPath $secretsPath | Where-Object {
            $_ -match ("^\s*" + $escapedName + "\s*=")
        } | Select-Object -Last 1

        if ([string]::IsNullOrWhiteSpace($line)) {
            return ""
        }

        $pattern = '^\s*' + $escapedName + '\s*=\s*"([^"]*)"\s*$'
        if ($line -notmatch $pattern) {
            return ""
        }

        return $Matches[1]
    } catch {
        return ""
    }
}

function Import-AtlasQuantLocalSecrets {
    $state = @{
        TwelveData = $false
        Fred = $false
    }

    $twelve = Read-AtlasQuantLocalSecret -Name "CHAVE_TWELVE_DATA"
    if (-not [string]::IsNullOrWhiteSpace($twelve)) {
        $env:CHAVE_TWELVE_DATA = $twelve
        $state.TwelveData = $true
    }

    $fred = Read-AtlasQuantLocalSecret -Name "CHAVE_FRED"
    if (-not [string]::IsNullOrWhiteSpace($fred)) {
        $env:CHAVE_FRED = $fred
        $state.Fred = $true
    }

    return $state
}

function Prepare-AtlasQuant {
    Clear-Host
    Write-Host "============================================================"
    Write-Host "       PREPARANDO AMBIENTE PRIVADO DO ATLASQUANT"
    Write-Host "============================================================"
    Write-Host ""
    $launcher = Get-PythonLauncher
    if (-not (Test-Path ".venv\Scripts\python.exe")) {
        Write-Host "Criando ambiente virtual local..."
        & $launcher.Exe @($launcher.Args) -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw "Falha ao criar o ambiente virtual." }
    } else {
        Write-Host "Ambiente virtual ja existe."
    }
    Write-Host ""
    Write-Host "Atualizando pip..."
    & ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw "Falha ao atualizar o pip." }
    Write-Host ""
    Write-Host "Instalando dependencias do AtlasQuant..."
    & ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw "Falha ao instalar as dependencias." }
    Write-Host ""
    Write-Host "[OK] Ambiente preparado com sucesso."
    Write-Host "Nada foi publicado na internet. O uso continua privado neste computador."
    Pause-AtlasQuant
}

function Get-AtlasQuantProcess {
    $pidFile = ".atlasquant_streamlit.pid"
    if (-not (Test-Path $pidFile)) { return $null }
    try {
        $savedPid = [int](Get-Content $pidFile -ErrorAction Stop | Select-Object -First 1)
        $proc = Get-Process -Id $savedPid -ErrorAction SilentlyContinue
        if ($null -eq $proc) {
            Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
            return $null
        }
        return $proc
    } catch {
        Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
        return $null
    }
}

function Start-AtlasQuant {
    Clear-Host
    if (-not (Test-Path ".venv\Scripts\python.exe")) {
        Write-Host "[AVISO] O ambiente ainda nao foi preparado."
        Write-Host "Execute primeiro a opcao 1."
        Pause-AtlasQuant
        return
    }

    Write-Host "============================================================"
    Write-Host "               INICIANDO O ATLASQUANT"
    Write-Host "============================================================"
    Write-Host ""

    $existing = Get-AtlasQuantProcess
    if ($null -ne $existing) {
        Write-Host "[OK] AtlasQuant ja esta rodando em segundo plano."
        Write-Host "Abrindo http://127.0.0.1:8501"
        Start-Process "http://127.0.0.1:8501"
        Pause-AtlasQuant
        return
    }

    $secretState = Import-AtlasQuantLocalSecrets
    if ($secretState.TwelveData) {
        Write-Host "[OK] Twelve Data local carregado para esta sessao."
    } else {
        Write-Host "[AVISO] Chave Twelve Data local nao foi localizada ou nao pode ser lida."
    }
    if ($secretState.Fred) {
        Write-Host "[OK] FRED local carregado para esta sessao."
    } else {
        Write-Host "[AVISO] CHAVE_FRED nao configurada. A aba EUA pode ficar sem dados oficiais."
    }

    $python = (Resolve-Path ".\.venv\Scripts\python.exe").Path
    $args = @(
        "-m", "streamlit", "run", "usd_macro_pro_v4_cloud.py",
        "--server.address", "127.0.0.1",
        "--server.port", "8501",
        "--server.headless", "true",
        "--browser.gatherUsageStats", "false"
    )

    $proc = Start-Process -FilePath $python -ArgumentList $args -WorkingDirectory (Get-Location).Path -WindowStyle Hidden -PassThru
    Set-Content -Path ".atlasquant_streamlit.pid" -Value $proc.Id -Encoding ASCII

    Write-Host "Aguardando o servidor local iniciar..."
    $ready = $false
    for ($i = 0; $i -lt 20; $i++) {
        Start-Sleep -Milliseconds 750
        $proc.Refresh()
        if ($proc.HasExited) {
            Remove-Item ".atlasquant_streamlit.pid" -Force -ErrorAction SilentlyContinue
            throw "O servidor encerrou durante a inicializacao."
        }
        try {
            $resp = Invoke-WebRequest -Uri "http://127.0.0.1:8501" -UseBasicParsing -TimeoutSec 1
            if ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 500) {
                $ready = $true
                break
            }
        } catch {}
    }

    if (-not $ready) {
        Write-Host "[AVISO] O processo esta ativo, mas o navegador pode levar mais alguns segundos."
    } else {
        Write-Host "[OK] AtlasQuant iniciado em segundo plano."
    }

    Write-Host "Endereco local: http://127.0.0.1:8501"
    Start-Process "http://127.0.0.1:8501"
    Write-Host ""
    Write-Host "Voce pode fechar este launcher; o AtlasQuant continuara rodando."
    Write-Host "Use a opcao 6 para encerrar o servidor local quando quiser."
    Pause-AtlasQuant
}

function Stop-AtlasQuant {
    Clear-Host
    $proc = Get-AtlasQuantProcess
    if ($null -eq $proc) {
        Write-Host "[INFO] Nenhum servidor AtlasQuant iniciado por este launcher esta ativo."
        Pause-AtlasQuant
        return
    }
    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    Remove-Item ".atlasquant_streamlit.pid" -Force -ErrorAction SilentlyContinue
    Write-Host "[OK] Servidor local do AtlasQuant encerrado."
    Pause-AtlasQuant
}

function Test-AtlasQuant {
    Clear-Host
    Write-Host "============================================================"
    Write-Host "             VERIFICACAO RAPIDA DO ATLASQUANT"
    Write-Host "============================================================"
    Write-Host ""
    if (-not (Test-Path ".venv\Scripts\python.exe")) {
        Write-Host "[FALHA] Ambiente virtual nao encontrado."
        Write-Host "Execute primeiro a opcao 1."
        Pause-AtlasQuant
        return
    }
    Write-Host "Verificando dependencias principais..."
    & ".\.venv\Scripts\python.exe" -c "import streamlit,pandas,numpy,requests,pyarrow; print('Dependencias principais: OK')"
    if ($LASTEXITCODE -ne 0) { throw "Falha ao importar dependencias principais." }
    Write-Host "Verificando sintaxe do aplicativo principal..."
    & ".\.venv\Scripts\python.exe" -m py_compile "usd_macro_pro_v4_cloud.py"
    if ($LASTEXITCODE -ne 0) { throw "Falha de sintaxe no aplicativo principal." }
    Write-Host ""
    Write-Host "[OK] Verificacao basica concluida."
    Write-Host "Modo privado/local preservado. Nenhuma ordem real e enviada por este launcher."
    Pause-AtlasQuant
}

function Configure-TwelveData {
    Clear-Host
    if (-not (Test-Path "AtlasQuant_Configurar_TwelveData.ps1")) {
        Write-Host "[ERRO] Configurador do Twelve Data nao encontrado."
        Write-Host "Atualize o pacote do AtlasQuant."
        Pause-AtlasQuant
        return
    }
    & powershell -NoProfile -ExecutionPolicy Bypass -File ".\AtlasQuant_Configurar_TwelveData.ps1"
}

function Configure-Fred {
    Clear-Host
    if (-not (Test-Path "AtlasQuant_Configurar_FRED.ps1")) {
        Write-Host "[ERRO] Configurador da FRED nao encontrado."
        Write-Host "Atualize o pacote do AtlasQuant."
        Pause-AtlasQuant
        return
    }
    & powershell -NoProfile -ExecutionPolicy Bypass -File ".\AtlasQuant_Configurar_FRED.ps1"
}

if (-not (Test-Path "usd_macro_pro_v4_cloud.py")) {
    Write-Host "[ERRO] Este launcher precisa ficar na pasta principal do AtlasQuant."
    Write-Host "Arquivo esperado: usd_macro_pro_v4_cloud.py"
    Pause-AtlasQuant
    exit 1
}

while ($true) {
    Clear-Host
    Write-Host "============================================================"
    Write-Host "               ATLASQUANT - WINDOWS PRIVADO"
    Write-Host "============================================================"
    Write-Host ""
    Write-Host " [1] Preparar ou atualizar o ambiente"
    Write-Host " [2] Iniciar o AtlasQuant"
    Write-Host " [3] Verificar a instalacao"
    Write-Host " [4] Configurar Twelve Data local"
    Write-Host " [5] Sair"
    Write-Host " [6] Parar AtlasQuant local"
    Write-Host " [7] Configurar FRED local"
    Write-Host ""
    $choice = Read-Host "Escolha uma opcao"
    try {
        switch ($choice) {
            "1" { Prepare-AtlasQuant }
            "2" { Start-AtlasQuant }
            "3" { Test-AtlasQuant }
            "4" { Configure-TwelveData }
            "5" { exit 0 }
            "6" { Stop-AtlasQuant }
            "7" { Configure-Fred }
            default {
                Write-Host ""
                Write-Host "Opcao invalida."
                Start-Sleep -Seconds 2
            }
        }
    } catch {
        Write-Host ""
        Write-Host ("[FALHA] " + $_.Exception.Message)
        Write-Host "A janela permanecera aberta para voce poder ler o erro."
        Pause-AtlasQuant
    }
}
        if ($line -notmatch $pattern) {
            return ""
        }

        $value = $Matches[1]
        $value = $value.Replace('\"', '"').Replace('\\', '\')
        return $value
    } catch {
        return ""
    }
}

function Import-AtlasQuantLocalSecrets {
    $state = @{
        TwelveData = $false
        Fred = $false
    }

    $twelve = Read-AtlasQuantLocalSecret -Name "CHAVE_TWELVE_DATA"
    if (-not [string]::IsNullOrWhiteSpace($twelve)) {
        $env:CHAVE_TWELVE_DATA = $twelve
        $state.TwelveData = $true
    }

    $fred = Read-AtlasQuantLocalSecret -Name "CHAVE_FRED"
    if (-not [string]::IsNullOrWhiteSpace($fred)) {
        $env:CHAVE_FRED = $fred
        $state.Fred = $true
    }

    return $state
}

function Prepare-AtlasQuant {
    Clear-Host
    Write-Host "============================================================"
    Write-Host "       PREPARANDO AMBIENTE PRIVADO DO ATLASQUANT"
    Write-Host "============================================================"
    Write-Host ""
    $launcher = Get-PythonLauncher
    if (-not (Test-Path ".venv\Scripts\python.exe")) {
        Write-Host "Criando ambiente virtual local..."
        & $launcher.Exe @($launcher.Args) -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw "Falha ao criar o ambiente virtual." }
    } else {
        Write-Host "Ambiente virtual ja existe."
    }
    Write-Host ""
    Write-Host "Atualizando pip..."
    & ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw "Falha ao atualizar o pip." }
    Write-Host ""
    Write-Host "Instalando dependencias do AtlasQuant..."
    & ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw "Falha ao instalar as dependencias." }
    Write-Host ""
    Write-Host "[OK] Ambiente preparado com sucesso."
    Write-Host "Nada foi publicado na internet. O uso continua privado neste computador."
    Pause-AtlasQuant
}

function Get-AtlasQuantProcess {
    $pidFile = ".atlasquant_streamlit.pid"
    if (-not (Test-Path $pidFile)) { return $null }
    try {
        $savedPid = [int](Get-Content $pidFile -ErrorAction Stop | Select-Object -First 1)
        $proc = Get-Process -Id $savedPid -ErrorAction SilentlyContinue
        if ($null -eq $proc) {
            Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
            return $null
        }
        return $proc
    } catch {
        Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
        return $null
    }
}

function Start-AtlasQuant {
    Clear-Host
    if (-not (Test-Path ".venv\Scripts\python.exe")) {
        Write-Host "[AVISO] O ambiente ainda nao foi preparado."
        Write-Host "Execute primeiro a opcao 1."
        Pause-AtlasQuant
        return
    }

    Write-Host "============================================================"
    Write-Host "               INICIANDO O ATLASQUANT"
    Write-Host "============================================================"
    Write-Host ""

    $existing = Get-AtlasQuantProcess
    if ($null -ne $existing) {
        Write-Host "[OK] AtlasQuant ja esta rodando em segundo plano."
        Write-Host "Abrindo http://127.0.0.1:8501"
        Start-Process "http://127.0.0.1:8501"
        Pause-AtlasQuant
        return
    }

    $secretState = Import-AtlasQuantLocalSecrets
    if ($secretState.TwelveData) {
        Write-Host "[OK] Twelve Data local carregado para esta sessao."
    } else {
        Write-Host "[AVISO] Chave Twelve Data local nao foi localizada ou nao pode ser lida."
    }
    if ($secretState.Fred) {
        Write-Host "[OK] FRED local carregado para esta sessao."
    } else {
        Write-Host "[AVISO] CHAVE_FRED nao configurada. A aba EUA pode ficar sem dados oficiais."
    }

    $python = (Resolve-Path ".\.venv\Scripts\python.exe").Path
    $args = @(
        "-m", "streamlit", "run", "usd_macro_pro_v4_cloud.py",
        "--server.address", "127.0.0.1",
        "--server.port", "8501",
        "--server.headless", "true",
        "--browser.gatherUsageStats", "false"
    )

    $proc = Start-Process -FilePath $python -ArgumentList $args -WorkingDirectory (Get-Location).Path -WindowStyle Hidden -PassThru
    Set-Content -Path ".atlasquant_streamlit.pid" -Value $proc.Id -Encoding ASCII

    Write-Host "Aguardando o servidor local iniciar..."
    $ready = $false
    for ($i = 0; $i -lt 20; $i++) {
        Start-Sleep -Milliseconds 750
        $proc.Refresh()
        if ($proc.HasExited) {
            Remove-Item ".atlasquant_streamlit.pid" -Force -ErrorAction SilentlyContinue
            throw "O servidor encerrou durante a inicializacao."
        }
        try {
            $resp = Invoke-WebRequest -Uri "http://127.0.0.1:8501" -UseBasicParsing -TimeoutSec 1
            if ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 500) {
                $ready = $true
                break
            }
        } catch {}
    }

    if (-not $ready) {
        Write-Host "[AVISO] O processo esta ativo, mas o navegador pode levar mais alguns segundos."
    } else {
        Write-Host "[OK] AtlasQuant iniciado em segundo plano."
    }

    Write-Host "Endereco local: http://127.0.0.1:8501"
    Start-Process "http://127.0.0.1:8501"
    Write-Host ""
    Write-Host "Voce pode fechar este launcher; o AtlasQuant continuara rodando."
    Write-Host "Use a opcao 6 para encerrar o servidor local quando quiser."
    Pause-AtlasQuant
}

function Stop-AtlasQuant {
    Clear-Host
    $proc = Get-AtlasQuantProcess
    if ($null -eq $proc) {
        Write-Host "[INFO] Nenhum servidor AtlasQuant iniciado por este launcher esta ativo."
        Pause-AtlasQuant
        return
    }
    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    Remove-Item ".atlasquant_streamlit.pid" -Force -ErrorAction SilentlyContinue
    Write-Host "[OK] Servidor local do AtlasQuant encerrado."
    Pause-AtlasQuant
}

function Test-AtlasQuant {
    Clear-Host
    Write-Host "============================================================"
    Write-Host "             VERIFICACAO RAPIDA DO ATLASQUANT"
    Write-Host "============================================================"
    Write-Host ""
    if (-not (Test-Path ".venv\Scripts\python.exe")) {
        Write-Host "[FALHA] Ambiente virtual nao encontrado."
        Write-Host "Execute primeiro a opcao 1."
        Pause-AtlasQuant
        return
    }
    Write-Host "Verificando dependencias principais..."
    & ".\.venv\Scripts\python.exe" -c "import streamlit,pandas,numpy,requests,pyarrow; print('Dependencias principais: OK')"
    if ($LASTEXITCODE -ne 0) { throw "Falha ao importar dependencias principais." }
    Write-Host "Verificando sintaxe do aplicativo principal..."
    & ".\.venv\Scripts\python.exe" -m py_compile "usd_macro_pro_v4_cloud.py"
    if ($LASTEXITCODE -ne 0) { throw "Falha de sintaxe no aplicativo principal." }
    Write-Host ""
    Write-Host "[OK] Verificacao basica concluida."
    Write-Host "Modo privado/local preservado. Nenhuma ordem real e enviada por este launcher."
    Pause-AtlasQuant
}

function Configure-TwelveData {
    Clear-Host
    if (-not (Test-Path "AtlasQuant_Configurar_TwelveData.ps1")) {
        Write-Host "[ERRO] Configurador do Twelve Data nao encontrado."
        Write-Host "Atualize o pacote do AtlasQuant."
        Pause-AtlasQuant
        return
    }
    & powershell -NoProfile -ExecutionPolicy Bypass -File ".\AtlasQuant_Configurar_TwelveData.ps1"
}

function Configure-Fred {
    Clear-Host
    if (-not (Test-Path "AtlasQuant_Configurar_FRED.ps1")) {
        Write-Host "[ERRO] Configurador da FRED nao encontrado."
        Write-Host "Atualize o pacote do AtlasQuant."
        Pause-AtlasQuant
        return
    }
    & powershell -NoProfile -ExecutionPolicy Bypass -File ".\AtlasQuant_Configurar_FRED.ps1"
}

if (-not (Test-Path "usd_macro_pro_v4_cloud.py")) {
    Write-Host "[ERRO] Este launcher precisa ficar na pasta principal do AtlasQuant."
    Write-Host "Arquivo esperado: usd_macro_pro_v4_cloud.py"
    Pause-AtlasQuant
    exit 1
}

while ($true) {
    Clear-Host
    Write-Host "============================================================"
    Write-Host "               ATLASQUANT - WINDOWS PRIVADO"
    Write-Host "============================================================"
    Write-Host ""
    Write-Host " [1] Preparar ou atualizar o ambiente"
    Write-Host " [2] Iniciar o AtlasQuant"
    Write-Host " [3] Verificar a instalacao"
    Write-Host " [4] Configurar Twelve Data local"
    Write-Host " [5] Sair"
    Write-Host " [6] Parar AtlasQuant local"
    Write-Host " [7] Configurar FRED local"
    Write-Host ""
    $choice = Read-Host "Escolha uma opcao"
    try {
        switch ($choice) {
            "1" { Prepare-AtlasQuant }
            "2" { Start-AtlasQuant }
            "3" { Test-AtlasQuant }
            "4" { Configure-TwelveData }
            "5" { exit 0 }
            "6" { Stop-AtlasQuant }
            "7" { Configure-Fred }
            default {
                Write-Host ""
                Write-Host "Opcao invalida."
                Start-Sleep -Seconds 2
            }
        }
    } catch {
        Write-Host ""
        Write-Host ("[FALHA] " + $_.Exception.Message)
        Write-Host "A janela permanecera aberta para voce poder ler o erro."
        Pause-AtlasQuant
    }
}