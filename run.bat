@echo off
setlocal
cd /d "%~dp0"

if not exist ".droxz\Scripts\python.exe" (
    echo Criando o ambiente virtual...
    python -m venv .droxz
    if errorlevel 1 goto :error
    ".droxz\Scripts\python.exe" -m pip install --upgrade pip
    ".droxz\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 goto :error
)

".droxz\Scripts\python.exe" -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)"
if errorlevel 1 (
    echo.
    echo O Python do ambiente virtual e anterior ao 3.11.
    echo Apague a pasta .droxz e instale o Python 3.11 ou superior.
    pause
    exit /b 1
)

".droxz\Scripts\python.exe" -c "import cv2, numpy, mss, pydirectinput, win32gui" >nul 2>nul
if errorlevel 1 (
    echo Instalando dependencias...
    ".droxz\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 goto :error
)

start "" ".droxz\Scripts\pythonw.exe" main.py
exit /b 0

:error
echo.
echo Falha ao preparar o ambiente.
echo Instale o Python 3.11 ou superior em https://www.python.org/downloads/
echo e marque a opcao "Add python.exe to PATH".
pause
exit /b 1
