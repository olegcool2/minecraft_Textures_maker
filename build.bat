@echo off
title MCTextureReplacer - EXE Builder
color 0B
echo ============================================================
echo   Minecraft Texture Replacer -- EXE Builder
echo ============================================================
echo.

REM Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found!
    echo Download from: https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during install.
    pause
    exit /b 1
)
echo [OK] Python found.

REM Install dependencies
echo.
echo Installing dependencies...
python -m pip install --quiet --upgrade pip
python -m pip install --quiet pillow requests beautifulsoup4 pyinstaller
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install packages.
    pause
    exit /b 1
)
echo [OK] Packages installed.

REM Clean old build
echo.
echo Cleaning old build files...
if exist build   rmdir /s /q build
if exist dist    rmdir /s /q dist
if exist MCTextureReplacer.spec del /q MCTextureReplacer.spec

REM Build EXE
echo.
echo Building EXE (this may take 1-3 minutes)...
echo.
python -m PyInstaller ^
    --onefile ^
    --windowed ^
    --name "MCTextureReplacer" ^
    --collect-all "PIL" ^
    --collect-all "bs4" ^
    --collect-all "requests" ^
    --collect-all "charset_normalizer" ^
    --collect-all "certifi" ^
    --hidden-import "PIL._tkinter_finder" ^
    --hidden-import "tkinter" ^
    --hidden-import "tkinter.ttk" ^
    --hidden-import "tkinter.filedialog" ^
    --hidden-import "tkinter.messagebox" ^
    app.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Build failed! Check the output above.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   SUCCESS!
echo   Your EXE is ready at:
echo   dist\MCTextureReplacer.exe
echo.
echo   Share that single file - no Python needed!
echo ============================================================
echo.
explorer dist
pause