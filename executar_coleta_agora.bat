@echo off
setlocal EnableExtensions

REM ============================================================
REM DESCTRL - EXECUCAO MANUAL DA COLETA COMPLETA
REM Mesmo caminho usado pelo DESCTRL Manager e pela tarefa agendada:
REM abre o tunel SSH sozinho, impede duas coletas ao mesmo tempo e grava
REM o log em logs\coleta\coleta_AAAAMMDD_HHMMSS.log.
REM Para acompanhar com mais detalhes, use o DESCTRL Manager.
REM ============================================================

chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
cd /d "%~dp0"

set "PYTHON_CMD="
if exist "%~dp0venv\Scripts\python.exe" set "PYTHON_CMD=%~dp0venv\Scripts\python.exe"
if not defined PYTHON_CMD if exist "%~dp0.venv\Scripts\python.exe" set "PYTHON_CMD=%~dp0.venv\Scripts\python.exe"
if not defined PYTHON_CMD if exist "%~dp0backend\venv\Scripts\python.exe" set "PYTHON_CMD=%~dp0backend\venv\Scripts\python.exe"
if not defined PYTHON_CMD set "PYTHON_CMD=python"

echo ============================================================
echo DESCTRL - COLETA MANUAL (banco de producao)
echo Python: %PYTHON_CMD%
echo ============================================================
echo.

"%PYTHON_CMD%" -X utf8 -u -m backend.desctrl_manager.executor --origem manual %*
set "EXIT_CODE=%ERRORLEVEL%"

echo.
echo ============================================================
if "%EXIT_CODE%"=="0" (
    echo COLETA FINALIZADA COM SUCESSO.
) else if "%EXIT_CODE%"=="2" (
    echo JA EXISTE UMA COLETA EM ANDAMENTO. Nada foi iniciado.
) else (
    echo COLETA FINALIZADA COM ERRO. Codigo: %EXIT_CODE%
)
echo Logs: %~dp0logs\coleta
echo ============================================================
echo.
pause
exit /b %EXIT_CODE%
