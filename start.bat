@echo off
REM Script para iniciar o PDV Banca de Jornal no Windows
REM Verifica se Node.js está instalado

echo ====================================
echo   PDV Banca de Jornal
echo ====================================
echo.

where node >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [!] Node.js nao encontrado
    echo.
    echo Opcoes:
    echo 1. Instale Node.js de https://nodejs.org
    echo 2. Ou use Python: python -m http.server 8000
    echo.
    pause
    exit /b 1
)

echo [+] Node.js encontrado
echo.

REM Instala dependências se necessário
if not exist "node_modules\" (
    echo [*] Instalando dependências...
    call npm install
)

echo.
echo [*] Iniciando servidor em http://localhost:8000
echo [*] Pressione Ctrl+C para parar
echo.

call npm run serve
pause
