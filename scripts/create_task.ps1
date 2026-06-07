$taskName = "mystock-daily-research"
$projectDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$cmdPath = Join-Path $PSScriptRoot "run_daily.cmd"

$action = New-ScheduledTaskAction `
    -Execute "cmd.exe" `
    -Argument "/c `"$cmdPath`"" `
    -WorkingDirectory $projectDir

$trigger = New-ScheduledTaskTrigger -Daily -At "08:00"
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Force

Write-Host "OK: $taskName -> $cmdPath"
