@echo off
setlocal enabledelayedexpansion
:: =============================================================================
:: rebuild.bat -- Clean previous build artifacts then run build.bat from scratch.
:: Removes: build\, dist\, installer\Output\
:: Then invokes build.bat which handles deps + PyInstaller + Inno Setup.
:: =============================================================================

cd /d "%~dp0"

echo.
echo === [rebuild] Cleaning previous build artifacts ===

if exist "build" (
    echo  - removing build\
    rmdir /s /q "build"
    if errorlevel 1 (
        echo ERROR: failed to remove build\
        pause
        exit /b 1
    )
)

if exist "dist" (
    echo  - removing dist\
    rmdir /s /q "dist"
    if errorlevel 1 (
        echo ERROR: failed to remove dist\
        pause
        exit /b 1
    )
)

if exist "installer\Output" (
    echo  - removing installer\Output\
    rmdir /s /q "installer\Output"
    if errorlevel 1 (
        echo ERROR: failed to remove installer\Output\
        pause
        exit /b 1
    )
)

echo.
echo === [rebuild] Invoking build.bat ===
call build.bat
if errorlevel 1 (
    echo ERROR: build.bat failed.
    exit /b 1
)

echo.
echo =====================================================================
echo  REBUILD COMPLETE
echo =====================================================================
endlocal
