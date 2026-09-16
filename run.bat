@echo off
title Minecraft Texture Replacer
echo Starting...
python app.py
if %errorlevel% neq 0 (
    echo.
    echo ERROR: Python not installed or not in PATH.
    echo Download Python: https://www.python.org/downloads/
    echo Check ADD PYTHON TO PATH during install!
    pause
)