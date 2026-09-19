@echo off
title Minecraft Texture & Sound Replacer
set "PY_CMD=python"

python --version >nul 2>&1
if %errorlevel% neq 0 (
    if exist "%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe" (
        set "PY_CMD=%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe"
    ) else if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
        set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    ) else if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
        set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    ) else (
        where py >nul 2>&1
        if %errorlevel% equ 0 (
            set "PY_CMD=py"
        )
    )
)

echo Starting Minecraft Texture & Sound Replacer...
%PY_CMD% app.py
if %errorlevel% neq 0 (
    echo.
    echo ERROR: Python not installed or not working.
    echo Download Python: https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during install!
    pause
)