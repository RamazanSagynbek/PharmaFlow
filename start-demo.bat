@echo off
REM PharmaFlow presentation mode
cd /d "%~dp0"
python start.py --demo %*
if errorlevel 1 pause
