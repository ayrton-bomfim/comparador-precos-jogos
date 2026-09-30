@echo off
setlocal EnableExtensions

REM ============================================================
REM COMPARADOR - EXECUÇÃO MANUAL DA COLETA COMPLETA
REM Este arquivo deve ficar na RAIZ do projeto.
REM ============================================================

REM Força o CMD e o Python a trabalharem em UTF-8.
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

cd /d "%~dp0"

set "LOG_DIR=%~dp0logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

for /f "tokens=1-3 delims=/ " %%a in ("%date%") do set "DATA_LOG=%%c-%%b-%%a"
set "HORA_LOG=%time:~0,2%-%time:~3,2%-%time:~6,2%"
set "HORA_LOG=%HORA_LOG: =0%"
set "LOG_FILE=%LOG_DIR%\coleta_%DATA_LOG%_%HORA_LOG%.log"

> "%LOG_FILE%" echo ============================================================
>> "%LOG_FILE%" echo COMPARADOR - COLETA MANUAL
>> "%LOG_FILE%" echo Início: %date% %time%
>> "%LOG_FILE%" echo Diretório: %CD%
>> "%LOG_FILE%" echo ============================================================

echo ============================================================
echo COMPARADOR - COLETA MANUAL
echo ============================================================
echo.
echo Diretório: %CD%
echo Log: %LOG_FILE%
echo.

echo Verificando o Python...
where python >nul 2>nul
if errorlevel 1 (
    echo ERRO: Python não encontrado no PATH.
    echo ERRO: Python não encontrado no PATH.>> "%LOG_FILE%"
    echo.
    pause
    exit /b 1
)

python --version
if errorlevel 1 (
    echo ERRO: não foi possível executar o Python.
    echo ERRO: não foi possível executar o Python.>> "%LOG_FILE%"
    echo.
    pause
    exit /b 1
)

echo.
echo Iniciando a coleta completa...
echo.

REM Exibe no terminal e grava o mesmo texto em UTF-8 no arquivo de log.
powershell -NoProfile -Command "& { [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false); & python -X utf8 -u -m backend.coletores.agendador --agora 2>&1 | ForEach-Object { [Console]::WriteLine($_); Add-Content -LiteralPath '%LOG_FILE%' -Value $_ -Encoding UTF8 }; exit $LASTEXITCODE }"
set "EXIT_CODE=%ERRORLEVEL%"

>> "%LOG_FILE%" echo.
>> "%LOG_FILE%" echo Código de saída: %EXIT_CODE%
>> "%LOG_FILE%" echo Fim: %date% %time%

echo.
echo ============================================================
if "%EXIT_CODE%"=="0" (
    echo COLETA FINALIZADA COM SUCESSO.
    echo Consulte também o log em:
    echo %LOG_FILE%
) else (
    echo COLETA FINALIZADA COM ERRO. Código: %EXIT_CODE%
    echo Consulte o log em:
    echo %LOG_FILE%
)
echo ============================================================
echo.
echo A janela permanecera aberta para voce conferir o resultado.
pause

exit /b %EXIT_CODE%
