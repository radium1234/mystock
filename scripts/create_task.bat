@echo off
set "SCRIPT_DIR=%~dp0"
schtasks /Create /SC DAILY /TN "mystock-daily-research" /TR "cmd.exe /c \"\"%SCRIPT_DIR%run_daily.cmd\"\"" /ST 08:00 /F
