# mystock — 股市深度研究系统

基于 AI 多智能体驱动的每日股市深度研究系统。**不只是信息聚合，而是三层递进的多空博弈推演引擎。**

## 核心设计理念

每个分析维度必须回答三个问题：
- **多方怎么看？**（Bull case，附证据）
- **空方怎么看？**（Bear case，附证据）
- **我（用户视角）怎么看？**（综合判断，概率化）

每条新闻不只说「发生了 X」，还要追问：
- X 对谁有利？对谁有害？
- X 和 Y（看似无关的事件）是否有隐性关联？
- 历史上类似情况后市场怎么走？
- 聪明钱在这个背景下最可能做什么？

## 工作流程

1. 用户维护 `requirements.md` 作为每日研究需求单（含思考框架）
2. 每日通过 Windows 计划任务或手动命令 → `scripts/run_daily.cmd` 调用 Claude Code WebSearch + Python API 辅助
3. 三层递进执行：
   - **第一层（6 个独立 Claude Code 任务，默认最多 3 个并行）**：专业信息采集 — 宏观+政策/海外+中国科技/A股/半导体/加密/大V数据
   - **第二层（2 个独立 Claude Code 任务，可并行）**：深度推演 — 多空博弈+线索串联/催化剂场景
   - **决策层（串行）**：交易员用 50 万人民币起始现金生成模拟仓位和买卖变化表
   - **第三层（串行）**：综合分析大师执笔 HTML 报告 → 发送邮件
4. 报告生成 → 保存到 `output/YYYY-MM-DD-深度研报.html`
5. 通过 `scripts/send_email.py` 将报告发送到 QQ 邮箱

## 覆盖市场

- 🇺🇸 美股（纳斯达克、纽交所、S&P 500）
- 🇨🇳 A股（沪深两市）
- 🇭🇰 港股（香港交易所）
- 🪙 加密货币（BTC、ETH）

## API 路由策略

| 用途 | 模型 | 方式 | 价格 |
|------|------|------|------|
| **推特以外的最新网页信息** | Claude Code WebSearch | 必须通过 `scripts/run_daily.cmd` / `scripts/run_daily.ps1` 的独立 `claude --print` 任务路径 | 取决于 Claude Code |
| **通用分析/预测/报告** | DeepSeek V4 Flash | OpenRouter 直连 | ~$0.10/M 输入 |
| **X/Twitter 原始数据获取** | Grok（仅抓取，不分析） | xAI API，`--x-user` / `--x-query` | 最低价 Grok 模型 |
| **邮件发送** | 无（直接调用） | QQ SMTP + 授权码 | 免费 |

### 关键说明

- **最新网页信息必须走 Claude Code WebSearch**：也就是运行 `scripts/run_daily.cmd`，由多个独立 `claude --print` 任务执行第一层网页搜索。不要指望纯 Python 主脚本自己联网搜索新闻、公告、宏观数据或产业新闻。
- **每个专家是独立 Claude Code 任务，不是 subagent**：`run_daily.ps1` 只做外层编排；宏观+政策/海外科技/A股/半导体/加密/大V数据会分别启动独立 Claude Code 进程（共 6+2+1+1=10 个任务），输出保存到 `output/runs/<run-id>/`。
- **已取消 `.claude/workflows` 编排**：不要再通过 Claude workflow 触发每日研究。
- **只把外部动作封装为能力**：WebSearch、X API、DeepSeek、邮件发送可以封装；政策雷达、财报拆解、资金流、催化剂这类分析模块不要再拆成互相调用的 AI agent。
- **X/Twitter 优先走确定性 API 查询**：用 `python scripts/grok_api.py --x-user USER` 或 `--x-query QUERY` 获取原始推文，再交给分析模型；避免“AI 先决定搜什么”的调用环节。
- **速度优先约束**：你不关心具体K线，因此系统不做完整技术指标扫描；第一层专家应短而硬，优先事实、来源、结论和数据缺口。
- **DeepSeek V4 Flash** — 专业 agent 研究、市场预测、深度推演、报告汇总等所有通用任务（284B/13B MoE，1M 上下文）
- **Grok** — 仅用于 X/Twitter 原始数据抓取，不参与分析；默认用性价比最高的 Grok 模型
- **xAI API 需代理**：Clash Verge HTTP 代理 `127.0.0.1:7897`
- **OpenRouter 国内直连**：无需代理
- 绝对**不要**用网页搜索来补充推特数据 — 推特必须走 X API v2

## API 凭证

所有凭证保存在项目根目录 `.env` 文件：

```
XAI_API_KEY=xai-xxx                    # xAI Grok API（需 Clash 代理）
OPENROUTER_API_KEY=sk-or-v1-xxx        # OpenRouter（国内直连）
TWITTER_BEARER_TOKEN=AAAAAAAAAA...     # X API v2（推文搜索）
TWITTER_API_KEY=xxx                    # X API Key
TWITTER_API_SECRET=xxx                 # X API Secret
HTTP_PROXY=http://127.0.0.1:7897       # Clash HTTP 代理
HTTPS_PROXY=http://127.0.0.1:7897      # Clash HTTP 代理
```

## 深度研究引擎架构（v3.0）

```
scripts/run_daily.cmd                 ← 手动/Windows计划任务统一入口
scripts/run_daily.ps1                 ← 外层编排器：逐个启动独立 claude --print 任务
│
├─ 第一层：专业信息采集（6 个独立 Claude Code 任务，默认 MaxParallel=3）
│  ├─ 01-macro-master                 ← 宏观 regime + 全球资金流 + 特朗普政策信号
│  ├─ 02-offshore-equity              ← 美股 + 港股/中概（合并，共用 Mag 7/AI 估值逻辑）
│  ├─ 03-a-share-master               ← A股政策/资金/标的
│  ├─ 04-semiconductor-chain          ← 半导体 + AI 产业链
│  ├─ 05-crypto-master                ← BTC/ETH + 链上/衍生品/ETF
│  └─ 06-influencer-sentiment         ← 大V推文数据采集（仅采集，不分析）
│
├─ 第二层：深度推演（2 个独立 Claude Code 任务）
│  ├─ 07-bull-bear-arena              ← 多空博弈台 + 线索串联/历史镜鉴（合并）
│  └─ 08-catalyst-scenario            ← 前瞻催化剂场景推演（双场景）
│
├─ 决策层：交易员模拟组合（串行）
│  └─ 09-trader-portfolio             ← 50万RMB模拟组合：买入/卖出/持有/现金比例/仓位变化
│
└─ 第三层：报告撰写（串行）
   ├─ 10-comprehensive-writer         ← 综合分析大师整合 → HTML 报告
   └─ scripts/send_email.py           ← QQ 邮件发送
```

## 提示词库

所有 agent 的 system prompt 独立管理在 `prompts/deep-research/`：

| 文件 | 用途 |
|------|------|
| `system-base.md` | **通用深度思考约束** — 所有 agent 共享 |
| `macro-master.md` | 宏观与政策信号（含特朗普 K 线映射） |
| `offshore-equity-master.md` | 海外与中国科技股票（美股+港股/中概合并） |
| `a-share-master.md` | A股分析大师角色设定 |
| `semiconductor-chain.md` | 半导体产业链分析专家角色设定 |
| `crypto-master.md` | 加密分析大师角色设定 |
| `bull-bear-arena.md` | 多空博弈台 + 线索串联（合并） |
| `catalyst-scenario.md` | 催化剂场景推演角色设定 |
| `trader-portfolio.md` | 交易员 50万RMB 模拟组合角色设定 |
| `comprehensive-writer.md` | 综合分析大师/最终主笔角色设定 |

## 用户思考习惯（Memory 系统）

用户的分析框架存储在 `memory/thinking-patterns/`，每次运行自动注入到 agent 的 system prompt 中。

当前已记录的思考框架：
- **IPO 掩护出货**：大跌+重大IPO临近 → 机构可能为打新出货换仓，非真正看空
- **大V客观解析**：客观分析大V情绪方向和强度，不预设其为反向指标

更新方式：在对话中表达新的分析视角 → AI 自动写入 memory。

## 报告模板

`templates/deep-report.html` — 暗色主题专业研报模板，包含：
- 核心推演卡片
- 多空博弈台（双列对比）
- 线索串联卡片
- 催化剂场景推演表格
- 标的深度分析卡片（含 mini bull/bear）
- 大V信号解读（含客观分析）
- 风险矩阵
- 交易员仓位（50万RMB模拟组合、买卖动作、目标权重、目标金额、仓位变化、认错条件）
- 操作启示（涨/跌/横盘三场景）

## 核心文件

| 文件 | 说明 |
|------|------|
| `requirements.md` | **需求单 + 思考框架** — 编辑此文件控制研究内容和分析视角 |
| `profile.json` | **用户真实持仓与账户信息** — 交易员每次读取此文件获取最新持仓，给出个性化建议 |
| `config.json` | 邮件配置、调度设置 |
| `scripts/run_daily.cmd` | **统一触发命令** — 手动运行和 Windows 计划任务都调用它 |
| `scripts/run_daily.ps1` | **独立 Claude 任务编排器** — 通过 Claude Code WebSearch 获取推特以外的最新网页信息 |
| `scripts/grok_api.py` | **统一 API 助手**（DeepSeek/Grok/X 搜索） |
| `scripts/send_email.py` | QQ 邮件发送脚本（SMTP + 授权码） |
| `templates/deep-report.html` | HTML 报告模板 |
| `prompts/deep-research/` | 提示词库（专业 agent 角色 prompt） |
| `memory/thinking-patterns/` | 用户思考习惯记忆 |
| `memory/portfolio.md` | 交易员 50万RMB 模拟组合状态，用于生成仓位变化表 |
| `.env` | 所有 API 凭证和代理配置 |

## 推特搜索完整流程（确定性 X API 优先）

优先使用确定性 X API 能力：

```bash
python scripts/grok_api.py --x-user bboczeng --max-results 10
python scripts/grok_api.py --x-query "from:realDonaldTrump -is:retweet" --max-results 10
python scripts/grok_api.py --x-user aleabitoreddit --max-results 10 --json
```

旧的 Grok 工具调用链保留兼容，但不作为默认路径：

```
① python scripts/grok_api.py --xai --search "搜索 @user 的推文"
② Grok 返回 tool_call: x_search({"query": "from:username"})
③ 脚本通过 X API v2 执行实际搜索
④ 搜索结果返回给 Grok 分析
⑤ Grok 输出分析报告
```

**注意**：
- X API v2 基础版不支持 `since:` / `until:` 操作符
- 如果 X API 返回 `CreditsDepleted`（402），表示免费配额用完

## 手动运行

```bash
# 最新网页信息深度研究（推荐；手动和定时任务同一入口）
scripts\run_daily.cmd

# 等价 PowerShell 命令
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\run_daily.ps1

# 跳过邮件/推特，或改为串行运行
scripts\run_daily.cmd -NoEmail
scripts\run_daily.cmd -NoTwitter
scripts\run_daily.cmd -Sequential

# 单次 API 调用
python scripts/grok_api.py "你的问题"                           # DeepSeek 通用
python scripts/grok_api.py --x-user bboczeng --max-results 10   # X API 能力：只抓原始推文，不调用AI
python scripts/grok_api.py --x-query "from:realDonaldTrump -is:retweet" --max-results 10
python scripts/grok_api.py --xai --search "搜 @user 推文"       # 旧兼容：Grok + X API 搜推特
python scripts/grok_api.py --xai "直接问 Grok"                  # xAI Grok 直调

# 发送邮件
python scripts/send_email.py --subject "主题" --body "<h1>HTML内容</h1>"
python scripts/send_email.py --subject "主题" --file "output/report.html"

# 列表模型
python scripts/grok_api.py --list-models
```

## 邮件配置（QQ 邮箱 SMTP）

`config.json`：
```json
{
  "email": {
    "method": "smtp_password",
    "smtp_server": "smtp.qq.com",
    "smtp_port": 587,
    "sender_email": "1379066563@qq.com",
    "recipient_email": "1379066563@qq.com",
    "password": "你的16位授权码"
  }
}
```

## 定时任务

- Windows 任务计划程序 → `mystock-daily-research`
- 触发时间：每天 09:00 和 21:00（亚洲上海时区）
- 执行命令：`scripts/run_daily.cmd`
- 注册命令：`powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\create_schtask.ps1`

## 网络配置

Clash Verge 代理信息：
- HTTP 代理端口：`127.0.0.1:7897`
- SOCKS 端口：`7898`
- 混合端口：`7897`
- TUN 模式已启用但 SSL 握手有问题，优先用 HTTP 代理
