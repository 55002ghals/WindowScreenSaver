@echo off
setlocal enabledelayedexpansion
:: =============================================================================
:: Build WinLayoutSaverSetup.exe end-to-end.
:: 1) Ensure Python deps (incl. PyInstaller) are installed.
:: 2) Run PyInstaller -> dist\WinLayoutSaver\
:: 3) Ensure Inno Setup (ISCC) is installed (winget) - install if missing.
:: 4) Run ISCC -> installer\Output\WinLayoutSaverSetup.exe
:: =============================================================================

cd /d "%~dp0"

echo.
echo === [1/4] Installing Python dependencies ===
pip install -r requirements.txt -r requirements-dev.txt
if errorlevel 1 (
    echo ERROR: pip install failed.
    pause
    exit /b 1
)

echo.
echo === [2/4] Building exes with PyInstaller ===
if exist build rmdir /s /q build
if exist dist\WinLayoutSaver rmdir /s /q dist\WinLayoutSaver
python -m PyInstaller WinLayoutSaver.spec --noconfirm
if errorlevel 1 (
    echo ERROR: PyInstaller build failed.
    pause
    exit /b 1
)
if not exist dist\WinLayoutSaver\WinLayoutSaver.exe (
    echo ERROR: dist\WinLayoutSaver\WinLayoutSaver.exe missing after build.
    pause
    exit /b 1
)

echo.
echo === [3/4] Locating Inno Setup (ISCC) ===
set "ISCC="
for %%P in (
    "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
    "%ProgramFiles%\Inno Setup 6\ISCC.exe"
    "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
    "%ProgramFiles(x86)%\Inno Setup 5\ISCC.exe"
) do (
    if exist %%P set "ISCC=%%~P"
)
if not defined ISCC (
    where ISCC >nul 2>&1 && for /f "delims=" %%I in ('where ISCC') do set "ISCC=%%I"
)
if not defined ISCC (
    echo ISCC.exe not found. Installing Inno Setup via winget...
    winget install --id JRSoftware.InnoSetup --accept-source-agreements --accept-package-agreements --silent
    if errorlevel 1 (
        echo ERROR: winget install failed. Install Inno Setup manually:
        echo   https://jrsoftware.org/isdl.php
        pause
        exit /b 1
    )
    for %%P in (
        "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
        "%ProgramFiles%\Inno Setup 6\ISCC.exe"
        "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
    ) do (
        if exist %%P set "ISCC=%%~P"
    )
    if not defined ISCC (
        echo ERROR: ISCC.exe still not found after winget install.
        pause
        exit /b 1
    )
)
echo Using ISCC: !ISCC!

echo.
echo === [4/4] Reading version + compiling installer ===
for /f "delims=" %%V in ('python -c "from src.version import __version__; print(__version__)"') do set "APP_VER=%%V"
echo App version: !APP_VER!

"!ISCC!" /DMyAppVersion=!APP_VER! installer\WinLayoutSaver.iss
if errorlevel 1 (
    echo ERROR: ISCC compile failed.
    pause
    exit /b 1
)

echo.
echo =====================================================================
echo  BUILD COMPLETE
echo  Installer: installer\Output\WinLayoutSaverSetup.exe
echo =====================================================================
pause
endlocal
