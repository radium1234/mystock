# run_daily.ps1 — 每日股市深度研究定时任务入口
# 由 Windows 任务计划程序每天 09:00 / 21:00 触发
#
# 执行方式：claude --print 模式（保留 WebSearch 能力）
# Python 脚本负责 X API/邮件等辅助功能

$ErrorActionPreference = "Stop"
$projectDir = "c:\Users\Shan Lei\Desktop\test\mystock"

# 切换到项目目录
Set-Location $projectDir

# 创建日志目录
$logDir = "$projectDir\output\logs"
if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
}

$dateStr = Get-Date -Format 'yyyyMMdd-HHmm'
$logFile = "$logDir\run-$dateStr.log"

# 开始日志
$timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
"================================================" | Out-File -FilePath $logFile -Encoding UTF8
"  mystock 深度研究 — 定时任务开始" | Out-File -FilePath $logFile -Encoding UTF8 -Append
"  时间：$timestamp" | Out-File -FilePath $logFile -Encoding UTF8 -Append
"  引擎：Claude Code Agent + Python API 辅助" | Out-File -FilePath $logFile -Encoding UTF8 -Append
"================================================" | Out-File -FilePath $logFile -Encoding UTF8 -Append

try {
    # 检查 Claude Code 是否可用
    $claudePath = Get-Command claude -ErrorAction SilentlyContinue
    if (-not $claudePath) {
        $errMsg = "❌ 找不到 claude 命令，请确认 Claude Code 已安装并在 PATH 中"
        $errMsg | Out-File -FilePath $logFile -Encoding UTF8 -Append
        Write-Error $errMsg
        exit 1
    }

    "✅ Claude Code 路径：$($claudePath.Source)" | Out-File -FilePath $logFile -Encoding UTF8 -Append

    # 运行深度研究（通过 Claude Code agent，保留 WebSearch）
    "🚀 启动深度研究（多空博弈 + 线索串联）..." | Out-File -FilePath $logFile -Encoding UTF8 -Append

    claude --print "请执行 mystock 深度研究。步骤：
1. 读取 requirements.md 获取研究任务和思考框架
2. 读取 memory/thinking-patterns/ 获取用户思考习惯
3. 读取 prompts/deep-research/system-base.md 获取深度思考约束
4. 第一层并行搜索（WebSearch + Python API）：
   - 半导体 + AI 板块深度新闻（用 WebSearch）
   - 所有关注个股最新动态（用 WebSearch）
   - 宏观数据 + 资金流向（用 WebSearch）
   - 大V推文抓取：python scripts/grok_api.py --xai --search '搜索 @aleabitoreddit 和 @bboczeng 最近推文'
   - 加密货币行情（用 WebSearch）
5. 第二层深度推演（用 DeepSeek via OpenRouter）：
   - 多空博弈台：每市场构建 Bull vs Bear
   - 线索串联：找非显性关联、历史镜鉴、聪明钱逻辑
   - 催化剂场景推演：未来2周事件做偏多/偏空双场景分析
6. 第三层：按 templates/deep-report.html 模板写完整 HTML 报告到 output/YYYY-MM-DD-深度研报.html
7. 发送邮件：python scripts/send_email.py --subject '📊 mystock 深度研报 - YYYY-MM-DD' --file output/YYYY-MM-DD-深度研报.html

关键要求：
- 每个分析都要有多空双视角，不允许只说一方
- 给出概率化判断，不骑墙
- 检查 IPO 日历与市场大跌的重合度（用户思考习惯）
- 大V情绪要做反向阅读
- 报告带超链接
- 用中文输出" 2>&1 | Tee-Object -FilePath $logFile -Append

    $exitCode = $LASTEXITCODE

    if ($exitCode -eq 0) {
        $successMsg = "✅ 深度研究完成 — $timestamp"
        $successMsg | Out-File -FilePath $logFile -Encoding UTF8 -Append
        Write-Host $successMsg
    } else {
        $warnMsg = "⚠️ Claude Code 退出码：$exitCode，请检查日志"
        $warnMsg | Out-File -FilePath $logFile -Encoding UTF8 -Append
        Write-Host $warnMsg
    }

} catch {
    $errorMsg = "❌ 执行失败：$_"
    $errorMsg | Out-File -FilePath $logFile -Encoding UTF8 -Append
    Write-Error $errorMsg
    exit 1
}

"任务结束。" | Out-File -FilePath $logFile -Encoding UTF8 -Append
