@echo off
cd /d "%~dp0"
title AtlasQuant - Windows Privado
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0AtlasQuant_Windows_Privado.ps1"
if errorlevel 1 (
  echo.
  echo [FALHA] O launcher do AtlasQuant terminou com erro.
  echo A mensagem acima mostra a causa.
  echo.
  pause
)
