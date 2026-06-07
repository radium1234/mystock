# run_daily.ps1 - mystock daily research orchestrator
#
# One entry for manual runs and Windows Task Scheduler:
#   powershell.exe -NoProfile -ExecutionPolicy Bypass -File "scripts\run_daily.ps1"
#
# Design:
# - No Claude workflow.
# - No subagent/Task delegation inside Claude.
# - Each role is launched as a separate `claude --print` process.
# - Intermediate prompts/results are saved under output/runs/<run-id>/.

[CmdletBinding()]
param(
    [switch]$NoEmail,
    [switch]$NoTwitter,
    [switch]$Sequential,
    [ValidateRange(1, 8)]
    [int]$MaxParallel = 8,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()

$projectDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $projectDir

$userBin = Join-Path $env:USERPROFILE "bin"
if (Test-Path $userBin) {
    $env:PATH = "$userBin;$env:PATH"
}

$dateTag = Get-Date -Format "yyyy-MM-dd"
$dateDisplay = Get-Date -Format "yyyy-MM-dd HH:mm:ss zzz"
$runId = Get-Date -Format "yyyyMMdd-HHmmss"
$runDir = Join-Path $projectDir "output\runs\$runId"
$promptDir = Join-Path $runDir "prompts"
$layer1Dir = Join-Path $runDir "layer1"
$layer2Dir = Join-Path $runDir "layer2"
$finalDir = Join-Path $runDir "final"
$logDir = Join-Path $projectDir "output\logs"
$logFile = Join-Path $logDir "run-$runId.log"
$latestFile = Join-Path $projectDir "output\runs\latest-run.txt"
$reportPath = Join-Path $projectDir "output\$dateTag-深度研报.html"

foreach ($dir in @($promptDir, $layer1Dir, $layer2Dir, $finalDir, $logDir)) {
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
}

$utf8NoBom = [System.Text.UTF8Encoding]::new($false)

function Set-TextFile {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][AllowEmptyString()][string]$Text
    )
    $parent = Split-Path -Parent $Path
    if ($parent -and -not (Test-Path $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    [System.IO.File]::WriteAllText($Path, $Text, $script:utf8NoBom)
}

function Write-Log {
    param([Parameter(Mandatory = $true)][string]$Message)
    $line = "{0}  {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    $line | Tee-Object -FilePath $logFile -Append
}

function Get-ProjectRelativePath {
    param([Parameter(Mandatory = $true)][string]$Path)
    $full = [System.IO.Path]::GetFullPath($Path)
    if ($full.StartsWith($projectDir, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $full.Substring($projectDir.Length).TrimStart("\")
    }
    return $full
}

function Set-EnvironmentVariableValue {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][AllowEmptyString()][string]$Value
    )

    [System.Environment]::SetEnvironmentVariable($Name, $Value, "Process")
}

function Import-DotEnvFile {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path $Path)) {
        return 0
    }

    $count = 0
    foreach ($line in [System.IO.File]::ReadAllLines($Path, [System.Text.Encoding]::UTF8)) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) {
            continue
        }

        $match = [regex]::Match($trimmed, '^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$')
        if (-not $match.Success) {
            continue
        }

        $name = $match.Groups[1].Value
        $value = $match.Groups[2].Value.Trim()
        $commentIndex = $value.IndexOf(" #")
        if ($commentIndex -ge 0) {
            $value = $value.Substring(0, $commentIndex).TrimEnd()
        }
        if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
            $value = $value.Substring(1, $value.Length - 2)
        }

        Set-EnvironmentVariableValue -Name $name -Value $value
        $count++
    }

    return $count
}

function Import-VSCodeClaudeEnvironment {
    $settingsPaths = @(
        (Join-Path $env:APPDATA "Code\User\settings.json"),
        (Join-Path $env:APPDATA "Cursor\User\settings.json"),
        (Join-Path $env:APPDATA "Windsurf\User\settings.json")
    )

    $count = 0
    foreach ($settingsPath in $settingsPaths) {
        if (-not (Test-Path $settingsPath)) {
            continue
        }

        $text = [System.IO.File]::ReadAllText($settingsPath, [System.Text.Encoding]::UTF8)
        $matches = [regex]::Matches($text, '"name"\s*:\s*"([^"]+)"\s*,\s*"value"\s*:\s*"([^"]*)"', "Singleline")
        foreach ($match in $matches) {
            $name = $match.Groups[1].Value
            $value = $match.Groups[2].Value
            if ($name -notmatch '^(ANTHROPIC_|CLAUDE_CODE_|API_TIMEOUT_MS$)') {
                continue
            }

            if (-not [System.Environment]::GetEnvironmentVariable($name, "Process")) {
                Set-EnvironmentVariableValue -Name $name -Value $value
                $count++
            }
        }
    }

    return $count
}

function Initialize-ClaudeEnvironment {
    $vsCodeCount = Import-VSCodeClaudeEnvironment
    $dotEnvCount = Import-DotEnvFile -Path (Join-Path $projectDir ".env")

    if ($env:ANTHROPIC_BASE_URL -and $env:ANTHROPIC_AUTH_TOKEN -and $env:ANTHROPIC_API_KEY) {
        Remove-Item Env:ANTHROPIC_API_KEY -ErrorAction SilentlyContinue
        Write-Log "Claude env: removed ANTHROPIC_API_KEY because ANTHROPIC_BASE_URL + ANTHROPIC_AUTH_TOKEN are configured."
    }

    Write-Log "Claude env: loaded $vsCodeCount variable(s) from VS Code settings and $dotEnvCount variable(s) from .env."
    if ($env:ANTHROPIC_BASE_URL) {
        Write-Log "Claude env: ANTHROPIC_BASE_URL is configured."
    }
    if ($env:ANTHROPIC_MODEL) {
        Write-Log "Claude env: ANTHROPIC_MODEL=$env:ANTHROPIC_MODEL"
    }
}

function Resolve-ClaudeExecutable {
    $vscodeClaude = Get-ChildItem "$env:USERPROFILE\.vscode\extensions\anthropic.claude-code-*\resources\native-binary\claude.exe" -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending |
        Select-Object -First 1 -ExpandProperty FullName

    if ($vscodeClaude) {
        return $vscodeClaude
    }

    $claudeCmd = Get-Command claude -ErrorAction SilentlyContinue
    if ($claudeCmd) {
        return $claudeCmd.Source
    }

    throw "Cannot find Claude Code executable. Install Claude Code or add claude.exe to PATH."
}

function Test-ClaudePrintAuth {
    param([Parameter(Mandatory = $true)][string]$ClaudeExe)

    $probeOutput = & $ClaudeExe --print "Reply with exactly: OK" 2>&1
    $probeExit = if ($null -eq $LASTEXITCODE) { 0 } else { $LASTEXITCODE }
    $probeText = ($probeOutput | Out-String).Trim()

    if ($probeExit -ne 0 -or $probeText -notmatch "OK") {
        if ($env:ANTHROPIC_API_KEY) {
            $apiKeyLength = $env:ANTHROPIC_API_KEY.Length
            Remove-Item Env:ANTHROPIC_API_KEY -ErrorAction SilentlyContinue
            $retryOutput = & $ClaudeExe --print "Reply with exactly: OK" 2>&1
            $retryExit = if ($null -eq $LASTEXITCODE) { 0 } else { $LASTEXITCODE }
            $retryText = ($retryOutput | Out-String).Trim()

            if ($retryExit -eq 0 -and $retryText -match "OK") {
                Write-Log "Claude auth preflight passed after temporarily removing ANTHROPIC_API_KEY (length $apiKeyLength)."
                return
            }

            $probeText = @"
$probeText

Retry after temporarily removing ANTHROPIC_API_KEY:
$retryText
"@
        }

        $hint = @"
Claude Code --print authentication check failed.

Observed output:
$probeText

Fix options:
1. If using Claude subscription auth, run `claude auth login --claudeai` in an interactive terminal.
2. If using Anthropic Console API billing, replace the current ANTHROPIC_API_KEY with a key that is allowed to call Claude models.
3. If a stale ANTHROPIC_API_KEY is set globally, remove it before running this script so Claude Code can use OAuth/keychain auth.
"@
        throw $hint
    }
}

function New-ClaudeTask {
    param(
        [Parameter(Mandatory = $true)][string]$Id,
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Group,
        [Parameter(Mandatory = $true)][string]$OutputPath,
        [Parameter(Mandatory = $true)][string]$Prompt
    )

    [pscustomobject]@{
        Id = $Id
        Name = $Name
        Group = $Group
        OutputPath = $OutputPath
        PromptPath = Join-Path $promptDir "$Id.prompt.md"
        Prompt = $Prompt
    }
}

function Format-TaskFileList {
    param([Parameter(Mandatory = $true)][object[]]$Tasks)

    return (($Tasks | ForEach-Object {
        "- $($_.Name): $(Get-ProjectRelativePath $_.OutputPath)"
    }) -join "`n")
}

function Save-TaskPrompt {
    param([Parameter(Mandatory = $true)][pscustomobject]$Task)
    Set-TextFile -Path $Task.PromptPath -Text $Task.Prompt
}

function Invoke-ClaudeTaskDirect {
    param(
        [Parameter(Mandatory = $true)][pscustomobject]$Task,
        [Parameter(Mandatory = $true)][string]$ClaudeExe,
        [switch]$ContinueOnTaskFailure
    )

    Write-Log "START [$($Task.Group)] $($Task.Name)"
    try {
        $prompt = [System.IO.File]::ReadAllText($Task.PromptPath, [System.Text.Encoding]::UTF8)
        $started = Get-Date
        $rawOutput = & $ClaudeExe --print $prompt 2>&1
        $exitCode = if ($null -eq $LASTEXITCODE) { 0 } else { $LASTEXITCODE }
        $text = ($rawOutput | Out-String).TrimEnd()
        Set-TextFile -Path $Task.OutputPath -Text ($text + "`n")

        $duration = [int]((Get-Date) - $started).TotalSeconds
        if ($exitCode -ne 0) {
            if ($ContinueOnTaskFailure) {
                Write-Log "FAIL  [$($Task.Group)] $($Task.Name) (${duration}s, exit $exitCode, continued)"
                return
            }
            throw "Claude task failed: $($Task.Name), exit code $exitCode, output $(Get-ProjectRelativePath $Task.OutputPath)"
        }

        Write-Log "DONE  [$($Task.Group)] $($Task.Name) (${duration}s, $($text.Length) chars)"
    }
    catch {
        Set-TextFile -Path $Task.OutputPath -Text "TASK FAILED: $($Task.Name)`n`n$_`n"
        if ($ContinueOnTaskFailure) {
            Write-Log "FAIL  [$($Task.Group)] $($Task.Name) (continued): $_"
            return
        }
        throw
    }
}

function Start-ClaudeJob {
    param(
        [Parameter(Mandatory = $true)][pscustomobject]$Task,
        [Parameter(Mandatory = $true)][string]$ClaudeExe
    )

    Start-Job -Name $Task.Id -ArgumentList @(
        $ClaudeExe,
        $projectDir,
        $Task.PromptPath,
        $Task.OutputPath,
        $Task.Name,
        $Task.Group
    ) -ScriptBlock {
        param($ClaudeExe, $ProjectDir, $PromptPath, $OutputPath, $TaskName, $TaskGroup)

        $ErrorActionPreference = "Stop"
        [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
        Set-Location $ProjectDir

        $started = Get-Date
        try {
            $prompt = [System.IO.File]::ReadAllText($PromptPath, [System.Text.Encoding]::UTF8)
            $rawOutput = & $ClaudeExe --print $prompt 2>&1
            $exitCode = if ($null -eq $LASTEXITCODE) { 0 } else { $LASTEXITCODE }
            $text = ($rawOutput | Out-String).TrimEnd()
            [System.IO.File]::WriteAllText($OutputPath, $text + "`n", [System.Text.UTF8Encoding]::new($false))

            [pscustomobject]@{
                Name = $TaskName
                Group = $TaskGroup
                ExitCode = $exitCode
                OutputPath = $OutputPath
                Chars = $text.Length
                Seconds = [int]((Get-Date) - $started).TotalSeconds
            }
        }
        catch {
            $text = "TASK FAILED: $TaskName`n`n$_"
            [System.IO.File]::WriteAllText($OutputPath, $text + "`n", [System.Text.UTF8Encoding]::new($false))

            [pscustomobject]@{
                Name = $TaskName
                Group = $TaskGroup
                ExitCode = 1
                OutputPath = $OutputPath
                Chars = $text.Length
                Seconds = [int]((Get-Date) - $started).TotalSeconds
            }
        }
    }
}

function Invoke-ClaudeTaskGroup {
    param(
        [Parameter(Mandatory = $true)][string]$GroupName,
        [Parameter(Mandatory = $true)][object[]]$Tasks,
        [Parameter(Mandatory = $true)][string]$ClaudeExe,
        [Parameter(Mandatory = $true)][int]$Parallelism,
        [switch]$ContinueOnTaskFailure
    )

    Write-Log "=== ${GroupName}: $($Tasks.Count) task(s), max parallel $Parallelism ==="

    foreach ($task in $Tasks) {
        Save-TaskPrompt -Task $task
        if ($DryRun) {
            Set-TextFile -Path $task.OutputPath -Text "DRY RUN: $($task.Name)`nPrompt: $(Get-ProjectRelativePath $task.PromptPath)`n"
            Write-Log "DRY   [$($task.Group)] $($task.Name)"
        }
    }

    if ($DryRun) {
        return
    }

    if ($Sequential -or $Parallelism -le 1 -or $Tasks.Count -eq 1) {
        foreach ($task in $Tasks) {
            Invoke-ClaudeTaskDirect -Task $task -ClaudeExe $ClaudeExe -ContinueOnTaskFailure:$ContinueOnTaskFailure
        }
        return
    }

    $queue = New-Object System.Collections.Queue
    foreach ($task in $Tasks) {
        $queue.Enqueue($task)
    }

    $jobs = @{}
    while ($queue.Count -gt 0 -or $jobs.Count -gt 0) {
        while ($queue.Count -gt 0 -and $jobs.Count -lt $Parallelism) {
            $task = $queue.Dequeue()
            Write-Log "START [$($task.Group)] $($task.Name)"
            $job = Start-ClaudeJob -Task $task -ClaudeExe $ClaudeExe
            $jobs[$job.Id] = [pscustomobject]@{ Job = $job; Task = $task }
        }

        Start-Sleep -Seconds 3

        foreach ($jobId in @($jobs.Keys)) {
            $entry = $jobs[$jobId]
            $job = $entry.Job
            if ($job.State -eq "Running") {
                continue
            }

            $result = Receive-Job -Job $job -ErrorAction SilentlyContinue
            $reason = $job.ChildJobs[0].JobStateInfo.Reason
            Remove-Job -Job $job -Force
            $jobs.Remove($jobId)

            if ($job.State -ne "Completed") {
                if ($ContinueOnTaskFailure) {
                    Set-TextFile -Path $entry.Task.OutputPath -Text "TASK FAILED: $($entry.Task.Name)`n`n$reason`n"
                    Write-Log "FAIL  [$($entry.Task.Group)] $($entry.Task.Name) (continued): $reason"
                    continue
                }
                throw "Claude task crashed: $($entry.Task.Name). $reason"
            }

            if ($result.ExitCode -ne 0) {
                if ($ContinueOnTaskFailure) {
                    Write-Log "FAIL  [$($result.Group)] $($result.Name) ($($result.Seconds)s, exit $($result.ExitCode), continued)"
                    continue
                }
                throw "Claude task failed: $($result.Name), exit code $($result.ExitCode), output $(Get-ProjectRelativePath $result.OutputPath)"
            }

            Write-Log "DONE  [$($result.Group)] $($result.Name) ($($result.Seconds)s, $($result.Chars) chars)"
        }
    }
}

$commonHeader = @"
你是 mystock 每日研报流水线中的一个独立 Claude Code 任务。

硬性边界：
- 这是一个单独的 `claude --print` 进程，不是 `.claude/workflows` workflow，也不是 subagent。
- 不要调用 Task/subagent/workflow 编排工具；只完成「当前角色」这一件事。
- **必须积极使用 WebSearch 采集最新网页信息，并对关键事实做交叉验证（至少 2 个独立来源）。**
- 保留每条关键信息的来源 URL、发布日期/事件日期和关键数字。
- 推特/X 原始数据只用 `python scripts/grok_api.py --x-user ...` 或 `--x-query ...` 获取，不要用网页搜索替代推特。
- 搜不到可靠资料时明确写「数据缺口」，不要用模型记忆补最新事实。
- 每个重要判断都要给 Bull/Bear 双视角、概率化结论和认错条件。
- 用中文输出，Markdown 格式，优先事实、证据、结论、数据缺口。

运行信息：
- 日期：$dateDisplay
- 项目根目录：$projectDir
- 本轮输出目录：$(Get-ProjectRelativePath $runDir)
"@

function New-Layer1Prompt {
    param(
        [string]$Title,
        [string]$RoleFile,
        [string]$Focus,
        [string]$Extra = ""
    )

$text = @"
$commonHeader

# 当前角色
$Title

# 必读文件
- requirements.md：关注标的、研究维度、自定义问题、市场预测、关注的大V、思考框架
- profile.json：真实持仓与账户权限
- memory/MEMORY.md：记忆索引
- prompts/deep-research/base/system-base.md：通用深度思考约束
- prompts/deep-research/$RoleFile：本角色完整设定和输出格式

# 研究焦点
$Focus

# 输出要求
- 控制在 1200-2200 中文字，短而硬。
- **必须用 WebSearch 采集最新信息，每条关键事实至少 2 个独立来源交叉验证。**
- 列出 5-10 个最关键事实或数据点，每个带来源 URL 和日期。
- 单独列出「多方逻辑」「空方逻辑」「综合判断」「认错条件」「数据缺口」。
- 不写报告总稿，不写 HTML，只输出本角色研究结果。

$Extra
"@
return $text
}

$macroExtra = @"
如果未使用 -NoTwitter，请先用 Bash 运行以下命令获取特朗普推文和政策信号：
```
python scripts/grok_api.py --x-query 'from:realDonaldTrump -is:retweet' --max-results 10
python scripts/grok_api.py --x-query 'Trump (tariff OR China OR Fed OR dollar) -is:retweet' --max-results 10
```
当前 NoTwitter=$([bool]$NoTwitter)。如果 NoTwitter=True，则跳过 X API，只用 WebSearch 查政策新闻，并明确标注 X 数据缺口。
"@

$influencerExtra = @"
如果未使用 -NoTwitter，请先用 Bash 运行：
```
python scripts/grok_api.py --x-user aleabitoreddit --max-results 10
python scripts/grok_api.py --x-user bboczeng --max-results 10
```
当前 NoTwitter=$([bool]$NoTwitter)。如果 NoTwitter=True，则直接输出「已跳过 X API」。本任务只做数据采集和情绪标注，不做深度分析。
"@

$layer1Tasks = @()
$layer1Tasks += New-ClaudeTask -Id "01-macro-master" -Name "宏观与政策信号" -Group "layer1" -OutputPath (Join-Path $layer1Dir "01-macro-master.md") -Prompt (New-Layer1Prompt `
        -Title "宏观与政策信号" `
        -RoleFile "layer1/macro-master.md" `
        -Focus "全球宏观 regime、Fed/CME FedWatch、美债/美元/VIX、中国 PMI/社融、全球资金流、特朗普政策信号（关税/Fed/芯片/AI/加密）及地缘风险的 K 线映射。" `
        -Extra $macroExtra)

$layer1Tasks += New-ClaudeTask -Id "02-us-stock-master" -Name "美股分析大师" -Group "layer1" -OutputPath (Join-Path $layer1Dir "02-us-stock-master.md") -Prompt (New-Layer1Prompt `
        -Title "美股分析大师" `
        -RoleFile "layer1/us-stock-master.md" `
        -Focus "SPY/QQQ/Mag 7/MU 最新行情、财报和估值变化、AI capex、ETF 资金流、期权/情绪，拆解谁透支预期、谁还有空间。")

$layer1Tasks += New-ClaudeTask -Id "03-hk-china-master" -Name "港股与中概专家" -Group "layer1" -OutputPath (Join-Path $layer1Dir "03-hk-china-master.md") -Prompt (New-Layer1Prompt `
        -Title "港股与中概专家" `
        -RoleFile "layer1/hk-china-master.md" `
        -Focus "腾讯、阿里、小米、恒生科技、南向资金、港元/HIBOR、平台经济与 AI 硬件估值修复，以及美股/A股对港股的传导。")

$layer1Tasks += New-ClaudeTask -Id "04-a-share-master" -Name "A股分析大师" -Group "layer1" -OutputPath (Join-Path $layer1Dir "04-a-share-master.md") -Prompt (New-Layer1Prompt `
        -Title "A股分析大师" `
        -RoleFile "layer1/a-share-master.md" `
        -Focus "贵州茅台、五粮液、宁德时代、比亚迪、沪电股份，以及 A 股政策、北向/ETF/两融、半导体/新能源/白酒/消费主线。")

$layer1Tasks += New-ClaudeTask -Id "05-crypto-master" -Name "加密分析大师" -Group "layer1" -OutputPath (Join-Path $layer1Dir "05-crypto-master.md") -Prompt (New-Layer1Prompt `
        -Title "加密分析大师" `
        -RoleFile "layer1/crypto-master.md" `
        -Focus "BTC/ETH 价格、ETF 资金流、恐惧贪婪指数、链上数据、稳定币流动性、交易所余额、资金费率、监管动态，以及与 Nasdaq/美元/实际利率的相关性。")

$layer1Tasks += New-ClaudeTask -Id "06-stock-deep" -Name "个股分析大师" -Group "layer1" -OutputPath (Join-Path $layer1Dir "06-stock-deep.md") -Prompt (New-Layer1Prompt `
        -Title "个股分析大师" `
        -RoleFile "layer1/stock-deep.md" `
        -Focus "读取 requirements.md 和 profile.json 确定标的（含半导体标的），用 WebSearch 采集最新信息动态分析。无预设模板，临场决定框架。")

$layer1Tasks += New-ClaudeTask -Id "07-sector-deep" -Name "板块分析大师" -Group "layer1" -OutputPath (Join-Path $layer1Dir "07-sector-deep.md") -Prompt (New-Layer1Prompt `
        -Title "板块分析大师" `
        -RoleFile "layer1/sector-deep.md" `
        -Focus "读取 requirements.md 确定已启用的板块，用 WebSearch 采集最新信息动态分析。无预设模板，临场决定框架。考虑板块轮动效应。")

$layer1Tasks += New-ClaudeTask -Id "08-influencer-sentiment" -Name "大V情绪数据采集" -Group "layer1" -OutputPath (Join-Path $layer1Dir "08-influencer-sentiment.md") -Prompt (New-Layer1Prompt `
        -Title "大V情绪数据采集" `
        -RoleFile "layer1/influencer-sentiment.md" `
        -Focus "抓取并整理 @aleabitoreddit 和 @bboczeng 最近推文。标注每条推文的情绪方向（看多/看空/中性）和强度（极端/温和/观望）。不做深度分析，只做数据采集和情绪标注。" `
        -Extra $influencerExtra)

$layer1FileList = Format-TaskFileList -Tasks $layer1Tasks

function New-Layer2Prompt {
    param(
        [string]$Title,
        [string]$RoleFile,
        [string]$Focus,
        [string]$Extra = ""
    )

$text = @"
$commonHeader

# 当前角色
$Title

# 必读文件
- prompts/deep-research/base/system-base.md
- prompts/deep-research/$RoleFile
- 以下第一层独立 Claude 任务输出：
$layer1FileList

# 工作方式
先逐个读取第一层输出，再完成本角色推演。不要重新组织 subagent，也不要调用 workflow。除非发现关键数据缺口，否则不要重复做全量网页搜索。

# 研究焦点
$Focus

# 输出要求
- 结论必须引用第一层中的具体证据。
- 每个判断必须写概率、关键变量、认错条件。
- 明确指出最薄弱的一环或最可能出错的假设。

$Extra
"@
return $text
}

$layer2Tasks = @()
$layer2Tasks += New-ClaudeTask -Id "09-bull-advocate" -Name "多方辩护官" -Group "layer2" -OutputPath (Join-Path $layer2Dir "09-bull-advocate.md") -Prompt (New-Layer2Prompt `
        -Title "多方辩护官" `
        -RoleFile "layer2/bull-advocate.md" `
        -Focus "逐市场（美股/A股/港股/加密）构建最强多头论据链，引用第一层具体证据。穷尽一切多头逻辑，不要自我反驳。")

$layer2Tasks += New-ClaudeTask -Id "10-bear-advocate" -Name "空方辩护官" -Group "layer2" -OutputPath (Join-Path $layer2Dir "10-bear-advocate.md") -Prompt (New-Layer2Prompt `
        -Title "空方辩护官" `
        -RoleFile "layer2/bear-advocate.md" `
        -Focus "逐市场（美股/A股/港股/加密）构建最强空头论据链，引用第一层具体证据。穷尽一切空头逻辑，不要自我反驳。")

$layer2Tasks += New-ClaudeTask -Id "11-catalyst-scenario" -Name "催化剂场景辩论" -Group "layer2" -OutputPath (Join-Path $layer2Dir "11-catalyst-scenario.md") -Prompt (New-Layer2Prompt `
        -Title "催化剂场景辩论" `
        -RoleFile "layer2/catalyst-scenario.md" `
        -Focus "对未来 2 周关键事件（FOMC/CPI/财报/IPO/监管/特朗普信号等）做多空双面推演，模拟多方和空方会如何解读同一事件。")

$layer2FileList = Format-TaskFileList -Tasks $layer2Tasks

$arbiterPrompt = @"
$commonHeader

# 当前角色
首席仲裁官

# 必读文件
- prompts/deep-research/base/system-base.md
- prompts/deep-research/layer2/arbiter.md
- 第一层数据：
$layer1FileList
- 第二层辩论记录：
$layer2FileList

# 工作方式
1. 逐个读取第一层数据和三方辩论输出。
2. 评估多方和空方谁的证据链更完整、逻辑更扎实。
3. 给出有倾向性的最终裁决，不做和事佬。
4. 寻找被双方都忽略的关键变量。

# 输出要求
按 arbiter.md 格式完整输出：多空最终裁决（按市场）、线索串联（3-5条）、关键变量清单、风险矩阵。
"@

$arbiterTask = New-ClaudeTask -Id "12-arbiter" -Name "首席仲裁官" -Group "arbiter" -OutputPath (Join-Path $layer2Dir "12-arbiter.md") -Prompt $arbiterPrompt

$traderPrompt = @"
$commonHeader

# 当前角色
交易员个性化仓位决策

# 必读文件
- profile.json
- memory/portfolio.md（如存在）
- prompts/deep-research/base/system-base.md
- prompts/deep-research/decision/trader-portfolio.md
- 第一层独立 Claude 任务输出：
$layer1FileList
- 第二层辩论记录：
$layer2FileList
- 首席仲裁官裁决：
$(Get-ProjectRelativePath $arbiterTask.OutputPath)

# 输出六部分
1. 现有持仓审查表：读取 profile.json 获取用户真实持仓，逐一给出加仓/减仓/持有/清仓/观望建议。
2. 新建仓建议：推荐 1-3 个新标的，优先半导体/AI/科技/加密，并考虑科创板、港股通、美股、加密权限。
3. 50万 RMB AI 模拟组合：与 memory/portfolio.md 上期状态对比，给出目标权重、目标金额、买卖动作、仓位变化。
4. 风险警示：检查 profile.json 中是否有杠杆仓位并特别警示。
5. 情景调整规则：上行/下行/横盘。
6. 写回 memory/portfolio.md 的状态摘要。

# 文件写回
完成后请用 Write/Edit 工具覆盖 `memory/portfolio.md`，写入第 6 部分状态摘要和本期目标组合。stdout 仍然输出完整交易员建议。
"@

$traderTask = New-ClaudeTask -Id "11-trader-portfolio" -Name "交易员仓位决策" -Group "decision" -OutputPath (Join-Path $finalDir "11-trader-portfolio.md") -Prompt $traderPrompt

$allResearchFiles = @($layer1Tasks + $layer2Tasks + @($arbiterTask, $traderTask))
$allResearchFileList = Format-TaskFileList -Tasks $allResearchFiles

$writerPrompt = @"
$commonHeader

# 当前角色
综合分析大师/最终主笔

# 必读文件
- prompts/deep-research/base/system-base.md
- prompts/deep-research/writer/comprehensive-writer.md
- templates/deep-report.html
- 所有独立 Claude 任务输出：
$allResearchFileList

# 任务
基于上述材料生成完整 HTML 深度研报，并写入：
`$(Get-ProjectRelativePath $reportPath)`

# 报告章节
1. CORE_NARRATIVE + CORE_VERDICT：今日核心推演 + 综合判断
2. BULL_BEAR_ARENA：四市场多空博弈台（含线索串联和历史镜鉴）
3. CATALYST_SCENARIOS：催化剂场景表格
4. STOCK_DEEP_DIVE：标的深度分析，每标的一个卡片含 mini bull/bear
5. INFLUENCER_SIGNALS：大V信号解读，含客观分析
6. CRYPTO_SECTION：加密货币专题
7. TRADER_PORTFOLIO：三张表，持仓审查/新建仓建议/AI模拟组合，加风险警示
8. RISK_MATRIX：风险矩阵
9. PLAYBOOK：涨/跌/横盘三场景操作启示

# 写作要求
- 使用 templates/deep-report.html 已有 CSS class 替换占位符。
- 所有 section 必须生成；数据不足写「数据暂缺」。
- 保留来源链接和关键数字。
- 不要把完整 HTML 粘贴到 stdout；stdout 只输出保存路径、缺口和检查结果。
"@

$writerTask = New-ClaudeTask -Id "12-comprehensive-writer" -Name "综合分析大师执笔" -Group "writer" -OutputPath (Join-Path $finalDir "12-comprehensive-writer.md") -Prompt $writerPrompt

Set-TextFile -Path $latestFile -Text "$runId`n"

$claudeExe = if ($DryRun) { "<dry-run>" } else { Resolve-ClaudeExecutable }
Initialize-ClaudeEnvironment
if (-not $DryRun) {
    Test-ClaudePrintAuth -ClaudeExe $claudeExe
}

$manifest = [ordered]@{
    run_id = $runId
    date = $dateDisplay
    project_dir = $projectDir
    run_dir = Get-ProjectRelativePath $runDir
    report_path = Get-ProjectRelativePath $reportPath
    no_email = [bool]$NoEmail
    no_twitter = [bool]$NoTwitter
    sequential = [bool]$Sequential
    max_parallel = $MaxParallel
    dry_run = [bool]$DryRun
    claude = $claudeExe
    tasks = @($layer1Tasks + $layer2Tasks + @($arbiterTask, $traderTask, $writerTask)) | ForEach-Object {
        [ordered]@{
            id = $_.Id
            name = $_.Name
            group = $_.Group
            prompt = Get-ProjectRelativePath $_.PromptPath
            output = Get-ProjectRelativePath $_.OutputPath
        }
    }
}
Set-TextFile -Path (Join-Path $runDir "manifest.json") -Text (($manifest | ConvertTo-Json -Depth 6) + "`n")

Write-Log "mystock daily research started"
Write-Log "Project: $projectDir"
Write-Log "Run dir: $(Get-ProjectRelativePath $runDir)"
Write-Log "Report: $(Get-ProjectRelativePath $reportPath)"
Write-Log "Claude: $claudeExe"
Write-Log "NoEmail=$([bool]$NoEmail), NoTwitter=$([bool]$NoTwitter), Sequential=$([bool]$Sequential), MaxParallel=$MaxParallel, DryRun=$([bool]$DryRun)"

try {
    Invoke-ClaudeTaskGroup -GroupName "Layer 1 information gathering" -Tasks $layer1Tasks -ClaudeExe $claudeExe -Parallelism $MaxParallel -ContinueOnTaskFailure
    Invoke-ClaudeTaskGroup -GroupName "Layer 2 debating" -Tasks $layer2Tasks -ClaudeExe $claudeExe -Parallelism ([Math]::Min($MaxParallel, 3)) -ContinueOnTaskFailure
    Invoke-ClaudeTaskGroup -GroupName "Layer 2 arbiter" -Tasks @($arbiterTask) -ClaudeExe $claudeExe -Parallelism 1
    Invoke-ClaudeTaskGroup -GroupName "Decision layer" -Tasks @($traderTask) -ClaudeExe $claudeExe -Parallelism 1
    Invoke-ClaudeTaskGroup -GroupName "Writer layer" -Tasks @($writerTask) -ClaudeExe $claudeExe -Parallelism 1

    if (-not $DryRun -and -not (Test-Path $reportPath)) {
        throw "Report was not created: $(Get-ProjectRelativePath $reportPath). Check $(Get-ProjectRelativePath $writerTask.OutputPath)."
    }

    if (-not $NoEmail -and -not $DryRun) {
        Write-Log "START [email] send report"
        $subject = "mystock 深度研报 - $dateTag"
        $emailOutput = & python scripts/send_email.py --subject $subject --file $reportPath 2>&1
        $emailExit = if ($null -eq $LASTEXITCODE) { 0 } else { $LASTEXITCODE }
        Set-TextFile -Path (Join-Path $finalDir "13-email.log") -Text (($emailOutput | Out-String).TrimEnd() + "`n")

        if ($emailExit -ne 0) {
            throw "Email failed with exit code $emailExit. Check $(Get-ProjectRelativePath (Join-Path $finalDir "13-email.log"))."
        }
        Write-Log "DONE  [email] sent"
    }
    elseif ($NoEmail) {
        Write-Log "SKIP  [email] NoEmail=True"
    }

    Write-Log "mystock daily research finished"
    Write-Host ""
    Write-Host "Done."
    Write-Host "Run dir : $(Get-ProjectRelativePath $runDir)"
    Write-Host "Log     : $(Get-ProjectRelativePath $logFile)"
    Write-Host "Report  : $(Get-ProjectRelativePath $reportPath)"
}
catch {
    Write-Log "FAILED $_"
    Write-Error $_
    exit 1
}
