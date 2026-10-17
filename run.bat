@echo off
setlocal
cd /d "%~dp0"
title LAN File Share

where python >nul 2>nul
if not errorlevel 1 (
    set "PY=python"
) else (
    where py >nul 2>nul
    if not errorlevel 1 (
        set "PY=py -3"
    ) else (
        echo [ERROR] Python not found. Please install Python 3.8+ and check "Add python.exe to PATH".
        echo Download: https://www.python.org/downloads/
        pause
        exit /b 1
    )
)

echo [1/3] Checking dependencies...
%PY% -m pip install -q -r requirements.txt
if errorlevel 1 (
    echo Retry with Tsinghua mirror...
    %PY% -m pip install -q -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
)

echo [2/3] Starting server...
%PY% main.py

echo [3/3] Exited.
pause
endlocal
