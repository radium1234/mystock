$taskName = "mystock-daily-research"
$projectDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$cmdPath = Join-Path $PSScriptRoot "run_daily.cmd"

$action = New-ScheduledTaskAction `
    -Execute "cmd.exe" `
    -Argument "/c `"$cmdPath`"" `
    -WorkingDirectory $projectDir

$trigger1 = New-ScheduledTaskTrigger -Daily -At "09:00"
$trigger2 = New-ScheduledTaskTrigger -Daily -At "21:00"
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger @($trigger1, $trigger2) -Settings $settings -Force

Write-Host "Task created: $taskName"
Write-Host "Schedule    : daily 09:00 and 21:00"
Write-Host "Command     : $cmdPath"
