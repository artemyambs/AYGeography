@echo off
setlocal
cd /d "%~dp0"

set "BUILD_PYTHON=.venv-build\Scripts\python.exe"

where py >nul 2>nul
if errorlevel 1 (
    echo Python Launcher was not found. Install Python 3.11 or newer to build.
    echo Python is not required on the player's computer.
    pause
    exit /b 1
)

if not exist "%BUILD_PYTHON%" (
    py -3 -m venv .venv-build
    if errorlevel 1 goto :error
)

"%BUILD_PYTHON%" -c "import PyInstaller, pygame, pygame_gui" >nul 2>nul
if errorlevel 1 (
    "%BUILD_PYTHON%" -m pip install --disable-pip-version-check -r requirements-build.txt
    if errorlevel 1 goto :error
)

"%BUILD_PYTHON%" tools\build_app_icon.py
if errorlevel 1 goto :error

"%BUILD_PYTHON%" -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --distpath "dist" ^
    --workpath "build" ^
    AYGeography.spec
if errorlevel 1 goto :error

"%BUILD_PYTHON%" tools\package_portable.py
if errorlevel 1 goto :error

echo.
echo Portable build: dist\AYGeography-portable.zip
echo Extract it and run AYGeography\AYGeography.exe.
echo Python and internet access are not required on the player's computer.
exit /b 0

:error
echo.
echo Failed to build the AYGeography portable distribution.
pause
exit /b 1
