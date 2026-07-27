@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
    echo Python Launcher не найден. Установите Python 3.11 или новее.
    pause
    exit /b 1
)

if not exist ".venv-build\Scripts\python.exe" (
    py -3 -m venv .venv-build
    if errorlevel 1 goto :error
)

".venv-build\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements-build.txt
if errorlevel 1 goto :error

".venv-build\Scripts\python.exe" -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --onefile ^
    --windowed ^
    --name AYGeography ^
    --collect-all pygame_gui ^
    --add-data "assets;assets" ^
    --add-data "configs;configs" ^
    main.py
if errorlevel 1 goto :error

echo.
echo Готово: dist\AYGeography.exe
exit /b 0

:error
echo.
echo Не удалось собрать AYGeography.exe
pause
exit /b 1
