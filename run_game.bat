@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if not errorlevel 1 (
    py -3 bootstrap.py
    if errorlevel 1 pause
    exit /b
)

where python >nul 2>nul
if not errorlevel 1 (
    python bootstrap.py
    if errorlevel 1 pause
    exit /b
)

echo Python не найден.
echo Установите Python 3.11 или новее с сайта python.org и повторно запустите этот файл.
pause
