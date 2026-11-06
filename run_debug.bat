@echo off
cd /d "%~dp0"
if not exist ".droxz\Scripts\python.exe" (
    echo Execute run.bat primeiro para criar o ambiente virtual.
    pause
    exit /b 1
)
".droxz\Scripts\python.exe" main.py
pause
