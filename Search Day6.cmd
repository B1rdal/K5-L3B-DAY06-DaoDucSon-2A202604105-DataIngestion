@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0starter\scripts\search.ps1" %*
set "day6_exit=%errorlevel%"
if not defined DAY6_NO_PAUSE pause
exit /b %day6_exit%
