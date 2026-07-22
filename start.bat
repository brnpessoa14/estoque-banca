@echo off
setlocal
title Banca Facil

where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Python 3 nao foi encontrado.
    echo Instale pelo site https://www.python.org/downloads/ e marque "Add Python to PATH".
    pause
    exit /b 1
)

echo Iniciando Banca Facil em http://127.0.0.1:8000
python start.py
if %ERRORLEVEL% NEQ 0 pause
endlocal
