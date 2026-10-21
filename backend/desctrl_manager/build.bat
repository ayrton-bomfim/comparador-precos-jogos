@echo off
setlocal
cd /d "%~dp0"
py -m pip install -r requirements-manager.txt
if errorlevel 1 (
    echo ERRO: falha ao instalar dependencias.
    pause
    exit /b 1
)
py -m PyInstaller --noconfirm --clean --windowed --name DESCTRL-Manager app.py
if errorlevel 1 (
    echo ERRO: compilacao falhou.
    pause
    exit /b 1
)
echo.
echo Executavel criado em dist\DESCTRL-Manager\DESCTRL-Manager.exe
pause
