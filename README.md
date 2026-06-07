<p align="center">
  <h1 align="center">📈 mystock</h1>
  <p align="center"><strong>AI 多智能体驱动的每日股市深度研究系统</strong></p>
  <p align="center">三层递进 · 多空博弈推演 · 不只是信息聚合</p>
</p>

---

## 🧠 核心理念

> **每条新闻不只说「发生了 X」，还要追问「然后呢？」**

这个系统不是新闻摘要器，而是一个**多空博弈推演引擎**。每个分析维度必须回答三个问题：

| 视角 | 问题 |
|------|------|
| 🟢 **多方** | Bull case — 为什么看涨？证据是什么？ |
| 🔴 **空方** | Bear case — 为什么看跌？证据是什么？ |
| 🧑 **你** | 综合判断 — 概率化结论，不骑墙 |

每条信息都经过四层追问：
- 对谁有利？对谁有害？
- 和看似无关的事件有无隐性关联？
- 历史上类似情况后市场怎么走？
- **聪明钱在这个背景下最可能做什么？**

---

## 🏗️ 引擎架构（v3.0）

```
scripts/run_daily.cmd                 ← 手动/Windows 计划任务统一入口
scripts/run_daily.ps1                 ← 外层编排器：逐个启动独立 claude --print 任务
│
├─ 🔍 第一层：专业信息采集（6 个独立 Claude Code 任务，默认最多 3 个并行）
│  ├─ 01-macro-master                 ← 宏观 regime + 全球资金流 + 特朗普政策信号
│  ├─ 02-offshore-equity              ← 美股 + 港股/中概（合并 Mag 7/AI 估值）
│  ├─ 03-a-share-master               ← A股 政策/资金/标的
│  ├─ 04-semiconductor-chain          ← 半导体 + AI 产业链
│  ├─ 05-crypto-master                ← BTC/ETH + 链上/衍生品/ETF
│  └─ 06-influencer-sentiment         ← 大V 推文数据采集（仅采集，不分析）
│
├─ ⚔️ 第二层：深度推演（2 个独立 Claude Code 任务）
│  ├─ 07-bull-bear-arena              ← 多空博弈台 + 线索串联/历史镜鉴（合并）
│  └─ 08-catalyst-scenario            ← 前瞻催化剂场景推演（双场景）
│
├─ 💰 决策层：交易员模拟组合（串行）
│  └─ 09-trader-portfolio             ← 50 万 RMB 模拟组合：买入/卖出/持有/现金比例/仓位变化
│
└─ 📝 第三层：报告撰写（串行）
   ├─ 10-comprehensive-writer         ← 综合分析大师整合 → HTML 报告
   └─ scripts/send_email.py           ← QQ 邮件发送
```

---

## 🌍 覆盖市场

| 市场 | 范围 |
|------|------|
| 🇺🇸 **美股** | 纳斯达克、纽交所、S&P 500 |
| 🇨🇳 **A股** | 沪深两市 |
| 🇭🇰 **港股** | 香港交易所 |
| 🪙 **加密货币** | BTC、ETH |

---

## 🚀 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/radium1234/mystock.git
cd mystock
```

### 2. 配置 API 凭证

```bash
cp .env.example .env
cp config.example.json config.json
```

编辑 `.env` 填入你的 API 密钥：

| 变量 | 用途 | 获取方式 |
|------|------|----------|
| `XAI_API_KEY` | Grok 推特数据抓取 | [xAI API](https://x.ai/api) |
| `OPENROUTER_API_KEY` | DeepSeek V4 Flash 通用分析 | [OpenRouter](https://openrouter.ai/) |
| `TWITTER_BEARER_TOKEN` | X API v2 推文搜索 | [X Developer](https://developer.x.com/) |
| `TWITTER_API_KEY` / `TWITTER_API_SECRET` | X API v2 认证 | [X Developer](https://developer.x.com/) |
| `HTTP_PROXY` / `HTTPS_PROXY` | 国内访问 xAI 需 Clash Verge 代理 | 本地 `127.0.0.1:7897` |

编辑 `config.json` 填入：
- QQ 邮箱 + SMTP 授权码（[获取授权码](https://service.mail.qq.com/)）

### 3. 安装依赖

```bash
pip install requests python-dotenv
```

### 4. 编辑需求单

编辑 `requirements.md`，勾选你想研究的标的和维度。

编辑 `profile.json`，填入你的真实持仓信息，交易员会基于它给出个性化建议。

### 5. 运行

```bash
# 完整深度研究（推荐；手动和定时任务同一入口）
scripts\run_daily.cmd

# 跳过邮件
scripts\run_daily.cmd -NoEmail

# 跳过推特（X API 配额用完时）
scripts\run_daily.cmd -NoTwitter

# 串行运行（不并行启动 Claude Code 任务）
scripts\run_daily.cmd -Sequential
```

---

## 🔧 单次 API 调用

```bash
# 通用分析（OpenRouter → DeepSeek V4 Flash）
python scripts/grok_api.py "分析今天NVDA的走势"

# X API 确定性抓取（只抓原始推文，不调用 AI）
python scripts/grok_api.py --x-user bboczeng --max-results 10
python scripts/grok_api.py --x-query "from:realDonaldTrump -is:retweet" --max-results 10

# Grok + X API 搜推特（兼容旧路径）
python scripts/grok_api.py --xai --search "搜 @aleaborteddit 的推文"

# xAI Grok 直调
python scripts/grok_api.py --xai "直接问 Grok"

# 列出可用模型
python scripts/grok_api.py --list-models
```

---

## 📬 发送邮件

```bash
# 发送 HTML 内容
python scripts/send_email.py --subject "今日研报" --body "<h1>内容</h1>"

# 发送报告文件
python scripts/send_email.py --subject "今日研报" --file "output/report.html"
```

---

## ⏰ 定时任务

通过 Windows 任务计划程序自动运行：

```powershell
# 创建计划任务（每天 09:00 和 21:00，亚洲上海时区）
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\create_schtask.ps1
```

- 任务名：`mystock-daily-research`
- 触发时间：每天 `09:00` 和 `21:00`（Asia/Shanghai）
- 入口：`scripts/run_daily.cmd`
- 手动运行和计划任务使用同一条命令。

---

## 📂 项目结构

```
mystock/
├── requirements.md              # 📋 研究需求单 + 思考框架（编辑这个！）
├── profile.json                 # 💼 用户真实持仓与账户信息
├── .env.example                 # 🔑 环境变量模板
├── config.example.json          # 📧 邮件配置模板
│
├── scripts/
│   ├── run_daily.cmd            # 🪟 手动/计划任务统一入口
│   ├── run_daily.ps1            # ⚙️ 独立 Claude Code 任务编排器
│   ├── grok_api.py              # 🔌 统一 API 助手（DeepSeek/Grok/X）
│   ├── send_email.py            # 📬 QQ 邮件发送
│   ├── create_schtask.ps1       # 🔧 创建 Windows 计划任务
│   ├── create_task.bat          # 🔧 计划任务注册（备用）
│   └── create_task.ps1          # 🔧 计划任务注册（备用）
│
├── prompts/deep-research/       # 🎭 提示词库（三层架构）
│   ├── base/                    # 基础层 — 通用深度思考约束
│   │   └── system-base.md
│   ├── layer1/                  # 第一层 — 专业信息采集（6 个角色）
│   │   ├── macro-master.md      #   宏观与政策信号（含特朗普 K 线映射）
│   │   ├── us-stock-master.md   #   美股分析大师
│   │   ├── hk-china-master.md   #   港股/中概分析大师
│   │   ├── a-share-master.md    #   A股分析大师
│   │   ├── crypto-master.md     #   加密分析大师
│   │   ├── stock-deep.md        #   标的深度分析
│   │   ├── sector-deep.md       #   行业深度分析
│   │   └── influencer-sentiment.md  # 大V情绪采集
│   ├── layer2/                  # 第二层 — 深度推演（4 个角色）
│   │   ├── bull-advocate.md     #   多方辩手
│   │   ├── bear-advocate.md     #   空方辩手
│   │   ├── arbiter.md           #   裁判/线索串联
│   │   └── catalyst-scenario.md #   催化剂场景推演
│   ├── decision/                # 决策层 — 交易员
│   │   └── trader-portfolio.md  #   50 万 RMB 模拟组合
│   └── writer/                  # 第三层 — 报告撰写
│       └── comprehensive-writer.md  # 综合分析大师/主笔
│
├── templates/
│   └── deep-report.html         # 🎨 暗色主题专业研报模板
│
├── memory/
│   ├── portfolio.md             # 💰 交易员模拟组合状态
│   ├── MEMORY.md                # 🧠 记忆索引
│   └── thinking-patterns/       # 🧠 用户思考习惯记忆（自动注入 prompt）
│
└── output/                      # 📄 生成的研报（gitignore）
    └── YYYY-MM-DD-深度研报.html
```

---

## 🛡️ 安全说明

**API 密钥和邮箱密码绝不会上传到 GitHub。** 仓库只包含 `.example` 模板文件：

| 文件 | 状态 |
|------|------|
| `.env` | 🔒 `.gitignore` 排除 |
| `config.json` | 🔒 `.gitignore` 排除 |
| `.env.example` | ✅ 安全模板 |
| `config.example.json` | ✅ 安全模板 |

---

## 🔬 研报内容亮点

每份研报包含：

- ⚔️ **多空博弈台** — 双列 Bull vs Bear 对比，附证据
- 🔗 **线索串联** — 看似无关事件的隐性关联
- 🪞 **历史镜鉴** — 「现在最像历史上的哪段行情？」
- 🧠 **聪明钱推理** — 机构在这个背景下最可能做什么
- 🎯 **催化剂场景推演** — 上行情景 vs 下行情景
- 📊 **标的深度分析** — 每标的含 mini bull/bear
- 📡 **大V 信号解读** — 含客观分析（不预设反向指标）
- ⚠️ **风险矩阵** — 概率 × 影响程度
- 💰 **交易员仓位** — 50 万 RMB 模拟组合、买卖动作、目标权重、仓位变化、认错条件
- 🧭 **操作启示** — 涨 / 跌 / 横盘三场景应对

---

## 📋 API 路由

| 用途 | 模型 | 方式 | 价格 |
|------|------|------|------|
| **推特以外的最新网页信息** | Claude Code WebSearch | `scripts/run_daily.cmd` 独立 `claude --print` 任务 | 取决于 Claude Code |
| **通用分析/预测/报告** | DeepSeek V4 Flash | OpenRouter 直连 | ~$0.10/M 输入 |
| **X/Twitter 原始数据获取** | Grok（仅抓取，不分析） | xAI API（需代理） | 最低价模型 |
| **邮件发送** | 无（直接调用） | QQ SMTP + 授权码 | 免费 |

> **关键说明**：最新网页信息必须走 Claude Code WebSearch — 由 `run_daily.ps1` 启动多个独立 `claude --print` 任务执行第一层网页搜索，不依赖 Python 脚本联网。

---

## 🧠 思考框架

系统内置用户的投资分析框架，每次运行自动注入 agent prompt：

- **大资金行为逻辑** — IPO 掩护出货、大宗交易异动
- **多空博弈思维** — 每个判断必须 Bull + Bear 双面呈现
- **大V 信号客观解读** — 客观分析情绪方向和强度，不预设反向
- **历史镜鉴** — 寻找历史上最相似的行情片段
- **跨市场联动** — 美股→A股/港股传导、加密-纳斯达克相关性
- **资金面 ≠ 基本面** — 区分短期交易逻辑 vs 中期配置逻辑

在对话中表达新的分析视角 → 系统自动写入 `memory/thinking-patterns/`。

---

## 📄 许可证

MIT License
