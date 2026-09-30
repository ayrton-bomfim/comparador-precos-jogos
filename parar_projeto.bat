@echo off
setlocal EnableExtensions
title Comparador - Encerramento
cd /d "%~dp0"

echo ==================================================
echo   COMPARADOR DE PRECOS - ENCERRAMENTO
echo ==================================================
echo.

echo [1/3] Parando Backend - porta 8000...
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do (
    taskkill /PID %%P /T /F >nul 2>&1
)
echo [OK] Backend encerrado.
echo.

echo [2/3] Parando Frontend - porta 5173...
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":5173" ^| findstr "LISTENING"') do (
    taskkill /PID %%P /T /F >nul 2>&1
)
echo [OK] Frontend encerrado.
echo.

echo [3/3] Fechando abas dos terminais...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws=New-Object -ComObject WScript.Shell; if($ws.AppActivate('Comparador - Backend FastAPI')){$ws.SendKeys('exit{ENTER}');Start-Sleep -Milliseconds 300}; if($ws.AppActivate('Comparador - Backend FastAI')){$ws.SendKeys('exit{ENTER}');Start-Sleep -Milliseconds 300}; if($ws.AppActivate('Comparador - Frontend Vite')){$ws.SendKeys('exit{ENTER}');Start-Sleep -Milliseconds 300}"
echo [OK] Terminais tratados.
echo.

echo O navegador nao sera alterado.
echo Feche a guia do Comparador manualmente.
echo.

timeout /t 2 /nobreak >nul
endlocal
exit /b 0
