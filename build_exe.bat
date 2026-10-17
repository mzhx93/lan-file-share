@echo off
cd /d "%~dp0"
echo Installing PyInstaller...
python -m pip install -q pyinstaller
echo Building (output: dist\LanFileShare.exe)...
python -m PyInstaller --noconsole --onefile --name LanFileShare main.py
echo Done: dist\LanFileShare.exe
pause
