@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start_atelier.ps1" -Environment test -Port 8111
exit /b %ERRORLEVEL%

