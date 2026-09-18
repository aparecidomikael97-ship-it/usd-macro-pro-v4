@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title AtlasQuant - Windows Privado

if not exist "usd_macro_pro_v4_cloud.py" (
  echo.
  echo [ERRO] Este arquivo precisa ficar na pasta principal do AtlasQuant.
  echo Arquivo esperado: usd_macro_pro_v4_cloud.py
  echo.
  pause
  exit /b 1
)

:menu
cls
echo ============================================================
echo               ATLASQUANT - WINDOWS PRIVADO
echo ============================================================
echo.
echo  [1] Preparar ou atualizar o ambiente
echo  [2] Iniciar o AtlasQuant
echo  [3] Verificar a instalacao
echo  [4] Sair
echo.
set /p AQ_OPCAO=Escolha uma opcao: 

if "%AQ_OPCAO%"=="1" goto instalar
if "%AQ_OPCAO%"=="2" goto iniciar
if "%AQ_OPCAO%"=="3" goto verificar
if "%AQ_OPCAO%"=="4" goto fim

echo.
echo Opcao invalida.
timeout /t 2 >nul
goto menu

:python_base
where py >nul 2>&1
if %errorlevel%==0 (
  set "AQ_PY=py -3"
  exit /b 0
)
where python >nul 2>&1
if %errorlevel%==0 (
  set "AQ_PY=python"
  exit /b 0
)
echo.
echo [ERRO] Python 3 nao foi encontrado no Windows.
echo Instale o Python 3 e marque a opcao "Add Python to PATH".
echo.
pause
exit /b 1

:instalar
cls
echo ============================================================
echo       PREPARANDO AMBIENTE PRIVADO DO ATLASQUANT
echo ============================================================
echo.
call :python_base
if errorlevel 1 goto menu

if not exist ".venv\Scripts\python.exe" (
  echo Criando ambiente virtual local...
  %AQ_PY% -m venv .venv
  if errorlevel 1 goto falha
) else (
  echo Ambiente virtual ja existe.
)

echo.
echo Atualizando pip...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto falha

echo.
echo Instalando dependencias do AtlasQuant...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto falha

echo.
echo [OK] Ambiente preparado com sucesso.
echo Nada foi publicado na internet. O uso continua privado neste computador.
echo.
pause
goto menu

:iniciar
cls
if not exist ".venv\Scripts\python.exe" (
  echo.
  echo [AVISO] O ambiente ainda nao foi preparado.
  echo Execute primeiro a opcao 1.
  echo.
  pause
  goto menu
)

echo ============================================================
echo               INICIANDO O ATLASQUANT
echo ============================================================
echo.
echo Endereco local: http://127.0.0.1:8501
echo Para encerrar, feche esta janela ou pressione CTRL+C.
echo.
".venv\Scripts\python.exe" -m streamlit run "usd_macro_pro_v4_cloud.py" --server.address 127.0.0.1 --server.port 8501 --server.headless false --browser.gatherUsageStats false
goto menu

:verificar
cls
echo ============================================================
echo             VERIFICACAO RAPIDA DO ATLASQUANT
echo ============================================================
echo.
if not exist ".venv\Scripts\python.exe" (
  echo [FALHA] Ambiente virtual nao encontrado.
  echo Execute primeiro a opcao 1.
  echo.
  pause
  goto menu
)

echo Verificando dependencias principais...
".venv\Scripts\python.exe" -c "import streamlit,pandas,numpy,requests,pyarrow; print('Dependencias principais: OK')"
if errorlevel 1 goto falha

echo Verificando sintaxe do aplicativo principal...
".venv\Scripts\python.exe" -m py_compile "usd_macro_pro_v4_cloud.py"
if errorlevel 1 goto falha

echo.
echo [OK] Verificacao basica concluida.
echo Modo privado/local preservado. Nenhuma ordem real e enviada por este launcher.
echo.
pause
goto menu

:falha
echo.
echo [FALHA] A etapa nao foi concluida.
echo Leia a mensagem acima antes de tentar novamente.
echo.
pause
goto menu

:fim
endlocal
exit /b 0
