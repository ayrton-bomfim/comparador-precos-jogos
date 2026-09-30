@echo off
setlocal EnableExtensions EnableDelayedExpansion
title Comparador - Inicializacao
cd /d "%~dp0"

echo ==================================================
echo   COMPARADOR DE PRECOS - INICIALIZACAO
echo ==================================================
echo.

if not exist "%~dp0backend\" (
    echo [ERRO] Pasta backend nao encontrada.
    pause
    exit /b 1
)

if not exist "%~dp0frontend\package.json" (
    echo [ERRO] frontend\package.json nao encontrado.
    pause
    exit /b 1
)

echo [1/5] Procurando Python...

set "PYTHON_CMD="
if exist "%~dp0backend\.venv\Scripts\python.exe" set "PYTHON_CMD=%~dp0backend\.venv\Scripts\python.exe"
if not defined PYTHON_CMD if exist "%~dp0.venv\Scripts\python.exe" set "PYTHON_CMD=%~dp0.venv\Scripts\python.exe"
if not defined PYTHON_CMD if exist "%~dp0backend\venv\Scripts\python.exe" set "PYTHON_CMD=%~dp0backend\venv\Scripts\python.exe"
if not defined PYTHON_CMD if exist "%~dp0venv\Scripts\python.exe" set "PYTHON_CMD=%~dp0venv\Scripts\python.exe"

if not defined PYTHON_CMD (
    where python >nul 2>&1
    if errorlevel 1 (
        echo [ERRO] Python nao encontrado.
        pause
        exit /b 1
    )
    set "PYTHON_CMD=python"
)

echo [OK] Python encontrado.
echo.

echo [2/5] Verificando frontend...

where npm >nul 2>&1
if errorlevel 1 (
    echo [ERRO] npm nao encontrado.
    pause
    exit /b 1
)

if not exist "%~dp0frontend\node_modules\.bin\vite.cmd" (
    echo [INFO] Executando npm install...
    pushd "%~dp0frontend"
    call npm install
    if errorlevel 1 (
        popd
        echo [ERRO] npm install falhou.
        pause
        exit /b 1
    )
    popd
)

echo [OK] Frontend pronto.
echo.

echo [3/5] Iniciando backend...

start "Comparador - Backend FastAPI" /D "%~dp0" cmd /k ""!PYTHON_CMD!" -m uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload"
if errorlevel 1 (
    echo [ERRO] Falha ao iniciar backend.
    pause
    exit /b 1
)

echo [OK] Backend iniciado.
echo.

echo [4/5] Iniciando frontend...

start "Comparador - Frontend Vite" /D "%~dp0frontend" cmd /k "npm run dev -- --host 127.0.0.1 --port 5173"
if errorlevel 1 (
    echo [ERRO] Falha ao iniciar frontend.
    pause
    exit /b 1
)

echo [OK] Frontend iniciado.
echo.

echo [5/5] Aguardando o Vite...

set /a TENTATIVAS=0
:aguardar
set /a TENTATIVAS+=1

powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $r=Invoke-WebRequest -Uri 'http://127.0.0.1:5173/' -UseBasicParsing -TimeoutSec 2; if($r.StatusCode -ge 200 -and $r.StatusCode -lt 500){exit 0}else{exit 1} } catch { exit 1 }" >nul 2>&1

if not errorlevel 1 goto abrir_firefox

if !TENTATIVAS! GEQ 45 (
    echo [AVISO] Frontend nao respondeu em 45 segundos.
    goto fim
)

timeout /t 1 /nobreak >nul
goto aguardar

:abrir_firefox

echo [OK] Frontend disponivel.
echo.
echo Abrindo o Comparador no Firefox...

set "FIREFOX_EXE="
if exist "%ProgramFiles%\Mozilla Firefox\firefox.exe" set "FIREFOX_EXE=%ProgramFiles%\Mozilla Firefox\firefox.exe"
if not defined FIREFOX_EXE if exist "%ProgramFiles(x86)%\Mozilla Firefox\firefox.exe" set "FIREFOX_EXE=%ProgramFiles(x86)%\Mozilla Firefox\firefox.exe"
if not defined FIREFOX_EXE if exist "%LocalAppData%\Mozilla Firefox\firefox.exe" set "FIREFOX_EXE=%LocalAppData%\Mozilla Firefox\firefox.exe"

if defined FIREFOX_EXE (
    start "" "!FIREFOX_EXE!" "http://localhost:5173/"
) else (
    where firefox.exe >nul 2>&1
    if not errorlevel 1 (
        start "" firefox.exe "http://localhost:5173/"
    ) else (
        echo [AVISO] Firefox nao encontrado.
        echo        Abra manualmente: http://localhost:5173/
    )
)

:fim
echo.
echo ==================================================
echo   PROJETO INICIADO
echo ==================================================
echo.
echo Esta janela sera fechada automaticamente.
timeout /t 2 /nobreak >nul

endlocal
exit /b 0
