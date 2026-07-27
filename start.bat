@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start_atelier.ps1" -Environment production -Port 8110
exit /b %ERRORLEVEL%

