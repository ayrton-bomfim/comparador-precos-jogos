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

echo [1/6] Procurando Python...
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

echo [2/6] Verificando npm e frontend...
where npm >nul 2>&1
if errorlevel 1 (
    echo [ERRO] npm nao encontrado.
    pause
    exit /b 1
)

if not exist "%~dp0frontend\node_modules\.bin\vite.cmd" (
    echo [INFO] Dependencias do frontend nao encontradas. Executando npm install...
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

echo [3/6] Verificando portas 8000 (API) e 5173 (Vite)...
echo Se algum programa estiver usando essas portas, sera mostrado antes de encerrar.
echo Digite SIM somente se os processos exibidos forem instancias antigas deste projeto.
echo.
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ports = @(8000,5173); $listeners = @(foreach($port in $ports){ Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | ForEach-Object { [PSCustomObject]@{Port=$port; ProcessId=$_.OwningProcess} } }); if($listeners.Count -gt 0){ foreach($item in $listeners){ $proc = Get-CimInstance Win32_Process -Filter ('ProcessId = ' + $item.ProcessId) -ErrorAction SilentlyContinue; Write-Host ('Porta ' + $item.Port + ' | PID ' + $item.ProcessId + ' | ' + $proc.Name); if($proc.CommandLine){ Write-Host ('  Comando: ' + $proc.CommandLine) } }; $answer = Read-Host 'Digite SIM para encerrar os processos listados e continuar'; if($answer -cne 'SIM'){ Write-Host 'Inicializacao cancelada. Nenhum processo foi encerrado.'; exit 2 }; $ids = @($listeners.ProcessId | Sort-Object -Unique); foreach($processId in $ids){ try { Stop-Process -Id $processId -Force -ErrorAction Stop; Write-Host ('Processo ' + $processId + ' encerrado.') } catch { Write-Host ('Nao foi possivel encerrar o processo ' + $processId + ': ' + $_.Exception.Message); exit 3 } }; Start-Sleep -Seconds 2; $remaining = @(foreach($port in $ports){ Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue }); if($remaining.Count -gt 0){ Write-Host 'Ainda existe processo escutando nas portas necessarias.'; exit 4 } }; exit 0"
if errorlevel 1 (
    echo.
    echo [AVISO] A inicializacao foi cancelada ou nao foi possivel liberar as portas.
    echo Confira os processos exibidos acima. Nenhuma nova instancia foi iniciada.
    pause
    exit /b 1
)
echo.

echo [4/6] Iniciando backend FastAPI sem recarga automatica...
start "Comparador - Backend FastAPI" /D "%~dp0" cmd /k ""!PYTHON_CMD!" -m uvicorn backend.app:app --host 127.0.0.1 --port 8000"

echo Aguardando API responder em /health...
set /a TENTATIVAS=0
:aguardar_backend
set /a TENTATIVAS+=1
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $r=Invoke-WebRequest -Uri 'http://127.0.0.1:8000/health' -UseBasicParsing -TimeoutSec 2; if($r.StatusCode -eq 200){exit 0}else{exit 1} } catch { exit 1 }" >nul 2>&1
if not errorlevel 1 goto backend_pronto
if !TENTATIVAS! GEQ 45 (
    echo [ERRO] A API nao respondeu em 45 segundos.
    echo Veja a janela 'Comparador - Backend FastAPI' e procure o traceback.
    echo O frontend nao sera iniciado para evitar paginas sem dados.
    pause
    exit /b 1
)
timeout /t 1 /nobreak >nul
goto aguardar_backend

:backend_pronto
echo [OK] API respondeu.
echo.

echo [5/6] Iniciando frontend Vite na porta fixa 5173...
start "Comparador - Frontend Vite" /D "%~dp0frontend" cmd /k "npm run dev -- --host 127.0.0.1 --port 5173 --strictPort"

echo Aguardando frontend responder...
set /a TENTATIVAS=0
:aguardar_frontend
set /a TENTATIVAS+=1
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $r=Invoke-WebRequest -Uri 'http://127.0.0.1:5173/' -UseBasicParsing -TimeoutSec 2; if($r.StatusCode -eq 200){exit 0}else{exit 1} } catch { exit 1 }" >nul 2>&1
if not errorlevel 1 goto frontend_pronto
if !TENTATIVAS! GEQ 45 (
    echo [ERRO] Frontend nao respondeu em 45 segundos.
    echo Veja a janela 'Comparador - Frontend Vite' para identificar o erro.
    pause
    exit /b 1
)
timeout /t 1 /nobreak >nul
goto aguardar_frontend

:frontend_pronto
echo [OK] Frontend respondeu.
echo.

echo [6/6] Abrindo o Comparador...
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
        echo [AVISO] Firefox nao encontrado. Abra http://localhost:5173/ manualmente.
    )
)

echo.
echo ==================================================
echo   PROJETO INICIADO
echo   Backend: http://127.0.0.1:8000
echo   Health : http://127.0.0.1:8000/health
echo   Frontend: http://localhost:5173/
echo ==================================================
echo Mantenha as janelas do backend e frontend abertas.
echo O backend foi iniciado sem --reload para evitar reinicios por arquivos do projeto/coleta.
echo Esta janela sera fechada em 5 segundos.
timeout /t 5 /nobreak >nul
endlocal
exit /b 0
