@echo off
setlocal

:: 1. py.exe (Python Launcher for Windows) check and install
where py >nul 2>&1
if %errorlevel% neq 0 (
    echo py.exe not found. Installing Python Launcher via winget...
    winget install --id Python.Launcher --accept-source-agreements --accept-package-agreements --silent
    if %errorlevel% neq 0 (
        echo ERROR: winget failed. Install Python Launcher manually:
        echo   https://www.python.org/downloads/  ^(bundled with official Python installer^)
        echo   or: winget install Python.Launcher
        pause
        exit /b 1
    )
    for /f "tokens=*" %%i in ('where py 2^>nul') do set PY_PATH=%%i
    if not defined PY_PATH (
        echo Python Launcher installed. Please reopen this terminal and run install.bat again.
        pause
        exit /b 0
    )
)

:: 2. pip install
echo Installing Python dependencies...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ERROR: pip install failed.
    pause
    exit /b 1
)

echo.
echo Setup complete.
pause
endlocal
