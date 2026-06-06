@echo off
schtasks /Create /SC DAILY /TN "mystock-daily-research" /TR "powershell.exe -ExecutionPolicy Bypass -File \"c:\Users\Shan Lei\Desktop\test\mystock\scripts\run_daily.ps1\"" /ST 08:00 /F
echo.
echo Done.
pause
