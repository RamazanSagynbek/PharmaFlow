@echo off
REM PharmaFlow: start the warehouse server and open the HMI window
cd /d "%~dp0"
python start.py %*
if errorlevel 1 pause
