@echo off
setlocal

set "PROJECT_DIR=%~dp0.."
pushd "%PROJECT_DIR%" >nul

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_daily.ps1" %*
set "EXIT_CODE=%ERRORLEVEL%"

popd >nul
exit /b %EXIT_CODE%
