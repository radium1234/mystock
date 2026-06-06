$t = Get-ScheduledTask -TaskName "mystock-daily-research"
$t.Triggers | ForEach-Object { Write-Host $_.StartBoundary }
