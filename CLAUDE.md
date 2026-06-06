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
2. 每日通过 Windows 计划任务 → `scripts/run_daily.ps1` 调用 Python 引擎
3. 三层递进执行：
   - **第一层（并行5 agent）**：信息采集 — 板块/个股/宏观/大V/加密货币
   - **第二层（并行3 agent）**：深度推演 — 多空博弈台/线索串联/催化剂场景
   - **第三层（串行）**：主笔撰写 HTML 报告 → 发送邮件
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
| **通用分析/预测/报告** | DeepSeek Chat | OpenRouter 直连 | ~$0.14/M 输入 |
| **推特/X 数据搜索** | Grok 4.3 生成搜索词 | xAI API（需 Clash 代理） | ~$0.00125/M |
| **X 推文实际抓取** | 无（直接调用） | X API v2（Bearer Token） | 基础版免费配额 |
| **邮件发送** | 无（直接调用） | QQ SMTP + 授权码 | 免费 |

### 关键说明

- **Grok 4.3** — 仅用于推特搜索的 `x_search` 工具调用，不做通用分析
- **DeepSeek** — 板块/个股新闻分析、市场预测、报告汇总等所有通用任务
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

## 深度研究引擎架构（v2.0）

```
scripts/run_deep_research.py          ← 主入口（Python 脚本）
│
├─ 第一层：信息采集（并行 5 agent）
│  ├─ agent_sector_deep()             ← 半导体 + AI 板块深度搜索
│  ├─ agent_stock_deep()              ← 所有关注标的深度搜索
│  ├─ agent_macro()                   ← 宏观 + 资金流向
│  ├─ agent_twitter()                 ← 大V推文抓取 (Grok + X API)
│  └─ agent_crypto()                  ← BTC/ETH 专项
│
├─ 第二层：深度推演（并行 3 agent）
│  ├─ agent_bull_bear()               ← 多空博弈台（每市场 Bull vs Bear）
│  ├─ agent_dot_connecting()          ← 线索串联 + 历史镜鉴 + 聪明钱推理
│  └─ agent_catalyst()                ← 前瞻催化剂场景推演（双场景）
│
└─ 第三层：报告撰写（串行）
   ├─ assemble_html_report()          ← 主笔整合 → HTML 报告
   └─ send_email()                    ← QQ 邮件发送
```

## 提示词库

所有 agent 的 system prompt 独立管理在 `prompts/deep-research/`：

| 文件 | 用途 |
|------|------|
| `system-base.md` | **通用深度思考约束** — 所有 agent 共享 |
| `sector-deep.md` | 板块深度搜索角色设定 |
| `stock-deep.md` | 个股深度搜索角色设定 |
| `macro-fundflow.md` | 宏观与资金面角色设定 |
| `crypto-deep.md` | 加密货币专项角色设定 |
| `bull-bear-arena.md` | 多空博弈台角色设定 |
| `dot-connecting.md` | 线索串联角色设定 |
| `catalyst-scenario.md` | 催化剂场景推演角色设定 |

## 用户思考习惯（Memory 系统）

用户的分析框架存储在 `memory/thinking-patterns/`，每次运行自动注入到 agent 的 system prompt 中。

当前已记录的思考框架：
- **IPO 掩护出货**：大跌+重大IPO临近 → 机构可能为打新出货换仓，非真正看空
- **大V反向阅读**：极端看空情绪可能是反向买入信号

更新方式：在对话中表达新的分析视角 → AI 自动写入 memory。

## 报告模板

`templates/deep-report.html` — 暗色主题专业研报模板，包含：
- 核心推演卡片
- 多空博弈台（双列对比）
- 线索串联卡片
- 催化剂场景推演表格
- 标的深度分析卡片（含 mini bull/bear）
- 大V信号解读（含反向阅读）
- 风险矩阵
- 操作启示（涨/跌/横盘三场景）

## 核心文件

| 文件 | 说明 |
|------|------|
| `requirements.md` | **需求单 + 思考框架** — 编辑此文件控制研究内容和分析视角 |
| `config.json` | 邮件配置、调度设置 |
| `scripts/run_deep_research.py` | **深度研究主引擎** — 三层递进核心脚本 |
| `scripts/grok_api.py` | **统一 API 助手**（DeepSeek/Grok/X 搜索） |
| `scripts/send_email.py` | QQ 邮件发送脚本（SMTP + 授权码） |
| `scripts/run_daily.ps1` | Windows 计划任务入口脚本 |
| `templates/deep-report.html` | HTML 报告模板 |
| `prompts/deep-research/` | 提示词库（8个角色 prompt） |
| `memory/thinking-patterns/` | 用户思考习惯记忆 |
| `.env` | 所有 API 凭证和代理配置 |
| `.claude/workflows/daily-research.js` | （旧版）workflow 引擎 — 已被 Python 引擎替代 |

## 推特搜索完整流程（xAI Grok + X API）

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
# 完整深度研究
python scripts/run_deep_research.py

# 跳过邮件
python scripts/run_deep_research.py --no-email

# 跳过推特
python scripts/run_deep_research.py --no-twitter

# 保存中间 JSON 数据
python scripts/run_deep_research.py --save-json

# 单次 API 调用
python scripts/grok_api.py "你的问题"                           # DeepSeek 通用
python scripts/grok_api.py --xai --search "搜 @user 推文"       # Grok + X API 搜推特
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
- 执行脚本：`scripts/run_daily.ps1`

## 网络配置

Clash Verge 代理信息：
- HTTP 代理端口：`127.0.0.1:7897`
- SOCKS 端口：`7898`
- 混合端口：`7897`
- TUN 模式已启用但 SSL 握手有问题，优先用 HTTP 代理
