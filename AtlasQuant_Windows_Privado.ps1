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
    Write-Host "Endereco local: http://127.0.0.1:8501"
    Write-Host "Para encerrar, feche esta janela ou pressione CTRL+C."
    Write-Host ""
    & ".\.venv\Scripts\python.exe" -m streamlit run "usd_macro_pro_v4_cloud.py" --server.address 127.0.0.1 --server.port 8501 --server.headless false --browser.gatherUsageStats false
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
    Write-Host ""
    $choice = Read-Host "Escolha uma opcao"
    try {
        switch ($choice) {
            "1" { Prepare-AtlasQuant }
            "2" { Start-AtlasQuant }
            "3" { Test-AtlasQuant }
            "4" { Configure-TwelveData }
            "5" { exit 0 }
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